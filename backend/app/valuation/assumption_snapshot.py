"""Sourced valuation-assumption snapshot (R44 (b) + R45 M5) and its idempotent loader.

Every row is a literal with its source URL, title and ``as_of`` (the date the
figure is valid for, or the fetch date where the source gives none). Nothing here
is read by the engines directly: ``load_snapshot`` writes the rows into
``valuation_assumptions`` through ``record_assumption`` and the engines resolve
them from there, so staleness (120 days for yields, 400 for the rest) applies.

Versioning (by design): ``record_assumption`` writes each row under the *current*
``VALUATION_METHODOLOGY_VERSION`` and ``resolve_assumptions`` reads only that version,
so rows recorded under an older methodology version (e.g. 1.0 or 1.1) are ignored after
a bump. Re-run this loader after any ``VALUATION_METHODOLOGY_VERSION`` change.

The relative-multiple targets (``target_pe/pb/ps``) are deliberately absent: no
sourced Egypt multiples exist, so those legs stay INSUFFICIENT_DATA.

Sources: ``.workflow/decisions/R44-sectors-and-valuation-assumptions.md`` (b),
``.workflow/decisions/R45-owner-review-r43-ui.md`` (M5 follow-up),
``.workflow/research/long-run-cost-of-equity-2026-10.md``.

Usage:
    python -m app.valuation.assumption_snapshot    # record the snapshot (idempotent)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from app.valuation.assumptions import MARKET_SCOPE, record_assumption

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

FETCHED_ON = date(2026, 10, 24)
SNAPSHOT_VERSION = "assumptions-2026-10-24"

DAMODARAN_BLOG = "https://aswathdamodaran.blogspot.com/2026/07/country-risk-drivers-measures-and.html"
DAMODARAN_CTRYPREM = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctrypremJuly26.xlsx"
DAMODARAN_DIFF_INFLATION = (
    "https://pages.stern.nyu.edu/~adamodar/pc/blog/DiffInflationRiskfree26.xlsx"
)


@dataclass(frozen=True, slots=True)
class SnapshotRow:
    key: str
    value: Decimal
    source_url: str
    source_title: str
    as_of: date
    note: str


SNAPSHOT: tuple[SnapshotRow, ...] = (
    SnapshotRow(
        key="risk_free_rate",
        value=Decimal("0.24128"),
        source_url="https://www.cbe.org.eg/en/auctions/egp-t-bonds-fixed-coupon",
        source_title=(
            "CBE EGP fixed-coupon T-bond auction 19/10/2026: 3y weighted average accepted yield"
        ),
        as_of=date(2026, 10, 19),
        note=(
            "Longest sourced EGP tenor (no 5y/10y auction on the page). Coupon 23.981%. "
            f"Read {FETCHED_ON.isoformat()}."
        ),
    ),
    SnapshotRow(
        key="equity_risk_premium",
        value=Decimal("0.0420"),
        source_url=DAMODARAN_CTRYPREM,
        source_title="Damodaran country risk premiums, July 2026: mature-market ERP "
        "(S&P 500 implied 4.42% less 0.22% US default spread)",
        as_of=date(2026, 7, 1),
        note=(
            "Refreshes R44's 4.23% (5 Jan 2026) per R45 M5 follow-up; explicit-stage cost of "
            f"equity = 24.128% + 4.20% = 28.328%. Read {FETCHED_ON.isoformat()}."
        ),
    ),
    SnapshotRow(
        key="long_run_inflation",
        value=Decimal("0.054"),
        source_url="https://www.imf.org/external/datamapper/api/v1/PCPIPCH/EGY",
        source_title="IMF DataMapper (WEO) Egypt CPI inflation 2031",
        as_of=FETCHED_ON,
        note=(
            "2026-2031: 13.3, 14.8, 8.9, 6.5, 5.8, 5.4 %. WEO edition not stated by the "
            "API response; as_of is the fetch date. Terminal growth = this value "
            "(zero real growth)."
        ),
    ),
    SnapshotRow(
        key="nominal_gdp_growth",
        value=Decimal("0.1359"),
        source_url="https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/EGY",
        source_title=(
            "Egypt nominal GDP growth cap (owner ruling F13, candidate G1): geometric "
            "average 2027-2031 of (1 + IMF real GDP growth) x (1 + IMF CPI) - 1"
        ),
        as_of=FETCHED_ON,
        note=(
            "Real growth 2027-2031: 4.7, 5.0, 5.5, 4.8, 4.8 % "
            "(https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/EGY); CPI "
            "14.8, 8.9, 6.5, 5.8, 5.4 % (https://www.imf.org/external/datamapper/api/v1/"
            "PCPIPCH/EGY); nominal 20.20, 14.35, 12.36, 10.88, 10.46 %. CPI stands in for "
            "the GDP deflator (approximation); WEO edition not stated by the API. Caps the "
            "3-year revenue CAGR used as stage-1 growth. Research: "
            f".workflow/research/long-run-cost-of-equity-2026-10.md, fetched "
            f"{FETCHED_ON.isoformat()}."
        ),
    ),
    SnapshotRow(
        key="long_run_cost_of_equity",
        value=Decimal("0.1751"),
        source_url=DAMODARAN_BLOG,
        source_title="Long-run EGP cost of equity (owner ruling R45 M5, candidate B): "
        "default-free long-run EGP rate + Egypt default spread + mature ERP",
        as_of=FETCHED_ON,
        note=(
            "7.34% (= 1.0423 x 1.054 / 1.0235 - 1; Damodaran July 2026 USD rate 4.23% and "
            f"US inflation 2.35% [{DAMODARAN_DIFF_INFLATION}], IMF 2031 Egypt CPI 5.4%) + "
            f"5.97% (Egypt Caa1 default spread, {DAMODARAN_CTRYPREM}) + 4.20% (mature ERP). "
            "No country risk premium (same structure as the explicit stage). Default spread "
            "and ERP held constant in perpetuity. Research: "
            f".workflow/research/long-run-cost-of-equity-2026-10.md, fetched "
            f"{FETCHED_ON.isoformat()}."
        ),
    ),
)


async def load_snapshot(session: AsyncSession) -> int:
    """Record every snapshot row at market scope (idempotent). Flushes only."""
    for row in SNAPSHOT:
        await record_assumption(
            session,
            key=row.key,
            scope=MARKET_SCOPE,
            value=row.value,
            source_url=row.source_url,
            source_title=row.source_title,
            as_of=row.as_of,
            note=f"{SNAPSHOT_VERSION}: {row.note}",
        )
    return len(SNAPSHOT)


def main() -> int:  # pragma: no cover - CLI wrapper
    async def _run() -> int:
        from sqlalchemy import select

        from app.db.session import async_session_factory
        from app.models.market import Company
        from app.services.recompute import Engine, Trigger, recompute_many

        async with async_session_factory() as session:
            count = await load_snapshot(session)
            await session.commit()
            ids = list((await session.execute(select(Company.id))).scalars().all())
        print(f"Recorded {count} sourced valuation assumptions ({SNAPSHOT_VERSION}).")
        report = await recompute_many(
            ids, Trigger.ASSUMPTIONS,
            engines={Engine.FAIR_VALUE, Engine.SCORE, Engine.THESIS},
        )
        print(report.summary())
        return 0

    return asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
