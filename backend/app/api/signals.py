"""API endpoints for market-wide signal rankings.

This is the app's primary surface: rank every company in the EGX universe on the
same date, filter the ranking, and always report how much of the market the data
actually covers.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.market import Company
from app.models.signals import MarketSignal, SignalRun, SignalStatusDB
from app.services.universe import UniverseService
from app.signals.engine import SignalEngine
from app.signals.scoring import DEFAULT_MODEL

router = APIRouter(prefix="/api/signals", tags=["signals"])


async def _company_index(session: AsyncSession) -> dict[uuid.UUID, tuple[str, str | None]]:
    """Map company_id -> (ticker, name).

    Resolving companies in one query avoids lazy-loading the relationship, which
    raises MissingGreenlet outside the async greenlet context.
    """
    rows = (await session.execute(select(Company.id, Company.ticker, Company.name))).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def _serialize(signal: MarketSignal, ticker: str, name: str | None) -> dict[str, object]:
    return {
        "ticker": ticker,
        "name": name,
        "as_of": signal.as_of.isoformat(),
        "model": f"{signal.model_name}@{signal.model_version}",
        "status": signal.status.value,
        "tier": signal.tier.value if signal.tier else None,
        "score": float(signal.score) if signal.score is not None else None,
        "rank": signal.rank,
        "universe_size": signal.universe_size,
        "data_coverage": float(signal.data_coverage) if signal.data_coverage is not None else None,
        "percentiles": signal.percentiles or {},
        "factors": signal.factors or {},
        "excluded_factors": signal.excluded_factors or [],
        "rationale": signal.rationale,
        "reason": signal.reason,
    }


@router.get("")
async def list_signals(
    as_of: date | None = Query(None, description="Ranking date (default: latest)"),
    model_version: str | None = Query(None),
    tier: str | None = Query(None, description="Filter by standing label"),
    min_score: float | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Ranked companies, best first, with the market's coverage attached."""
    engine = SignalEngine(session)
    signals, total = await engine.latest_signals(
        model_version=model_version,
        as_of=as_of,
        limit=limit,
        offset=offset,
        tier=tier,
        min_score=min_score,
    )
    if not signals:
        return {
            "as_of": None,
            "model": None,
            "total": 0,
            "count": len(signals),
            "results": [],
            "coverage": (await UniverseService(session).coverage()).as_dict(),
            "notice": "No ranking stored yet. Run the signal engine to populate it.",
        }

    index = await _company_index(session)
    latest_as_of = signals[0].as_of
    results = []
    for signal in signals:
        ticker, name = index.get(signal.company_id, ("", None))
        results.append(_serialize(signal, ticker, name))

    return {
        "as_of": latest_as_of.isoformat(),
        "model": f"{signals[0].model_name}@{signals[0].model_version}",
        "total": total,
        "count": len(signals),
        "results": results,
        "coverage": (await UniverseService(session).coverage()).as_dict(),
        "disclaimer": (
            "Research signal only, not investment advice. Scores are relative to "
            "the covered universe on this date and use price data only."
        ),
    }


@router.get("/model")
async def get_model() -> dict[str, object]:
    """Describe the active scoring model and its factors."""
    return DEFAULT_MODEL.describe()


