"""R47 P4: chart-pattern detection on synthetic series (pure, no database)."""

import random
from datetime import date, timedelta

from app.technical import patterns as P
from app.technical.patterns import PatternOccurrence, detect_patterns

START = date(2025, 1, 1)


def path(waypoints: list[tuple[int, float]]) -> list[float]:
    """Piecewise-linear closes through (index, price) waypoints, one bar per index."""
    out: list[float] = []
    for (i0, p0), (i1, p1) in zip(waypoints, waypoints[1:], strict=False):
        for i in range(i0, i1):
            out.append(p0 + (p1 - p0) * (i - i0) / (i1 - i0))
    out.append(waypoints[-1][1])
    return out


def series(closes: list[float]) -> list[tuple[date, float]]:
    return [(START + timedelta(days=i), c) for i, c in enumerate(closes)]


def of(found: list[PatternOccurrence], pattern: str) -> list[PatternOccurrence]:
    return [o for o in found if o.pattern == pattern]


HS_TOP = [(0, 80), (15, 100), (27, 90), (42, 115), (54, 90), (66, 100), (90, 80)]
HS_INV = [(0, 120), (15, 100), (27, 110), (42, 85), (54, 110), (66, 100), (90, 120)]
DOUBLE_TOP = [(0, 80), (20, 100), (40, 85.5), (60, 100), (90, 70)]
DOUBLE_BOTTOM = [(0, 120), (20, 100), (40, 114.5), (60, 100), (90, 130)]
ASCENDING = [
    (0, 80),
    (10, 100),
    (22, 84),
    (34, 100),
    (46, 90),
    (58, 100),
    (70, 96.5),
    (90, 110),
]
DESCENDING = [
    (0, 120),
    (10, 100),
    (22, 116),
    (34, 100),
    (46, 110),
    (58, 100),
    (70, 103.5),
    (90, 90),
]
SYMMETRICAL = [
    (0, 90),
    (10, 112),
    (22, 88),
    (34, 108),
    (46, 92),
    (58, 104),
    (70, 96.4),
    (90, 110),
]


# ---- each pattern is detected and confirmed on the right date ---------------------------------


def test_head_and_shoulders_top_confirmed_on_neckline_break() -> None:
    s = series(path(HS_TOP))
    found = of(detect_patterns(s), "head_and_shoulders_top")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "down"
    assert o.stats_key == "head_and_shoulders_top"
    # Neckline 90; the first close below it is session 79 (89.17).
    assert o.confirmation_date == s[79][0]
    assert o.confirmation_close < 90 <= s[78][1]
    assert o.break_level == 90
    assert o.start_date == s[15][0] and o.end_date == s[66][0]
    assert [p.label for p in o.points] == [
        "left_shoulder",
        "trough_1",
        "head",
        "trough_2",
        "right_shoulder",
    ]
    # Measured move: head (115) to neckline (90) projected below the neckline.
    assert o.target == 65
    assert o.lines[0].label == "neckline"


def test_head_and_shoulders_inverse_confirmed() -> None:
    s = series(path(HS_INV))
    found = of(detect_patterns(s), "head_and_shoulders_inverse")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "up"
    assert o.confirmation_date == s[79][0]
    assert o.break_level == 110
    assert o.target == 135  # 110 + (110 - 85)
    assert s[78][1] <= 110 < o.confirmation_close


def test_double_top_confirmed() -> None:
    s = series(path(DOUBLE_TOP))
    found = of(detect_patterns(s), "double_top")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "down"
    assert o.confirmation_date == s[75][0]
    assert o.break_level == 85.5
    assert o.target == 71.0  # 85.5 - (100 - 85.5)


def test_double_bottom_confirmed() -> None:
    s = series(path(DOUBLE_BOTTOM))
    found = of(detect_patterns(s), "double_bottom")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "up"
    assert o.confirmation_date == s[75][0]
    assert o.target == 129.0


def test_ascending_triangle_confirmed_on_break_of_flat_top() -> None:
    s = series(path(ASCENDING))
    found = of(detect_patterns(s), "ascending_triangle")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "up"
    assert o.confirmation_date == s[76][0]
    assert abs(o.break_level - 100) < 1e-9
    assert o.target is not None and o.target > o.break_level


def test_descending_triangle_confirmed_on_break_of_flat_bottom() -> None:
    s = series(path(DESCENDING))
    found = of(detect_patterns(s), "descending_triangle")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "down"
    assert o.confirmation_date == s[76][0]
    assert abs(o.break_level - 100) < 1e-9
    assert o.target is not None and o.target < o.break_level


