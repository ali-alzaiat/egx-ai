"""R50 data cross-checks: pure checks (synthetic values), service, API, tool and trigger."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import CARD_TOOLS, execute_tool
from app.dataquality import crosscheck as cc
from app.dataquality.constants import CROSSCHECK_METHODOLOGY_VERSION, STATUS_SEVERITY
from app.dataquality.crosscheck import LineInfo
from app.dataquality.crosscheck_service import CrosscheckService
from app.models.data_quality import DataCrosscheck
from app.statements.ontology import STATEMENT_LINES
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

D = Decimal
TODAY = date(2026, 10, 30)  # a Friday: not an EGX trading day


def line(
    code: str,
    value: str | None,
    *,
    period: str = "ANNUAL-2025",
    vendor: bool = False,
    page: bool = True,
    document: bool = True,
    xbrl: bool = False,
) -> LineInfo:
    return LineInfo(
        period=period,
        period_end=date(2025, 12, 31),
        code=code,
        value=D(value) if value is not None else None,
        vendor=vendor,
        has_document=document,
        has_page=page,
        xbrl=xbrl,
    )


# --- registry / helpers ------------------------------------------------------------------------


def test_methodology_version_and_identity_codes_exist_in_the_ontology() -> None:
    assert CROSSCHECK_METHODOLOGY_VERSION == "crosscheck-1.0"
    assert len(cc.available_identities()) == len(cc.IDENTITIES) == 3
    for identity in cc.IDENTITIES:
        codes = [identity.lhs, *(c for c, _ in (*identity.required, *identity.optional))]
        assert all(code in STATEMENT_LINES for code in codes)


def test_identity_with_an_unknown_ontology_code_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    bogus = cc.Identity("bogus", "total_assets", (("not_a_real_code", 1),))
    monkeypatch.setattr(cc, "IDENTITIES", (*cc.IDENTITIES, bogus))
    assert bogus not in cc.available_identities()


def test_worst_status_ranks_fail_over_warn_over_insufficient_over_pass() -> None:
    assert cc.worst_status(["pass", "insufficient_data"]) == "insufficient_data"
    assert cc.worst_status(["pass", "warn", "insufficient_data"]) == "warn"
    assert cc.worst_status(["warn", "fail", "pass"]) == "fail"
    assert cc.worst_status([]) == "pass"
    assert set(STATUS_SEVERITY) == {"pass", "warn", "fail", "insufficient_data"}


def test_relative_difference_zero_reference() -> None:
    assert cc.relative_difference(D(0), D(0)) == 0
    assert cc.relative_difference(D(0), D(5)) == 1
    assert cc.relative_difference(D(100), D(-100)) == 2


# --- provenance --------------------------------------------------------------------------------


def test_provenance_pass_warn_fail_and_missing() -> None:
    backed = [line(f"c{i}", "1") for i in range(8)]
    vendor = [line(f"v{i}", "1", vendor=True) for i in range(2)]
    assert cc.check_provenance(backed + vendor).status == "pass"  # 80% is not below 80%
    warn = cc.check_provenance(backed[:7] + vendor + [line("x", "1", vendor=True)] * 2)
    assert warn.status == "warn" and warn.evidence["filing_backed"] == 7
    vendor_only = cc.check_provenance(vendor)  # unconfirmed, not wrong (R50 B12)
    assert vendor_only.status == "warn" and vendor_only.evidence["vendor_only"] == 2
    unsourced = [line("u", "1", page=False, document=False)]
    fail = cc.check_provenance(unsourced)
    assert fail.status == "fail" and fail.evidence["other"] == 1
    assert cc.check_provenance([]).status == "insufficient_data"
    assert cc.check_provenance([line("a", None)]).status == "insufficient_data"


def test_provenance_needs_document_and_page_unless_xbrl() -> None:
    no_page = line("a", "1", page=False)
    no_doc = line("b", "1", document=False)
    xbrl = line("c", "1", page=False, xbrl=True)
    result = cc.check_provenance([no_page, no_doc, xbrl])
    assert result.evidence["filing_backed"] == 1 and result.evidence["other"] == 2


# --- cross-source ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vendor_value", "status", "band"),
    [
        ("1000", "pass", None),
        ("1009", "pass", None),  # 0.9% < 1%
        ("1010", "warn", "1_to_5_percent"),  # exactly 1%
        ("1050", "warn", "1_to_5_percent"),  # exactly 5%
        ("1051", "fail", "over_5_percent"),
        ("900", "fail", "over_5_percent"),
    ],
)
def test_cross_source_bands(vendor_value: str, status: str, band: str | None) -> None:
    result = cc.check_cross_source(
        [line("revenue", "1000")], [line("revenue", vendor_value, vendor=True)]
    )
    assert result.status == status
    assert [i["band"] for i in result.evidence["items"]] == ([band] if band else [])


def test_cross_source_evidence_never_contains_the_vendor_value() -> None:
    result = cc.check_cross_source(
        [line("revenue", "1000"), line("net_income", "200")],
        [line("revenue", "1234567.89", vendor=True), line("net_income", "206.5", vendor=True)],
    )
    assert result.status == "fail"
    blob = json.dumps(result.as_dict())
    assert "1234567" not in blob and "206.5" not in blob  # nor the exact difference
    assert result.evidence["items"][0] == {
        "period": "ANNUAL-2025",
        "ontology_code": "revenue",
        "band": "over_5_percent",
        "our_value": "1000",
    }
    assert set(result.evidence["items"][0]) == {"period", "ontology_code", "band", "our_value"}


def test_cross_source_needs_a_filing_line_and_a_vendor_line_of_the_same_period() -> None:
    vendor = [line("revenue", "5", vendor=True)]
    assert cc.check_cross_source([], vendor).status == "insufficient_data"
    other_period = [line("revenue", "5", period="ANNUAL-2024")]
    assert cc.check_cross_source(other_period, vendor).status == "insufficient_data"
    unbacked = [line("revenue", "5", page=False)]
    assert cc.check_cross_source(unbacked, vendor).status == "insufficient_data"
    zero = cc.check_cross_source([line("revenue", "0")], [line("revenue", "5", vendor=True)])
    assert zero.status == "fail"  # a zero filing value against a non-zero vendor value


# --- accounting identities ---------------------------------------------------------------------


def _balance(
    assets: str, liabilities: str = "900", equity: str = "1100", **extra: str
) -> list[LineInfo]:
    rows = [
        line("total_assets", assets),
        line("total_liabilities", liabilities),
        line("total_equity", equity),
    ]
    rows += [line(code, value) for code, value in extra.items()]
    return rows


@pytest.mark.parametrize(
    ("assets", "status"),
    [("2000", "pass"), ("2009", "pass"), ("2011", "warn"), ("2040", "warn"), ("2041", "fail")],
)
def test_balance_identity_bands(assets: str, status: str) -> None:
    result = cc.check_accounting_identities(_balance(assets))
    assert result.status == status
    assert result.evidence["evaluated"] == 1


def test_identity_adds_minority_interests_like_the_validator() -> None:
    rows = _balance("2100", minority_interests="100")
    assert cc.check_accounting_identities(rows).status == "pass"


def test_identity_missing_inputs_is_insufficient_never_pass() -> None:
    assert cc.check_accounting_identities([line("total_assets", "2000")]).status == (
        "insufficient_data"
    )
    assert cc.check_accounting_identities([]).status == "insufficient_data"
    assert cc.check_accounting_identities(_balance("2000", equity="1100")[:2]).status == (
        "insufficient_data"
    )


def test_identity_other_two_identities_and_zero_negative_values() -> None:
    rows = [
        line("total_assets", "2000"),
        line("current_assets", "800"),
        line("non_current_assets", "1200"),
        line("gross_profit", "400"),
        line("revenue", "1000"),
        line("cost_of_revenue", "600"),
    ]
    ok = cc.check_accounting_identities(rows)
    assert ok.status == "pass" and ok.evidence["evaluated"] == 2
    bad = cc.check_accounting_identities([*rows[:3], line("gross_profit", "100"), *rows[4:]])
    assert bad.status == "fail"
    assert bad.evidence["items"][0]["identity"] == "gross profit = revenue - cost of revenue"
    negative_equity = cc.check_accounting_identities(_balance("500", "900", "-400"))
    assert negative_equity.status == "pass"
    zeros = cc.check_accounting_identities(_balance("0", "0", "0"))
    assert zeros.status == "pass"


def test_vendor_backed_identity_shows_no_figures() -> None:
    rows = [
        line("total_assets", "2000", vendor=True),
        line("total_liabilities", "900", vendor=True),
        line("total_equity", "500", vendor=True),
    ]
    result = cc.check_accounting_identities(rows)
    assert result.status == "fail"
    item = result.evidence["items"][0]
    assert "left" not in item and "right" not in item and "relative_difference" in item
    filing = cc.check_accounting_identities(_balance("2000", equity="500"))
    assert filing.evidence["items"][0]["left"] == "2000"


# --- price sanity ------------------------------------------------------------------------------


def _bars(closes: list[str], start: date = date(2026, 9, 6)) -> list[tuple[date, D]]:
    """Closes on consecutive EGX trading days (Sun-Thu) from ``start`` (a Sunday)."""
    out: list[tuple[date, D]] = []
    day = start
    for raw in closes:
        while day.weekday() not in cc.EGX_TRADING_WEEKDAYS:
            day += timedelta(days=1)
        out.append((day, D(raw)))
        day += timedelta(days=1)
    return out


def test_trading_days_follow_the_egx_week() -> None:
    sunday = date(2026, 10, 25)
    assert cc.trading_days_between(sunday, date(2026, 10, 29)) == 4  # Mon..Thu
    assert cc.trading_days_between(date(2026, 10, 29), date(2026, 11, 1)) == 1  # Fri, Sat, Sun
    assert cc.trading_days_between(sunday, sunday) == 0


def test_price_sanity_passes_clean_series() -> None:
    result = cc.check_price_sanity(_bars(["10", "10.5", "10.2", "10.8", "11"]), TODAY)
    assert result.status == "pass" and result.evidence["closes_checked"] == 5


def test_price_sanity_fails_on_non_positive_close() -> None:
    result = cc.check_price_sanity(_bars(["10", "10.2", "0", "10.1"]), TODAY)
    assert result.status == "fail" and len(result.evidence["non_positive_closes"]) == 1


def test_price_sanity_limit_breach_and_split_exemption() -> None:
    breach = cc.check_price_sanity(_bars(["10", "10.5", "13", "13.1"]), TODAY)  # +23.8%
    assert breach.status == "fail" and breach.evidence["limit_breaches"][0]["change"] == "0.2381"
    at_limit = cc.check_price_sanity(_bars(["10", "12", "12.1"]), TODAY)  # exactly +20%
    assert at_limit.status == "pass"
    down = cc.check_price_sanity(_bars(["10", "12", "9", "9.1"]), TODAY)  # -25%
    assert down.status == "fail" and down.evidence["limit_breaches"][0]["change"] == "-0.2500"
    split = cc.check_price_sanity(_bars(["20", "21", "10.4", "10.5"]), TODAY)  # ~2:1
    assert split.status == "pass"
    assert len(split.evidence["possible_splits"]) == 1 and not split.evidence["limit_breaches"]


def test_price_sanity_gap_warns_and_skips_the_limit_across_it() -> None:
    bars = _bars(["10", "10.1"]) + _bars(["15", "15.1"], start=date(2026, 9, 27))
    result = cc.check_price_sanity(bars, TODAY)
    assert result.status == "warn" and result.evidence["gaps"][0]["missing_days"] > 5
    assert not result.evidence["limit_breaches"]  # +48% after the gap is not a limit breach


def test_price_sanity_short_or_old_series_is_insufficient() -> None:
    assert cc.check_price_sanity([], TODAY).status == "insufficient_data"
    assert cc.check_price_sanity(_bars(["10"]), TODAY).status == "insufficient_data"
    old = [(date(2024, 1, 2), D(10)), (date(2024, 1, 3), D(11))]
    assert cc.check_price_sanity(old, TODAY).status == "insufficient_data"
    future = [(TODAY + timedelta(days=3), D(10)), (TODAY + timedelta(days=4), D(11))]
    assert cc.check_price_sanity(future, TODAY).status == "insufficient_data"  # no look-ahead


# --- freshness ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("last_close", "status"),
    [
        (date(2026, 10, 29), "pass"),  # Thursday close; Friday is not a trading day
        (date(2026, 10, 26), "pass"),  # Mon 26 -> Tue, Wed, Thu = 3 trading days
        (date(2026, 10, 25), "warn"),  # 4 trading days
        (date(2026, 10, 14), "fail"),  # more than 10 trading days
    ],
)
def test_freshness_price_age_in_trading_days(last_close: date, status: str) -> None:
    result = cc.check_freshness(last_close, date(2026, 9, 30), TODAY)
    assert result.evidence["last_close"] == last_close.isoformat()
    assert result.status == status


@pytest.mark.parametrize(
    ("period_end", "behind", "status"),
    [
        (date(2026, 9, 30), 0, "pass"),
        (date(2026, 3, 31), 2, "pass"),  # 7 months -> 2 whole quarters
        (date(2026, 1, 31), 3, "warn"),  # 9 months
        (date(2025, 9, 30), 4, "warn"),  # 13 months -> 4 quarters, not more than 4
        (date(2025, 6, 30), 5, "fail"),  # 16 months
    ],
)
def test_freshness_period_age_in_quarters(period_end: date, behind: int, status: str) -> None:
    result = cc.check_freshness(date(2026, 10, 29), period_end, TODAY)
    assert result.evidence["quarters_behind"] == behind and result.status == status


def test_freshness_missing_inputs_are_insufficient_not_pass() -> None:
    assert cc.check_freshness(None, None, TODAY).status == "insufficient_data"
    fresh_price_only = cc.check_freshness(date(2026, 10, 29), None, TODAY)
    assert fresh_price_only.status == "insufficient_data"
    stale_price_no_period = cc.check_freshness(date(2026, 10, 1), None, TODAY)
    assert stale_price_no_period.status == "fail"  # the worst known status still shows
    assert cc.quarters_behind(date(2026, 12, 31), TODAY) == 0  # a future period end is not stale


# --- service, API and tool ---------------------------------------------------------------------


async def _seed_company(session: AsyncSession) -> tuple[uuid.UUID, str]:
    company = await make_company(session, sector="Banks")
    await seed_prices(session, company, bars=40)
    await seed_year(session, company, 2025, FULL_YEAR, tier="filing", page="12")
    # Vendor copy of two lines: revenue 6.2% off (fail band), net income equal (pass).
    await seed_year(
        session,
        company,
        2025,
        {"revenue": D("1062.37"), "net_income": D("200")},
        tier="vendor",
    )
    return company.id, company.ticker


async def test_service_run_stores_five_rows_and_reads_the_latest(
    db_session: AsyncSession,
) -> None:
    company_id, _ = await _seed_company(db_session)
    service = CrosscheckService(db_session)
    assert (await service.latest(company_id))["checks"] == []
    assert (await service.latest(company_id))["computed_at"] is None

    first = await service.run(company_id, now=datetime(2026, 10, 30, 8, tzinfo=UTC))
    assert [c["code"] for c in first["checks"]] == [
        "provenance",
        "cross_source",
        "accounting_identity",
        "price_sanity",
        "freshness",
    ]
    by_code = {c["code"]: c for c in first["checks"]}
    assert by_code["cross_source"]["status"] == "fail"
    assert by_code["cross_source"]["evidence"]["items"][0]["our_value"] == "1000.0000"
    assert "1062.37" not in json.dumps(first)  # the vendor value is not in the result
    assert by_code["accounting_identity"]["status"] == "pass"
    assert first["overall"] == "fail"

    second = await service.run(company_id, now=datetime(2026, 10, 31, 8, tzinfo=UTC))
    total = (
        await db_session.execute(
            select(func.count()).select_from(DataCrosscheck).where(
                DataCrosscheck.company_id == company_id
            )
        )
    ).scalar_one()
    assert total == 10  # append-only: two runs, five rows each
    latest = await service.latest(company_id)
    assert latest["computed_at"] == second["computed_at"] and len(latest["checks"]) == 5
    assert latest["methodology_version"] == "crosscheck-1.0"


async def test_crosscheck_api_get_run_and_404(client, db_session: AsyncSession) -> None:  # type: ignore[no-untyped-def]
    company_id, _ = await _seed_company(db_session)
    empty = await client.get(f"/api/data-quality/companies/{company_id}/crosschecks")
    assert empty.status_code == 200
    assert empty.json()["checks"] == [] and empty.json()["computed_at"] is None

    run = await client.post(f"/api/data-quality/companies/{company_id}/crosschecks/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["company_id"] == str(company_id) and body["overall"] == "fail"
    assert body["methodology_version"] == "crosscheck-1.0" and body["computed_at"]
    assert {"code", "status", "detail", "evidence"} <= set(body["checks"][0])
    assert "1062.37" not in run.text

    again = await client.get(f"/api/data-quality/companies/{company_id}/crosschecks")
    assert again.json()["checks"] == body["checks"]
    assert again.json()["computed_at"] == body["computed_at"]

    missing = uuid.uuid4()
    got = await client.get(f"/api/data-quality/companies/{missing}/crosschecks")
    assert got.status_code == 404
    assert (
        await client.post(f"/api/data-quality/companies/{missing}/crosschecks/run")
    ).status_code == 404


async def test_crosscheck_api_requires_the_token(anon_client) -> None:  # type: ignore[no-untyped-def]
    response = await anon_client.get(f"/api/data-quality/companies/{uuid.uuid4()}/crosschecks")
    assert response.status_code in (401, 403)


async def test_company_without_data_is_insufficient_everywhere(db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    result = await CrosscheckService(db_session).run(company.id)
    assert {c["status"] for c in result["checks"]} == {"insufficient_data"}
    assert result["overall"] == "insufficient_data"


async def test_data_check_tool_runs_once_then_reads_the_stored_run(
    db_session: AsyncSession,
) -> None:
    company_id, ticker = await _seed_company(db_session)
    first = await execute_tool(db_session, "data_check", {"ticker": ticker})
    assert first.ok, first.output
    out = first.output
    assert out["tool"] == "data_check" and out["ticker"] == ticker
    assert out["methodology_versions"] == {"crosscheck": "crosscheck-1.0"}
    assert out["data"]["overall"] == "fail" and len(out["data"]["checks"]) == 5
    assert "1062.37" not in json.dumps(out)  # no vendor figure reaches the model
    assert "company_id" not in json.dumps(out["data"])

    again = await execute_tool(db_session, "data_check", {"ticker": ticker})
    assert again.output["data"]["computed_at"] == out["data"]["computed_at"]  # not re-run
    rows = (
        await db_session.execute(
            select(func.count()).select_from(DataCrosscheck).where(
                DataCrosscheck.company_id == company_id
            )
        )
    ).scalar_one()
    assert rows == 5


def test_explain_card_data_check_is_wired() -> None:
    assert CARD_TOOLS["data_check"] == "data_check"
    from app.ai.prompts import EXPLAIN_PROMPTS

    assert "{ticker}" in EXPLAIN_PROMPTS["data_check"]
    assert set(CARD_TOOLS) == set(EXPLAIN_PROMPTS)


async def test_trigger_service_reruns_crosschecks_when_facts_land(
    db_session: AsyncSession,
) -> None:
    from app.continuous.trigger_service import TriggerService

    company_id, _ = await _seed_company(db_session)
    await TriggerService(db_session).on_facts_landed(company_id, [])
    latest = await CrosscheckService(db_session).latest(company_id)
    assert len(latest["checks"]) == 5 and latest["computed_at"] is not None


async def test_trigger_survives_a_crosscheck_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.continuous.trigger_service import TriggerService

    async def boom(self: CrosscheckService, company_id: uuid.UUID, now: datetime | None = None):  # type: ignore[no-untyped-def]
        raise RuntimeError("checks broke")

    monkeypatch.setattr(CrosscheckService, "run", boom)
    company = await make_company(db_session)
    result = await TriggerService(db_session).on_facts_landed(company.id, [])
    assert result.ledger_rows >= 1  # the trigger itself still completed
