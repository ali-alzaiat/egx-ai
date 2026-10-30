"""R47 P4: measured pattern odds (pure maths) and the patterns endpoint."""

import statistics
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.statement_seed import make_company
from tests.test_patterns import HS_TOP, path, series

from app.models.market import DailyPrice, DataSource, DataSourceType
from app.technical import pattern_backtest as B
from app.technical.patterns import detect_patterns

HS_KEY = "head_and_shoulders_top"
# Same head-and-shoulders top, confirmed on session 79 (close 89.17); different afterwards.
FALLS = path(HS_TOP[:-1] + [(90, 80), (160, 60)])
RISES = path(HS_TOP[:-1] + [(90, 80), (100, 95), (160, 120)])
DIPS_THEN_RISES = path(HS_TOP[:-1] + [(90, 80), (100, 70), (160, 110)])


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    B.clear_cache()


def _universe() -> dict[str, list[tuple[date, float]]]:
    return {"A": series(FALLS), "B": series(RISES), "C": series(DIPS_THEN_RISES)}


# ---- Wilson interval --------------------------------------------------------------------------


def test_wilson_interval_known_values() -> None:
    low, high = B.wilson_interval(8, 10)
    assert (round(low, 4), round(high, 4)) == (0.4902, 0.9433)
    low, high = B.wilson_interval(0, 10)
    assert low == 0.0 and round(high, 4) == 0.2775
    low, high = B.wilson_interval(50, 100)
    assert (round(low, 4), round(high, 4)) == (0.4038, 0.5962)
    low, high = B.wilson_interval(10, 10)
    assert high == 1.0 and round(low, 4) == 0.7225


# ---- base rate --------------------------------------------------------------------------------


def test_base_counts_by_hand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(B, "WARMUP_SESSIONS", 0)
    # Days 0-4 are all 10; days 20-24 are 11, 9, 10, 12, 8 -> +10%, -10%, 0, +20%, -20%.
    closes = [10.0] * 5 + [10.0] * 15 + [11.0, 9.0, 10.0, 12.0, 8.0]
    assert B.base_counts(closes, 20) == (2, 2, 5)
    assert B.base_counts(closes, 60) == (0, 0, 0)
    monkeypatch.setattr(B, "WARMUP_SESSIONS", 3)
    # Only days 3 and 4 qualify: 10 -> 12 (up) and 10 -> 8 (down).
    assert B.base_counts(closes, 20) == (1, 1, 2)


# ---- hit rate, base rate, median on a hand-made universe -------------------------------------


def test_hit_base_median_on_hand_made_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(B, "MIN_CASES", 3)
    universe = _universe()
    # All three confirm the top on the same session with the same close.
    confirm = []
    for rows in universe.values():
        found = [o for o in detect_patterns(rows) if o.pattern == HS_KEY]
        assert len(found) == 1
        confirm.append(found[0].confirmation_index)
    assert confirm == [79, 79, 79]

    result = B.backtest(universe)
    assert result.companies == 3
    cell20 = result.stats[HS_KEY][20]
    cell60 = result.stats[HS_KEY][60]
    assert cell20.sufficient and cell60.sufficient

    closes = {k: [c for _, c in v] for k, v in universe.items()}
    r20 = [c[99] / c[79] - 1 for c in closes.values()]
    r60 = [c[139] / c[79] - 1 for c in closes.values()]
    assert cell20.n == 3 and cell20.hits == sum(r < 0 for r in r20) == 2
    assert cell60.n == 3 and cell60.hits == sum(r < 0 for r in r60) == 1
    assert cell20.hit_rate == pytest.approx(2 / 3)
    assert cell20.median_return == pytest.approx(statistics.median(r20))
    assert cell60.median_return == pytest.approx(statistics.median(r60))
    assert (cell20.wilson_low, cell20.wilson_high) == pytest.approx(B.wilson_interval(2, 3))

    # Base rate: share of all stock-days (from the warm-up) whose forward return was negative.
    def share_down(h: int) -> float:
        down = total = 0
        for c in closes.values():
            for i in range(B.WARMUP_SESSIONS, len(c) - h):
                total += 1
                down += c[i + h] < c[i]
        return down / total

    assert cell20.base_rate == pytest.approx(share_down(20))
    assert cell60.base_rate == pytest.approx(share_down(60))
    assert cell20.difference == pytest.approx(2 / 3 - share_down(20))

    as_dict = cell20.to_dict()
    assert as_dict["status"] == "OK" and as_dict["n_companies"] == 3
    assert isinstance(as_dict["interval_excludes_base"], bool)


def test_expected_direction_up_uses_positive_returns_and_up_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(B, "MIN_CASES", 1)
    from tests.test_patterns import HS_INV

    up_after = path(HS_INV[:-1] + [(90, 120), (160, 150)])
    down_after = path(HS_INV[:-1] + [(90, 120), (100, 100), (160, 80)])
    result = B.backtest({"U": series(up_after), "D": series(down_after)})
    cell = result.stats["head_and_shoulders_inverse"][20]
    assert cell.n == 2 and cell.hits == 1  # inverse = expects up
    u, d = (c for c in (up_after, down_after))
    base_up = sum(
        1 for c in (u, d) for i in range(B.WARMUP_SESSIONS, len(c) - 20) if c[i + 20] > c[i]
    ) / sum(len(c) - 20 - B.WARMUP_SESSIONS for c in (u, d))
    assert cell.base_rate == pytest.approx(base_up)


