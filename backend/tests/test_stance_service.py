"""Deterministic stance service (zborsa plan Task 9, signal-rules-1.0).

The rubric is spec-fixed (plan Task 9), so these tests pin the exact
points: technical ±20, valuation gap +25 / −20, score tier ±10,
Shariah −30, freshness −15; confidence cap 40 on ANY missing engine;
the scenario-order guard; stop-level derivation; and the limitations
invariants (compliance copy first, stop copy always present).

Engines are patched at the repository/service seam so the rubric math
is isolated from the data layer and deterministic.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from app.signals.stance import (
    COMPLIANCE_COPY,
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


def _price_row(index: int, close: Decimal, low: Decimal | None = None) -> Any:
    return SimpleNamespace(
        date=date(2026, 1, 1) + timedelta(days=index), close=close, low=low
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


class EngineWorld:
    """Deterministic engine outputs injected at the repository seams."""

    def __init__(self) -> None:
        self.closes: Sequence[Decimal] = []
        self.low: Decimal | None = None
        self.scenarios: dict[str, dict[str, str | None]] = _scenarios()
        self.valuation_raises = False
        self.headline: float | None = None
        self.screening_row: Any | None = None
        self.stmt_lines: Sequence[Any] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.repositories.price import PriceRepository
        from app.repositories.screening import ScreeningRepository
        from app.repositories.statements import StatementLineRepository
        from app.scores.service import ScoreService
        from app.valuation.service import FairValueService

        world = self

        async def get_prices(
            _self: Any, _company_id: UUID, *_args: Any, **_kw: Any
        ) -> tuple[Sequence[Any], int]:
            rows = [
                _price_row(i, close, world.low) for i, close in enumerate(world.closes)
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

        async def screening_result(
            _self: Any, _company_id: UUID, *_a: Any, **_k: Any
        ) -> Any:
            return world.screening_row

        async def stmt_approved(_self: Any, _company_id: UUID) -> Sequence[Any]:
            return world.stmt_lines

        monkeypatch.setattr(PriceRepository, "get_prices", get_prices)
        monkeypatch.setattr(FairValueService, "fair_value", fair_value)
        monkeypatch.setattr(ScoreService, "latest_payload", latest_payload)
        monkeypatch.setattr(ScreeningRepository, "get_screening_result", screening_result)
        monkeypatch.setattr(
            StatementLineRepository, "latest_approved", stmt_approved
        )


def _bull_close_run(price: Decimal) -> list[Decimal]:
    """50 closes: flat base, rising tail; last close is `price` (< base but
    above both SMAs, so technical +20 and valuation +25 both trigger)."""
    base = [Decimal(90)] * 30
    tail_lvl = price - Decimal(1)
    return [*base, *([tail_lvl] * 19), price]


class TestRubricGoldens:
    async def test_max_bullish_case_is_hold(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.low = Decimal(88)
        world.headline = 80.0  # +10 (STRONG band)
        world.screening_row = SimpleNamespace(is_compliant=True)  # 0
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]  # 0
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        engines = {r.engine: r.text for r in result.reasons}
        assert engines["technical"] == "Technical composite +20 from SMA20/SMA50 alignment."
        assert engines["valuation"] == "Valuation gap +25."
        assert engines["score"] == "Score tier +10."
        assert engines["shariah"] == "Shariah +0."
        assert engines["freshness"] == "Freshness +0."
        # total 55 < 60 (BUY floor) -> the plan's own rubric caps at HOLD
        assert result.stance == Stance.HOLD
        assert result.confidence == 100
        assert result.limitations == [COMPLIANCE_COPY, STOP_COPY]

    async def test_price_above_bear_is_reduce(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.low = Decimal(90)
        world.scenarios = _scenarios(bull="120", base="95", bear="80")
        world.headline = 50.0  # mid tier -> 0
        world.screening_row = SimpleNamespace(is_compliant=True)
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        # tech +20, price 99 > base 95 -> not below base and above bear -> -20
        engines = {r.engine: r.text for r in result.reasons}
        assert engines["valuation"] == "Valuation gap -20."
        # 20 - 20 = 0 < 35 -> REDUCE per the fixed mapping
        assert result.stance == Stance.REDUCE
        assert result.confidence == 50

    async def test_shariah_non_compliant_minus_30(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.headline = 80.0
        world.screening_row = SimpleNamespace(is_compliant=False)  # -30
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        engines = {r.engine: r.text for r in result.reasons}
        assert engines["shariah"] == "Shariah -30."
        # 20 + 25 + 10 - 30 = 25 < 35 -> REDUCE
        assert result.stance == Stance.REDUCE

    async def test_stale_statements_minus_15_and_limitation(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.headline = 80.0
        world.screening_row = SimpleNamespace(is_compliant=True)
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=401))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        engines = {r.engine: r.text for r in result.reasons}
        assert engines["freshness"] == "Freshness -15."
        assert f"Statement freshness {401} days (>400)." in result.limitations
        assert result.statement_freshness == date.today() - timedelta(days=401)


class TestMissingInputs:
    async def test_all_engines_missing_caps_confidence_at_40(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = [Decimal(90), Decimal(91)]  # < 20 closes: no technical
        world.valuation_raises = True
        world.headline = None
        world.screening_row = None
        world.stmt_lines = []
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        assert result.stance == Stance.REDUCE  # total 0
        assert result.confidence == 40  # capped from 50
        # fresh gaps join the limitations list
        missing_line = next(
            line for line in result.limitations if line.startswith("Missing inputs:")
        )
        assert "technical indicators" in missing_line
        assert "valuation scenarios" in missing_line
        assert "investment score" in missing_line
        assert "shariah screening" in missing_line
        assert "statement freshness" in missing_line
        assert "Statement freshness unknown." in result.limitations
        assert result.limitations[0] == COMPLIANCE_COPY
        assert STOP_COPY in result.limitations

    async def test_missing_limitation_precedes_stop_copy(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = []
        world.valuation_raises = True
        world.stmt_lines = []
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        # compliance copy is always first, stop copy is always last
        assert result.limitations[0] == COMPLIANCE_COPY
        assert result.limitations[-1] == STOP_COPY


class TestScenarioOrderGuard:
    async def test_inverted_scenarios_become_insufficient(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.scenarios = _scenarios(bull="80", base="100", bear="120")  # inverted
        world.headline = 80.0
        world.screening_row = SimpleNamespace(is_compliant=True)
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        for key in ("bull", "base", "bear"):
            target = result.targets[key]
            assert target.status == "INSUFFICIENT_DATA"
            assert target.reason == "SCENARIO_ORDER"
            assert target.value == {"bull": "80", "base": "100", "bear": "120"}[key]
        # the guard voids the valuation input -> confidence capped
        assert result.confidence == 40
        missing_line = next(
            line for line in result.limitations if line.startswith("Missing inputs:")
        )
        assert "valuation scenarios" in missing_line


class TestTargetsAndStops:
    async def test_valuation_insufficient_targets_never_interpolated(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _bull_close_run(Decimal(99))
        world.scenarios = _scenarios(bull=None, base=None, bear=None, status="INSUFFICIENT_DATA")
        world.headline = 80.0
        world.screening_row = SimpleNamespace(is_compliant=True)
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        for key in ("bull", "base", "bear"):
            target = result.targets[key]
            assert target.value is None
            assert target.status == "INSUFFICIENT_DATA"

    async def test_stop_from_entry_price(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = []
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(
            test_company.ticker, entry_price=Decimal("100"), stop_pct=Decimal("10")
        )
        assert result.stop_level.status == "AVAILABLE"
        assert Decimal(result.stop_level.value) == Decimal("90")  # 100 * (1 - 10%)

    async def test_stop_from_range_low_without_entry(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = [Decimal(95), Decimal(92), Decimal(98)]
        world.low = Decimal(91)
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.stop_level.status == "AVAILABLE"
        assert Decimal(result.stop_level.value) == Decimal("91")

    async def test_stop_insufficient_without_prices(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = []
        world.low = None
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.stop_level.status == "INSUFFICIENT_DATA"
        assert result.stop_level.reason == "no price range"

    async def test_result_carries_version_and_freshness(
        self,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = []
        world.stmt_lines = [_stmt_row(date(2026, 5, 1))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)
        assert result.rules_version == SIGNAL_RULES_VERSION
        assert result.statement_freshness == date(2026, 5, 1)
        assert result.ticker == test_company.ticker
        assert result.company_id == str(test_company.id)


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
            "reasons",
            "limitations",
            "targets",
            "stop_level",
            "statement_freshness",
            "rules_version",
            "as_of",
        }
        assert body["rules_version"] == "signal-rules-1.0"
        assert body["limitations"] and body["limitations"][0] == COMPLIANCE_COPY
        assert set(body["targets"]) == {"bull", "base", "bear"}
        assert body["stance"] in {"buy", "hold", "reduce"}
        for reason in body["reasons"]:
            assert set(reason) == {"engine", "inputs", "text"}

    async def test_radar_page_size_cap_422(
        self, client: AsyncClient, db_session: Any
    ) -> None:
        res = await client.get("/api/stance/radar?page_size=200")
        assert res.status_code == 422

    async def test_radar_shape(
        self, client: AsyncClient, db_session: Any
    ) -> None:
        res = await client.get("/api/stance/radar?page_size=50")
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == len(body["items"])
        assert body["count"] <= 50
        for item in body["items"]:
            assert {"ticker", "company_id", "stance", "confidence"} <= set(item)
            # compute never raises hard: stance exists or is null on failure
            assert item["stance"] in {None, "buy", "hold", "reduce"}
            if item["stance"] is None:
                assert item["confidence"] is None
