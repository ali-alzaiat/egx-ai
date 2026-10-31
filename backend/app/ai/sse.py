"""Server-sent-event formatting for the assistant stream (pure).

One frame per event: ``event: <name>`` then ``data: <one-line JSON>`` then a blank line. JSON
never contains a raw newline, so a frame cannot be split or injected into by model text.
"""

import json
from decimal import Decimal
from typing import Any

EVENT_NAMES = frozenset({"meta", "status", "answer", "unverified", "error", "done"})

ERROR_CODES = frozenset(
    {"NO_KEY", "CAP_REACHED", "PROVIDER_ERROR", "INSUFFICIENT_DATA", "UNKNOWN_MODEL"}
)


#: Why a PROVIDER_ERROR happened; the UI picks its main line from this (R50 B16).
ERROR_REASONS = frozenset(
    {"auth", "rate_limit", "quota", "unavailable", "bad_request", "unknown"}
)


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def format_event(name: str, data: dict[str, Any]) -> str:
    """One SSE frame. Unknown event names are a programming error, not a runtime surprise."""
    if name not in EVENT_NAMES:
        raise ValueError(f"unknown SSE event: {name}")
    if name == "error" and data.get("code") not in ERROR_CODES:
        raise ValueError(f"unknown error code: {data.get('code')}")
    is_provider_error = name == "error" and data.get("code") == "PROVIDER_ERROR"
    if is_provider_error and data.get("reason") not in ERROR_REASONS:
        raise ValueError(f"PROVIDER_ERROR needs a known reason, got {data.get('reason')}")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_default)
    # U+2028/2029 are valid JSON but split lines in some SSE parsers.
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return f"event: {name}\ndata: {payload}\n\n"


def parse_events(stream_text: str) -> list[tuple[str, dict[str, Any]]]:
    """Inverse of ``format_event`` for a whole stream (used by tests and tooling)."""
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in stream_text.split("\n\n"):
        if not frame.strip():
            continue
        name = ""
        data = ""
        for line in frame.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data += line[len("data: ") :]
        events.append((name, json.loads(data)))
    return events
