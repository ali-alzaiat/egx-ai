"""Pure tests: number guardrail, SSE formatting and key scrubbing (R49)."""

from decimal import Decimal

import pytest

from app.ai.redact import scrub
from app.ai.sse import format_event, parse_events
from app.ai.verify import collect_numbers, extract_answer_numbers, verify

TOOL = {
    "tool": "valuation",
    "data": {
        "fair_value": {"value": "123.4567", "status": "AVAILABLE"},
        "price": 100,
        "margin": 0.1234,
        "revenue": "1234567890.00",
        "pe": "12.5",
        "items": [1, 2, 3],
        "note": "Net margin 18.25% in the latest year",
        "as_of": "2026-10-30",
        "company_id": "3f2a1b1c-0000-4000-8000-123456789012",
    },
}


def check(answer: str, user_text: str = "") -> tuple[bool, list[str]]:
    result = verify(answer, [TOOL], user_text)
    return result.verified, result.unverified


def test_planted_number_is_rejected() -> None:
    ok, bad = check("The fair value is 987.65 EGP.")
    assert not ok
    assert bad == ["987.65"]


def test_exact_and_rounded_forms_are_accepted() -> None:
    assert check("Fair value is 123.4567.")[0]
    assert check("Fair value is about 123.46.")[0]
    assert check("Fair value is about 123.5.")[0]
    assert check("Fair value is about 123.")[0]
    assert check("The P/E is 12.5.")[0]


def test_rejects_a_number_just_outside_tolerance() -> None:
    # 0.5% relative tolerance and rounding at the shown decimals; 130 is neither.
    assert not check("Fair value is 130.")[0]
    assert not check("The P/E is 14.")[0]


def test_percent_and_fraction_forms() -> None:
    assert check("Margin is 12.34%.")[0]  # tool fraction 0.1234
    assert check("Margin is 12.3%.")[0]
    assert check("Net margin is 18.25%.")[0]  # tool percent inside text
    assert not check("Margin is 21%.")[0]
    assert check("Margin ratio is 0.1234.")[0]


def test_arabic_indic_digits_and_separators() -> None:
    assert check("القيمة العادلة ١٢٣٫٤٦ جنيه")[0]
    assert check("هامش الربح ١٢٫٣٤٪")[0]
    assert check("الإيرادات ١٬٢٣٤٬٥٦٧٬٨٩٠")[0]
    assert not check("القيمة العادلة ٩٨٧٫٦٥")[0]


def test_thousands_separators_and_units() -> None:
    assert check("Revenue is 1,234,567,890.")[0]
    assert check("Revenue is 1.2 bn.")[0]
    assert check("Revenue is 1.23 billion.")[0]
    assert check("الإيرادات 1.2 مليار")[0]
    assert check("Revenue is 1,234.6 million.")[0]
    assert not check("Revenue is 2.4 bn.")[0]


def test_years_dates_ordinals_and_identifiers_are_ignored() -> None:
    answer = (
        "In 2025 and 2026-10-30 (Q3, FY2025) the 52-week range and 3rd quarter:\n"
        "1. First point\n2) Second point\n"
    )
    result = verify(answer, [TOOL])
    assert result.verified
    assert result.checked == 0


def test_user_numbers_count_as_given() -> None:
    assert not check("You hold 500 shares.")[0]
    assert check("You hold 500 shares.", user_text="I own 500 shares")[0]


def test_list_lengths_count_as_figures() -> None:
    assert check("Three items were returned.")[0]  # no digits: nothing to check
    assert check("3 items were returned.")[0]


def test_sign_is_ignored_for_direction_words() -> None:
    other = {"change_pct": "-5.20"}
    assert verify("It fell 5.2%.", [other]).verified


def test_result_shape() -> None:
    result = verify("Fair value 123.46 and 555.", [TOOL])
    assert result.as_dict() == {"verified": False, "checked": 2, "unverified": ["555"]}


def test_answer_without_numbers_is_verified_with_zero_checked() -> None:
    result = verify("Data is not available.", [])
    assert result.verified and result.checked == 0


def test_extract_reads_unit_and_decimals() -> None:
    (n,) = extract_answer_numbers("EGP 1.25 bn")
    assert n.mantissa == Decimal("1.25") and n.decimals == 2 and n.value == Decimal(1_250_000_000)


def test_collect_numbers_skips_dates_and_ids() -> None:
    pool = collect_numbers(TOOL)
    assert Decimal("123.4567") in pool
    assert Decimal("2026") not in pool
    assert Decimal("3") in pool  # list length


@pytest.mark.parametrize("name", ["meta", "status", "answer", "unverified", "error", "done"])
def test_sse_round_trip(name: str) -> None:
    data = {"code": "NO_KEY", "detail": "x"} if name == "error" else {"a": 1, "text": "مرحبا"}
    frame = format_event(name, data)
    assert frame.startswith(f"event: {name}\ndata: ")
    assert frame.endswith("\n\n")
    assert parse_events(frame) == [(name, data)]


def test_sse_frame_cannot_be_split_by_model_text() -> None:
    frame = format_event("answer", {"text": "line1\n\nevent: error\ndata: {}"})
    assert frame.count("\n\n") == 1  # only the terminator
    assert len(parse_events(frame)) == 1


def test_sse_serializes_decimal_and_rejects_unknown_names() -> None:
    assert '"1.50"' in format_event("done", {"cost_usd": Decimal("1.50")})
    with pytest.raises(ValueError):
        format_event("custom", {})
    with pytest.raises(ValueError):
        format_event("error", {"code": "SOMETHING_ELSE", "detail": ""})


def test_scrub_removes_exact_secret_and_key_shapes() -> None:
    secret = "sk-proj-ABCDEF1234567890"
    text = (
        f"Incorrect API key provided: {secret}. "
        "url=https://x/?key=AIzaSyA1B2C3D4E5F6 Bearer abcdef123456"
    )
    out = scrub(text, secret)
    assert secret not in out and "AIzaSy" not in out and "abcdef123456" not in out
