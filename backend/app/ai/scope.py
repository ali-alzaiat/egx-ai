"""Does a text name one of our companies? (R50 B8) Pure: no database, clock or model.

An answer that names none of our companies (by ticker or by name) and used no tool is general
education: it is labelled and its figures are not checked. Matching errs toward "names a
company", because that sends the answer through the normal number check (the safe direction).
"""

import re
import unicodedata
from collections.abc import Collection

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_ARABIC_FOLD = str.maketrans(
    {
        "أ": "ا",  # alef with hamza above
        "إ": "ا",  # alef with hamza below
        "آ": "ا",  # alef with madda
        "ى": "ي",  # alef maksura -> yaa
        "ة": "ه",  # taa marbuta -> haa
        "ؤ": "و",  # waw with hamza
        "ئ": "ي",  # yaa with hamza
    }
)
#: Legal-form words ("S.A.E", "Co", ...): never part of a company's identity.
_LEGAL = frozenset(
    {
        "sae", "s", "a", "e", "co", "company", "corp", "corporation", "ltd", "plc", "inc",
        "limited", "شركه", "ش", "م",
    }
)
#: Generic words dropped from a name only while two or more identifying words remain, so
#: "Talaat Moustafa Group Holding" is matched as "talaat moustafa" but "Telecom Egypt" keeps both.
_GENERIC = frozenset(
    {
        "for", "of", "the", "and", "group", "holding", "holdings", "egypt", "egyptian",
        "مصر", "المصريه", "ل", "في", "و",
    }
)
#: A single-word name shorter than this is too ambiguous to match on its own.
_MIN_SINGLE_WORD = 5
#: Words of a longer name (after filler words) that identify the company when they occur together.
_PREFIX_WORDS = 2


def normalize(text: str) -> str:
    """Lowercase, fold Arabic letter variants, drop diacritics and punctuation."""
    folded = unicodedata.normalize("NFKC", text).lower()
    folded = _TASHKEEL.sub("", folded).translate(_ARABIC_FOLD)
    return _NON_WORD.sub(" ", folded).strip()


def _significant_words(name: str) -> list[str]:
    without_parens = re.sub(r"\([^)]*\)", " ", name)
    words = [w for w in normalize(without_parens).split() if w not in _LEGAL]
    core = [w for w in words if w not in _GENERIC]
    return core if len(core) >= 2 else words


def _has_phrase(haystack: str, phrase: str) -> bool:
    return f" {phrase} " in f" {haystack} "


def _ticker_hit(text: str, ticker: str) -> bool:
    """Case-sensitive, word-boundary ticker match (so COMI is not found inside COMIX)."""
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(ticker)}(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _name_hit(normalized_text: str, name: str) -> bool:
    words = _significant_words(name)
    if not words:
        return False
    if len(words) == 1:
        return len(words[0]) >= _MIN_SINGLE_WORD and _has_phrase(normalized_text, words[0])
    return _has_phrase(normalized_text, " ".join(words)) or _has_phrase(
        normalized_text, " ".join(words[:_PREFIX_WORDS])
    )


def names_company(answer: str, tickers: Collection[str], names: Collection[str]) -> bool:
    """True when ``answer`` contains a ticker (exact case, word boundaries) or a company name.

    ``names`` are English and Arabic company names; both sides are normalised (case, Arabic
    letter variants, diacritics, punctuation, legal-form words) before comparing.
    """
    if not answer.strip():
        return False
    for ticker in tickers:
        if ticker and _ticker_hit(answer, ticker):
            return True
    normalized = normalize(answer)
    return any(name and _name_hit(normalized, name) for name in names)
