"""screen_companies: fixed filters over stored results, never free-form queries."""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import MAX_TOOL_ROWS
from app.ai.tools.analysis import STANCE_CODES, STANCE_LABELS
from app.ai.tools.base import ToolDef, ToolError, envelope, object_schema
from app.metrics.engine import METRIC_CALCULATORS
from app.models.market import CompanyStatus
from app.repositories.company import CompanyRepository
from app.repositories.metrics import MetricRepository
from app.repositories.price import PriceRepository

logger = logging.getLogger(__name__)

MAX_METRIC_FILTERS = 3
#: Stance is computed per company, so only the most traded survivors are evaluated.
MAX_STANCE_EVALUATIONS = 60
ALL_COMPANIES = 1000
SHARIAH_VERDICTS = ("COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_SCREENED")
FORMING_VALUES = ("any", "up", "down")
METRIC_OPS = {"gte": lambda a, b: a >= b, "lte": lambda a, b: a <= b}


def _parse_metric_filters(raw: Any) -> list[tuple[str, str, Decimal]]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_METRIC_FILTERS:
        raise ToolError(
            "INVALID_ARGUMENT", f"metrics must be a list of at most {MAX_METRIC_FILTERS}"
        )
    out: list[tuple[str, str, Decimal]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ToolError("INVALID_ARGUMENT", "each metric filter must be an object")
        code, op = item.get("code"), item.get("op")
        if code not in METRIC_CALCULATORS:
            raise ToolError(
                "INVALID_ARGUMENT", f"unknown metric code; valid: {sorted(METRIC_CALCULATORS)}"
            )
        if op not in METRIC_OPS:
            raise ToolError("INVALID_ARGUMENT", "op must be gte or lte")
        try:
            threshold = Decimal(str(item.get("value")))
        except InvalidOperation:
            raise ToolError("INVALID_ARGUMENT", "value must be a number") from None
        if not threshold.is_finite():
            raise ToolError("INVALID_ARGUMENT", "value must be a finite number")
        out.append((str(code), str(op), threshold))
    return out


async def _screen_companies(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.screening.status import shariah_statuses
    from app.signals.stance import StanceService
    from app.technical.pattern_backtest import forming_by_company
    from app.technical.patterns import forming_matches, forming_summary

    sector = args.get("sector")
    verdict = args.get("shariah_verdict")
    egx33 = args.get("egx33_member")
    stance_label = args.get("stance")
    forming = args.get("forming")
    if sector is not None and not isinstance(sector, str):
        raise ToolError("INVALID_ARGUMENT", "sector must be a string")
    if verdict is not None and verdict not in SHARIAH_VERDICTS:
        raise ToolError("INVALID_ARGUMENT", f"shariah_verdict must be one of {SHARIAH_VERDICTS}")
    if egx33 is not None and not isinstance(egx33, bool):
        raise ToolError("INVALID_ARGUMENT", "egx33_member must be true or false")
    if stance_label is not None and stance_label not in STANCE_CODES:
        raise ToolError("INVALID_ARGUMENT", f"stance must be one of {sorted(STANCE_CODES)}")
    if forming is not None and forming not in FORMING_VALUES:
        raise ToolError("INVALID_ARGUMENT", f"forming must be one of {FORMING_VALUES}")
    metric_filters = _parse_metric_filters(args.get("metrics"))
    limit = args.get("limit", 20)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ToolError("INVALID_ARGUMENT", "limit must be a positive integer")
    limit = min(limit, MAX_TOOL_ROWS)

    universe, _ = await CompanyRepository(session).list_companies(
        page=1, page_size=ALL_COMPANIES, status=CompanyStatus.ACTIVE
    )
    candidates = list(universe)
    notes: list[str] = []
    if sector:
        wanted = sector.strip().lower()
        candidates = [c for c in candidates if (c.sector or "").lower() == wanted]
        if not candidates:
            sectors = sorted({c.sector for c in universe if c.sector})
            return _result({}, [], 0, [f"No companies in sector '{sector}'. Sectors: {sectors}"])

    shariah_blocks: dict[Any, dict[str, Any]] = {}
    if verdict is not None or egx33 is not None:
        shariah_blocks = await shariah_statuses(session, [c.id for c in candidates])
        if verdict is not None:
            candidates = [c for c in candidates if shariah_blocks[c.id]["verdict"] == verdict]
        if egx33 is not None:
            candidates = [
                c for c in candidates if (shariah_blocks[c.id]["egx33"] == "member") == egx33
            ]

    forming_by_id = await forming_by_company(session) if forming is not None else {}
    if forming is not None:
        candidates = [
            c for c in candidates if forming_matches(forming_by_id.get(c.id, []), forming)
        ]

    metric_values: dict[Any, Any] = {}
    if metric_filters:
        codes = sorted({code for code, _, _ in metric_filters})
        metric_values = await MetricRepository(session).latest_available_values(
            [c.id for c in candidates], codes
        )
        kept = []
        for c in candidates:
            if all(
                (found := metric_values.get((c.id, code))) is not None
                and METRIC_OPS[op](found.value, threshold)
                for code, op, threshold in metric_filters
            ):
                kept.append(c)
        candidates = kept
        notes.append(
            "Metric filters use each company's newest stored annual value; companies whose "
            "metrics are not computed or are INSUFFICIENT_DATA are left out, not treated as zero."
        )

    stances: dict[Any, Any] = {}
    truncated = False
    if stance_label is not None:
        prices = PriceRepository(session)
        ranked = await prices.most_traded_company_ids(
            MAX_STANCE_EVALUATIONS, company_ids=[c.id for c in candidates]
        )
        truncated = len(candidates) > len(ranked)
        price_date = await prices.latest_price_date()
        wanted_code = STANCE_CODES[stance_label]
        by_id = {c.id: c for c in candidates}
        blocks = shariah_blocks or await shariah_statuses(session, ranked)
        service = StanceService(session)
        kept_ids = []
        for company_id in ranked:
            company = by_id[company_id]
            try:
                res = await service.compute_cached(
                    company.ticker, price_date, shariah=blocks.get(company_id)
                )
            except Exception:
                logger.warning("stance unavailable for %s", company.ticker, exc_info=True)
                continue
            if res.stance.value == wanted_code:
                stances[company_id] = res
                kept_ids.append(company_id)
        candidates = [by_id[i] for i in kept_ids]
        if truncated:
            notes.append(
                f"Stance was evaluated for the {MAX_STANCE_EVALUATIONS} most traded matches only."
            )

    candidates.sort(key=lambda c: c.ticker)
    rows: list[dict[str, Any]] = []
    for c in candidates[:limit]:
        row: dict[str, Any] = {"ticker": c.ticker, "name": c.name, "sector": c.sector}
        if c.id in shariah_blocks:
            row["shariah_verdict"] = shariah_blocks[c.id]["verdict"]
            row["egx33"] = shariah_blocks[c.id]["egx33"]
        if c.id in stances:
            row["stance"] = STANCE_LABELS[stances[c.id].stance.value]
            row["confidence"] = stances[c.id].confidence
        if forming is not None:
            row["forming"] = [forming_summary(f) for f in forming_by_id.get(c.id, [])]
        for code, _, _ in metric_filters:
            found = metric_values[(c.id, code)]
            row[code] = {
                "value": str(found.value),
                "unit": found.unit,
                "fiscal_year": found.fiscal_year,
            }
        rows.append(row)
    applied = {
        "sector": sector,
        "shariah_verdict": verdict,
        "egx33_member": egx33,
        "stance": stance_label,
        "forming": forming,
        "metrics": [{"code": c, "op": o, "value": str(v)} for c, o, v in metric_filters],
    }
    return _result(applied, rows, len(candidates), notes)


def _result(
    applied: dict[str, Any], rows: list[dict[str, Any]], total: int, notes: list[str]
) -> dict[str, Any]:
    return envelope(
        "screen_companies",
        ticker=None,
        as_of=None,
        methodology={},
        source="EGX AI stored results (Shariah screen, stance, chart shapes, metrics)",
        data={
            "filters": applied,
            "total_matches": total,
            "returned": len(rows),
            "items": rows,
            "notes": notes,
        },
    )


SCREEN_TOOL = ToolDef(
    name="screen_companies",
    description=(
        "List companies that match fixed filters: sector, our Shariah verdict, EGX33 "
        "membership, research stance, a chart shape forming now, and up to three metric "
        "thresholds. Filters combine with AND. Results are a research shortlist, not advice."
    ),
    parameters=object_schema(
        {
            "sector": {"type": "string", "description": "Exact sector name, e.g. Banks."},
            "shariah_verdict": {"type": "string", "enum": list(SHARIAH_VERDICTS)},
            "egx33_member": {"type": "boolean", "description": "Official EGX33 Shariah member."},
            "stance": {"type": "string", "enum": sorted(STANCE_CODES)},
            "forming": {
                "type": "string",
                "enum": list(FORMING_VALUES),
                "description": "A chart shape forming now: any, expected up, or expected down.",
            },
            "metrics": {
                "type": "array",
                "maxItems": MAX_METRIC_FILTERS,
                "items": object_schema(
                    {
                        "code": {"type": "string", "enum": sorted(METRIC_CALCULATORS)},
                        "op": {"type": "string", "enum": sorted(METRIC_OPS)},
                        "value": {"type": "number"},
                    },
                    ["code", "op", "value"],
                ),
            },
            "limit": {"type": "integer", "description": f"At most {MAX_TOOL_ROWS} rows."},
        }
    ),
    run=_screen_companies,
)
