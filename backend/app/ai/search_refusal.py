"""Providers that refused web search, remembered until the next UTC midnight (R50 B15).

In-process on purpose (a single-user tool, one server process): a restart forgets it and the
next search attempt simply finds out again. The clock is injectable so tests can roll the day.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


_clock: Clock = _utc_now
#: provider -> the UTC date on which it refused; the mark lapses when the date changes.
_refused: dict[str, date] = {}


def set_clock(clock: Clock | None) -> None:
    """Replace the clock (tests); None restores the real one."""
    global _clock
    _clock = clock or _utc_now


def mark_refused(provider: str) -> None:
    _refused[provider] = _clock().astimezone(UTC).date()


def is_refused(provider: str) -> bool:
    """True while today (UTC) is the day the provider refused search."""
    day = _refused.get(provider)
    if day is None:
        return False
    if day == _clock().astimezone(UTC).date():
        return True
    del _refused[provider]
    return False


def reset() -> None:
    _refused.clear()
