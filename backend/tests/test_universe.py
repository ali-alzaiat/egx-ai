"""Tests for universe discovery, snapshot provenance and provider metadata."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingestion.egx.provider import _free_float_ratio
from app.ingestion.egx.universe import (
    CompositeUniverseSource,
    PublicListingUniverseSource,
    SnapshotFileUniverseSource,
    UniverseDiscoveryError,
    UniverseEntry,
    UniverseSnapshot,
    _normalise,
    create_universe_source,
)

LISTING_HTML = """
<html><body>
<table id="main-table">
  <thead><tr><th>Symbol</th><th>Company Name</th><th>Price</th></tr></thead>
  <tbody>
    <tr><td>SDTI</td><td>SDS Industries</td><td>52.10</td></tr>
    <tr><td>AXPH</td><td>Egyptian Pharma</td><td>31.40</td></tr>
    <tr><td>COMI</td><td>Commercial International Bank</td><td>70.00</td></tr>
  </tbody>
</table>
</body></html>
"""


class TestNormalise:
    def test_uppercases_and_sorts(self):
        entries = _normalise([("zzz", "Zed"), ("aaa", "Alpha")])
        assert [e.ticker for e in entries] == ["AAA", "ZZZ"]

    def test_drops_invalid_tickers(self):
        assert _normalise([("", "No ticker"), ("!!!", "Bad")]) == ()

    def test_falls_back_to_ticker_when_name_missing(self):
        entries = _normalise([("SDTI", "   ")])
        assert entries[0].name == "SDTI"

    def test_deduplicates(self):
        entries = _normalise([("SDTI", "First"), ("SDTI", "Second")])
        assert len(entries) == 1

    def test_prefers_a_real_name_over_ticker_placeholder(self):
        """A later row with a real name must replace a ticker-only placeholder."""
        entries = _normalise([("SDTI", ""), ("SDTI", "SDS Industries")])
        assert entries[0].name == "SDS Industries"


class TestListingParse:
    def test_parses_symbol_and_name(self):
        entries = PublicListingUniverseSource().parse(LISTING_HTML)
        assert [e.ticker for e in entries] == ["AXPH", "COMI", "SDTI"]
        assert entries[1].name == "Commercial International Bank"
        assert entries[2].name == "SDS Industries"

    def test_raises_when_no_table(self):
        with pytest.raises(UniverseDiscoveryError, match="no table"):
            PublicListingUniverseSource().parse("<html><body>nope</body></html>")

    def test_raises_on_unexpected_columns(self):
        html = "<table><tr><th>Foo</th><th>Bar</th></tr><tr><td>1</td><td>2</td></tr></table>"
        with pytest.raises(UniverseDiscoveryError, match="missing expected columns"):
            PublicListingUniverseSource().parse(html)

    def test_skips_rows_with_missing_cells(self):
        html = """
        <table><tr><th>Symbol</th><th>Company Name</th></tr>
        <tr><td>SDTI</td></tr></table>
        """
        assert PublicListingUniverseSource().parse(html) == ()


class TestSnapshotRoundTrip:
    def _snapshot(self) -> UniverseSnapshot:
        return UniverseSnapshot(
            entries=(
                UniverseEntry(ticker="AXPH", name="Egyptian Pharma"),
                UniverseEntry(ticker="SDTI", name="SDS Industries"),
            ),
            source_name="STOCKANALYSIS_EGX_LISTING",
            source_url="https://stockanalysis.com/list/egyptian-stock-exchange/",
            fetched_at=datetime(2026, 9, 26, 10, 0, tzinfo=UTC),
        )

    def test_round_trip_preserves_entries(self, tmp_path: Path):
        source = SnapshotFileUniverseSource(path=tmp_path / "u.csv")
        source.write(self._snapshot())
        restored = SnapshotFileUniverseSource(path=tmp_path / "u.csv").read()
        assert [e.ticker for e in restored.entries] == ["AXPH", "SDTI"]
        assert restored.entries[1].name == "SDS Industries"

    def test_round_trip_preserves_provenance(self, tmp_path: Path):
        source = SnapshotFileUniverseSource(path=tmp_path / "u.csv")
        source.write(self._snapshot())
        restored = SnapshotFileUniverseSource(path=tmp_path / "u.csv").read()
        assert restored.source_url == self._snapshot().source_url
        assert restored.source_name == "STOCKANALYSIS_EGX_LISTING"
        assert restored.fetched_at == datetime(2026, 9, 26, 10, 0, tzinfo=UTC)

    def test_snapshot_is_marked_as_fallback(self, tmp_path: Path):
        source = SnapshotFileUniverseSource(path=tmp_path / "u.csv")
        source.write(self._snapshot())
        assert SnapshotFileUniverseSource(path=tmp_path / "u.csv").read().is_fallback is True

    def test_committed_snapshot_is_marked_as_fallback(self):
        """The repo's offline snapshot must never look like live data."""
        snapshot = SnapshotFileUniverseSource().read()
        assert snapshot.is_fallback is True
        assert snapshot.source_url, "snapshot must record where it came from"
        assert snapshot.fetched_at is not None
        assert len(snapshot) > 100, "EGX has ~220 active equities"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(UniverseDiscoveryError, match="no universe snapshot"):
            SnapshotFileUniverseSource(path=tmp_path / "missing.csv").read()

    def test_empty_file_raises(self, tmp_path: Path):
        path = tmp_path / "u.csv"
        path.write_text("# source: x\n# source_url: y\n")
        with pytest.raises(UniverseDiscoveryError, match="is empty"):
            SnapshotFileUniverseSource(path=path).read()


