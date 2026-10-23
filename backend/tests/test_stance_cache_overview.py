"""Stance cache (keyed by price date, TTL-bounded) and the Companies overview batch."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from app.signals import stance_cache
from app.signals.stance import StanceService

if TYPE_CHECKING:
    from httpx import AsyncClient

D1 = date(2026, 10, 21)
D2 = date(2026, 10, 22)


def _result(tag: str) -> Any:
    return SimpleNamespace(tag=tag)


class TestStanceCache:
    def test_hit_within_ttl(self) -> None:
        stance_cache.put("comi", D1, _result("a"), now=100.0)
        hit = stance_cache.get("COMI", D1, now=100.0 + stance_cache.CACHE_TTL_SECONDS)
        assert hit is not None and hit.tag == "a"

    def test_expires_after_ttl(self) -> None:
        stance_cache.put("COMI", D1, _result("a"), now=100.0)
        assert stance_cache.get("COMI", D1, now=100.1 + stance_cache.CACHE_TTL_SECONDS) is None

    def test_new_price_date_misses(self) -> None:
        stance_cache.put("COMI", D1, _result("a"), now=100.0)
        assert stance_cache.get("COMI", D2, now=100.0) is None

    def test_clear(self) -> None:
        stance_cache.put("COMI", D1, _result("a"), now=100.0)
        stance_cache.clear()
        assert stance_cache.get("COMI", D1, now=100.0) is None

    async def test_compute_cached_computes_once_per_price_date(
        self, db_session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        async def fake_compute(_self: Any, ticker: str, **_kw: Any) -> Any:
            calls.append(ticker)
            return _result(f"{ticker}-{len(calls)}")

        monkeypatch.setattr(StanceService, "compute", fake_compute)
        service = StanceService(db_session)
        first = await service.compute_cached("COMI", D1)
        again = await service.compute_cached("COMI", D1)
        newer = await service.compute_cached("COMI", D2)
        assert first is again
        assert newer is not first
        assert calls == ["COMI", "COMI"]


class TestOverviewEndpoint:
    async def test_one_request_for_the_page(
        self, client: AsyncClient, test_company: Any
    ) -> None:
        res = await client.get(
            f"/api/companies/overview?tickers={test_company.ticker.lower()},NOPE"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["missing"] == ["NOPE"]
        row = body["items"][test_company.ticker]
        assert set(row) == {"company_id", "stance", "latest_price", "gross_margin"}
        assert row["company_id"] == str(test_company.id)
        # No prices or statements for this company: nulls, never zeros.
        assert row["latest_price"] is None
        assert row["stance"] is None or row["stance"]["stance"] in {"buy", "hold", "reduce"}

    @pytest.mark.parametrize("tickers", ["", " , ", ",".join(f"T{i}" for i in range(51))])
    async def test_ticker_count_is_bounded(self, client: AsyncClient, tickers: str) -> None:
        res = await client.get(f"/api/companies/overview?tickers={tickers}")
        assert res.status_code == 422

    async def test_not_swallowed_by_company_id_route(self, client: AsyncClient) -> None:
        res = await client.get("/api/companies/overview")
        assert res.status_code == 422  # missing tickers, not "invalid UUID"
        assert "tickers" in res.text
