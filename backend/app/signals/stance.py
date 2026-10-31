"""Deterministic stance service (signal-rules-2.2).

I/O shell around the pure rules in :mod:`app.signals.rules`: loads prices,
valuation scenarios, the investment score, statement freshness and the
Shariah block, then lets the rules decide. No LLM, no trained model. Every
output carries the methodology version, the inputs used, and a non-empty
limitations list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.repositories.statements import StatementLineRepository
from app.scores.service import ScoreService
from app.screening.status import shariah_statuses
from app.signals import stance_cache
from app.signals.rules import (
    FAIR_VALUE_CONFIDENCE_LEVELS,
    LOW_LIQUIDITY_EGP,
    MIN_MARKET_PEERS,
    SIGNAL_RULES_VERSION,
    STALE_STATEMENT_DAYS,
    Bar,
    Liquidity,
    ReferenceLevels,
    Stance,
    composite,
    confidence_for,
    fair_value_discount,
    liquidity,
    market_median_discount,
    reference_levels,
    relative_fair_value_subscore,
    score_subscore,
    stance_for,
    technical_view,
    valuation_subscore,
)
from app.valuation.service import FairValueService

logger = logging.getLogger(__name__)

__all__ = [
    "COMPLIANCE_COPY",
    "LEVELS_COPY",
    "SIGNAL_RULES_VERSION",
    "STOP_COPY",
    "LimitationItem",
    "ReasonPart",
    "Stance",
    "StanceResult",
    "StanceService",
]

PRICE_HISTORY_BARS = 260
# The range-low stop fallback looks at recent bars only, not the full history.
RANGE_LOW_BARS = 90
COMPLIANCE_COPY = (
    "Research calculation — not investment advice · حساب بحثي — ليس توصية استثمارية"
)
STOP_COPY = "a risk reference, not an order condition"
LEVELS_COPY = (
    "Reference levels are a volatility band (ATR) around the last close under these "
    "assumptions — not a forecast or a price target."
)


@dataclass(frozen=True)
class ReasonPart:
    """One sentence of a reason as a code plus parameters (strings as the English prints them)."""

    code: str
    params: dict[str, str]


@dataclass
class Reason:
    engine: str
    inputs: dict[str, str]
    text: str
    parts: list[ReasonPart] = field(default_factory=list)


@dataclass(frozen=True)
class LimitationItem:
    """One limitation as a code plus parameters, with the English sentence as the fallback."""

    code: str
    params: dict[str, str]
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
    price: Decimal | None
    score: Decimal | None
    coverage: Decimal
    reasons: list[Reason]
    limitations: list[str]
    targets: dict[str, TargetLevel]
    stop_level: TargetLevel
    reference_levels: ReferenceLevels | None
    liquidity: Liquidity
    shariah: dict[str, Any]
    statement_freshness: date | None
    rules_version: str
    as_of: datetime
    limitation_items: list[LimitationItem] = field(default_factory=list)


def _decimal(raw: Any) -> Decimal | None:
    try:
        return Decimal(str(raw)) if raw is not None else None
    except Exception:
        return None


class StanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.prices = PriceRepository(session)
        self.statements = StatementLineRepository(session)
        self.valuation = FairValueService(session)
        self.score = ScoreService(session)

    async def compute(
        self,
        ticker: str,
        entry_price: Decimal | None = None,
        stop_pct: Decimal = Decimal("10"),
        shariah: dict[str, Any] | None = None,
    ) -> StanceResult:
        """Stance for one ticker; ``shariah`` lets batch callers pass a prefetched block."""
        company = await self.companies.get_by_ticker(ticker)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        as_of = datetime.now(UTC)
        limitations: list[str] = []
        limitation_items: list[LimitationItem] = []

        def limit(code: str, text: str, params: dict[str, str] | None = None) -> None:
            limitations.append(text)
            limitation_items.append(LimitationItem(code, params or {}, text))

        limit("compliance_footer", COMPLIANCE_COPY)
        reasons: list[Reason] = []
        missing: list[str] = []
        missing_codes: list[str] = []
        subscores: dict[str, Decimal | None] = {}

        # Prices (newest first from the repository; rules want oldest first)
        price_rows, _ = await self.prices.get_prices(company.id, page_size=PRICE_HISTORY_BARS)
        bars = [
            Bar(close=r.close, high=r.high, low=r.low, volume=r.volume)
            for r in sorted(price_rows, key=lambda r: r.date)
            if r.close is not None
        ]
        current_price = bars[-1].close if bars else None

        # Technical
        view = technical_view(bars)
        if view is None:
            missing.append("technical indicators")
            missing_codes.append("technical")
            subscores["technical"] = None
        else:
            subscores["technical"] = view.subscore
            reasons.append(
                Reason(
                    engine="technical",
                    inputs=view.inputs,
                    text=" ".join(c.detail for c in view.components),
                    parts=[ReasonPart(c.code, dict(c.params)) for c in view.components],
                )
            )
            for note in view.notes:
                reasons.append(
                    Reason(
                        engine="volume",
                        inputs=view.inputs,
                        text=note.text,
                        parts=[ReasonPart(note.code, dict(note.params))],
                    )
                )

        # Valuation: scenarios win; else the market-relative fair-value discount (R46 S2)
        payload = await self._valuation_payload(company.id)
        targets, base, bear, bull = self._scenario_targets(payload)
        currency_reason = self._currency_mismatch(payload)
        fv_sub: Decimal | None = None
        fv_reason: Reason | None = None
        fv_note: str | None = None
        if currency_reason is not None:
            # Price and statements are in different currencies: nothing is compared.
            targets = {
                key: TargetLevel(value=t.value, status="INSUFFICIENT_DATA", reason=currency_reason)
                for key, t in targets.items()
            }
            base = bear = bull = None
        elif base is None and current_price is not None:
            fv_sub, fv_reason, fv_note = await self._fair_value_view(payload, current_price)
        if currency_reason is not None:
            missing.append("valuation (" + currency_reason + ")")
            missing_codes.append("valuation")
            subscores["valuation"] = None
        elif fv_sub is not None and fv_reason is not None:
            subscores["valuation"] = fv_sub
            reasons.append(fv_reason)
        elif base is None or current_price is None:
            missing.append(
                "valuation scenarios or fair value"
                + (f" ({fv_note})" if fv_note else " (Medium+ confidence)")
            )
            missing_codes.append("valuation")
            subscores["valuation"] = None
        else:
            sub = valuation_subscore(current_price, bear, base, bull)
            subscores["valuation"] = sub
            reasons.append(
                Reason(
                    engine="valuation",
                    inputs={
                        "bear": str(bear) if bear is not None else "n/a",
                        "base": str(base),
                        "bull": str(bull) if bull is not None else "n/a",
                        "price": str(current_price),
                    },
                    text=f"Price vs scenario range: sub-score {sub:+}.",
                    parts=[ReasonPart("scenario_range", {"subscore": f"{sub:+}"})],
                )
            )

        # Investment score
        headline = await self._headline(company.id)
        if headline is None:
            missing.append("investment score")
            missing_codes.append("score")
            subscores["score"] = None
        else:
            sub = score_subscore(headline)
            subscores["score"] = sub
            reasons.append(
                Reason(
                    engine="score",
                    inputs={"headline": str(headline)},
                    text=f"Investment score {headline}: sub-score {sub:+.2f}.",
                    parts=[
                        ReasonPart(
                            "investment_score",
                            {"headline": str(headline), "subscore": f"{sub:+.2f}"},
                        )
                    ],
                )
            )

        # Statement freshness (gates confidence; never moves the stance)
        stmt_lines = await self.statements.latest_approved(company.id)
        dates = [ln.published_date for ln in stmt_lines if ln.published_date is not None]
        freshness = max(dates) if dates else None
        stale = False
        if freshness is None:
            limit("statement_freshness_unknown", "Statement freshness unknown.")
        else:
            age = (date.today() - freshness).days
            stale = age > STALE_STATEMENT_DAYS
            if stale:
                limit(
                    "statement_stale",
                    f"Statement freshness {age} days (>{STALE_STATEMENT_DAYS}).",
                    {"days": str(age), "max_days": str(STALE_STATEMENT_DAYS)},
                )

        # Liquidity gate
        liq = liquidity(bars)
        if liq.low:
            limit(
                "low_liquidity",
                f"LOW LIQUIDITY: average value traded below EGP {LOW_LIQUIDITY_EGP:,} "
                f"over {liq.window} sessions; levels may not be executable.",
                {"min_egp": f"{LOW_LIQUIDITY_EGP:,}", "window": str(liq.window)},
            )

        # Composite → stance + confidence
        score, coverage = composite(subscores)
        technical_only = subscores.get("technical") is not None and all(
            subscores.get(k) is None for k in ("valuation", "score")
        )
        if score is None:
            stance, confidence = Stance.HOLD, 0
            limit("no_engine_input", "No engine produced an input: stance defaults to hold.")
        else:
            stance = stance_for(score)
            confidence = confidence_for(
                score,
                coverage,
                technical_only=technical_only,
                low_liquidity=bool(liq.low),
                stale_statements=stale,
            )
        if technical_only:
            limit("technical_only", "Technical-only stance: no fundamentals available yet.")
        if missing:
            limit(
                "missing_inputs",
                "Missing inputs: " + ", ".join(missing) + ".",
                {"inputs": ",".join(missing_codes)},
            )

        # Reference levels + stop
        levels = reference_levels(bars)
        if levels is not None:
            limit("levels_band", LEVELS_COPY)
        stop_level = self._stop_level(entry_price, stop_pct, levels, bars)
        limit("stop_reference", STOP_COPY)

        if shariah is None:
            shariah = (await shariah_statuses(self.session, [company.id]))[company.id]

        return StanceResult(
            company_id=str(company.id),
            ticker=company.ticker,
            stance=stance,
            confidence=confidence,
            price=current_price,
            score=score,
            coverage=coverage,
            reasons=reasons,
            limitations=limitations,
            targets=targets,
            stop_level=stop_level,
            reference_levels=levels,
            liquidity=liq,
            shariah=shariah,
            statement_freshness=freshness,
            rules_version=SIGNAL_RULES_VERSION,
            as_of=as_of,
            limitation_items=limitation_items,
        )

    async def compute_cached(
        self,
        ticker: str,
        price_date: date | None,
        shariah: dict[str, Any] | None = None,
    ) -> StanceResult:
        """Default-parameter stance, reused until new prices land (or the TTL)."""
        cached = stance_cache.get(ticker, price_date)
        if cached is not None:
            return cached
        result = await self.compute(ticker, shariah=shariah)
        stance_cache.put(ticker, price_date, result)
        return result

    async def _valuation_payload(self, company_id: Any) -> dict[str, Any] | None:
        try:
            return await self.valuation.latest_payload(company_id)
        except Exception:
            logger.warning("fair value unavailable for %s", company_id, exc_info=True)
            return None

    @staticmethod
    def _currency_mismatch(payload: dict[str, Any] | None) -> str | None:
        """The "price in USD, statements in EGP" reason when the stored fair value says so."""
        block = payload.get("currency") if isinstance(payload, dict) else None
        if isinstance(block, dict) and block.get("status") == "MISMATCH":
            return str(block.get("reason"))
        return None

    async def _market_discounts(self) -> list[Decimal]:
        cached = stance_cache.get_market_discounts()
        if cached is not None:
            return cached
        values = await self.valuation.snapshots.peer_discounts(
            sorted(FAIR_VALUE_CONFIDENCE_LEVELS)
        )
        stance_cache.put_market_discounts(values)
        return values

    async def _fair_value_view(
        self, payload: dict[str, Any] | None, price: Decimal
    ) -> tuple[Decimal | None, Reason | None, str | None]:
        """(sub-score, reason, note): market-relative discount, or why it is unavailable."""
        if not isinstance(payload, dict):
            return None, None, None
        fair_value = _decimal((payload.get("fair_value") or {}).get("value"))
        level = str((payload.get("confidence") or {}).get("level"))
        if fair_value is None:
            return None, None, None
        if level not in FAIR_VALUE_CONFIDENCE_LEVELS:
            return None, None, f"fair value confidence {level} is below Medium"
        discount = fair_value_discount(price, fair_value)
        if discount is None:
            return None, None, None
        peers = await self._market_discounts()
        market = market_median_discount(peers)
        if market is None:
            note = (
                f"only {len(peers)} companies with Medium+ fair values; "
                f"{MIN_MARKET_PEERS} needed for a market median"
            )
            return None, None, note
        sub = relative_fair_value_subscore(discount, market)
        reason = Reason(
            engine="valuation",
            inputs={
                "fair_value": str(fair_value),
                "price": str(price),
                "discount": str(discount),
                "market_median_discount": str(market),
                "peers": str(len(peers)),
                "confidence": level,
            },
            text=(
                f"Price is {1 - discount:.2f}x fair value vs a market median of "
                f"{1 - market:.2f}x ({len(peers)} companies, {level} confidence): "
                f"sub-score {sub:+.2f}."
            ),
            parts=[
                ReasonPart(
                    "fair_value_vs_market",
                    {
                        "ratio": f"{1 - discount:.2f}",
                        "market_ratio": f"{1 - market:.2f}",
                        "peers": str(len(peers)),
                        "confidence": level,
                        "subscore": f"{sub:+.2f}",
                    },
                )
            ],
        )
        return sub, reason, None

    @staticmethod
    def _scenario_targets(
        payload: dict[str, Any] | None,
    ) -> tuple[dict[str, TargetLevel], Decimal | None, Decimal | None, Decimal | None]:
        """Valuation scenarios as targets; an inverted set is INSUFFICIENT_DATA."""
        scenarios = (payload or {}).get("scenarios", {}) if isinstance(payload, dict) else {}
        targets: dict[str, TargetLevel] = {}
        values: dict[str, Decimal | None] = {}
        for key in ("bull", "base", "bear"):
            scen = scenarios.get(key, {}) if isinstance(scenarios, dict) else {}
            if not isinstance(scen, dict):
                scen = {}
            raw = scen.get("value")
            values[key] = _decimal(raw)
            targets[key] = TargetLevel(
                value=raw,
                status=str(scen.get("status", "INSUFFICIENT_DATA")),
                reason=scen.get("reason"),
            )
        bull, base, bear = values["bull"], values["base"], values["bear"]
        if bull is not None and base is not None and bear is not None and not (
            bear < base < bull
        ):
            for key in targets:
                targets[key] = TargetLevel(
                    value=targets[key].value, status="INSUFFICIENT_DATA", reason="SCENARIO_ORDER"
                )
            return targets, None, None, None
        return targets, base, bear, bull

    async def _headline(self, company_id: Any) -> Decimal | None:
        payload = await self.score.latest_payload(company_id)
        assessment = payload.get("assessment") if isinstance(payload, dict) else None
        if not isinstance(assessment, dict):
            return None
        return _decimal((assessment.get("headline") or {}).get("value"))

    @staticmethod
    def _stop_level(
        entry_price: Decimal | None,
        stop_pct: Decimal,
        levels: ReferenceLevels | None,
        bars: list[Bar],
    ) -> TargetLevel:
        if entry_price is not None:
            stop = entry_price * (Decimal("1") - stop_pct / Decimal("100"))
            return TargetLevel(value=str(stop), status="AVAILABLE", reason="entry_pct")
        if levels is not None:
            return TargetLevel(value=str(levels.downside), status="AVAILABLE", reason="atr")
        lows = [b.low for b in bars[-RANGE_LOW_BARS:] if b.low is not None]
        if lows:
            return TargetLevel(value=str(min(lows)), status="AVAILABLE", reason="range_low")
        return TargetLevel(value=None, status="INSUFFICIENT_DATA", reason="no price range")
