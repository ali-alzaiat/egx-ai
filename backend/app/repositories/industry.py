"""Repository for industry taxonomy, peer overrides, and metric profiles."""

import uuid
from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.constants import INDUSTRY_METHODOLOGY_VERSION
from app.models.industry import (
    CompanyPeerOverride,
    EgxSector,
    GicsIndustry,
    GicsIndustryGroup,
    GicsSector,
    GicsSubIndustry,
    IndustryMetricProfile,
)
from app.models.market import Company


class IndustryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_egx_sector(self, egx_sector_id: uuid.UUID) -> EgxSector | None:
        return await self.session.get(EgxSector, egx_sector_id)

    async def get_egx_sector_by_name(self, name: str) -> EgxSector | None:
        result = await self.session.execute(select(EgxSector).where(EgxSector.name == name))
        return result.scalar_one_or_none()

    async def gics_chain_for_sub_industry(
        self, sub_industry_id: uuid.UUID
    ) -> tuple[GicsSector, GicsIndustryGroup, GicsIndustry, GicsSubIndustry] | None:
        """Return the 4-level GICS chain for one sub-industry id, or None."""
        sub = await self.session.get(GicsSubIndustry, sub_industry_id)
        if sub is None:
            return None
        industry = await self.session.get(GicsIndustry, sub.industry_id)
        if industry is None:
            return None
        group = await self.session.get(GicsIndustryGroup, industry.group_id)
        if group is None:
            return None
        sector = await self.session.get(GicsSector, group.sector_id)
        if sector is None:
            return None
        return (sector, group, industry, sub)

    async def list_peers_in_egx_sector(
        self, egx_sector_id: uuid.UUID, exclude_company_id: uuid.UUID
    ) -> Sequence[Company]:
        result = await self.session.execute(
            select(Company)
            .where(Company.egx_sector_id == egx_sector_id)
            .where(Company.id != exclude_company_id)
            .order_by(Company.ticker)
        )
        return result.scalars().all()

    async def list_peers_in_sub_industry(
        self, sub_industry_id: uuid.UUID, exclude_company_id: uuid.UUID
    ) -> Sequence[Company]:
        result = await self.session.execute(
            select(Company)
            .where(Company.gics_sub_industry_id == sub_industry_id)
            .where(Company.id != exclude_company_id)
            .order_by(Company.ticker)
        )
        return result.scalars().all()

    async def get_override(self, company_id: uuid.UUID) -> CompanyPeerOverride | None:
        result = await self.session.execute(
            select(CompanyPeerOverride).where(CompanyPeerOverride.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def list_companies_by_ids(self, company_ids: list[uuid.UUID]) -> Sequence[Company]:
        if not company_ids:
            return []
        result = await self.session.execute(
            select(Company).where(Company.id.in_(company_ids)).order_by(Company.ticker)
        )
        return result.scalars().all()

    async def upsert_override(
        self, company_id: uuid.UUID, peer_company_ids: list[uuid.UUID]
    ) -> CompanyPeerOverride:
        stmt = (
            pg_insert(CompanyPeerOverride)
            .values(
                company_id=company_id,
                peer_company_ids=[str(p) for p in peer_company_ids],
                methodology_version=INDUSTRY_METHODOLOGY_VERSION,
            )
            .on_conflict_do_update(
                constraint="uq_company_peer_override",
                set_={
                    "peer_company_ids": [str(p) for p in peer_company_ids],
                    "methodology_version": INDUSTRY_METHODOLOGY_VERSION,
                },
            )
            .returning(CompanyPeerOverride)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def profile_for_egx_sector(
        self, egx_sector_id: uuid.UUID | None
    ) -> tuple[str, Sequence[IndustryMetricProfile]]:
        """Industry-scoped profile rows, else the default profile rows."""
        if egx_sector_id is not None:
            scoped = await self.session.execute(
                select(IndustryMetricProfile)
                .where(IndustryMetricProfile.egx_sector_id == egx_sector_id)
                .where(
                    IndustryMetricProfile.methodology_version
                    == INDUSTRY_METHODOLOGY_VERSION
                )
                .order_by(IndustryMetricProfile.display_order)
            )
            rows = scoped.scalars().all()
            if rows:
                return (rows[0].profile_key, rows)
        default = await self.session.execute(
            select(IndustryMetricProfile)
            .where(IndustryMetricProfile.profile_key == "default")
            .where(
                IndustryMetricProfile.methodology_version == INDUSTRY_METHODOLOGY_VERSION
            )
            .order_by(IndustryMetricProfile.display_order)
        )
        rows = default.scalars().all()
        key = rows[0].profile_key if rows else "default"
        return (key, rows)

    async def latest_metric_values(
        self, company_ids: list[uuid.UUID], metric_key: str
    ) -> dict[uuid.UUID, tuple[str | None, str | None]]:
        """Latest AVAILABLE metric value per company as (value_str, unit).

        Missing data stays absent from the dict — never zero-filled.
        """
        from app.models.metrics import FinancialMetric, MetricStatusDB

        if not company_ids:
            return {}
        result = await self.session.execute(
            select(FinancialMetric)
            .where(FinancialMetric.company_id.in_(company_ids))
            .where(FinancialMetric.metric_code == metric_key)
            .where(FinancialMetric.status == MetricStatusDB.AVAILABLE)
            .order_by(
                FinancialMetric.company_id, desc(FinancialMetric.calculated_at)
            )
        )
        out: dict[uuid.UUID, tuple[str | None, str | None]] = {}
        for m in result.scalars().all():
            if m.company_id not in out:
                out[m.company_id] = (
                    str(m.value) if m.value is not None else None,
                    m.unit,
                )
        return out
