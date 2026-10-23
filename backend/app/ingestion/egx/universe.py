"""Discovery of the full EGX listed-company universe.

The universe is *discovered*, never hardcoded. A dated CSV snapshot is kept in
``data/`` as an auditable offline fallback; the live source is preferred and its
provenance (URL + fetch time) is always recorded.

Adding a second source (official EGX feed, a paid vendor) only means
implementing :class:`UniverseSource`.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")

DEFAULT_LISTING_URL = "https://stockanalysis.com/list/egyptian-stock-exchange/"
DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parents[4] / "data" / "egx_universe.csv"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True, slots=True)
class UniverseEntry:
    """A single listed company as reported by a universe source."""

    ticker: str
    name: str


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    """A point-in-time view of the listed universe plus its provenance."""

    entries: tuple[UniverseEntry, ...]
    source_name: str
    source_url: str
    fetched_at: datetime
    is_fallback: bool = False
    notes: str = ""

    def tickers(self) -> tuple[str, ...]:
        return tuple(e.ticker for e in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


class UniverseDiscoveryError(RuntimeError):
    """Raised when no universe source could produce a usable snapshot."""


class UniverseSource(Protocol):
    """Protocol for anything that can enumerate the listed universe."""

    name: str

    async def fetch(self) -> UniverseSnapshot: ...


def _normalise(rows: Iterable[tuple[str, str]]) -> tuple[UniverseEntry, ...]:
    """Clean, uppercase and de-duplicate raw ticker/name pairs.

    Rows with an unusable ticker are dropped rather than guessed at.
    """
    seen: dict[str, UniverseEntry] = {}
    for raw_ticker, raw_name in rows:
        if not raw_ticker:
            continue
        ticker = raw_ticker.strip().upper()
        if not TICKER_RE.match(ticker):
            continue
        name = (raw_name or "").strip() or ticker
        if ticker not in seen or seen[ticker].name == ticker:
            seen[ticker] = UniverseEntry(ticker=ticker, name=name)
    return tuple(sorted(seen.values(), key=lambda e: e.ticker))


class PublicListingUniverseSource:
    """Discover the universe from a public listing page.

    Currently stockanalysis.com's EGX listing table, which reports the exchange
    as "EGX" and enumerates every actively traded equity.
    """

    name = "STOCKANALYSIS_EGX_LISTING"

    def __init__(
        self,
        url: str = DEFAULT_LISTING_URL,
        timeout: float = 30.0,
    ) -> None:
        self.url = url
        self.timeout = timeout

    def parse(self, html: str) -> tuple[UniverseEntry, ...]:
        """Extract (ticker, name) pairs from the listing page HTML."""
        from bs4 import BeautifulSoup  # imported lazily: only needed for live fetch

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="main-table") or soup.find("table")
        if table is None:
            raise UniverseDiscoveryError("listing page contained no table")

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        try:
            sym_idx = headers.index("symbol")
            name_idx = headers.index("company name")
        except ValueError as exc:
            raise UniverseDiscoveryError(
                f"listing table missing expected columns, found {headers}"
            ) from exc

        rows: list[tuple[str, str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) <= max(sym_idx, name_idx):
                continue
            symbol = cells[sym_idx].get_text(strip=True)
            if not symbol or not TICKER_RE.match(symbol.upper()):
                continue
            rows.append((symbol, cells[name_idx].get_text(strip=True)))
        return _normalise(rows)

    async def fetch(self) -> UniverseSnapshot:
        import anyio

        def _get() -> str:
            import requests  # imported lazily: only needed for a live fetch, not at app start

            response = requests.get(self.url, headers=BROWSER_HEADERS, timeout=self.timeout)
            response.raise_for_status()
            return response.text

        html = await anyio.to_thread.run_sync(_get)
        entries = self.parse(html)
        if not entries:
            raise UniverseDiscoveryError("listing page produced no entries")
        logger.info("Discovered %d EGX companies from %s", len(entries), self.url)
        return UniverseSnapshot(
            entries=entries,
            source_name=self.name,
            source_url=self.url,
            fetched_at=datetime.now(UTC),
        )


@dataclass
class SnapshotFileUniverseSource:
    """Read a previously captured universe snapshot from disk.

    The file keeps a provenance header so an offline snapshot is never
    mistaken for live data.
    """

    path: Path = DEFAULT_SNAPSHOT_PATH
    name: str = "EGX_UNIVERSE_SNAPSHOT"
    _cache: UniverseSnapshot | None = field(default=None, init=False, repr=False)

    def write(self, snapshot: UniverseSnapshot) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        buffer.write(f"# source: {snapshot.source_name}\n")
        buffer.write(f"# source_url: {snapshot.source_url}\n")
        buffer.write(f"# fetched_at: {snapshot.fetched_at.isoformat()}\n")
        buffer.write(f"# count: {len(snapshot.entries)}\n")
        writer = csv.writer(buffer)
        writer.writerow(["ticker", "name"])
        writer.writerows((e.ticker, e.name) for e in snapshot.entries)
        self.path.write_text(buffer.getvalue(), encoding="utf-8")
        return self.path

    def read(self) -> UniverseSnapshot:
        if self._cache is not None:
            return self._cache
        if not self.path.exists():
            raise UniverseDiscoveryError(f"no universe snapshot at {self.path}")

        meta: dict[str, str] = {}
        data_lines: list[str] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                key, _, value = line[1:].partition(":")
                meta[key.strip()] = value.strip()
            elif line.strip():
                data_lines.append(line)

        entries = _normalise(
            (row["ticker"], row["name"]) for row in csv.DictReader(data_lines)
        )
        if not entries:
            raise UniverseDiscoveryError(f"universe snapshot at {self.path} is empty")

        fetched_raw = meta.get("fetched_at")
        try:
            fetched_at = datetime.fromisoformat(fetched_raw) if fetched_raw else datetime.now(UTC)
        except ValueError:
            fetched_at = datetime.now(UTC)

        self._cache = UniverseSnapshot(
            entries=entries,
            source_name=meta.get("source", self.name),
            source_url=meta.get("source_url", ""),
            fetched_at=fetched_at,
            is_fallback=True,
            notes="offline snapshot",
        )
        return self._cache

    async def fetch(self) -> UniverseSnapshot:
        return self.read()


class CompositeUniverseSource:
    """Try each source in order and return the first usable snapshot."""

    def __init__(self, sources: Sequence[UniverseSource]) -> None:
        if not sources:
            raise ValueError("at least one universe source is required")
        self.sources = list(sources)
        self.name = "+".join(s.name for s in self.sources)

    async def fetch(self) -> UniverseSnapshot:
        errors: list[str] = []
        for source in self.sources:
            try:
                snapshot = await source.fetch()
            except Exception as exc:  # noqa: BLE001 - want to try the next source
                logger.warning("Universe source %s failed: %s", source.name, exc)
                errors.append(f"{source.name}: {exc}")
                continue
            if snapshot.entries:
                return snapshot
            errors.append(f"{source.name}: empty result")
        raise UniverseDiscoveryError("no universe source succeeded: " + "; ".join(errors))


def create_universe_source(
    use_live: bool = True,
    snapshot_path: Path | None = None,
) -> UniverseSource:
    """Build the default universe source chain."""
    snapshot = SnapshotFileUniverseSource(
        path=snapshot_path or DEFAULT_SNAPSHOT_PATH,
    )
    if not use_live:
        return snapshot
    return CompositeUniverseSource([PublicListingUniverseSource(), snapshot])
