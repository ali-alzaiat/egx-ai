"""The assistant's tool registry and the single, safe way to run a tool."""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.base import ToolSpec
from app.ai.tools.analysis import ANALYSIS_TOOLS
from app.ai.tools.base import ToolDef, ToolError
from app.ai.tools.company import COMPANY_TOOLS
from app.ai.tools.screen import SCREEN_TOOL

logger = logging.getLogger(__name__)

#: A result larger than this is refused rather than silently truncated.
MAX_TOOL_OUTPUT_CHARS = 60_000

TOOLS: dict[str, ToolDef] = {
    t.name: t for t in (*COMPANY_TOOLS, *ANALYSIS_TOOLS, SCREEN_TOOL)
}

#: The tool behind each "Explain this" card.
CARD_TOOLS = {
    "score": "investment_score",
    "valuation": "valuation",
    "stance": "stance",
    "shariah": "shariah_status",
    "data_check": "data_check",
}


def tool_specs() -> list[ToolSpec]:
    return [t.spec() for t in TOOLS.values()]


@dataclass(frozen=True)
class ToolOutcome:
    """What running a tool produced: the JSON the model sees, and whether it was an error."""

    output: dict[str, Any]
    ok: bool
    ticker: str | None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def to_json(output: dict[str, Any]) -> str:
    return json.dumps(output, ensure_ascii=False, default=_jsonable)


async def execute_tool(session: AsyncSession, name: str, arguments: dict[str, Any]) -> ToolOutcome:
    """Run one tool. Never raises: a failure becomes an error result the model can report."""
    tool = TOOLS.get(name)
    if tool is None:
        unknown = {"error": "UNKNOWN_TOOL", "detail": f"No tool named {name}"}
        return ToolOutcome(unknown, False, None)
    if "__invalid_arguments__" in arguments:
        return ToolOutcome(
            {"error": "INVALID_ARGUMENT", "detail": "arguments were not valid JSON"}, False, None
        )
    ticker = arguments.get("ticker")
    try:
        output = await tool.run(session, arguments)
        if len(to_json(output)) > MAX_TOOL_OUTPUT_CHARS:
            return ToolOutcome(
                {"error": "RESULT_TOO_LARGE", "detail": "Result too large; narrow the request."},
                False,
                None,
            )
        return ToolOutcome(output, True, output.get("ticker"))
    except ToolError as exc:
        return ToolOutcome({"error": exc.code, "detail": exc.message}, False, None)
    except HTTPException as exc:
        return ToolOutcome({"error": "NOT_FOUND", "detail": str(exc.detail)}, False, None)
    except Exception:
        logger.warning("tool %s failed", name, exc_info=True)
        await session.rollback()
        return ToolOutcome(
            {"error": "TOOL_FAILED", "detail": "The tool failed; the data is unavailable now."},
            False,
            ticker if isinstance(ticker, str) else None,
        )
