"""Real-data sanity check for the stance radar (QA gate, CONTRACT step 7).

Passing tests prove the code matches the spec, not that its output makes sense.
This runs the stance engine over the most-traded companies in the configured
database and reports the stance distribution next to market breadth. When one
stance covers more than ``CONCENTRATION_THRESHOLD`` of names, the QA handoff
must explain why (e.g. a broad sell-off) — or treat it as a defect.

Usage:
    python -m app.signals.sanity                 # report
    python -m app.signals.sanity --strict        # exit 1 when concentrated
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
from dataclasses import dataclass
from decimal import Decimal

CONCENTRATION_THRESHOLD = Decimal("0.8")
BREADTH_SESSIONS = 20


@dataclass(frozen=True)
class DistributionReport:
    total: int
    shares: dict[str, Decimal]
    dominant: str | None
    concentrated: bool


def distribution_report(
    counts: dict[str, int], threshold: Decimal = CONCENTRATION_THRESHOLD
) -> DistributionReport:
    """Share of each outcome and whether one outcome exceeds ``threshold``."""
    total = sum(counts.values())
    if total == 0:
        return DistributionReport(total=0, shares={}, dominant=None, concentrated=False)
    shares = {k: Decimal(v) / Decimal(total) for k, v in counts.items()}
    dominant = max(shares, key=lambda k: shares[k])
    return DistributionReport(
        total=total,
        shares=shares,
        dominant=dominant,
        concentrated=shares[dominant] > threshold,
    )


async def _run(limit: int) -> tuple[DistributionReport, list[Decimal]]:
    from collections import Counter

    from app.db.session import async_session_factory
    from app.repositories.company import CompanyRepository
    from app.repositories.price import PriceRepository
    from app.signals.stance import StanceService

    async with async_session_factory() as session:
        prices = PriceRepository(session)
        ranked = await prices.most_traded_company_ids(limit)
        companies = {c.id: c for c in await CompanyRepository(session).list_by_ids(ranked)}
        service = StanceService(session)
        counts: Counter[str] = Counter()
        changes: list[Decimal] = []
        for company_id in ranked:
            company = companies.get(company_id)
            if company is None:
                continue
            result = await service.compute(company.ticker)
            counts[result.stance.value] += 1
            rows, _ = await prices.get_prices(company_id, page_size=BREADTH_SESSIONS + 1)
            closes = [r.close for r in sorted(rows, key=lambda r: r.date)]
            if len(closes) == BREADTH_SESSIONS + 1 and closes[0] > 0:
                changes.append(closes[-1] / closes[0] - Decimal("1"))
    return distribution_report(dict(counts)), changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=50, help="most-traded companies to check")
    parser.add_argument("--strict", action="store_true", help="exit 1 when concentrated")
    args = parser.parse_args()

    report, changes = asyncio.run(_run(args.limit))
    print(f"Stance distribution over {report.total} most-traded companies:")
    for stance, share in sorted(report.shares.items()):
        print(f"  {stance:<7} {share * 100:5.1f}%")
    if changes:
        falling = sum(1 for c in changes if c < 0) / len(changes)
        median = statistics.median(changes)
        print(
            f"Market breadth ({BREADTH_SESSIONS} sessions): median change "
            f"{median * 100:+.1f}%, {falling * 100:.0f}% of names falling"
        )
    if report.concentrated:
        print(
            f"CONCENTRATED: '{report.dominant}' exceeds "
            f"{CONCENTRATION_THRESHOLD * 100:.0f}% - explain it in the QA handoff "
            "(does market breadth justify it?) or treat it as a defect."
        )
        return 1 if args.strict else 0
    print("OK: no single stance dominates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