class TestComposite:
    class _Stub:
        def __init__(self, name: str, entries: tuple[UniverseEntry, ...] | None = None,
                     error: Exception | None = None) -> None:
            self.name = name
            self._entries = entries or ()
            self._error = error

        async def fetch(self) -> UniverseSnapshot:
            if self._error:
                raise self._error
            return UniverseSnapshot(
                entries=self._entries,
                source_name=self.name,
                source_url="https://example.com",
                fetched_at=datetime.now(UTC),
            )

    async def test_prefers_first_working_source(self):
        live = self._Stub("LIVE", (UniverseEntry("A", "Alpha"),))
        snapshot = await CompositeUniverseSource([live]).fetch()
        assert [e.ticker for e in snapshot.entries] == ["A"]

    async def test_falls_back_when_live_fails(self):
        live = self._Stub("LIVE", error=RuntimeError("404"))
        backup = self._Stub("BACKUP", (UniverseEntry("B", "Beta"),))
        snapshot = await CompositeUniverseSource([live, backup]).fetch()
        assert [e.ticker for e in snapshot.entries] == ["B"]

    async def test_falls_back_when_live_returns_empty(self):
        live = self._Stub("LIVE", ())
        backup = self._Stub("BACKUP", (UniverseEntry("B", "Beta"),))
        snapshot = await CompositeUniverseSource([live, backup]).fetch()
        assert [e.ticker for e in snapshot.entries] == ["B"]

    async def test_raises_when_everything_fails(self):
        sources = [self._Stub("A", error=RuntimeError("x")), self._Stub("B", ())]
        with pytest.raises(UniverseDiscoveryError, match="no universe source succeeded"):
            await CompositeUniverseSource(sources).fetch()

    def test_requires_at_least_one_source(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeUniverseSource([])


class TestCreateUniverseSource:
    def test_offline_returns_snapshot(self):
        assert isinstance(create_universe_source(use_live=False), SnapshotFileUniverseSource)

    def test_live_returns_composite_with_snapshot_fallback(self):
        source = create_universe_source(use_live=True)
        assert isinstance(source, CompositeUniverseSource)
        assert len(source.sources) == 2
        assert isinstance(source.sources[-1], SnapshotFileUniverseSource)


class TestFreeFloatRatio:
    def test_ratio_of_float_to_outstanding(self):
        assert _free_float_ratio(Decimal("500000000"), Decimal("1000000000")) == Decimal(
            "0.5000"
        )

    def test_fully_floated_is_one(self):
        assert _free_float_ratio(Decimal("1000"), Decimal("1000")) == Decimal("1.0000")

    def test_missing_float_returns_none(self):
        assert _free_float_ratio(None, Decimal("1000")) is None

    def test_missing_shares_returns_none(self):
        assert _free_float_ratio(Decimal("500"), None) is None

    def test_zero_shares_returns_none(self):
        assert _free_float_ratio(Decimal("500"), Decimal("0")) is None

    def test_ratio_above_one_rejected(self):
        """Yahoo sometimes reports float > outstanding; that is not a fraction."""
        assert _free_float_ratio(Decimal("2000"), Decimal("1000")) is None

    def test_negative_rejected(self):
        assert _free_float_ratio(Decimal("-5"), Decimal("1000")) is None

    def test_result_fits_numeric_10_4(self):
        """Column is Numeric(10, 4); a raw share count would overflow it."""
        ratio = _free_float_ratio(Decimal("987654321000"), Decimal("1000000000000"))
        assert ratio == Decimal("0.9877")