@router.get("/coverage")
async def get_coverage(
    min_history_days: int = Query(DEFAULT_MODEL.min_history_days, ge=1),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """How much of the EGX universe the app can currently analyse."""
    coverage = await UniverseService(session).coverage(min_history_days=min_history_days)
    return coverage.as_dict()


@router.get("/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    """History of scoring runs."""
    rows = (
        await session.execute(select(SignalRun).order_by(SignalRun.as_of.desc()).limit(limit))
    ).scalars().all()
    return [
        {
            "as_of": r.as_of.isoformat(),
            "model": f"{r.model_name}@{r.model_version}",
            "universe_total": r.universe_total,
            "scored_count": r.scored_count,
            "unscorable_count": r.unscorable_count,
            "coverage_ratio": float(r.coverage_ratio),
            "notes": r.notes,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/unscorable")
async def list_unscorable(
    as_of: date | None = Query(None),
    model_version: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    """Companies the engine refused to score, and why.

    A market-wide tool is only trustworthy if it can say what it left out.
    """
    version = model_version or DEFAULT_MODEL.version
    query = select(MarketSignal).where(
        MarketSignal.model_version == version,
        MarketSignal.status != SignalStatusDB.SCORED,
    )
    if as_of:
        query = query.where(MarketSignal.as_of == as_of)
    else:
        query = query.where(
            MarketSignal.as_of
            == select(MarketSignal.as_of)
            .where(MarketSignal.model_version == version)
            .order_by(MarketSignal.as_of.desc())
            .limit(1)
            .scalar_subquery()
        )
    query = query.limit(limit)

    signals = (await session.execute(query)).scalars().all()
    index = await _company_index(session)
    return [
        {
            "ticker": index.get(s.company_id, (None, None))[0],
            "name": index.get(s.company_id, (None, None))[1],
            "status": s.status.value,
            "reason": s.reason,
        }
        for s in signals
    ]


@router.get("/{ticker}/support")
async def get_support(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Support levels for a single EGX ticker, derived from historical price action.

    Identifies recent swing‑low local minima in the 200‑day price series as
    potential floor levels.  Discloses the price source and that these are
    research signals only, not predictions or investment advice.
    """
    from sqlalchemy import text

    # verify ticker exists
    company = (
        await session.execute(select(Company).where(Company.ticker == ticker.upper()))
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # pull the most recent 200 daily closes
    prices_stmt = text("""
        select close from daily_prices
        where company_id in (select id from companies where ticker=:t)
        order by date desc limit 200
    """).params(t=ticker.upper())
    closes_raw = (await session.execute(prices_stmt)).scalars().all()
    if len(closes_raw) < 10:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient price history for {ticker} (got {len(closes_raw)} rows)",
        )

    closes = [float(c) for c in closes_raw]

    # find local minima (swing lows) within the most recent 20 bars
    lookback = 20
    minima: list[dict[str, object]] = []
    for i in range(1, len(closes) - 1):
        if (
            closes[i] < closes[i - 1]
            and closes[i] < closes[i + 1]
            # only keep the most recent `lookback` bars
            and i >= len(closes) - lookback
        ):
            # find the date for this close
            date_stmt = text(
                "select date from daily_prices where company_id in "
                "(select id from companies where ticker=:t) and close=:c "
                "order by date desc limit 1"
            ).params(t=ticker.upper(), c=closes[i])
            date_row = (await session.execute(date_stmt)).first()
            date_val = date_row[0] if date_row else None
            minima.append(
                {
                    "price": round(closes[i], 2),
                    "date": str(date_val) if date_val else None,
                    "volume": None,  # volume not included in this minimal query
                }
            )

    # sort ascending by price and take top 5
    minima.sort(key=lambda x: x["price"])
    support_levels = minima[:5]

    # latest close
    latest_stmt = text("""
        select close from daily_prices
        where company_id in (select id from companies where ticker=:t)
        order by date desc limit 1
    """).params(t=ticker.upper())
    latest = (await session.execute(latest_stmt)).scalar()

    return {
        "ticker": ticker,
        "latest_close": round(float(latest), 2) if latest else None,
        "best_buy_price": {
            "price": round(float(latest), 2) if latest else None,
            "note": (
                "This is the most recent daily close from the price provider, "
                "not a real-time market ask/bid. Use as a research signal only."
            ),
        } if latest else None,
        "support_levels": support_levels,
        "disclaimer": (
            "Research signal only, not investment advice. Support levels are derived "
            "from historical price action (recent swing‑low local minima) and do not "
            "predict future price movement. Based on 200‑day close series from the "
            "designated price provider; coverage may be partial for some tickers. "
            "The last close price is shown for reference only and does not represent "
            "a current market executable price."
        ),
    }


@router.post("/run")
async def run_signals(
    as_of: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Recompute the ranking for a date and persist it."""
    engine = SignalEngine(session)
    try:
        result = await engine.run(as_of=as_of, persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "as_of": result.as_of.isoformat(),
        "model": f"{result.model_name}@{result.model_version}",
        "universe_total": result.universe_total,
        "scored_count": result.scored_count,
        "unscorable_count": result.unscorable_count,
        "coverage_ratio": result.coverage_ratio,
    }


@router.get("/{ticker}")
async def get_signal(
    ticker: str,
    as_of: date | None = Query(None),
    model_version: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """One company's signal detail, including the factor breakdown."""
    company = (
        await session.execute(select(Company).where(Company.ticker == ticker.upper()))
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    version = model_version or DEFAULT_MODEL.version
    query = select(MarketSignal).where(
        MarketSignal.company_id == company.id,
        MarketSignal.model_version == version,
    )
    query = query.where(
        MarketSignal.as_of == as_of
    ) if as_of else query.order_by(MarketSignal.as_of.desc())
    query = query.limit(1)

    signal = (await session.execute(query)).scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="No signal stored for this company")

    payload = _serialize(signal, company.ticker, company.name)
    payload["sector"] = company.sector
    payload["industry"] = company.industry
    return payload
