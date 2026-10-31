"""Number guardrail (R49 A3): every figure in an answer must trace to a tool result. Pure.

``verify(answer, tool_results, user_text)`` extracts the numbers an answer states and checks
each against every number found in this turn's tool results (and the user's own message).
It is a check on the model's wording, not financial math: a figure passes only when a tool
returned it, allowing for display rounding and percent <-> fraction (12% vs 0.12).

Accepted forms: Western and Arabic-Indic digits, ``,`` / ``٬`` thousands, ``٫`` decimals,
``%`` / ``٪``, and the units k, m, mn, bn, b, thousand, million, billion, trillion and the
Arabic ألف, مليون, مليار, تريليون. Sign is ignored (the model may say "fell 5.2%" for -5.2).
Ignored on purpose: years 1900-2100 written alone, dates and times, list ordinals ("1."),
ordinal suffixes (3rd), identifiers like Q3 / FY2025 and hyphenated compounds (52-week).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

# Relative tolerance on top of display rounding (contract: "or 0.5% relative").
RELATIVE_TOLERANCE = Decimal("0.005")

_ARABIC_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_ARABIC_DIGITS.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})
_ARABIC_DIGITS[ord("٫")] = "."
_ARABIC_DIGITS[ord("٬")] = ","
_ARABIC_DIGITS[ord("٪")] = "%"
_ARABIC_DIGITS[ord("−")] = "-"

_SCALES = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "ألف": Decimal(1_000),
    "الف": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "مليون": Decimal(1_000_000),
    "b": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
    "مليار": Decimal(1_000_000_000),
    "trillion": Decimal(1_000_000_000_000),
    "تريليون": Decimal(1_000_000_000_000),
}

_NOISE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}(?:[T ]\d{1,2}:\d{2}(?::\d{2})?)?"  # ISO dates / datetimes
    r"|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"  # 30/10/2026
    r"|\d{4}/\d{2,4}"  # fiscal 2025/26
    r"|\d{1,2}:\d{2}(?::\d{2})?"  # clock times
)

_NUMBER = re.compile(
    r"(?<![A-Za-z_\d.])"
    r"(?P<num>\d{1,3}(?:,\d{3})++(?:\.\d++)?+|\d++(?:\.\d++)?+)"
    r"(?:\s?(?P<unit>%|percent\b|pct\b"
    r"|(?:trillion|billion|million|thousand|bn|mn|k|m|b)(?![A-Za-z])"
    r"|مليون|مليار|تريليون|ألف|الف))?",
    re.IGNORECASE,
)
_HYPHEN_COMPOUND = re.compile(r"-[A-Za-z]")
_ORDINAL_SUFFIX = re.compile(r"(?:st|nd|rd|th)\b", re.IGNORECASE)
_LIST_MARKER_PREFIX = re.compile(r"^\s*(?:[-*•#>]+\s*)?$")
_ISO_DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].*)?$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@dataclass(frozen=True)
class AnswerNumber:
    """A figure the answer states: ``raw`` as written, magnitude, shown decimals, scale."""

    raw: str
    mantissa: Decimal
    decimals: int
    scale: Decimal
    is_percent: bool

    @property
    def value(self) -> Decimal:
        return self.mantissa * self.scale


@dataclass(frozen=True)
class VerifyResult:
    verified: bool
    checked: int
    unverified: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"verified": self.verified, "checked": self.checked, "unverified": self.unverified}


def normalize_digits(text: str) -> str:
    """Arabic-Indic digits and separators to their Western forms."""
    return text.translate(_ARABIC_DIGITS)


def _to_decimal(num: str) -> Decimal | None:
    try:
        return Decimal(num.replace(",", ""))
    except InvalidOperation:
        return None


def extract_answer_numbers(text: str) -> list[AnswerNumber]:
    """The checkable figures in ``text`` (see the module docstring for what is ignored)."""
    cleaned = _NOISE.sub(lambda m: " " * len(m.group(0)), normalize_digits(text))
    found: list[AnswerNumber] = []
    for m in _NUMBER.finditer(cleaned):
        num = m.group("num")
        unit = (m.group("unit") or "").lower()
        after = cleaned[m.end() :]
        before_line = cleaned[cleaned.rfind("\n", 0, m.start()) + 1 : m.start()]
        if _HYPHEN_COMPOUND.match(after) or _ORDINAL_SUFFIX.match(after):
            continue
        if (
            not unit
            and after[:1] in (".", ")")
            and after[1:2] in (" ", "\t")
            and _LIST_MARKER_PREFIX.match(before_line)
        ):
            continue  # "1. First point"
        mantissa = _to_decimal(num)
        if mantissa is None:
            continue
        is_percent = unit in ("%", "percent", "pct")
        scale = _SCALES.get(unit, Decimal(1))
        decimals = len(num.split(".")[1]) if "." in num else 0
        if (
            not unit
            and decimals == 0
            and "," not in num
            and len(num) == 4
            and 1900 <= int(num) <= 2100
        ):
            continue  # a year
        found.append(
            AnswerNumber(
                raw=m.group(0).strip(),
                mantissa=mantissa,
                decimals=decimals,
                scale=scale,
                is_percent=is_percent,
            )
        )
    return found


def _scan_plain(text: str) -> list[Decimal]:
    """Every number in a tool/user string, as magnitudes (no unit scaling, no filtering)."""
    out: list[Decimal] = []
    for m in re.finditer(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", normalize_digits(text)):
        value = _to_decimal(m.group(0))
        if value is not None:
            out.append(value)
    return out


def collect_numbers(*sources: Any) -> list[Decimal]:
    """All numbers in JSON-like tool results (and strings): magnitudes, plus list lengths.

    Dates and ids are skipped; numbers inside free text (reasons, notes) are included.
    """
    pool: list[Decimal] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, int | Decimal):
            pool.append(abs(Decimal(node)))
        elif isinstance(node, float):
            if node == node and node not in (float("inf"), float("-inf")):
                pool.append(abs(Decimal(str(node))))
        elif isinstance(node, str):
            if _ISO_DATE_FULL.match(node) or _UUID.match(node):
                return
            pool.extend(_scan_plain(node))
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in ("id", "company_id", "period_id"):
                    continue
                walk(value)
        elif isinstance(node, list | tuple):
            pool.append(Decimal(len(node)))
            for item in node:
                walk(item)

    for source in sources:
        walk(source)
    return pool


def _close(candidate: Decimal, target: Decimal, tolerance: Decimal) -> bool:
    diff = abs(candidate - target)
    if diff <= tolerance:
        return True
    return candidate != 0 and diff / abs(candidate) <= RELATIVE_TOLERANCE


def _matches(number: AnswerNumber, pool: Iterable[Decimal]) -> bool:
    half = Decimal("0.5") * (Decimal(10) ** -number.decimals)
    scaled_tol = half * number.scale
    for x in pool:
        if _close(x, number.value, scaled_tol):
            return True
        if number.scale != 1 and _close(x, number.mantissa, half):
            return True  # the tool already reports in that unit
        if number.is_percent and _close(x * 100, number.value, scaled_tol):
            return True  # tool fraction 0.12 vs answer 12%
    return False


def verify(answer: str, tool_results: Iterable[Any], user_text: str = "") -> VerifyResult:
    """Check every figure of ``answer`` against the tool results and the user's message."""
    pool = collect_numbers(list(tool_results), user_text)
    numbers = extract_answer_numbers(answer)
    unverified: list[str] = []
    for number in numbers:
        if not _matches(number, pool) and number.raw not in unverified:
            unverified.append(number.raw)
    return VerifyResult(verified=not unverified, checked=len(numbers), unverified=unverified)