def test_symmetrical_triangle_takes_direction_of_its_break() -> None:
    s = series(path(SYMMETRICAL))
    found = of(detect_patterns(s), "symmetrical_triangle")
    assert len(found) == 1
    o = found[0]
    assert o.direction == "up" and o.stats_key == "symmetrical_triangle_up"
    assert o.confirmation_date >= o.known_date

    down = path(SYMMETRICAL[:-1] + [(90, 80)])
    found_down = of(detect_patterns(series(down)), "symmetrical_triangle")
    assert len(found_down) == 1
    assert found_down[0].direction == "down"
    assert found_down[0].stats_key == "symmetrical_triangle_down"


# ---- near misses are not patterns -------------------------------------------------------------


def test_unconfirmed_patterns_are_not_reported() -> None:
    # Same shapes, but the price never breaks the neckline / boundary.
    assert not of(detect_patterns(series(path(HS_TOP[:-1] + [(90, 97)]))), "head_and_shoulders_top")
    assert not of(detect_patterns(series(path(DOUBLE_TOP[:-1] + [(90, 92)]))), "double_top")
    assert not of(detect_patterns(series(path(ASCENDING[:-1] + [(90, 97)]))), "ascending_triangle")


def test_head_and_shoulders_near_misses() -> None:
    weak_head = [(0, 80), (15, 100), (27, 90), (42, 101), (54, 90), (66, 100), (90, 80)]
    lopsided = [(0, 80), (15, 100), (27, 90), (42, 130), (54, 90), (66, 115), (90, 80)]
    for wp in (weak_head, lopsided):
        assert not of(detect_patterns(series(path(wp))), "head_and_shoulders_top")


def test_double_top_near_misses() -> None:
    peaks_far_apart = [(0, 80), (20, 100), (40, 85.5), (60, 106), (90, 70)]
    shallow = [(0, 80), (20, 100), (40, 96), (60, 100), (90, 70)]
    too_close = [(0, 80), (20, 100), (25, 85.5), (28, 100), (90, 70)]
    for wp in (peaks_far_apart, shallow, too_close):
        assert not of(detect_patterns(series(path(wp))), "double_top")


def test_rectangle_and_channel_are_not_triangles() -> None:
    rectangle = [(0, 90), (10, 100), (22, 90), (34, 100), (46, 90), (58, 100), (70, 90), (90, 80)]
    channel = [(0, 80), (10, 100), (22, 90), (34, 110), (46, 100), (58, 120), (70, 110), (90, 130)]
    for wp in (rectangle, channel):
        found = detect_patterns(series(path(wp)))
        assert not [o for o in found if o.pattern.endswith("triangle")]


def test_short_history_gives_nothing() -> None:
    assert detect_patterns(series(path(HS_TOP)[: P.MIN_SESSIONS - 1])) == []
    assert detect_patterns([]) == []


# ---- no look-ahead ----------------------------------------------------------------------------


def test_pivot_is_known_only_after_its_window() -> None:
    s = series(path(HS_TOP))
    o = of(detect_patterns(s), "head_and_shoulders_top")[0]
    assert o.known_date == s[66 + P.PIVOT_WINDOW][0]
    assert o.confirmation_date >= o.known_date
    # One session short of the right shoulder being known: the pattern cannot exist yet.
    cut = detect_patterns(s[: 66 + P.PIVOT_WINDOW])
    assert not of(cut, "head_and_shoulders_top")


def test_truncating_at_confirmation_gives_the_same_detection() -> None:
    for wp, name in (
        (HS_TOP, "head_and_shoulders_top"),
        (DOUBLE_BOTTOM, "double_bottom"),
        (ASCENDING, "ascending_triangle"),
        (SYMMETRICAL, "symmetrical_triangle"),
    ):
        s = series(path(wp))
        o = of(detect_patterns(s), name)[0]
        cut = s[: o.confirmation_index + 1]
        assert of(detect_patterns(cut), name) == [o]
        # One session earlier it is not yet confirmed.
        assert not of(detect_patterns(s[: o.confirmation_index]), name)


def test_future_closes_do_not_change_an_earlier_occurrence() -> None:
    closes = path(HS_TOP)
    base = of(detect_patterns(series(closes)), "head_and_shoulders_top")[0]
    rng = random.Random(3)
    mutated = closes[: base.confirmation_index + 1] + [60 + rng.random() * 80 for _ in range(60)]
    again = of(detect_patterns(series(mutated)), "head_and_shoulders_top")
    assert again and again[0] == base


