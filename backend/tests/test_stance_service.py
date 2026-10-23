"""Deterministic stance service (signal-rules-2.0).

The pure rule math is pinned in ``test_signal_rules.py``; these tests pin
the service wiring: missing engines lower confidence instead of biasing the
stance, BUY is reachable, Shariah is reported beside (never inside) the
score, the scenario-order guard, stop-level derivation, and the
limitations invariants (compliance copy first, stop copy last).

Engines are patched at the repository/service seam so the wiring is
isolated from the data layer and deterministic.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from app.api.stance import _liquidity
from app.models.market import DailyPrice, DataSource, DataSourceType
from app.models.screening import ScreeningEgxMembership
from app.signals.rules import Bar, Liquidity
from app.signals.stance import (
    COMPLIANCE_COPY,
    LEVELS_COPY,
    SIGNAL_RULES_VERSION,
    STOP_COPY,
    Stance,
    StanceService,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from httpx import AsyncClient

STUB_BULL_VALUE = "120"
STUB_BASE_VALUE = "100"
STUB_BEAR_VALUE = "80"


def _price_row(
    index: int, close: Decimal, low: Decimal | None = None, volume: int = 200_000
) -> Any:
    return SimpleNamespace(
        date=date(2026, 1, 1) + timedelta(days=index),
        close=close,
        high=close + Decimal(1),
        low=low if low is not None else close - Decimal(1),
        volume=volume,
    )


def _stmt_row(published: date) -> Any:
    return SimpleNamespace(published_date=published)


def _scenarios(
    bull: str | None = STUB_BULL_VALUE,
    base: str | None = STUB_BASE_VALUE,
    bear: str | None = STUB_BEAR_VALUE,
    status: str = "AVAILABLE",
) -> dict[str, dict[str, str | None]]:
    return {
        "bull": {"value": bull, "status": status, "reason": None},
        "base": {"value": base, "status": status, "reason": None},
        "bear": {"value": bear, "status": status, "reason": None},
    }


def _uptrend(n: int = 220, start: Decimal = Decimal(10)) -> list[Decimal]:
    """Steady 1% rise per session: every vote bullish except RSI (overbought, 0)."""
    out = [start]
    for _ in range(n - 1):
        out.append((out[-1] * Decimal("1.01")).quantize(Decimal("0.0001")))
    return out


def _downtrend(n: int = 220, start: Decimal = Decimal(80)) -> list[Decimal]:
    out = [start]
    for _ in range(n - 1):
        out.append((out[-1] * Decimal("0.99")).quantize(Decimal("0.0001")))
    return out


class EngineWorld:
    """Deterministic engine outputs injected at the repository seams."""

    def __init__(self) -> None:
        self.closes: Sequence[Decimal] = []
        self.low: Decimal | None = None
        self.volume = 200_000
        self.scenarios: dict[str, dict[str, str | None]] = _scenarios(
            None, None, None, status="INSUFFICIENT_DATA"
        )
        self.valuation_raises = False
        self.headline: float | None = None
        self.stmt_lines: Sequence[Any] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.repositories.price import PriceRepository
        from app.repositories.statements import StatementLineRepository
        from app.scores.service import ScoreService
        from app.valuation.service import FairValueService

        world = self

        async def get_prices(
            _self: Any, _company_id: UUID, *_args: Any, **_kw: Any
        ) -> tuple[Sequence[Any], int]:
            rows = [
                _price_row(i, close, world.low, world.volume)
                for i, close in enumerate(world.closes)
            ]
            return rows, len(rows)

        async def fair_value(
            _self: Any, _company_id: UUID, _inp: Any = None
        ) -> dict[str, Any]:
            if world.valuation_raises:
                raise RuntimeError("valuation engine down (simulated)")
            return {"scenarios": world.scenarios}

        async def latest_payload(_self: Any, _company_id: UUID) -> dict[str, Any]:
            assessment = (
                {"headline": {"value": world.headline}}
                if world.headline is not None
                else None
            )
            return {
                "company_id": str(_company_id),
                "assessment": assessment,
                "methodology_version": "m",
                "scale": {},
                "disclaimer": "d",
            }

        async def stmt_approved(_self: Any, _company_id: UUID) -> Sequence[Any]:
            return world.stmt_lines

        monkeypatch.setattr(PriceRepository, "get_prices", get_prices)
        monkeypatch.setattr(FairValueService, "fair_value", fair_value)
        monkeypatch.setattr(ScoreService, "latest_payload", latest_payload)
        monkeypatch.setattr(StatementLineRepository, "latest_approved", stmt_approved)


class TestStanceRules:
    async def test_technical_only_uptrend_is_buy_with_capped_confidence(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # v1 scored the missing engines as 0, so this case was "reduce".
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        assert result.stance == Stance.BUY
        assert result.score == Decimal("80.0")  # 4 of 5 votes bullish, RSI neutral
        assert result.coverage == Decimal("0.4")
        assert 0 < result.confidence <= 50
        assert "Technical-only stance: no fundamentals available yet." in result.limitations

    async def test_all_engines_bullish_is_buy_full_coverage(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        last = world.closes[-1]
        world.scenarios = _scenarios(
            bull=str(last * 3), base=str(last * 2), bear=str(last * Decimal("1.5"))
        )  # price below bear → valuation +1
        world.headline = 100.0
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        assert result.stance == Stance.BUY
        assert result.coverage == Decimal("1")
        # (40*0.8 + 35*1 + 25*1) / 100 = 92 → confidence 50 + 92/2 = 96
        assert result.score == Decimal("92.0")
        assert result.confidence == 96
        assert {r.engine for r in result.reasons} >= {"technical", "valuation", "score"}

    async def test_downtrend_overvalued_is_reduce(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _downtrend()
        last = world.closes[-1]
        world.scenarios = _scenarios(
            bull=str(last / 2), base=str(last / 3), bear=str(last / 4)
        )  # price above bull → valuation -1
        world.headline = 10.0
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.stance == Stance.REDUCE
        assert result.score is not None and result.score <= Decimal("-25")

    async def test_shariah_is_reported_not_scored(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.stance == Stance.BUY
        assert result.shariah["verdict"] == "NOT_SCREENED"
        assert result.shariah["egx33"] in {"unknown", "not_member"}
        assert all(r.engine != "shariah" for r in result.reasons)

    async def test_egx33_member_shown_in_shariah_block(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_session.add(
            ScreeningEgxMembership(
                company_id=test_company.id,
                methodology_version="test",
                member=True,
                review_cycle="2099-02",  # newest cycle in the database
                source="https://www.egx.com.eg/test",
            )
        )
        await db_session.flush()
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.shariah["egx33"] == "member"
        assert result.shariah["egx33_review_cycle"] == "2099-02"
        assert result.shariah["egx33_source"] == "https://www.egx.com.eg/test"
        assert result.shariah["verdict"] == "NOT_SCREENED"  # EGX33 never becomes our verdict

    async def test_stale_statements_cap_confidence(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.headline = 100.0
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=401))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert "Statement freshness 401 days (>400)." in result.limitations
        assert result.confidence <= 40
        assert result.statement_freshness == date.today() - timedelta(days=401)

    async def test_low_liquidity_flag_and_cap(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.volume = 10  # a few hundred EGP a day
        world.headline = 100.0
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.liquidity.low is True
        assert result.confidence <= 30
        assert any(line.startswith("LOW LIQUIDITY") for line in result.limitations)


class TestMissingInputs:
    async def test_no_inputs_is_hold_with_zero_confidence(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = [Decimal(90), Decimal(91)]  # < 20 closes: no technical
        world.valuation_raises = True
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        assert result.stance == Stance.HOLD
        assert result.confidence == 0
        assert result.score is None
        missing_line = next(
            line for line in result.limitations if line.startswith("Missing inputs:")
        )
        assert "technical indicators" in missing_line
        assert "valuation scenarios" in missing_line
        assert "investment score" in missing_line
        assert "Statement freshness unknown." in result.limitations

    async def test_compliance_first_stop_copy_last(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.limitations[0] == COMPLIANCE_COPY
        assert result.limitations[-1] == STOP_COPY
        assert LEVELS_COPY in result.limitations


class TestScenarioOrderGuard:
    async def test_inverted_scenarios_become_insufficient(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.scenarios = _scenarios(bull="80", base="100", bear="120")  # inverted
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        for key in ("bull", "base", "bear"):
            target = result.targets[key]
            assert target.status == "INSUFFICIENT_DATA"
            assert target.reason == "SCENARIO_ORDER"
            assert target.value == {"bull": "80", "base": "100", "bear": "120"}[key]
        missing_line = next(
            line for line in result.limitations if line.startswith("Missing inputs:")
        )
        assert "valuation scenarios" in missing_line


class TestTargetsAndStops:
    async def test_valuation_insufficient_targets_never_interpolated(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        for key in ("bull", "base", "bear"):
            target = result.targets[key]
            assert target.value is None
            assert target.status == "INSUFFICIENT_DATA"

    async def test_reference_levels_from_atr(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = [Decimal(10)] * 30  # high/low = close ± 1 → ATR 2
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        levels = result.reference_levels
        assert levels is not None
        assert (levels.entry, levels.upside, levels.downside) == (
            Decimal("10.00"), Decimal("14.00"), Decimal("7.00"),
        )
        assert result.stop_level.reason == "atr"
        assert Decimal(str(result.stop_level.value)) == Decimal("7.00")

    async def test_stop_from_entry_price(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(
            test_company.ticker, entry_price=Decimal("100"), stop_pct=Decimal("10")
        )
        assert result.stop_level.status == "AVAILABLE"
        assert Decimal(str(result.stop_level.value)) == Decimal("90")  # 100 * (1 - 10%)

    async def test_stop_from_range_low_without_atr(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = [Decimal(95), Decimal(92), Decimal(98)]  # too short for ATR
        world.low = Decimal(91)
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.reference_levels is None
        assert result.stop_level.reason == "range_low"
        assert Decimal(str(result.stop_level.value)) == Decimal("91")

    def test_range_low_uses_recent_bars_only(self) -> None:
        old = [Bar(close=Decimal(10), high=Decimal(10), low=Decimal(1))] * 50
        recent = [Bar(close=Decimal(10), high=Decimal(10), low=Decimal(9))] * 90
        stop = StanceService._stop_level(None, Decimal(10), None, [*old, *recent])
        assert stop.reason == "range_low"
        assert Decimal(str(stop.value)) == Decimal(9)

    async def test_stop_insufficient_without_prices(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.stop_level.status == "INSUFFICIENT_DATA"
        assert result.stop_level.reason == "no price range"

    async def test_result_carries_version_and_freshness(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.stmt_lines = [_stmt_row(date(2026, 5, 1))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.rules_version == SIGNAL_RULES_VERSION == "signal-rules-2.0"
        assert result.statement_freshness == date(2026, 5, 1)
        assert result.ticker == test_company.ticker
        assert result.company_id == str(test_company.id)


async def _seed_recent_prices(db_session: Any, company_id: uuid.UUID, days: int = 25) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"TEST_SRC_{uuid.uuid4().hex[:6]}",
        source_type=DataSourceType.SYNTHETIC,
    )
    db_session.add(source)
    await db_session.flush()
    today = date.today()
    for i in range(days):
        close = Decimal(10) + Decimal(i) / Decimal(10)
        db_session.add(
            DailyPrice(
                company_id=company_id,
                date=today - timedelta(days=days - 1 - i),
                open=close,
                high=close + Decimal(1),
                low=close - Decimal(1),
                close=close,
                volume=1_000_000_000,  # far above any real EGX name: ranks first
                source_id=source.id,
            )
        )
    await db_session.flush()


class TestStanceApi:
    async def test_unknown_company_404(
        self, client: AsyncClient, db_session: Any
    ) -> None:
        res = await client.get("/api/stance/companies/NOPE")
        assert res.status_code == 404

    @pytest.mark.parametrize("bad_pct", ["0", "95", "-5"])
    async def test_stop_pct_validation_422(
        self, client: AsyncClient, test_company: Any, db_session: Any, bad_pct: str
    ) -> None:
        res = await client.get(
            f"/api/stance/companies/{test_company.ticker}?stop_pct={bad_pct}"
        )
        assert res.status_code == 422

    async def test_stop_pct_90_boundary_ok(
        self, client: AsyncClient, test_company: Any, db_session: Any
    ) -> None:
        res = await client.get(
            f"/api/stance/companies/{test_company.ticker}?stop_pct=90"
        )
        assert res.status_code == 200

    async def test_response_shape(
        self, client: AsyncClient, test_company: Any, db_session: Any
    ) -> None:
        res = await client.get(f"/api/stance/companies/{test_company.ticker}")
        assert res.status_code == 200
        body = res.json()
        assert set(body) == {
            "company_id",
            "ticker",
            "stance",
            "confidence",
            "price",
            "score",
            "coverage",
            "reasons",
            "limitations",
            "targets",
            "stop_level",
            "reference_levels",
            "liquidity",
            "shariah",
            "statement_freshness",
            "rules_version",
            "as_of",
        }
        assert body["rules_version"] == "signal-rules-2.0"
        assert body["limitations"] and body["limitations"][0] == COMPLIANCE_COPY
        assert set(body["targets"]) == {"bull", "base", "bear"}
        assert set(body["shariah"]) == {
            "verdict", "methodology_version", "egx33", "egx33_review_cycle",
            "egx33_source", "note",
        }
        assert body["stance"] in {"buy", "hold", "reduce"}
        for reason in body["reasons"]:
            assert set(reason) == {"engine", "inputs", "text"}

    @pytest.mark.parametrize("query", ["page_size=200", "page_size=0", "shariah=other"])
    async def test_radar_validation_422(
        self, client: AsyncClient, db_session: Any, query: str
    ) -> None:
        res = await client.get(f"/api/stance/radar?{query}")
        assert res.status_code == 422

    async def test_radar_ranks_most_traded_first(
        self, client: AsyncClient, db_session: Any, test_company: Any
    ) -> None:
        await _seed_recent_prices(db_session, test_company.id)
        res = await client.get("/api/stance/radar?page_size=3")
        assert res.status_code == 200
        body = res.json()
        assert body["rules_version"] == "signal-rules-2.0"
        assert body["count"] == len(body["items"]) <= 3
        assert body["items"][0]["ticker"] == test_company.ticker
        for item in body["items"]:
            assert {
                "ticker", "company_id", "name", "stance", "confidence", "score",
                "price", "reference_levels", "low_liquidity", "shariah",
            } == set(item)
            assert item["stance"] in {None, "buy", "hold", "reduce"}
            if item["stance"] is None:
                assert item["confidence"] is None

    async def test_radar_egx33_filter(
        self, client: AsyncClient, db_session: Any, test_company: Any
    ) -> None:
        await _seed_recent_prices(db_session, test_company.id)
        db_session.add(
            ScreeningEgxMembership(
                company_id=test_company.id,
                methodology_version="test",
                member=True,
                review_cycle="2099-02",
                source="https://www.egx.com.eg/test",
            )
        )
        await db_session.flush()

        res = await client.get("/api/stance/radar?page_size=10&shariah=egx33")
        assert res.status_code == 200
        items = res.json()["items"]
        assert items[0]["ticker"] == test_company.ticker  # seeded as most traded
        assert all(item["shariah"]["egx33"] == "member" for item in items)

    def test_zero_value_traded_is_zero_not_null(self) -> None:
        payload = _liquidity(Liquidity(avg_value_traded=Decimal("0.00"), window=20, low=True))
        assert payload["avg_value_traded"] == "0.00"
        assert _liquidity(Liquidity(None, 20, None))["avg_value_traded"] is None
