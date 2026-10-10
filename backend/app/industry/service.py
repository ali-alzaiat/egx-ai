"""Industry service: peer resolution, profile lookup, honest percentiles."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.constants import (
    INDUSTRY_METHODOLOGY_VERSION,
    MAX_OVERRIDE_PEERS,
)
from app.industry.percentiles import explain_percentile, peer_percentile
from app.metrics.definitions import get_metric
from app.models.market import Company
from app.repositories.company import CompanyRepository
from app.repositories.industry import IndustryRepository

PeerBasis = str  # "override" | "egx_sector" | "gics_sub_industry" | "none"


def _to_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


class IndustryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.industry = IndustryRepository(session)

    async def _require_company(self, company_id: uuid.UUID) -> Company:
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return company

    async def resolve_peers(
        self, company: Company
    ) -> tuple[list[Company], PeerBasis]:
        """Default peers = same EGX sector, fallback same GICS sub-industry.

        A persisted override wins over both defaults.
        """
        override = await self.industry.get_override(company.id)
        if override is not None:
            ids: list[uuid.UUID] = []
            for raw in override.peer_company_ids:
                try:
                    ids.append(uuid.UUID(str(raw)))
                except ValueError:
                    continue
            peers = [
                c
                for c in await self.industry.list_companies_by_ids(ids)
                if c.id != company.id
            ]
            return (peers, "override")

        if company.egx_sector_id is not None:
            peers = list(
                await self.industry.list_peers_in_egx_sector(
                    company.egx_sector_id, company.id
                )
            )
            if peers:
                return (peers, "egx_sector")

        if company.gics_sub_industry_id is not None:
            peers = list(
                await self.industry.list_peers_in_sub_industry(
                    company.gics_sub_industry_id, company.id
                )
            )
            if peers:
                return (peers, "gics_sub_industry")

        return ([], "none")

    async def set_peer_override(
        self, company_id: uuid.UUID, peer_company_ids: list[uuid.UUID]
    ) -> dict[str, Any]:
        company = await self._require_company(company_id)
        seen: list[uuid.UUID] = []
        for pid in peer_company_ids:
            if pid == company.id:
                raise HTTPException(
                    status_code=400, detail="Peer list must not include the company itself"
                )
            if pid not in seen:
                seen.append(pid)
        if len(seen) > MAX_OVERRIDE_PEERS:
            raise HTTPException(
                status_code=400,
                detail=f"Peer list capped at {MAX_OVERRIDE_PEERS} companies",
            )
        existing = await self.industry.list_companies_by_ids(seen)
        found = {c.id for c in existing}
        missing = [str(p) for p in seen if p not in found]
        if missing:
            raise HTTPException(
                status_code=400, detail=f"Unknown peer companies: {missing}"
            )
        override = await self.industry.upsert_override(company.id, seen)
        await self.session.flush()
        peers = await self.industry.list_companies_by_ids(seen)
        return {
            "company_id": str(company.id),
            "peer_company_ids": [str(c.id) for c in peers],
            "methodology_version": override.methodology_version,
            "updated_at": override.updated_at.isoformat(),
        }

    async def peer_snapshot(
        self, company_id: uuid.UUID, as_of: date | None = None
    ) -> dict[str, Any]:
        """Peers + per-metric percentiles + profile version for one company."""
        company = await self._require_company(company_id)
        as_of = as_of or datetime.now(UTC).date()
        as_of_text = as_of.isoformat()

        peers, basis = await self.resolve_peers(company)
        profile_key, profile_rows = await self.industry.profile_for_egx_sector(
            company.egx_sector_id
        )

        egx_sector_name: str | None = None
        if company.egx_sector_id is not None:
            egx = await self.industry.get_egx_sector(company.egx_sector_id)
            egx_sector_name = egx.name if egx else None

        gics: dict[str, str] | None = None
        if company.gics_sub_industry_id is not None:
            chain = await self.industry.gics_chain_for_sub_industry(
                company.gics_sub_industry_id
            )
            if chain is not None:
                sector, group, industry, sub = chain
                gics = {
                    "sector_code": sector.code,
                    "sector_name": sector.name,
                    "industry_group_code": group.code,
                    "industry_group_name": group.name,
                    "industry_code": industry.code,
                    "industry_name": industry.name,
                    "sub_industry_code": sub.code,
                    "sub_industry_name": sub.name,
                }

        universe = [company, *peers]
        universe_ids = [c.id for c in universe]
        percentiles: list[dict[str, Any]] = []
        for row in profile_rows:
            values = await self.industry.latest_metric_values(universe_ids, row.metric_key)
            target_raw, unit = values.get(company.id, (None, None))
            target = _to_decimal(target_raw)
            peer_vals = [_to_decimal(values.get(p.id, (None, None))[0]) for p in peers]
            result = peer_percentile(row.metric_key, target, peer_vals)
            metric_def = get_metric(row.metric_key)
            display = metric_def.display_name if metric_def is not None else row.metric_key
            explanation = explain_percentile(
                company.ticker,
                display,
                target_raw,
                result,
                profile_key,
                INDUSTRY_METHODOLOGY_VERSION,
                as_of_text,
            )
            percentiles.append(
                {
                    "metric_key": row.metric_key,
                    "display_name": display,
                    "value": f"{result.value:.2f}" if result.value is not None else None,
                    "status": result.status.value,
                    "unit": unit,
                    "n_peers": result.n_peers,
                    "n_with_data": result.n_with_data,
                    "explanation": explanation,
                    "reason": explanation,
                }
            )

        return {
            "company": {
                "id": str(company.id),
                "ticker": company.ticker,
                "name": company.name,
                "sector": company.sector,
                "egx_sector": egx_sector_name,
                "gics": gics,
            },
            "peers": {
                "basis": basis,
                "items": [
                    {"id": str(p.id), "ticker": p.ticker, "name": p.name}
                    for p in peers
                ],
            },
            "profile": {
                "profile_id": profile_key,
                "methodology_version": INDUSTRY_METHODOLOGY_VERSION,
                "metric_keys": [r.metric_key for r in profile_rows],
            },
            "percentiles": percentiles,
            "n_peers": len(peers),
            "methodology_version": INDUSTRY_METHODOLOGY_VERSION,
            "as_of": as_of_text,
        }