def _random_walk(seed: int, n: int) -> list[float]:
    rng = random.Random(seed)
    price = 100.0
    out = []
    for _ in range(n):
        price *= 1 + rng.gauss(0.0, 0.025)
        out.append(price)
    return out


def test_every_prefix_of_a_random_walk_agrees_with_the_full_run() -> None:
    s = series(_random_walk(11, 900))
    full = detect_patterns(s)
    assert len(full) >= 5  # the property below is only meaningful with occurrences present
    for cut in range(100, 900, 37):
        expected = [o for o in full if o.confirmation_index <= cut]
        assert detect_patterns(s[: cut + 1]) == expected, cut


def test_occurrences_are_ordered_and_do_not_reuse_a_formation() -> None:
    found = detect_patterns(series(_random_walk(5, 1500)))
    assert [o.confirmation_index for o in found] == sorted(o.confirmation_index for o in found)
    last: dict[str, int] = {}
    for o in found:
        start = (o.start_date - START).days
        assert start > last.get(o.stats_key, -1)
        last[o.stats_key] = o.confirmation_index
        assert o.start_date <= o.end_date <= o.known_date <= o.confirmation_date


def test_flat_and_bad_closes_do_not_crash() -> None:
    flat = series([10.0] * 100)
    assert detect_patterns(flat) == []
    with_gaps = series([10.0] * 30 + [0.0] * 5 + [10.0] * 30)
    assert detect_patterns(with_gaps) == []


# ---- forming shapes (R47 P6) ------------------------------------------------------------------


def test_head_and_shoulders_top_is_forming_before_its_neckline_breaks() -> None:
    # Right shoulder at 66 becomes known at 71; the neckline (90) breaks at 79. Cut at 75.
    s = series(path(HS_TOP))[:76]
    assert of(detect_patterns(s), "head_and_shoulders_top") == []
    forming = [f for f in P.forming_now(s) if f.pattern == "head_and_shoulders_top"]
    assert len(forming) == 1
    f = forming[0]
    assert f.expected == "down"
    assert f.confirm_below == 90 and f.confirm_above is None
    assert f.invalid_above == 115 and f.invalid_below is None
    assert f.known_date == s[71][0] and f.end_date == s[66][0]
    assert f.sessions_left == 71 + P.CONFIRM_WITHIN - 75
    assert f.lines and all(ln.end.date == s[75][0] for ln in f.lines)
    d = P.forming_to_dict(f)
    assert d["confirm_below"] == "90.0000" and d["invalid_above"] == "115.0000"


def test_forming_shape_resolves_as_confirmed_in_the_full_series() -> None:
    events = [
        e for e in P.forming_events(series(path(HS_TOP))) if e.pattern == "head_and_shoulders_top"
    ]
    assert [(e.known_index, e.outcome, e.outcome_index, e.direction) for e in events] == [
        (71, "confirmed", 79, "down")
    ]
    assert not [
        f for f in P.forming_now(series(path(HS_TOP))) if f.pattern == "head_and_shoulders_top"
    ]


def test_shape_without_a_break_expires_and_is_not_forming() -> None:
    drifts = series(path(HS_TOP[:-1] + [(80, 95), (120, 95)]))
    events = [e for e in P.forming_events(drifts) if e.pattern == "head_and_shoulders_top"]
    assert [(e.outcome, e.outcome_index) for e in events] == [("expired", 71 + P.CONFIRM_WITHIN)]
    assert not [f for f in P.forming_now(drifts) if f.pattern == "head_and_shoulders_top"]


def test_close_past_the_head_fails_the_shape() -> None:
    breaks_up = series(path(HS_TOP[:-1] + [(72, 95), (85, 120), (100, 125)]))
    events = [e for e in P.forming_events(breaks_up) if e.pattern == "head_and_shoulders_top"]
    assert len(events) == 1 and events[0].outcome == "failed"


def test_forming_events_on_a_prefix_never_use_later_closes() -> None:
    s = series(_random_walk(11, 900))
    full = {(e.pattern, e.known_index): e for e in P.forming_events(s)}
    assert any(e.outcome == "confirmed" for e in full.values())
    for cut in range(100, 900, 37):
        prefix = P.forming_events(s[: cut + 1])
        assert {(e.pattern, e.known_index) for e in prefix} == {k for k in full if k[1] <= cut}, cut
        for e in prefix:
            later = full[(e.pattern, e.known_index)]
            if e.outcome == "open":
                assert e.outcome_index == cut and later.outcome_index > cut
            else:
                assert e == later
