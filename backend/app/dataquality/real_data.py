"""Data-first gate: how many companies have real (non-synthetic) fundamentals.

A company counts when it has at least one financial fact from a non-SYNTHETIC
source (or from a registered disclosure filing), or an approved / auto-validated
statement line. CONTRACT.md blocks any phase that consumes fundamentals until
this reaches the minimum.

Usage:
    python -m app.dataquality.real_data                  # report
    python -m app.dataquality.real_data --min-companies 5  # exit 1 below 5
"""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_MIN_COMPANIES = 5

_REAL_DATA_COMPANIES = text(
    """
    SELECT COUNT(DISTINCT company_id) FROM (
        SELECT f.company_id
        FROM financial_facts f
        LEFT JOIN financial_documents d ON d.id = f.document_id
        LEFT JOIN data_sources s ON s.id = d.source_id
        WHERE f.filing_id IS NOT NULL
           OR (s.id IS NOT NULL AND s.source_type::text <> 'SYNTHETIC')
        UNION
        SELECT l.company_id
        FROM financial_statement_lines l
        WHERE l.ext_status::text IN ('approved', 'auto_validated')
    ) AS real_companies
    """
)


async def real_data_company_count(session: AsyncSession) -> int:
    """Companies with at least one real (non-synthetic) fundamental input."""
    result = await session.execute(_REAL_DATA_COMPANIES)
    return int(result.scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-companies", type=int, default=DEFAULT_MIN_COMPANIES)
    args = parser.parse_args()

    async def _count() -> int:
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await real_data_company_count(session)

    count = asyncio.run(_count())
    print(f"Companies with real fundamentals: {count} (gate: {args.min_companies})")
    if count < args.min_companies:
        print("BLOCKED: phases that consume fundamentals may not start (CONTRACT data-first gate).")
        return 1
    print("OK: data-first gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