def test_fewer_than_30_cases_is_insufficient_data() -> None:
    result = B.backtest(_universe())
    cell = result.stats[HS_KEY][20]
    assert not cell.sufficient and cell.n == 3
    assert cell.to_dict() == {
        "status": "INSUFFICIENT_DATA",
        "value": None,
        "reason": "too few cases (3)",
        "n": 3,
        "n_companies": 3,
    }
    # A pattern that never occurs reports zero cases, not a made-up rate.
    empty = result.stats["double_bottom"][60].to_dict()
    assert empty["status"] == "INSUFFICIENT_DATA" and empty["reason"] == "too few cases (0)"
    assert set(result.stats) == set(B.STATS_KEYS)


def test_occurrence_without_a_full_horizon_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(B, "MIN_CASES", 1)
    short = series(FALLS[:105])  # confirmation at 79: 20-session return exists, 60 does not
    result = B.backtest({"S": short})
    assert result.stats[HS_KEY][20].n == 1
    assert result.stats[HS_KEY][60].n == 0


def test_result_carries_overlap_note_and_universe() -> None:
    payload = B.backtest(_universe()).to_dict()
    assert "overlap" in payload["overlap_note"].lower()
    assert payload["universe"]["companies"] == 3
    assert payload["universe"]["horizons"] == [20, 60]
    assert set(payload["stats"][HS_KEY]) == {"20", "60"}


def test_cli_table_lists_every_key() -> None:
    text = B.format_table(B.backtest(_universe()))
    for key in B.STATS_KEYS:
        assert key in text
    assert "INSUFFICIENT_DATA: too few cases" in text


# ---- endpoint ---------------------------------------------------------------------------------


async def _seed_prices(
    db: AsyncSession, company_id: uuid.UUID, closes: list[float], end: date
) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"R47 patterns {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.DATA_PROVIDER,
    )
    db.add(source)
    await db.flush()
    first = end - timedelta(days=len(closes) - 1)
    for i, close in enumerate(closes):
        c = Decimal(str(round(close, 4)))
        db.add(
            DailyPrice(
                id=uuid.uuid4(),
                company_id=company_id,
                date=first + timedelta(days=i),
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1000,
                source_id=source.id,
            )
        )
    await db.flush()


async def test_endpoint_unknown_company_is_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/technical/companies/{uuid.uuid4()}/patterns")
    assert resp.status_code == 404


async def test_endpoint_requires_token(anon_client: AsyncClient) -> None:
    resp = await anon_client.get(f"/api/technical/companies/{uuid.uuid4()}/patterns")
    assert resp.status_code in (401, 403)


async def test_endpoint_short_history_is_insufficient_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    await _seed_prices(db_session, company.id, [10.0 + i * 0.1 for i in range(30)], date.today())
    resp = await client.get(f"/api/technical/companies/{company.id}/patterns")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["patterns"] == []
    assert "too little price history" in body["reason"]


async def test_endpoint_returns_recent_pattern_with_points_and_stats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    end = date.today()
    await _seed_prices(db_session, company.id, path(HS_TOP), end)
    resp = await client.get(f"/api/technical/companies/{company.id}/patterns")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "version",
        "as_of",
        "status",
        "patterns",
        "stats",
        "universe",
        "note",
        "overlap_note",
    }
    assert body["version"].startswith("patterns-")
    assert body["status"] == "OK"
    assert body["as_of"] == end.isoformat()
    assert body["note"] == (
        "patterns are drawn by fixed rules; odds are measured on EGX history, not a prediction"
    )
    hs = [p for p in body["patterns"] if p["pattern"] == HS_KEY]
    assert len(hs) == 1
    first = end - timedelta(days=len(path(HS_TOP)) - 1)
    assert hs[0]["confirmation_date"] == (first + timedelta(days=79)).isoformat()
    assert hs[0]["direction"] == "down"
    assert [pt["label"] for pt in hs[0]["points"]][2] == "head"
    assert hs[0]["points"][2]["price"] == "115.0000"
    assert hs[0]["target"]["price"] == "65.0000"
    assert "convention" in hs[0]["target"]["label"]
    # One stock in the universe: far under 30 cases, so the stats say so instead of a rate.
    cell = body["stats"][HS_KEY]["20"]
    assert cell["status"] == "INSUFFICIENT_DATA" and cell["value"] is None
    assert body["universe"]["companies"] == 1


