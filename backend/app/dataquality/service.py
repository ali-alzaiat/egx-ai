"""Data-quality service: I/O, scoring composition, persistence."""

import uuid
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality import scores
from app.dataquality.scores import (
    METHODOLOGY_VERSION,
    DataQualityScore,
    DataQualityStatus,
)
from app.ingestion.validation import FinancialFactValidator
from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, DailyPrice, DataSource

CRITICAL_FACT_LABELS = (
    "revenue",
    "net_income",
    "total_assets",
    "total_equity",
    "operating_cash_flow",
)

PRICE_FIELDS = ("open", "high", "low", "close", "volume")
PROFILE_FIELDS = ("name", "sector", "industry", "shares_outstanding", "free_float")


def _status_db_to_domain(status: DataQualityStatusDB) -> DataQualityStatus:
    return DataQualityStatus(status.value)


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


class DataQualityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _append_issues(self, score: DataQualityScore, *extra: str) -> DataQualityScore:
        return replace(score, issues=score.issues + tuple(extra))

    async def _get_source(self, source_id: uuid.UUID | None) -> DataSource | None:
        if source_id is None:
            return None
        stmt = select(DataSource).where(DataSource.id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def assess(
        self,
        company_id: uuid.UUID,
        scope: str,
        as_of: date | None = None,
    ) -> DataQualityScore:
        if as_of is None:
            as_of = datetime.now(UTC).date()

        if scope == "price_history":
            return await self._assess_price_history(company_id, as_of)
        if scope == "company_profile":
            return await self._assess_company_profile(company_id, as_of)
        if scope == "financial_statements":
            return await self._assess_financial_statements(company_id, as_of)
        raise HTTPException(status_code=400, detail=f"Unknown scope: {scope}")

    async def _assess_price_history(
        self, company_id: uuid.UUID, as_of: date
    ) -> DataQualityScore:
        stmt = (
            select(DailyPrice)
            .where(DailyPrice.company_id == company_id)
            .where(DailyPrice.date <= as_of)
            .order_by(DailyPrice.date.asc())
        )
        result = await self.session.execute(stmt)
        bars: list[DailyPrice] = list(result.scalars().all())

        if not bars:
            score = scores.score_for(
                scope="price_history",
                as_of=as_of,
                present=0,
                required=len(PRICE_FIELDS),
                observed=0,
                expected_depth=1,
                days_stale=None,
                errors=0,
                warnings=0,
                source_type=None,
                no_rows=True,
            )
            score = self._append_issues(
                score, "validation: no facts to validate \u2014 check not run"
            )
            await self._persist(company_id, "price_history", score, None, as_of)
            return score

        latest = bars[-1]
        oldest = bars[0]
        present = sum(
            1 for field in PRICE_FIELDS if getattr(latest, field) is not None
        )
        observed = len(bars)
        expected_depth = round(((as_of - oldest.date).days + 1) * 5 / 7)
        expected_depth = max(1, expected_depth)
        days_stale = (as_of - latest.date).days

        source = await self._get_source(latest.source_id)
        source_type = source.source_type if source else None

        score = scores.score_for(
            scope="price_history",
            as_of=as_of,
            present=present,
            required=len(PRICE_FIELDS),
            observed=observed,
            expected_depth=expected_depth,
            days_stale=days_stale,
            errors=0,
            warnings=0,
            source_type=source_type,
            no_rows=False,
        )

        reason = (
            f"latest bar {latest.date.isoformat()}; "
            f"{observed}/{expected_depth} expected trading days"
        )
        components = list(score.components)
        components[3] = replace(components[3], reason=reason)
        score = replace(score, components=tuple(components))
        score = self._append_issues(
            score, "validation: no facts to validate \u2014 check not run"
        )
        await self._persist(
            company_id, "price_history", score, latest.source_id, as_of
        )
        return score

    async def _assess_company_profile(
        self, company_id: uuid.UUID, as_of: date
    ) -> DataQualityScore:
        stmt = select(Company).where(Company.id == company_id)
        company = (await self.session.execute(stmt)).scalar_one()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        present = sum(
            1 for field in PROFILE_FIELDS if getattr(company, field) is not None
        )
        days_stale = (as_of - company.updated_at.date()).days

        score = scores.score_for(
            scope="company_profile",
            as_of=as_of,
            present=present,
            required=len(PROFILE_FIELDS),
            observed=1,
            expected_depth=1,
            days_stale=days_stale,
            errors=0,
            warnings=0,
            source_type=None,
            no_rows=False,
        )
        score = self._append_issues(
            score, "validation: no facts to validate \u2014 check not run"
        )
        await self._persist(company_id, "company_profile", score, None, as_of)
        return score

    async def _assess_financial_statements(
        self, company_id: uuid.UUID, as_of: date
    ) -> DataQualityScore:
        periods = (
            await self.session.execute(
                select(FinancialPeriod).where(
                    FinancialPeriod.company_id == company_id
                )
            )
        ).scalars().all()
        facts: list[FinancialFact] = list(
            (
                await self.session.execute(
                    select(FinancialFact).where(
                        FinancialFact.company_id == company_id
                    )
                )
            ).scalars().all()
        )

        if not periods and not facts:
            score = scores.score_for(
                scope="financial_statements",
                as_of=as_of,
                present=0,
                required=len(CRITICAL_FACT_LABELS),
                observed=0,
                expected_depth=8,
                days_stale=None,
                errors=0,
                warnings=0,
                source_type=None,
                no_rows=True,
            )
            score = self._append_issues(
                score,
                "validation: no facts to validate \u2014 check not run",
                "freshness: no publication dates available \u2014 check not run",
            )
            await self._persist(
                company_id, "financial_statements", score, None, as_of
            )
            return score

        present_set = set()
        for f in facts:
            label = f.normalized_label or f.reported_label or ""
            label = label.casefold().strip()
            if label in CRITICAL_FACT_LABELS:
                present_set.add(label)

        latest_doc = (
            await self.session.execute(
                select(FinancialDocument)
                .join(
                    FinancialPeriod,
                    FinancialDocument.period_id == FinancialPeriod.id,
                )
                .where(FinancialPeriod.company_id == company_id)
                .where(FinancialDocument.publication_date.is_not(None))
                .where(FinancialDocument.publication_date <= as_of)
                .order_by(FinancialDocument.publication_date.desc())
            )
        ).scalars().first()

        if latest_doc is None or latest_doc.publication_date is None:
            days_stale = None
            source_type = None
        else:
            days_stale = (as_of - latest_doc.publication_date).days
            source = await self._get_source(latest_doc.source_id)
            source_type = source.source_type if source else None

        validator = FinancialFactValidator()
        results = validator.validate_facts(facts)
        errors = sum(len(r.errors) for r in results)
        warnings = sum(len(r.warnings) for r in results)

        score = scores.score_for(
            scope="financial_statements",
            as_of=as_of,
            present=len(present_set),
            required=len(CRITICAL_FACT_LABELS),
            observed=len(periods),
            expected_depth=8,
            days_stale=days_stale,
            errors=errors,
            warnings=warnings,
            source_type=source_type,
            no_rows=False,
        )

        issues = list(score.issues)
        if not facts:
            issues.append(
                "validation: no facts to validate \u2014 check not run"
            )
        if latest_doc is None:
            issues.append(
                "freshness: no publication dates available \u2014 check not run"
            )
        components = list(score.components)
        if latest_doc is not None and latest_doc.publication_date is not None:
            pub = latest_doc.publication_date.isoformat()
            components[1] = replace(
                components[1],
                reason=f"latest filing published {pub}; {days_stale} days stale",
            )
        score = replace(
            score,
            components=tuple(components),
            issues=tuple(issues),
        )
        source_id = latest_doc.source_id if latest_doc is not None else None
        await self._persist(
            company_id, "financial_statements", score, source_id, as_of
        )
        return score

    async def latest(
        self,
        company_id: uuid.UUID,
        scope: str,
        methodology_version: str | None = None,
    ) -> DataQualityScore | None:
        version = methodology_version or METHODOLOGY_VERSION
        stmt = (
            select(DataQualityAssessment)
            .where(DataQualityAssessment.company_id == company_id)
            .where(DataQualityAssessment.scope == scope)
            .where(DataQualityAssessment.methodology_version == version)
            .order_by(
                desc(DataQualityAssessment.as_of),
                desc(DataQualityAssessment.computed_at),
            )
        )
        row = (await self.session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return self._row_to_score(row)

    def _row_to_score(self, row: DataQualityAssessment) -> DataQualityScore:
        components = tuple(
            scores.QualityComponent(
                key=_as_str(c.get("key")),
                label=_as_str(c.get("label")) or _as_str(c.get("key")),
                score=_as_float(c.get("score")),
                weight=_as_float(c.get("weight")),
                reason=_as_str(c.get("reason")),
            )
            for c in row.components
        )
        issues = row.issues if isinstance(row.issues, list) else []
        return DataQualityScore(
            scope=row.scope,
            as_of=row.as_of,
            status=_status_db_to_domain(row.status),
            score=float(row.score),
            components=components,
            issues=tuple(issues),
            methodology_version=row.methodology_version,
        )

    async def _persist(
        self,
        company_id: uuid.UUID,
        scope: str,
        score: DataQualityScore,
        source_id: uuid.UUID | None,
        as_of: date,
    ) -> None:
        existing = (
            await self.session.execute(
                select(DataQualityAssessment)
                .where(DataQualityAssessment.company_id == company_id)
                .where(DataQualityAssessment.scope == scope)
                .where(DataQualityAssessment.as_of == as_of)
                .where(
                    DataQualityAssessment.methodology_version
                    == score.methodology_version
                )
            )
        ).scalars().first()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        self.session.add(
            DataQualityAssessment(
                id=uuid.uuid4(),
                company_id=company_id,
                scope=scope,
                as_of=as_of,
                score=Decimal(f"{score.score:.2f}"),
                status=DataQualityStatusDB(score.status.value),
                components=[asdict(c) for c in score.components],
                issues=list(score.issues),
                methodology_version=score.methodology_version,
                source_id=source_id,
                computed_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
