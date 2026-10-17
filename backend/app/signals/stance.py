"""Deterministic stance service (signal-rules-1.0).

A pure-ish rules engine over the engines we already own: technical
indicators, valuation scenario range, investment score, Shariah state,
statement freshness. No LLM, no trained model. Every output carries the
methodology version, the inputs used, and a non-empty limitations list.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.repositories.screening import ScreeningRepository
from app.repositories.statements import StatementLineRepository
from app.scores.service import ScoreService
from app.technical.indicators import calculate_sma
from app.technical.service import TechnicalInput, TechnicalService
from app.valuation.service import FairValueInput, FairValueService

logger = logging.getLogger(__name__)

SIGNAL_RULES_VERSION = "signal-rules-1.0"
COMPLIANCE_COPY = (
    "Research calculation — not investment advice · حساب بحثي — ليس توصية استثمارية"
)
STOP_COPY = "a risk reference, not an order condition"


class Stance(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"


@dataclass
class Reason:
    engine: str
    inputs: dict[str, str]
    text: str


@dataclass
class TargetLevel:
    value: str | None
    status: str
    reason: str | None


@dataclass
class StanceResult:
    company_id: str
    ticker: str
    stance: Stance
    confidence: int
    reasons: list[Reason]
    limitations: list[str]
    targets: dict[str, TargetLevel]
    stop_level: TargetLevel
    statement_freshness: date | None
    rules_version: str
    as_of: datetime


class StanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.prices = PriceRepository(session)
        self.statements = StatementLineRepository(session)
        self.screening = ScreeningRepository(session)
        self.technical = TechnicalService(session)
        self.valuation = FairValueService(session)
        self.score = ScoreService(session)

    async def compute(
        self,
        ticker: str,
        entry_price: Decimal | None = None,
        stop_pct: Decimal = Decimal("10"),
    ) -> StanceResult:
        company = await self.companies.get_by_ticker(ticker)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        as_of = datetime.now(UTC)
        limitations: list[str] = [COMPLIANCE_COPY]
        reasons: list[Reason] = []
        missing: list[str] = []

        # Prices
        price_rows, _ = await self.prices.get_prices(company.id, page_size=90)
        price_rows_asc = sorted(price_rows, key=lambda r: r.date)
        closes = [r.close for r in price_rows_asc if r.close is not None]
        highs = [r.high for r in price_rows_asc if r.high is not None]
        lows = [r.low for r in price_rows_asc if r.low is not None]
        volumes = [r.volume for r in price_rows_asc if r.volume is not None]
        current_price = closes[-1] if closes else None

        # Technical
        sma20: Decimal | None = None
        sma50: Decimal | None = None
        technical_available = False
        if len(closes) >= 20:
            try:
                r20 = calculate_sma(closes, 20)
                if r20.status.value == "AVAILABLE":
                    sma20 = r20.value
                r50 = calculate_sma(closes, 50) if len(closes) >= 50 else None
                if r50 is not None and r50.status.value == "AVAILABLE":
                    sma50 = r50.value
                technical_available = sma20 is not None
            except Exception:  # pragma: no cover - defensive
                technical_available = False
        tech_points = 0
        if not technical_available or current_price is None:
            missing.append("technical indicators")
        else:
            if sma20 is not None and sma50 is not None:
                if current_price > sma20 and sma20 > sma50:
                    tech_points = 20
                elif current_price < sma20 and sma20 < sma50:
                    tech_points = -20
            reasons.append(
                Reason(
                    engine="technical",
                    inputs={
                        "sma20": str(sma20) if sma20 is not None else "n/a",
                        "sma50": str(sma50) if sma50 is not None else "n/a",
                        "price": str(current_price) if current_price is not None else "n/a",
                    },
                    text=f"Technical composite {tech_points:+d} from SMA20/SMA50 alignment.",
                )
            )

        # Valuation
        fv_payload: dict[str, Any] | None = None
        try:
            fv_payload = await self.valuation.fair_value(company.id, FairValueInput())
        except Exception:
            fv_payload = None
        scenarios_raw = (fv_payload or {}).get("scenarios", {}) if isinstance(fv_payload, dict) else {}
        targets: dict[str, TargetLevel] = {}
        valuation_available = False
        base_value: Decimal | None = None
        bear_value: Decimal | None = None
        bull_value: Decimal | None = None
        for key in ("bull", "base", "bear"):
            scen = scenarios_raw.get(key, {}) if isinstance(scenarios_raw, dict) else {}
            if not isinstance(scen, dict):
                scen = {}
            val_str = scen.get("value")
            try:
                val_dec = Decimal(val_str) if val_str is not None else None
            except Exception:
                val_dec = None
            targets[key] = TargetLevel(
                value=val_str if val_str is not None else None,
                status=str(scen.get("status", "INSUFFICIENT_DATA")),
                reason=scen.get("reason"),
            )
            if key == "base":
                base_value = val_dec
            if key == "bear":
                bear_value = val_dec
            if key == "bull":
                bull_value = val_dec
        if base_value is not None:
            valuation_available = True
        # scenario order guard
        if bull_value is not None and base_value is not None and bear_value is not None:
            if not (bear_value < base_value < bull_value):
                for key in ("bull", "base", "bear"):
                    targets[key] = TargetLevel(
                        value=targets[key].value,
                        status="INSUFFICIENT_DATA",
                        reason="SCENARIO_ORDER",
                    )
                base_value = None
                valuation_available = False
        val_points = 0
        if valuation_available and current_price is not None and base_value is not None:
            if current_price < base_value:
                val_points = 25
            elif bear_value is not None and current_price > bear_value:
                val_points = -20
        if not valuation_available:
            missing.append("valuation scenarios")
        else:
            reasons.append(
                Reason(
                    engine="valuation",
                    inputs={
                        "base": str(base_value) if base_value is not None else "n/a",
                        "bear": str(bear_value) if bear_value is not None else "n/a",
                        "price": str(current_price) if current_price is not None else "n/a",
                    },
                    text=f"Valuation gap {val_points:+d}.",
                )
            )

        # Score
        score_payload = await self.score.latest_payload(company.id)
        assessment = score_payload.get("assessment") if isinstance(score_payload, dict) else None
        headline = None
        if isinstance(assessment, dict):
            headline_raw = (assessment.get("headline") or {}).get("value")
            try:
                headline = float(headline_raw) if headline_raw is not None else None
            except (TypeError, ValueError):
                headline = None
        score_tier_points = 0
        if headline is None:
            missing.append("investment score")
        else:
            if headline >= 70:
                score_tier_points = 10
            elif headline <= 30:
                score_tier_points = -10
            reasons.append(
                Reason(
                    engine="score",
                    inputs={"headline": str(headline)},
                    text=f"Score tier {score_tier_points:+d}.",
                )
            )

        # Shariah
        screening_row = await self.screening.get_screening_result(company.id)
        shariah_points = 0
        if screening_row is None:
            missing.append("shariah screening")
        else:
            if screening_row.is_compliant is False:
                shariah_points = -30
            reasons.append(
                Reason(
                    engine="shariah",
                    inputs={"is_compliant": str(screening_row.is_compliant)},
                    text=f"Shariah {shariah_points:+d}.",
                )
            )

        # Statement freshness
        stmt_lines = await self.statements.latest_approved(company.id)
        freshness: date | None = None
        if stmt_lines:
            dates = [ln.published_date for ln in stmt_lines if ln.published_date is not None]
            freshness = max(dates) if dates else None
        freshness_points = 0
        if freshness is None:
            missing.append("statement freshness")
            limitations.append("Statement freshness unknown.")
        else:
            try:
                age = (date.today() - freshness).days
            except Exception:
                age = 0
            if age > 400:
                freshness_points = -15
                limitations.append(f"Statement freshness {age} days (>400).")
            reasons.append(
                Reason(
                    engine="freshness",
                    inputs={"published_date": freshness.isoformat()},
                    text=f"Freshness {freshness_points:+d}.",
                )
            )

        total = tech_points + val_points + score_tier_points + shariah_points + freshness_points

        if missing:
            limitations.append("Missing inputs: " + ", ".join(missing) + ".")

        # Cap confidence if any missing
        confidence = max(0, min(100, 50 + total))
        if missing:
            confidence = min(confidence, 40)

        if total >= 60:
            stance = Stance.BUY
        elif total >= 35:
            stance = Stance.HOLD
        else:
            stance = Stance.REDUCE

        # Stop level
        if entry_price is not None:
            stop_value = entry_price * (Decimal("1") - stop_pct / Decimal("100"))
            stop_level = TargetLevel(
                value=str(stop_value),
                status="AVAILABLE",
                reason=None,
            )
        else:
            if lows:
                stop_value = min(lows)
                stop_level = TargetLevel(value=str(stop_value), status="AVAILABLE", reason=None)
            else:
                stop_level = TargetLevel(value=None, status="INSUFFICIENT_DATA", reason="no price range")
        limitations.append(STOP_COPY)

        return StanceResult(
            company_id=str(company.id),
            ticker=company.ticker,
            stance=stance,
            confidence=confidence,
            reasons=reasons,
            limitations=limitations,
            targets=targets,
            stop_level=stop_level,
            statement_freshness=freshness,
            rules_version=SIGNAL_RULES_VERSION,
            as_of=as_of,
        )
