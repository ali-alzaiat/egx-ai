"""Score-tab extras computed on read from approved statement lines (R47 Q1/Q2).

``piotroski`` and ``dividend_safety`` sit beside the investment score in
``GET /api/scores/companies/{id}``. They are not persisted and not part of the score, so the
score and its methodology version are unchanged. Banks come from the statement lines
(net loans + deposits) or the loaded EGX sector, whichever is known.
"""

import dataclasses
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.backfill import normalize_sector_name
from app.models.market import Company
from app.scores.dividend_safety import (
    DIVIDEND_LINE_CODES,
    HISTORY_YEARS,
    evaluate_dividend_safety,
)
from app.scores.piotroski import PIOTROSKI_LINE_CODES, evaluate_piotroski
from app.statements import bridge
from app.statements.bridge import LineValue, PeriodLines, load_company_statements

BANK_SECTOR = "Banks"


def _values(p: PeriodLines | None, codes: Iterable[str]) -> dict[str, Decimal] | None:
    if p is None:
        return None
    return {c: lv.value for c in codes if (lv := p.get(c)) is not None}


def _lines(p: PeriodLines | None, codes: Iterable[str]) -> list[LineValue]:
    if p is None:
        return []
    return [lv for c in codes if (lv := p.get(c)) is not None]


def _source(lines: list[LineValue]) -> dict[str, Any]:
    tier = bridge.tier_of(lines)
    return {
        "source_tier": tier,
        "provisional": tier == "vendor",
        "sources": [bridge.provenance(lv) for lv in bridge.unique_sources(lines)],
    }


async def build_score_extras(session: AsyncSession, company: Company) -> dict[str, Any]:
    """``{"piotroski": {...}, "dividend_safety": {...}}`` for one company."""
    return await build_extras_for(session, company.id, company.sector)


async def build_extras_for(
    session: AsyncSession, company_id: uuid.UUID, sector: str | None
) -> dict[str, Any]:
    statements = await load_company_statements(session, company_id)
    latest = statements.latest()
    prior = statements.prior(latest) if latest is not None else None

    by_sector = sector is not None and normalize_sector_name(sector) == BANK_SECTOR
    by_lines = bridge.is_bank(latest)
    is_bank = by_sector or by_lines
    bank_reason = (
        "Banks are not scored: working capital, gross margin and debt/asset ratios do not "
        "describe a bank "
        + ("(statement lines show net loans and deposits)." if by_lines else "(EGX sector: Banks).")
    )

    piotroski = evaluate_piotroski(
        _values(latest, PIOTROSKI_LINE_CODES),
        _values(prior, PIOTROSKI_LINE_CODES),
        fiscal_year=latest.fiscal_year if latest is not None else None,
        prior_fiscal_year=latest.fiscal_year - 1 if latest is not None else None,
        is_bank=is_bank,
        bank_reason=bank_reason,
    )
    piotroski_payload = dataclasses.asdict(piotroski)
    piotroski_payload.update(
        _source(_lines(latest, PIOTROSKI_LINE_CODES) + _lines(prior, PIOTROSKI_LINE_CODES))
    )

    year_values: dict[int, dict[str, Decimal]] = {}
    year_lines: list[LineValue] = []
    for back in range(HISTORY_YEARS):
        p = statements.years_back(latest, back) if latest is not None else None
        values = _values(p, DIVIDEND_LINE_CODES)
        if p is not None and values is not None:
            year_values[p.fiscal_year] = values
            year_lines.extend(_lines(p, DIVIDEND_LINE_CODES))
    dividend = evaluate_dividend_safety(
        year_values, latest.fiscal_year if latest is not None else None, is_bank=is_bank
    )
    dividend_payload = dataclasses.asdict(dividend)
    dividend_payload.update(_source(year_lines))

    return {"piotroski": piotroski_payload, "dividend_safety": dividend_payload}
