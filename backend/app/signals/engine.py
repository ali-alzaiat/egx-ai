"""Runs the cross-sectional scoring engine across the entire universe.

The engine is the answer to "which EGX stocks stand out right now": it loads
every active company's price history, computes factors, ranks companies against
each other on the same date, and persists both the ranking and an honest record
of what it could not cover.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.market import Company, CompanyStatus, DailyPrice
from app.models.signals import (
    MarketSignal,
    SignalRun,
    SignalStatusDB,
    UniverseCoverageSnapshot,
)
from app.services.universe import UniverseService
from app.signals.factors import PriceBar, compute_factors
from app.signals.scoring import (
    DEFAULT_MODEL,
    RankedMarket,
    ScoringModel,
    explain,
    score_market,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.universe import CoverageReport
    from app.signals.factors import FactorSet

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 400


@dataclass(frozen=True, slots=True)
class SignalRunResult:
    """Outcome of one scoring run."""

    as_of: date
    model_name: str
    model_version: str
    universe_total: int
    scored_count: int
    unscorable_count: int
    coverage_ratio: float
    market: RankedMarket


class SignalEngine:
    """Computes and persists market-wide rankings."""

    def __init__(
        self,
        session: AsyncSession,
        model: ScoringModel = DEFAULT_MODEL,
        lookback_days: int = LOOKBACK_DAYS,
    ) -> None:
        self.session = session
        self.model = model
        self.lookback_days = lookback_days

    async def _load_universe_bars(
        self,
        as_of: date,
    ) -> tuple[dict[str, list[PriceBar]], dict[str, int], list[str]]:
        """Load price history per ticker plus observation counts and inactive names."""
        rows = (
            await self.session.execute(
                select(
                    Company.ticker,
                    DailyPrice.date,
                    DailyPrice.close,
                    DailyPrice.high,
                    DailyPrice.low,
                    DailyPrice.volume,
                )
                .join(DailyPrice, DailyPrice.company_id == Company.id)
                .where(
                    Company.status == CompanyStatus.ACTIVE,
                    DailyPrice.date <= as_of,
                )
                .order_by(Company.ticker, DailyPrice.date)
            )
        ).all()

        grouped: dict[str, list[PriceBar]] = {}
        for ticker, bar_date, close, high, low, volume in rows:
            bars = grouped.setdefault(ticker, [])
            bars.append(
                PriceBar(
                    date=bar_date,
                    close=float(close),
                    high=float(high),
                    low=float(low),
                    volume=int(volume),
                )
            )
        return grouped, {t: len(b) for t, b in grouped.items()}, []

    async def _inactive_tickers(self) -> list[str]:
        return list(
            (
                await self.session.execute(
                    select(Company.ticker).where(Company.status != CompanyStatus.ACTIVE)
                )
            ).scalars().all()
        )

    async def latest_price_date(self) -> date | None:
        return (
            await self.session.execute(
                select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)
            )
        ).scalar_one_or_none()

    async def run(
        self,
        as_of: date | None = None,
        persist: bool = True,
    ) -> SignalRunResult:
        """Score the whole universe for one date.

        Args:
            as_of: the date to score. Defaults to the latest price date.
            persist: write results to the database.

        Returns:
            A :class:`SignalRunResult` including the full ranking.
        """
        target = as_of or await self.latest_price_date()
        if target is None:
            raise ValueError("No price data available; run the market sync first")

        grouped, counts, _ = await self._load_universe_bars(target)
        inactive = await self._inactive_tickers()

        universe = UniverseService(self.session)
        coverage = await universe.coverage(min_history_days=self.model.min_history_days)

        factor_sets: list[FactorSet] = []
        unscorable: dict[str, str] = {}

        for ticker, bars in grouped.items():
            fs = compute_factors(
                ticker, bars, min_observations=self.model.min_history_days
            )
            if fs is None:
                unscorable[ticker] = (
                    f"only {counts.get(ticker, len(bars))} price observations; "
                    f"{self.model.min_history_days} required"
                )
                continue
            factor_sets.append(fs)

        for ticker in coverage.unpriced_tickers:
            unscorable.setdefault(ticker, "no price data from the configured source")
        for ticker in inactive:
            unscorable.setdefault(ticker, "not currently listed as active")

        market = score_market(factor_sets, self.model, unscorable=unscorable)
        scored = market.scored_count
        total = coverage.active_total
        ratio = (scored / total) if total else 0.0

        if persist:
            await self._persist(market, coverage, target, ratio)

        logger.info(
            "Signals %s v%s as of %s: %d scored / %d active (%.1f%%), %d unscorable",
            self.model.name, self.model.version, target, scored, total,
            ratio * 100, len(unscorable),
        )
        return SignalRunResult(
            as_of=target,
            model_name=self.model.name,
            model_version=self.model.version,
            universe_total=total,
            scored_count=scored,
            unscorable_count=len(unscorable),
            coverage_ratio=ratio,
            market=market,
        )

    async def _persist(
        self,
        market: RankedMarket,
        coverage: CoverageReport,
        as_of: date,
        ratio: float,
    ) -> None:
        company_ids = dict(
            (
                await self.session.execute(select(Company.ticker, Company.id))
            ).all()
        )

        rows: list[dict[str, object]] = []
        for scored in market.ranked:
            company_id = company_ids.get(scored.ticker)
            if company_id is None:
                continue
            rows.append(
                {
                    "company_id": company_id,
                    "as_of": as_of,
                    "model_name": self.model.name,
                    "model_version": self.model.version,
                    "status": SignalStatusDB.SCORED.value,
                    "tier": scored.tier.value if scored.tier else None,
                    "score": Decimal(str(scored.score)),
                    "rank": scored.rank,
                    "universe_size": market.scored_count,
                    "data_coverage": Decimal(str(round(scored.used_weight, 4))),
                    "factors": scored.factors,
                    "percentiles": scored.percentiles,
                    "excluded_factors": list(scored.excluded),
                    "rationale": explain(scored, self.model),
                    "reason": None,
                }
            )

        for ticker, reason in market.unscorable.items():
            company_id = company_ids.get(ticker)
            if company_id is None:
                continue
            status = (
                SignalStatusDB.NO_PRICE_DATA
                if "no price data" in reason
                else SignalStatusDB.INSUFFICIENT_HISTORY
            )
            rows.append(
                {
                    "company_id": company_id,
                    "as_of": as_of,
                    "model_name": self.model.name,
                    "model_version": self.model.version,
                    "status": status.value,
                    "tier": None,
                    "score": None,
                    "rank": None,
                    "universe_size": market.scored_count,
                    "data_coverage": None,
                    "factors": {},
                    "percentiles": {},
                    "excluded_factors": [],
                    "rationale": None,
                    "reason": reason,
                }
            )

        if rows:
            stmt = pg_insert(MarketSignal).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_market_signal_company_date_model",
                set_={
                    "status": stmt.excluded.status,
                    "tier": stmt.excluded.tier,
                    "score": stmt.excluded.score,
                    "rank": stmt.excluded.rank,
                    "universe_size": stmt.excluded.universe_size,
                    "data_coverage": stmt.excluded.data_coverage,
                    "factors": stmt.excluded.factors,
                    "percentiles": stmt.excluded.percentiles,
                    "excluded_factors": stmt.excluded.excluded_factors,
                    "rationale": stmt.excluded.rationale,
                    "reason": stmt.excluded.reason,
                },
            )
            await self.session.execute(stmt)

        run_stmt = pg_insert(SignalRun).values(
            {
                "as_of": as_of,
                "model_name": self.model.name,
                "model_version": self.model.version,
                "universe_total": coverage.active_total,
                "scored_count": market.scored_count,
                "unscorable_count": len(market.unscorable),
                "coverage_ratio": Decimal(str(round(ratio, 4))),
                "config": self.model.describe(),
                "notes": (
                    f"{market.scored_count} of {coverage.active_total} active companies "
                    f"scored; price coverage {coverage.priced_of_active * 100:.1f}%"
                ),
            }
        )
        await self.session.execute(
            run_stmt.on_conflict_do_update(
                constraint="uq_signal_run_date_model",
                set_={
                    "universe_total": run_stmt.excluded.universe_total,
                    "scored_count": run_stmt.excluded.scored_count,
                    "unscorable_count": run_stmt.excluded.unscorable_count,
                    "coverage_ratio": run_stmt.excluded.coverage_ratio,
                    "config": run_stmt.excluded.config,
                    "notes": run_stmt.excluded.notes,
                },
            )
        )

        await self.session.execute(
            pg_insert(UniverseCoverageSnapshot)
            .values(
                {
                    "as_of": as_of,
                    "universe_total": coverage.universe_total,
                    "active_total": coverage.active_total,
                    "with_price_data": coverage.with_price_data,
                    "analyzable": coverage.analyzable,
                    "unscorable": coverage.unscorable,
                    "coverage_ratio": Decimal(str(round(coverage.priced_of_active, 4))),
                    "universe_source": "EGX_UNIVERSE",
                    "universe_source_url": "",
                    "unpriced_tickers": list(coverage.unpriced_tickers),
                    "is_fallback_source": False,
                }
            )
            .on_conflict_do_nothing()
        )
        await self.session.commit()

    async def latest_signals(
        self,
        model_version: str | None = None,
        as_of: date | None = None,
        limit: int = 50,
        offset: int = 0,
        tier: str | None = None,
        min_score: float | None = None,
    ) -> tuple[Sequence[MarketSignal], int]:
        """Read back a stored ranking, best first."""
        version = model_version or self.model.version
        target = as_of or await self._latest_stored_date(version)

        query = select(MarketSignal).where(
            MarketSignal.model_version == version,
            MarketSignal.status == SignalStatusDB.SCORED,
        )
        count_query = select(MarketSignal).where(
            MarketSignal.model_version == version,
            MarketSignal.status == SignalStatusDB.SCORED,
        )
        if target is not None:
            query = query.where(MarketSignal.as_of == target)
            count_query = count_query.where(MarketSignal.as_of == target)
        if tier:
            query = query.where(MarketSignal.tier == tier)
            count_query = count_query.where(MarketSignal.tier == tier)
        if min_score is not None:
            query = query.where(MarketSignal.score >= min_score)
            count_query = count_query.where(MarketSignal.score >= min_score)

        total = len((await self.session.execute(count_query)).scalars().all())
        query = query.order_by(MarketSignal.rank).limit(limit).offset(offset)
        return (await self.session.execute(query)).scalars().all(), total

    async def _latest_stored_date(self, version: str) -> date | None:
        return (
            await self.session.execute(
                select(MarketSignal.as_of)
                .where(MarketSignal.model_version == version)
                .order_by(MarketSignal.as_of.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
