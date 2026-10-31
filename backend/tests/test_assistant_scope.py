"""R50 B8: does a text name one of our companies? Pure matching on tickers and EN/AR names."""

import pytest

from app.ai.scope import names_company, normalize

TICKERS = {"COMI", "SWDY", "TMGH"}
NAMES = [
    "Commercial International Bank (Egypt) S.A.E",
    "البنك التجاري الدولي (مصر)",
    "Elsewedy Electric Co. S.A.E.",
    "Talaat Moustafa Group Holding",
    "Telecom Egypt",
    "Edita Food Industries",
    "Ezz",
    None,
    "",
]
CLEAN = [n for n in NAMES if n]


def check(answer: str) -> bool:
    return names_company(answer, TICKERS, CLEAN)


@pytest.mark.parametrize(
    "answer",
    [
        "COMI closed higher.",
        "Both COMI, and SWDY rose.",
        "(TMGH) is a developer.",
        "tickers: COMI/SWDY",
        "Looking at COMI.",
    ],
)
def test_ticker_match_is_word_bounded_and_case_sensitive(answer: str) -> None:
    assert check(answer) is True


@pytest.mark.parametrize(
    "answer",
    [
        "COMIX is a made-up word.",  # longer word containing the ticker
        "xCOMI is not it either.",
        "COMI_2 and COMI9 are other symbols.",
        "comi is lower case, not a ticker mention.",
        "A P/E ratio compares price with earnings.",
        "",
        "   ",
    ],
)
def test_text_without_a_whole_ticker_is_not_a_company(answer: str) -> None:
    assert check(answer) is False


@pytest.mark.parametrize(
    "answer",
    [
        "Commercial International Bank reported growth.",
        "commercial international bank egypt s.a.e is large",  # case and punctuation ignored
        "The Elsewedy Electric group makes cables.",
        "Talaat Moustafa is a property developer.",
        "Telecom Egypt owns the network.",
        "Edita Food Industries makes snacks.",
        "البنك التجاري الدولي أعلن نتائجه.",
        "البنك  التجاري  الدولي",  # extra spaces
    ],
)
def test_company_names_match_in_english_and_arabic(answer: str) -> None:
    assert check(answer) is True


def test_arabic_letter_variants_and_diacritics_are_folded() -> None:
    assert names_company("البَنْك التِّجَارِيّ الدّولي", set(), ["البنك التجاري الدولي"]) is True
    assert normalize("أإآ ة ى") == normalize("ااا ه ي")
    assert names_company("البنك التجاري الدولي", set(), ["البنك التجارى الدولى"]) is True


@pytest.mark.parametrize(
    "answer",
    [
        "Banks earn interest on loans.",  # a generic word from a name is not enough
        "Telecom companies are capital intensive.",  # 'telecom' alone is not the company
        "Electric utilities are regulated.",
        "Food companies face commodity risk.",
        "Ezz is a short word.",  # a single short word is too ambiguous to match
    ],
)
def test_generic_words_from_a_name_do_not_name_a_company(answer: str) -> None:
    assert check(answer) is False


def test_empty_inputs() -> None:
    assert names_company("COMI", set(), []) is False
    assert names_company("COMI", {"", "COMI"}, [""]) is True
    assert names_company("anything", {"COMI"}, [""]) is False
