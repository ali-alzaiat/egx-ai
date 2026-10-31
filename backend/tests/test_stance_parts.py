"""R51: stance reasons and limitations as codes plus parameters (display-only).

The English ``text`` / ``limitations`` stay as they are; ``parts`` and ``limitation_items`` let a
client write the same sentences in another language. Parameter values are the strings exactly as
the English text prints them. Numbers here are made up.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from tests.test_stance_service import (
    EngineWorld,
    _downtrend,
    _scenarios,
    _stmt_row,
    _uptrend,
)

from app.signals import stance_cache
from app.signals.rules import Bar, Component, technical_view
from app.signals.stance import (
    COMPLIANCE_COPY,
    LEVELS_COPY,
    STOP_COPY,
    Reason,
    StanceService,
)

if TYPE_CHECKING:
    import pytest
    from httpx import AsyncClient

D = Decimal


def _bars(closes: list[Decimal], volume: int | None = 100_000) -> list[Bar]:
    return [Bar(close=c, high=c + D("1"), low=c - D("1"), volume=volume) for c in closes]


def _by_code(components: list[Component]) -> dict[str, Component]:
    return {c.code: c for c in components}


def _zigzag(up: Decimal, down: Decimal, n: int = 60) -> list[Decimal]:
    """Alternating +up / -down moves, starting high enough to stay positive."""
    out = [D("100")]
    for i in range(n - 1):
        out.append(out[-1] + (up if i % 2 == 0 else -down))
    return out


class TestTechnicalParts:
    def test_uptrend_codes_and_params(self) -> None:
        view = technical_view(_bars(_uptrend()))
        assert view is not None
        by = _by_code(view.components)
        assert list(by) == ["trend", "long_trend", "rsi", "macd", "momentum"]
        assert by["trend"].params == {"side": "above", "ma": "SMA50"}
        assert by["trend"].detail == "Price above SMA50."
        assert by["long_trend"].params == {"side": "above"}
        assert by["long_trend"].detail == "SMA50 above SMA200."
        assert by["rsi"].params["state"] == "overbought"
        rsi_value = by["rsi"].params["value"]
        assert by["rsi"].detail == f"RSI {rsi_value} overbought: no momentum credit."
        assert by["macd"].params == {"side": "positive"}
        assert by["macd"].detail == "MACD line positive (EMA12 vs EMA26)."
        assert by["momentum"].params["direction"] == "up"
        assert by["momentum"].detail == f"Up {by['momentum'].params['pct']}% over 20 sessions."

    def test_downtrend_codes_and_params(self) -> None:
        view = technical_view(_bars(_downtrend()))
        assert view is not None
        by = _by_code(view.components)
        assert by["trend"].params == {"side": "below", "ma": "SMA50"}
        assert by["trend"].detail == "Price below SMA50."
        assert by["long_trend"].params == {"side": "below"}
        assert by["rsi"].params["state"] == "oversold"
        assert by["rsi"].detail == (
            f"RSI {by['rsi'].params['value']} oversold: no momentum penalty."
        )
        assert by["macd"].params == {"side": "negative"}
        momentum = by["momentum"]
        assert momentum.params["direction"] == "down"
        assert not momentum.params["pct"].startswith("-")  # unsigned for down
        assert momentum.detail == f"Down {momentum.params['pct']}% over 20 sessions."

    def test_short_history_trend_uses_sma20(self) -> None:
        view = technical_view(_bars(_uptrend(30)))
        assert view is not None
        by = _by_code(view.components)
        assert by["trend"].params["ma"] == "SMA20"
        assert by["trend"].detail == "Price above SMA20."
        assert "long_trend" not in by

    def test_price_at_the_average_is_at(self) -> None:
        view = technical_view(_bars([D("10")] * 60))
        assert view is not None
        by = _by_code(view.components)
        assert by["trend"].params == {"side": "at", "ma": "SMA50"}
        assert by["trend"].detail == "Price at SMA50."
        assert by["macd"].params == {"side": "flat"}
        assert by["momentum"].params == {"direction": "flat", "pct": "0.0"}
        assert by["momentum"].detail == "Flat (0.0%) over 20 sessions."

    def test_rsi_above_and_below_fifty(self) -> None:
        above = technical_view(_bars(_zigzag(D("1"), D("0.7"))))
        below = technical_view(_bars(_zigzag(D("0.7"), D("1"))))
        assert above is not None and below is not None
        rsi_up = _by_code(above.components)["rsi"]
        rsi_down = _by_code(below.components)["rsi"]
        assert rsi_up.params["state"] == "above_50"
        assert rsi_up.detail == f"RSI {rsi_up.params['value']} above 50."
        assert rsi_down.params["state"] == "below_50"
        assert rsi_down.detail == f"RSI {rsi_down.params['value']} below 50."

    def test_flat_momentum_keeps_its_sign(self) -> None:
        closes = [D("100")] * 60
        closes[-1] = D("95.4")  # -4.6% over 20 sessions, inside the +-5% band
        view = technical_view(_bars(closes))
        assert view is not None
        momentum = _by_code(view.components)["momentum"]
        assert momentum.params == {"direction": "flat", "pct": "-4.6"}
        assert momentum.detail == "Flat (-4.6%) over 20 sessions."

    def test_volume_note_has_a_code_and_ratio(self) -> None:
        bars = _bars(_uptrend(60))
        last = bars[-1]
        bars[-1] = Bar(close=last.close, high=last.high, low=last.low, volume=500_000)
        view = technical_view(bars)
        assert view is not None
        assert view.notes[0].code == "volume_unusual"
        assert view.notes[0].params == {"ratio": "5.0"}
        assert view.notes[0].text == "Unusual volume: 5.0x the 20-session average."


class TestServiceParts:
    @staticmethod
    def _codes(result: Any, engine: str) -> list[str]:
        return [p.code for r in result.reasons if r.engine == engine for p in r.parts]

    async def test_parts_align_with_the_text_sentences(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        last = world.closes[-1]
        world.scenarios = _scenarios(
            bull=str(last * 3), base=str(last * 2), bear=str(last * D("1.5"))
        )
        world.headline = 62.0
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        technical = next(r for r in result.reasons if r.engine == "technical")
        assert [p.code for p in technical.parts] == [
            "trend", "long_trend", "rsi", "macd", "momentum"
        ]
        scenario = next(r for r in result.reasons if r.engine == "valuation")
        assert scenario.text == "Price vs scenario range: sub-score +1."
        assert [(p.code, p.params) for p in scenario.parts] == [
            ("scenario_range", {"subscore": "+1"})
        ]
        score = next(r for r in result.reasons if r.engine == "score")
        assert score.text == "Investment score 62.0: sub-score +0.24."
        assert [(p.code, p.params) for p in score.parts] == [
            ("investment_score", {"headline": "62.0", "subscore": "+0.24"})
        ]

    async def test_fair_value_part_matches_the_text(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.fair_value = "1000"
        world.fv_confidence = "High"
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        reason = next(r for r in result.reasons if r.engine == "valuation")
        (part,) = reason.parts
        assert part.code == "fair_value_vs_market"
        assert set(part.params) == {"ratio", "market_ratio", "peers", "confidence", "subscore"}
        assert part.params["market_ratio"] == "0.50"
        assert part.params["peers"] == "25"
        assert part.params["confidence"] == "High"
        assert reason.text == (
            f"Price is {part.params['ratio']}x fair value vs a market median of "
            f"{part.params['market_ratio']}x ({part.params['peers']} companies, "
            f"{part.params['confidence']} confidence): sub-score {part.params['subscore']}."
        )

    async def test_volume_reason_carries_its_part(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from types import SimpleNamespace

        from app.repositories.price import PriceRepository

        world = EngineWorld()
        world.closes = _uptrend(60)
        world.install(monkeypatch)
        quiet = await StanceService(db_session).compute(test_company.ticker)
        assert self._codes(quiet, "volume") == []

        async def spiky(_self: Any, _company_id: Any, *_a: Any, **_kw: Any) -> Any:
            rows = [
                SimpleNamespace(
                    date=date(2026, 1, 1) + timedelta(days=i),
                    close=close,
                    high=close + D(1),
                    low=close - D(1),
                    volume=1_000_000 if i == len(world.closes) - 1 else 200_000,
                )
                for i, close in enumerate(world.closes)
            ]
            return rows, len(rows)

        monkeypatch.setattr(PriceRepository, "get_prices", spiky)
        result = await StanceService(db_session).compute(test_company.ticker)
        reason = next(r for r in result.reasons if r.engine == "volume")
        assert [(p.code, p.params) for p in reason.parts] == [
            ("volume_unusual", {"ratio": "5.0"})
        ]
        assert reason.text == "Unusual volume: 5.0x the 20-session average."

    async def test_limitation_items_align_with_limitations(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.headline = 62.0
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=10))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        assert len(result.limitation_items) == len(result.limitations)
        assert [i.text for i in result.limitation_items] == result.limitations
        codes = [i.code for i in result.limitation_items]
        assert codes[0] == "compliance_footer"
        assert codes[-1] == "stop_reference"
        assert "levels_band" in codes
        assert result.limitation_items[0].text == COMPLIANCE_COPY
        assert result.limitation_items[-1].text == STOP_COPY
        assert next(i for i in result.limitation_items if i.code == "levels_band").text == (
            LEVELS_COPY
        )

    async def test_technical_only_and_missing_inputs(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        items = {i.code: i for i in result.limitation_items}
        assert "technical_only" in items
        assert items["statement_freshness_unknown"].params == {}
        assert items["missing_inputs"].params == {"inputs": "valuation,score"}
        assert items["missing_inputs"].text.startswith("Missing inputs: valuation scenarios")
        assert [i.text for i in result.limitation_items] == result.limitations

    async def test_no_input_at_all(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = [D(90), D(91)]
        world.valuation_raises = True
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        items = {i.code: i for i in result.limitation_items}
        assert "no_engine_input" in items
        assert items["missing_inputs"].params == {"inputs": "technical,valuation,score"}
        assert "technical_only" not in items
        assert "levels_band" not in items
        assert [i.text for i in result.limitation_items] == result.limitations

    async def test_stale_statement_params(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.stmt_lines = [_stmt_row(date.today() - timedelta(days=401))]
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        item = next(i for i in result.limitation_items if i.code == "statement_stale")
        assert item.params == {"days": "401", "max_days": "400"}
        assert item.text == "Statement freshness 401 days (>400)."

    async def test_low_liquidity_params(
        self, db_session: Any, test_company: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.volume = 10
        world.install(monkeypatch)

        result = await StanceService(db_session).compute(test_company.ticker)

        item = next(i for i in result.limitation_items if i.code == "low_liquidity")
        assert item.params == {"min_egp": "500,000", "window": "20"}
        assert "EGP 500,000" in item.text
        assert "over 20 sessions" in item.text

    def test_reasons_built_without_parts_still_work(self) -> None:
        # Older callers / cached objects without parts: the default is an empty list.
        assert Reason(engine="technical", inputs={}, text="x").parts == []


class TestStanceApiParts:
    async def test_additive_fields_in_the_response(
        self,
        client: AsyncClient,
        db_session: Any,
        test_company: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        world = EngineWorld()
        world.closes = _uptrend()
        world.headline = 62.0
        world.install(monkeypatch)
        stance_cache.clear()

        res = await client.get(f"/api/stance/companies/{test_company.ticker}")

        assert res.status_code == 200
        body = res.json()
        technical = next(r for r in body["reasons"] if r["engine"] == "technical")
        assert set(technical) == {"engine", "inputs", "text", "parts"}
        assert technical["parts"][0] == {
            "code": "trend",
            "params": {"side": "above", "ma": "SMA50"},
        }
        score = next(r for r in body["reasons"] if r["engine"] == "score")
        assert score["parts"] == [
            {"code": "investment_score", "params": {"headline": "62.0", "subscore": "+0.24"}}
        ]
        assert len(body["limitation_items"]) == len(body["limitations"])
        assert [i["text"] for i in body["limitation_items"]] == body["limitations"]
        assert body["limitation_items"][0] == {
            "code": "compliance_footer",
            "params": {},
            "text": COMPLIANCE_COPY,
        }
        low = next(
            (i for i in body["limitation_items"] if i["code"] == "missing_inputs"), None
        )
        assert low is not None and low["params"] == {"inputs": "valuation"}
        stance_cache.clear()
