"""Tool plumbing: definition, argument validation, the result envelope.

Tools are read-only wrappers over the same services the API routers use, so the assistant sees
exactly what the UI shows. They never compute financial figures; ``INSUFFICIENT_DATA`` blocks
pass through untouched (never turned into zero).
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.base import ToolSpec
from app.models.market import Company
from app.repositories.company import CompanyRepository

_TICKER_RE = re.compile(r"^[A-Za-z0-9._\-]{1,20}$")

#: Keys that identify rows, not facts: useless to the model and noise for the number check.
NOISE_KEYS = frozenset({"id", "company_id", "period_id", "source_id", "created_at", "updated_at"})


class ToolError(Exception):
    """A tool refused its arguments or has nothing to return; the model sees ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


ToolRunner = Callable[[AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]]
InsufficientCheck = Callable[[dict[str, Any]], str | None]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    run: ToolRunner
    #: Returns the reason when a result holds nothing to explain (used by /explain).
    insufficient: InsufficientCheck | None = None

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)


def object_schema(
    properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TICKER_PROPERTY = {
    "type": "string",
    "description": "EGX ticker symbol, for example COMI. Must exist in our company list.",
}


async def resolve_company(session: AsyncSession, args: dict[str, Any]) -> Company:
    """The company named by ``args['ticker']``, validated against the company table."""
    ticker = args.get("ticker")
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker.strip()):
        raise ToolError("INVALID_ARGUMENT", "ticker must be an EGX ticker symbol")
    company = await CompanyRepository(session).get_by_ticker(ticker.strip().upper())
    if company is None:
        raise ToolError("UNKNOWN_TICKER", f"No company with ticker {ticker.strip().upper()}")
    return company


def strip_noise(node: Any) -> Any:
    """Recursively drop row identifiers and audit timestamps."""
    if isinstance(node, dict):
        return {k: strip_noise(v) for k, v in node.items() if k not in NOISE_KEYS}
    if isinstance(node, list):
        return [strip_noise(v) for v in node]
    return node


def today_utc() -> str:
    return datetime.now(UTC).date().isoformat()


def first_text(*candidates: Any) -> str | None:
    for c in candidates:
        if isinstance(c, str) and c:
            return c
    return None


def envelope(
    tool: str,
    *,
    ticker: str | None,
    as_of: str | None,
    methodology: dict[str, Any],
    source: str,
    data: Any,
) -> dict[str, Any]:
    """Every tool result: where it came from, when, under which methodology versions."""
    return {
        "tool": tool,
        "ticker": ticker,
        # The data's own date when it has one, else the day it was read.
        "as_of": as_of or today_utc(),
        "methodology_versions": methodology,
        "source": source,
        "data": data,
    }
