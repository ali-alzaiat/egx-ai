"""R47 P1 day summary, P2 price backfill, Q3 fundamentals freshness on the company payload."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.statement_seed import make_company, seed_year

from app.ingestion.backfill_prices import apply_backfill, format_report, missing_bars, window
from app.ingestion.provider import DailyPriceData
from app.models.market import Company, DailyPrice, DataSource, DataSourceType

D = Decimal


async def _source(db: AsyncSession) -> DataSource:
    source = DataSource(
        id=uuid.uuid4(), name=f"R47 prices {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.DATA_PROVIDER,
    )
    db.add(source)
    await db.flush()
    return source


def _bar(day: date, close: str, volume: int = 1000, ticker: str = "X") -> DailyPriceData:
    c = D(close)
    return DailyPriceData(
        ticker=ticker, date=day, open=c, high=c + 1, low=c - 1, close=c,
        adjusted_close=None, volume=volume, value_traded=None, trades=None,
    )


async def _store(
    db: AsyncSession, company: Company, source: DataSource, bars: list[DailyPriceData]
) -> None:
    for b in bars:
        db.add(
            DailyPrice(
                id=uuid.uuid4(), company_id=company.id, date=b.date, open=b.open, high=b.high,
                low=b.low, close=b.close, volume=b.volume, source_id=source.id,
            )
        )
    await db.flush()


async def _count(db: AsyncSession, company: Company) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(DailyPrice).where(DailyPrice.company_id == company.id)
        )
    ).scalar_one()


# --- P1: latest price day summary ----------------------------------------------------------


async def test_latest_price_gives_day_summary_with_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    source = await _source(db_session)
    await _store(
        db_session, company, source,
        [_bar(date(2026, 10, 28), "40.00"), _bar(date(2026, 10, 29), "42.00", volume=5000)],
    )
    body = (await client.get(f"/api/companies/{company.id}/prices/latest")).json()
    assert body["status"] == "AVAILABLE"
    assert body["date"] == "2026-10-29"
    assert (body["open"], body["high"], body["low"], body["close"]) == (
        "42.0000", "43.0000", "41.0000", "42.0000",
    )
    assert body["volume"] == 5000
    assert body["previous_close"] == "40.0000" and body["previous_date"] == "2026-10-28"
    assert body["change"] == "2.0000" and body["change_pct"] == "5.00"
    assert body["change_reason"] is None


async def test_latest_price_without_previous_session_has_null_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    await _store(db_session, company, await _source(db_session), [_bar(date(2026, 10, 29), "42")])
    body = (await client.get(f"/api/companies/{company.id}/prices/latest")).json()
    assert body["status"] == "AVAILABLE" and body["close"] == "42.0000"
    assert body["change"] is None and body["change_pct"] is None
    assert body["previous_close"] is None
    assert "No earlier stored session" in body["change_reason"]


async def test_prices_endpoint_returns_five_years_in_one_request(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    source = await _source(db_session)
    first = date(2021, 11, 1)
    bars = [_bar(first + timedelta(days=i), "10") for i in range(1300)]
    await _store(db_session, company, source, bars)
    resp = await client.get(
        f"/api/companies/{company.id}/prices",
        params={"start_date": "2021-11-01", "end_date": "2026-10-30", "page_size": 1300},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 1300 and len(body["items"]) == 1300
    assert body["items"][0]["date"] > body["items"][-1]["date"]  # newest first
    over = await client.get(f"/api/companies/{company.id}/prices", params={"page_size": 2001})
    assert over.status_code == 422


# --- Q3: fundamentals freshness ------------------------------------------------------------


async def test_company_payload_exposes_fundamentals_freshness(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    await seed_year(db_session, company, 2023, {"revenue": D("90")})
    await seed_year(db_session, company, 2024, {"revenue": D("100")})
    for url in (f"/api/companies/{company.id}", f"/api/companies/ticker/{company.ticker}"):
        body = (await client.get(url)).json()
        f = body["fundamentals"]
        assert f["status"] == "AVAILABLE" and f["fiscal_year"] == 2024
        assert f["source_tier"] == "vendor" and f["provisional"] is True
        assert f["period_end"].startswith("2024")
        assert "sector_match_basis" in body


async def test_company_payload_without_fundamentals_is_insufficient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    f = (await client.get(f"/api/companies/{company.id}")).json()["fundamentals"]
    assert f["status"] == "INSUFFICIENT_DATA" and f["fiscal_year"] is None
    assert f["source_tier"] is None and f["provisional"] is None and f["reason"]


async def test_filing_tier_is_not_provisional(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    await seed_year(db_session, company, 2024, {"revenue": D("100")}, tier="filing", page="3")
    f = (await client.get(f"/api/companies/{company.id}")).json()["fundamentals"]
    assert f["source_tier"] == "filing" and f["provisional"] is False


# --- P2: backfill --------------------------------------------------------------------------


def test_window_is_five_years_back() -> None:
    start, end = window(5, today=date(2026, 10, 30))
    assert end == date(2026, 10, 30)
    assert date(2021, 10, 29) <= start <= date(2021, 10, 31)


def test_missing_bars_filters_stored_window_and_duplicates() -> None:
    bars = [
        _bar(date(2020, 1, 1), "1"),  # before the window
        _bar(date(2024, 1, 2), "2"),
        _bar(date(2024, 1, 2), "9"),  # duplicate date: first one wins
        _bar(date(2024, 1, 3), "3"),  # already stored
        _bar(date(2024, 1, 4), "4"),
        _bar(date(2027, 1, 1), "5"),  # after the window
    ]
    out = missing_bars(bars, {date(2024, 1, 3)}, date(2023, 1, 1), date(2025, 1, 1))
    assert [(b.date, b.close) for b in out] == [
        (date(2024, 1, 2), D("2")), (date(2024, 1, 4), D("4")),
    ]


async def test_backfill_inserts_only_missing_and_never_overwrites(
    db_session: AsyncSession,
) -> None:
    company = await make_company(db_session)
    source = await _source(db_session)
    await _store(db_session, company, source, [_bar(date(2025, 9, 18), "50")])
    start, end = date(2021, 10, 30), date(2026, 10, 30)
    fetched = [
        _bar(date(2021, 11, 1), "10"),
        _bar(date(2023, 5, 1), "20"),
        _bar(date(2025, 9, 18), "999"),  # Yahoo differs from the stored bar: must not overwrite
    ]

    dry = await apply_backfill(
        db_session, company, fetched, start, end, source_id=None, dry_run=True
    )
    assert dry.rows_added == 2 and await _count(db_session, company) == 1

    first = await apply_backfill(
        db_session, company, fetched, start, end, source_id=source.id, dry_run=False
    )
    assert first.status == "ok"
    assert (first.rows_added, first.already_stored, first.fetched) == (2, 1, 3)
    assert first.first_date_before == date(2025, 9, 18)
    assert first.first_date_after == date(2021, 11, 1)
    assert await _count(db_session, company) == 3

    kept = (
        await db_session.execute(
            select(DailyPrice.close).where(
                DailyPrice.company_id == company.id, DailyPrice.date == date(2025, 9, 18)
            )
        )
    ).scalar_one()
    assert kept == D("50.0000")

    again = await apply_backfill(
        db_session, company, fetched, start, end, source_id=source.id, dry_run=False
    )
    assert again.rows_added == 0 and await _count(db_session, company) == 3


async def test_backfill_reports_no_history_and_errors_without_writing(
    db_session: AsyncSession,
) -> None:
    company = await make_company(db_session)
    start, end = date(2021, 10, 30), date(2026, 10, 30)
    none = await apply_backfill(db_session, company, [], start, end, source_id=None, dry_run=False)
    assert none.status == "no_history" and none.rows_added == 0 and none.first_date_after is None
    err = await apply_backfill(
        db_session, company, RuntimeError("boom"), start, end, source_id=None, dry_run=False
    )
    assert err.status == "error" and err.detail == "boom"
    assert await _count(db_session, company) == 0
    report = format_report([none, err], dry_run=True)
    assert "DRY RUN" in report and "0/2 companies with history" in report