async def test_endpoint_hides_patterns_older_than_a_year(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    # The pattern confirms on day 79; a flat tail of 400 days puts that over a year before as_of.
    closes = path(HS_TOP) + [80.0] * 400
    await _seed_prices(db_session, company.id, closes, date.today())
    body = (await client.get(f"/api/technical/companies/{company.id}/patterns")).json()
    assert body["status"] == "OK"
    assert not [p for p in body["patterns"] if p["pattern"] == HS_KEY]


async def test_universe_stats_are_cached_until_prices_change(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await make_company(db_session)
    await _seed_prices(db_session, company.id, path(HS_TOP), date.today())
    calls = 0
    real = B.backtest

    def counting(universe: B.Mapping[object, B.Series]) -> B.BacktestResult:
        nonlocal calls
        calls += 1
        return real(universe)

    monkeypatch.setattr(B, "backtest", counting)
    url = f"/api/technical/companies/{company.id}/patterns"
    assert (await client.get(url)).status_code == 200
    assert (await client.get(url)).status_code == 200
    assert calls == 1
    other = await make_company(db_session)
    await _seed_prices(db_session, other.id, path(HS_TOP), date.today())
    assert (await client.get(url)).status_code == 200
    assert calls == 2


# ---- forming odds (R47 P6) --------------------------------------------------------------------


def test_forming_stats_count_outcomes_and_measure_from_the_forming_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(B, "MIN_CASES", 1)
    drifts = path(HS_TOP[:-1] + [(80, 95), (160, 95)])  # expires without a break
    result = B.backtest({**_universe(), "D": series(drifts)})
    hs = result.forming[HS_KEY]
    assert (hs.n, hs.confirmed, hs.expired, hs.failed) == (4, 3, 1, 0)
    assert hs.expected == "down"
    # Measured from session 71 (known), not from the break at 79.
    expected = [c[71 + 20] / c[71] - 1 for c in (FALLS, RISES, DIPS_THEN_RISES, drifts)]
    assert hs.horizons[20].n == 4
    assert hs.horizons[20].median_return == pytest.approx(statistics.median(expected))
    d = hs.to_dict()
    assert d["status"] == "OK" and d["confirm_rate"] == 0.75
    assert d["up_break_share"] == 0.0
    assert set(d["horizons"]) == {"20", "60"}


def test_symmetrical_triangle_forming_has_no_hit_cells() -> None:
    result = B.backtest(_universe())
    sym = result.forming["symmetrical_triangle"]
    assert sym.expected is None and sym.horizons == {}
    assert sym.to_dict()["status"] == "INSUFFICIENT_DATA"
    assert set(result.forming) == set(B.PATTERN_TYPES)
    assert "forming" in B.format_table(result)


# ---- forming-pattern filter (R47 P7) ----------------------------------------------------------


async def _forming_and_complete(db: AsyncSession) -> tuple[str, str]:
    """One company with an inverse head and shoulders still forming, one whose top confirmed."""
    from tests.test_patterns import HS_INV

    forming = await make_company(db)
    done = await make_company(db)
    await _seed_prices(db, forming.id, path(HS_INV)[:76], date.today())
    await _seed_prices(db, done.id, path(HS_TOP), date.today())
    return forming.ticker, done.ticker


async def test_companies_filter_by_forming_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    forming, done = await _forming_and_complete(db_session)

    async def tickers(choice: str) -> set[str]:
        resp = await client.get("/api/companies", params={"forming": choice, "page_size": 200})
        assert resp.status_code == 200
        return {c["ticker"] for c in resp.json()["items"]}

    assert forming in await tickers("any") and done not in await tickers("any")
    assert forming in await tickers("up")
    # The same two 110 peaks also form a double top, so it is listed under "down" too.
    assert forming in await tickers("down") and done not in await tickers("down")
    bad = await client.get("/api/companies", params={"forming": "sideways"})
    assert bad.status_code == 422


async def test_overview_adds_forming_shapes_only_when_asked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    forming, done = await _forming_and_complete(db_session)
    plain = await client.get("/api/companies/overview", params={"tickers": f"{forming},{done}"})
    assert "forming" not in plain.json()["items"][forming]
    resp = await client.get(
        "/api/companies/overview", params={"tickers": f"{forming},{done}", "forming": "true"}
    )
    items = resp.json()["items"]
    shapes = [s for s in items[forming]["forming"] if s["pattern"] == "head_and_shoulders_inverse"]
    assert len(shapes) == 1
    assert shapes[0]["expected"] == "up"
    assert shapes[0]["confirm_above"] == "110.0000" and shapes[0]["confirm_below"] is None
    assert shapes[0]["sessions_left"] == 71 + 20 - 75
    assert items[done]["forming"] == []


def test_forming_matches_counts_a_symmetrical_triangle_as_any_only() -> None:
    from app.technical.patterns import FormingPattern, forming_matches

    def shape(expected: str | None) -> FormingPattern:
        return FormingPattern(
            "symmetrical_triangle" if expected is None else "double_bottom",
            expected,  # type: ignore[arg-type]
            date(2026, 1, 1),
            date(2026, 2, 1),
            date(2026, 2, 6),
            5,
            None,
            None,
            None,
            None,
            (),
            (),
        )

    assert forming_matches([shape(None)], "any")
    assert not forming_matches([shape(None)], "up") and not forming_matches([], "any")
    assert forming_matches([shape(None), shape("up")], "up")
