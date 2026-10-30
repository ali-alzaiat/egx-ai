"""Chart-pattern detection (R47 P4, P6): fixed rules, display only.

Pure and deterministic: no database, clock or I/O. Patterns are *drawn by fixed rules*; they are
not predictions. How often each one worked on EGX history is measured in ``pattern_backtest``.

Method (``PATTERNS_VERSION``; every threshold lives in this module's constants, and changing one
requires bumping the version):

* Series: stored daily closes, one bar per stored session, oldest first (bars with a close <= 0
  are dropped). "Sessions" below are stored bars.
* Extrema: **window pivots**. A close is a pivot high when it is higher than every close in the
  ``PIVOT_WINDOW`` (5) sessions before it and not lower than every close in the 5 sessions
  after it (mirror for pivot lows). Chosen over Lo-Mamaysky-Wang kernel smoothing because it has no
  bandwidth to tune, uses the raw closes the user sees, and states its own delay exactly: a pivot
  at session ``i`` can only be known at session ``i + w`` (``t0``), so it is never used before.
  Consecutive pivots of the same kind are merged to the more extreme one, so the list that the
  rules see alternates high / low. The merge is applied in the order the pivots become known, so
  the list at any session depends only on closes up to that session.
* Patterns (LMW-style rules on that alternating list), each a *candidate* the moment its last
  key point becomes known:
  - Head and shoulders top / inverse: 5 alternating pivots; head beyond both shoulders by
    ``HEAD_MARGIN``; shoulders within ``SHOULDER_TOL`` of their mean; the two troughs (peaks)
    within ``NECKLINE_TOL`` of their mean and beyond both shoulders; neckline through the troughs.
  - Double top / double bottom: 3 alternating pivots; the two extremes within ``DOUBLE_TOL`` of
    their mean, ``DOUBLE_MIN_GAP``..``DOUBLE_MAX_GAP`` sessions apart, the middle pivot at least
    ``DOUBLE_MIN_DEPTH`` beyond them; neckline at the middle pivot.
  - Ascending / descending / symmetrical triangles: the last 4 to 6 pivots with at least 2 highs and
    2 lows, a least-squares line through the highs and through the lows; flat side within
    ``TRI_FLAT_TOL`` and sloped side at least ``TRI_SLOPE_MIN`` (both as total change over the
    pattern span, relative to the mean price), every pivot within ``TRI_FIT_TOL`` of its line,
    and the gap between the lines shrunk to ``TRI_CONVERGE`` of its starting width.
  There is no prior-trend filter and no volume rule.
* **Confirmed only.** A candidate counts when a close breaks the neckline / boundary in the
  pattern's direction within ``CONFIRM_WITHIN`` sessions of ``t0``: the first such close at or after
  ``t0`` (a break earlier than ``t0`` could not have been recognised yet). It is dead if a close
  first goes the other way past the pattern (above the head / peaks for a top, past the opposite
  boundary of a directional triangle). Symmetrical triangles take the direction of their break.
* Overlaps: per pattern key, a later occurrence is dropped if its formation starts on or before the
  confirmation of an earlier accepted one (greedy in confirmation order), so one formation is
  not counted several times.
* Measured target: the standard textbook convention (head-to-neckline height, peak-to-trough
  height, widest triangle gap), projected from the broken level. It is a convention, not a
  forecast, and is omitted when a downside target would not be positive.

* **Forming (patterns-1.1, R47 P6).** The same candidates, overlap-filtered per pattern type in
  the order they became known (a later one is dropped while an earlier accepted one of that type
  is still unresolved). Each resolves as confirmed, failed (a close went the other way past it) or
  expired (no break within ``CONFIRM_WITHIN`` sessions of ``t0``, or a triangle reached its apex).
  One still unresolved at the last session is *forming*: shown with the closes that would confirm
  or invalidate it, and with odds measured from ``t0`` (``pattern_backtest``), never with the
  odds of confirmed patterns.

Look-ahead: the result for a confirmation on session ``c`` is identical when the series is cut at
``c`` (tested); a pivot enters the rules at ``i + w``. The forming state at session ``e`` uses
only closes up to ``e``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

PATTERNS_VERSION = "patterns-1.1"

PIVOT_WINDOW = 5
MIN_SESSIONS = 60
CONFIRM_WITHIN = 20

HEAD_MARGIN = 0.02
SHOULDER_TOL = 0.04
NECKLINE_TOL = 0.05
HS_MIN_SPAN = 25
HS_MAX_SPAN = 160

DOUBLE_TOL = 0.03
DOUBLE_MIN_DEPTH = 0.05
DOUBLE_MIN_GAP = 10
DOUBLE_MAX_GAP = 120

TRI_PIVOT_COUNTS: tuple[int, ...] = (4, 5, 6)
TRI_MIN_TOUCHES = 2
TRI_MIN_SPAN = 20
TRI_MAX_SPAN = 120
TRI_FLAT_TOL = 0.02
TRI_SLOPE_MIN = 0.04
TRI_FIT_TOL = 0.015
TRI_CONVERGE = 0.7

PATTERN_TYPES: tuple[str, ...] = (
    "head_and_shoulders_top",
    "head_and_shoulders_inverse",
    "double_top",
    "double_bottom",
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle",
)
#: Keys the backtest reports on (a symmetrical triangle is split by the direction it broke).
STATS_KEYS: tuple[str, ...] = (
    "head_and_shoulders_top",
    "head_and_shoulders_inverse",
    "double_top",
    "double_bottom",
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle_up",
    "symmetrical_triangle_down",
)
#: Direction each stats key expects (what counts as a hit).
KEY_DIRECTION: dict[str, Literal["up", "down"]] = {
    "head_and_shoulders_top": "down",
    "head_and_shoulders_inverse": "up",
    "double_top": "down",
    "double_bottom": "up",
    "ascending_triangle": "up",
    "descending_triangle": "down",
    "symmetrical_triangle_up": "up",
    "symmetrical_triangle_down": "down",
}

#: Direction a forming shape is expected to break (None: a symmetrical triangle can go either way).
FORMING_DIRECTION: dict[str, Literal["up", "down"] | None] = {
    "head_and_shoulders_top": "down",
    "head_and_shoulders_inverse": "up",
    "double_top": "down",
    "double_bottom": "up",
    "ascending_triangle": "up",
    "descending_triangle": "down",
    "symmetrical_triangle": None,
}

NOTE = "patterns are drawn by fixed rules; odds are measured on EGX history, not a prediction"
FORMING_NOTE = (
    "forming: no breakout yet, and many shapes never break out; odds are measured from the "
    "forming stage, not from a breakout"
)
TARGET_LABEL = "measured move (chart-pattern convention, not a forecast)"

Direction = Literal["up", "down"]
Outcome = Literal["confirmed", "failed", "expired", "open"]
_PRICE_FMT = "{:.4f}"


@dataclass(frozen=True, slots=True)
class PatternPoint:
    label: str
    date: date
    price: float


@dataclass(frozen=True, slots=True)
class PatternLine:
    label: str
    start: PatternPoint
    end: PatternPoint


@dataclass(frozen=True, slots=True)
class PatternOccurrence:
    pattern: str
    stats_key: str
    direction: Direction
    start_date: date
    end_date: date  # last key point (the pivot itself, not the session it became known)
    known_date: date  # session on which the last key point became known (pivot + window)
    confirmation_date: date
    confirmation_index: int
    confirmation_close: float
    break_level: float
    points: tuple[PatternPoint, ...]
    lines: tuple[PatternLine, ...]
    target: float | None


@dataclass(frozen=True, slots=True)
class FormingEvent:
    """One overlap-filtered candidate and how it stood at the last session scanned."""

    pattern: str
    known_index: int  # t0: the session its last key point became known
    outcome: Outcome
    outcome_index: int  # session it resolved on; the last session when still open
    direction: Direction | None  # break direction when confirmed


@dataclass(frozen=True, slots=True)
class FormingPattern:
    """A shape still forming at the last session (R47 P6)."""

    pattern: str
    expected: Direction | None
    start_date: date
    end_date: date
    known_date: date
    sessions_left: int  # sessions after the last one in which a break can still confirm it
    confirm_above: float | None  # a close above this confirms an upward break
    confirm_below: float | None  # a close below this confirms a downward break
    invalid_above: float | None  # a close above this kills a downward pattern
    invalid_below: float | None  # a close below this kills an upward pattern
    points: tuple[PatternPoint, ...]
    lines: tuple[PatternLine, ...]


@dataclass(frozen=True, slots=True)
class _Pivot:
    kind: Literal["H", "L"]
    idx: int
    price: float


@dataclass(frozen=True, slots=True)
class _Line:
    slope: float
    intercept: float

    def at(self, idx: float) -> float:
        return self.slope * idx + self.intercept


def _through(i1: int, p1: float, i2: int, p2: float) -> _Line:
    slope = (p2 - p1) / (i2 - i1)
    return _Line(slope, p1 - slope * i1)


def _flat(price: float) -> _Line:
    return _Line(0.0, price)


def _fit(points: Sequence[tuple[int, float]]) -> _Line:
    """Least-squares line through (index, price) points (at least two distinct indexes)."""
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    slope = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx
    return _Line(slope, my - slope * mx)


@dataclass(slots=True)
class _Candidate:
    pattern: str
    start_idx: int
    last_idx: int
    t0: int
    points: list[tuple[str, int, float]]
    mode: Literal["down", "up", "either"]
    upper: _Line | None  # upside boundary / failure level
    lower: _Line | None  # downside boundary / failure level
    apex_idx: float | None
    line_specs: list[tuple[str, int, _Line]]  # label, start index, line (drawn to the break)
    height: float  # measured-move height


def window_pivots(closes: Sequence[float], window: int = PIVOT_WINDOW) -> list[_Pivot]:
    """All pivots, in index order. Pivot ``i`` is only *known* at ``i + window``."""
    out: list[_Pivot] = []
    for i in range(window, len(closes) - window):
        c = closes[i]
        left = closes[i - window : i]
        right = closes[i + 1 : i + window + 1]
        if c > max(left) and c >= max(right):
            out.append(_Pivot("H", i, c))
        elif c < min(left) and c <= min(right):
            out.append(_Pivot("L", i, c))
    return out


def _merge(alt: list[_Pivot], pivot: _Pivot) -> bool:
    """Add ``pivot`` keeping the list alternating; True when the last element changed."""
    if alt and alt[-1].kind == pivot.kind:
        last = alt[-1]
        more_extreme = pivot.price > last.price if pivot.kind == "H" else pivot.price < last.price
        if not more_extreme:
            return False
        alt[-1] = pivot
        return True
    alt.append(pivot)
    return True


def _rel_diff(a: float, b: float) -> float:
    return abs(a - b) / ((a + b) / 2)


def _head_and_shoulders(alt: list[_Pivot], t0: int) -> _Candidate | None:
    if len(alt) < 5:
        return None
    ls, t1, head, t2, rs = alt[-5:]
    top = rs.kind == "H"
    if top:
        if not (head.price >= max(ls.price, rs.price) * (1 + HEAD_MARGIN)):
            return None
        if not max(t1.price, t2.price) < min(ls.price, rs.price):
            return None
    else:
        if not (head.price <= min(ls.price, rs.price) * (1 - HEAD_MARGIN)):
            return None
        if not min(t1.price, t2.price) > max(ls.price, rs.price):
            return None
    if _rel_diff(ls.price, rs.price) > SHOULDER_TOL:
        return None
    if _rel_diff(t1.price, t2.price) > NECKLINE_TOL:
        return None
    if not HS_MIN_SPAN <= rs.idx - ls.idx <= HS_MAX_SPAN:
        return None
    neck = _through(t1.idx, t1.price, t2.idx, t2.price)
    head_price = head.price
    height = abs(head_price - neck.at(head.idx))
    pts = [
        ("left_shoulder", ls.idx, ls.price),
        ("trough_1" if top else "peak_1", t1.idx, t1.price),
        ("head", head.idx, head.price),
        ("trough_2" if top else "peak_2", t2.idx, t2.price),
        ("right_shoulder", rs.idx, rs.price),
    ]
    return _Candidate(
        pattern="head_and_shoulders_top" if top else "head_and_shoulders_inverse",
        start_idx=ls.idx,
        last_idx=rs.idx,
        t0=t0,
        points=pts,
        mode="down" if top else "up",
        upper=_flat(head_price) if top else neck,
        lower=neck if top else _flat(head_price),
        apex_idx=None,
        line_specs=[("neckline", t1.idx, neck)],
        height=height,
    )


def _double(alt: list[_Pivot], t0: int) -> _Candidate | None:
    if len(alt) < 3:
        return None
    p1, mid, p2 = alt[-3:]
    top = p2.kind == "H"
    if _rel_diff(p1.price, p2.price) > DOUBLE_TOL:
        return None
    if not DOUBLE_MIN_GAP <= p2.idx - p1.idx <= DOUBLE_MAX_GAP:
        return None
    if top:
        if not mid.price <= min(p1.price, p2.price) * (1 - DOUBLE_MIN_DEPTH):
            return None
        edge = max(p1.price, p2.price)
        height = (p1.price + p2.price) / 2 - mid.price
    else:
        if not mid.price >= max(p1.price, p2.price) * (1 + DOUBLE_MIN_DEPTH):
            return None
        edge = min(p1.price, p2.price)
        height = mid.price - (p1.price + p2.price) / 2
    return _Candidate(
        pattern="double_top" if top else "double_bottom",
        start_idx=p1.idx,
        last_idx=p2.idx,
        t0=t0,
        points=[
            ("peak_1" if top else "trough_1", p1.idx, p1.price),
            ("trough" if top else "peak", mid.idx, mid.price),
            ("peak_2" if top else "trough_2", p2.idx, p2.price),
        ],
        mode="down" if top else "up",
        upper=_flat(edge) if top else _flat(mid.price),
        lower=_flat(mid.price) if top else _flat(edge),
        apex_idx=None,
        line_specs=[("neckline", mid.idx, _flat(mid.price))],
        height=height,
    )


def _triangles(alt: list[_Pivot], t0: int) -> list[_Candidate]:
    out: list[_Candidate] = []
    for count in TRI_PIVOT_COUNTS:
        if len(alt) < count:
            continue
        window = alt[-count:]
        highs = [(p.idx, p.price) for p in window if p.kind == "H"]
        lows = [(p.idx, p.price) for p in window if p.kind == "L"]
        if len(highs) < TRI_MIN_TOUCHES or len(lows) < TRI_MIN_TOUCHES:
            continue
        first, last = window[0].idx, window[-1].idx
        span = last - first
        if not TRI_MIN_SPAN <= span <= TRI_MAX_SPAN:
            continue
        upper, lower = _fit(highs), _fit(lows)
        if any(abs(p - upper.at(i)) > TRI_FIT_TOL * p for i, p in highs):
            continue
        if any(abs(p - lower.at(i)) > TRI_FIT_TOL * p for i, p in lows):
            continue
        mean = sum(p.price for p in window) / count
        d_up = upper.slope * span / mean  # total change of the upper line over the span
        d_low = lower.slope * span / mean
        gap_start = upper.at(first) - lower.at(first)
        gap_end = upper.at(last) - lower.at(last)
        if gap_start <= 0 or gap_end <= 0 or gap_end > TRI_CONVERGE * gap_start:
            continue
        pattern: str | None = None
        mode: Literal["down", "up", "either"] = "either"
        if abs(d_up) <= TRI_FLAT_TOL and d_low >= TRI_SLOPE_MIN:
            pattern, mode = "ascending_triangle", "up"
        elif abs(d_low) <= TRI_FLAT_TOL and d_up <= -TRI_SLOPE_MIN:
            pattern, mode = "descending_triangle", "down"
        elif d_up <= -TRI_SLOPE_MIN and d_low >= TRI_SLOPE_MIN:
            pattern, mode = "symmetrical_triangle", "either"
        if pattern is None:
            continue
        apex = (lower.intercept - upper.intercept) / (upper.slope - lower.slope)
        out.append(
            _Candidate(
                pattern=pattern,
                start_idx=first,
                last_idx=last,
                t0=t0,
                points=[
                    (("peak_" if p.kind == "H" else "trough_") + str(n + 1), p.idx, p.price)
                    for n, p in enumerate(window)
                ],
                mode=mode,
                upper=upper,
                lower=lower,
                apex_idx=apex,
                line_specs=[("upper_boundary", first, upper), ("lower_boundary", first, lower)],
                height=gap_start,
            )
        )
    return out


def _resolve(
    closes: Sequence[float], cand: _Candidate, end: int
) -> tuple[Outcome, int, Direction | None]:
    """How ``cand`` stands at session ``end``, using closes up to ``end`` only."""
    deadline = cand.t0 + CONFIRM_WITHIN
    stop = min(end, deadline)
    for idx in range(cand.last_idx + 1, stop + 1):
        if cand.apex_idx is not None and idx >= cand.apex_idx:
            return "expired", idx, None
        c = closes[idx]
        up = cand.upper.at(idx) if cand.upper is not None else math.inf
        low = cand.lower.at(idx) if cand.lower is not None else -math.inf
        if cand.mode == "down":
            if c > up:
                return "failed", idx, None
            if idx >= cand.t0 and c < low:
                return "confirmed", idx, "down"
        elif cand.mode == "up":
            if c < low:
                return "failed", idx, None
            if idx >= cand.t0 and c > up:
                return "confirmed", idx, "up"
        elif idx >= cand.t0:
            if c > up:
                return "confirmed", idx, "up"
            if c < low:
                return "confirmed", idx, "down"
    if stop < deadline:
        return "open", end, None
    return "expired", stop, None


def _confirm(closes: Sequence[float], cand: _Candidate) -> tuple[int, Direction] | None:
    """First close that breaks the pattern in its direction, or None when dead / expired / open."""
    outcome, idx, direction = _resolve(closes, cand, len(closes) - 1)
    if outcome != "confirmed" or direction is None:
        return None
    return idx, direction


def _stats_key(pattern: str, direction: Direction) -> str:
    return f"{pattern}_{direction}" if pattern == "symmetrical_triangle" else pattern


def _bars(series: Sequence[tuple[date, float | Decimal]]) -> list[tuple[date, float]]:
    return sorted({d: float(c) for d, c in series if float(c) > 0}.items())


def _candidates(closes: Sequence[float]) -> list[_Candidate]:
    """Every candidate, in the order it becomes known (``t0`` non-decreasing)."""
    candidates: list[_Candidate] = []
    alt: list[_Pivot] = []
    for pivot in window_pivots(closes):
        if not _merge(alt, pivot):
            continue
        t0 = pivot.idx + PIVOT_WINDOW
        for cand in (_head_and_shoulders(alt, t0), _double(alt, t0)):
            if cand is not None:
                candidates.append(cand)
        candidates.extend(_triangles(alt, t0))
    return candidates


def _forming(closes: Sequence[float]) -> list[tuple[_Candidate, FormingEvent]]:
    """Overlap-filtered candidates with their outcome at the last session."""
    end = len(closes) - 1
    live_until: dict[str, int] = {}
    out: list[tuple[_Candidate, FormingEvent]] = []
    for cand in _candidates(closes):
        if cand.start_idx <= live_until.get(cand.pattern, -1):
            continue
        outcome, idx, direction = _resolve(closes, cand, end)
        live_until[cand.pattern] = idx
        out.append((cand, FormingEvent(cand.pattern, cand.t0, outcome, idx, direction)))
    return out


def forming_events(series: Sequence[tuple[date, float | Decimal]]) -> list[FormingEvent]:
    """Every overlap-filtered candidate and its outcome (the backtest's forming cases)."""
    bars = _bars(series)
    if len(bars) < MIN_SESSIONS:
        return []
    return [event for _, event in _forming([b[1] for b in bars])]


def forming_now(series: Sequence[tuple[date, float | Decimal]]) -> list[FormingPattern]:
    """Shapes still forming at the last session, most recently known first."""
    bars = _bars(series)
    if len(bars) < MIN_SESSIONS:
        return []
    dates = [b[0] for b in bars]
    closes = [b[1] for b in bars]
    end = len(closes) - 1
    out: list[FormingPattern] = []
    for cand, event in _forming(closes):
        if event.outcome != "open":
            continue
        up = cand.upper.at(end) if cand.upper is not None else None
        low = cand.lower.at(end) if cand.lower is not None else None
        last_ok = cand.t0 + CONFIRM_WITHIN
        if cand.apex_idx is not None:
            last_ok = min(last_ok, math.ceil(cand.apex_idx) - 1)
        out.append(
            FormingPattern(
                pattern=cand.pattern,
                expected=FORMING_DIRECTION[cand.pattern],
                start_date=dates[cand.start_idx],
                end_date=dates[cand.last_idx],
                known_date=dates[cand.t0],
                sessions_left=max(0, last_ok - end),
                confirm_above=up if cand.mode in ("up", "either") else None,
                confirm_below=low if cand.mode in ("down", "either") else None,
                invalid_above=up if cand.mode == "down" else None,
                invalid_below=low if cand.mode == "up" else None,
                points=tuple(PatternPoint(label, dates[i], p) for label, i, p in cand.points),
                lines=tuple(
                    PatternLine(
                        label,
                        PatternPoint(label, dates[i], line.at(i)),
                        PatternPoint(label, dates[end], line.at(end)),
                    )
                    for label, i, line in cand.line_specs
                ),
            )
        )
    out.sort(key=lambda f: f.known_date, reverse=True)
    return out


def detect_patterns(series: Sequence[tuple[date, float | Decimal]]) -> list[PatternOccurrence]:
    """Confirmed occurrences, oldest confirmation first. Empty when under ``MIN_SESSIONS`` bars."""
    bars = _bars(series)
    if len(bars) < MIN_SESSIONS:
        return []
    dates = [b[0] for b in bars]
    closes = [b[1] for b in bars]
    candidates = _candidates(closes)

    confirmed: list[tuple[int, int, int, _Candidate, Direction]] = []
    for order, cand in enumerate(candidates):
        hit = _confirm(closes, cand)
        if hit is not None:
            confirmed.append((hit[0], cand.start_idx, order, cand, hit[1]))
    confirmed.sort(key=lambda r: (r[0], r[1], r[2]))

    last_confirm: dict[str, int] = {}
    out: list[PatternOccurrence] = []
    for conf_idx, _start, _order, cand, direction in confirmed:
        key = _stats_key(cand.pattern, direction)
        if cand.start_idx <= last_confirm.get(key, -1):
            continue
        last_confirm[key] = conf_idx
        out.append(_occurrence(cand, conf_idx, direction, dates, closes))
    return out


def _occurrence(
    cand: _Candidate,
    conf_idx: int,
    direction: Direction,
    dates: Sequence[date],
    closes: Sequence[float],
) -> PatternOccurrence:
    broken = cand.upper if direction == "up" else cand.lower
    assert broken is not None
    level = broken.at(conf_idx)
    target: float | None = level + cand.height if direction == "up" else level - cand.height
    if target is not None and target <= 0:
        target = None
    points = tuple(PatternPoint(label, dates[i], p) for label, i, p in cand.points)
    lines = tuple(
        PatternLine(
            label,
            PatternPoint(label, dates[i], line.at(i)),
            PatternPoint(label, dates[conf_idx], line.at(conf_idx)),
        )
        for label, i, line in cand.line_specs
    )
    return PatternOccurrence(
        pattern=cand.pattern,
        stats_key=_stats_key(cand.pattern, direction),
        direction=direction,
        start_date=dates[cand.start_idx],
        end_date=dates[cand.last_idx],
        known_date=dates[cand.t0],
        confirmation_date=dates[conf_idx],
        confirmation_index=conf_idx,
        confirmation_close=closes[conf_idx],
        break_level=level,
        points=points,
        lines=lines,
        target=target,
    )


def _price(value: float) -> str:
    return _PRICE_FMT.format(value)


def _point_dict(p: PatternPoint) -> dict[str, Any]:
    return {"label": p.label, "date": p.date.isoformat(), "price": _price(p.price)}


def occurrence_to_dict(o: PatternOccurrence) -> dict[str, Any]:
    """JSON-ready form (prices as 4-decimal strings, like the volatility cone)."""
    return {
        "pattern": o.pattern,
        "stats_key": o.stats_key,
        "direction": o.direction,
        "start_date": o.start_date.isoformat(),
        "end_date": o.end_date.isoformat(),
        "known_date": o.known_date.isoformat(),
        "confirmation_date": o.confirmation_date.isoformat(),
        "confirmation_close": _price(o.confirmation_close),
        "break_level": _price(o.break_level),
        "points": [_point_dict(p) for p in o.points],
        "lines": [
            {"label": ln.label, "start": _point_dict(ln.start), "end": _point_dict(ln.end)}
            for ln in o.lines
        ],
        "target": (
            {"price": _price(o.target), "label": TARGET_LABEL} if o.target is not None else None
        ),
    }


def _opt_price(value: float | None) -> str | None:
    return _price(value) if value is not None else None


#: Forming-pattern filter choices (R47 P7): any shape, or by its expected break.
FormingFilter = Literal["any", "up", "down"]


def forming_matches(shapes: Sequence[FormingPattern], wanted: FormingFilter) -> bool:
    """Whether any shape matches; a symmetrical triangle (no expected break) is "any" only."""
    if wanted == "any":
        return bool(shapes)
    return any(f.expected == wanted for f in shapes)


def forming_summary(f: FormingPattern) -> dict[str, Any]:
    """The table form of a forming shape: no points or lines."""
    return {
        "pattern": f.pattern,
        "expected": f.expected,
        "known_date": f.known_date.isoformat(),
        "sessions_left": f.sessions_left,
        "confirm_above": _opt_price(f.confirm_above),
        "confirm_below": _opt_price(f.confirm_below),
    }


def forming_to_dict(f: FormingPattern) -> dict[str, Any]:
    """JSON-ready form of a forming shape."""
    return {
        "pattern": f.pattern,
        "expected": f.expected,
        "start_date": f.start_date.isoformat(),
        "end_date": f.end_date.isoformat(),
        "known_date": f.known_date.isoformat(),
        "sessions_left": f.sessions_left,
        "confirm_above": _opt_price(f.confirm_above),
        "confirm_below": _opt_price(f.confirm_below),
        "invalid_above": _opt_price(f.invalid_above),
        "invalid_below": _opt_price(f.invalid_below),
        "points": [_point_dict(p) for p in f.points],
        "lines": [
            {"label": ln.label, "start": _point_dict(ln.start), "end": _point_dict(ln.end)}
            for ln in f.lines
        ],
    }
