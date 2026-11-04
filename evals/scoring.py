"""Scoring functions for the evals. All pure: they take plain data and return plain results.

Nothing here calls a model, the pipeline or search(), so every function can be tested
with hand-made inputs. Two groups:
  1. Deterministic: compare the product IDs and the extracted filter with the CSV row.
  2. Behavioral: score one TurnResult against one line of datasets/behavioral.jsonl.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas import Product, SearchSpec, TurnResult
from evals.ground_truth import expected_ids, passes_filter, sort_value

# ---------------------------------------------------------------------------
# Deterministic set
# ---------------------------------------------------------------------------


def precision_recall_f1(expected: set[int], returned: set[int]) -> tuple[float, float, float]:
    """Precision, recall and F1 of the returned IDs against the expected IDs.

    Both empty is a correct answer ("nothing matches" and the agent found nothing): 1.0.
    Exactly one empty is a miss or a false alarm: 0.0.
    """
    if not expected and not returned:
        return 1.0, 1.0, 1.0
    if not expected or not returned:
        return 0.0, 0.0, 0.0
    hits = len(expected & returned)
    precision = hits / len(returned)
    recall = hits / len(expected)
    if precision + recall == 0:
        return precision, recall, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def top_k_is_correct(spec: SearchSpec, catalog: list[Product], returned_ids: list[int]) -> bool:
    """True when the returned list is a right answer for a top_k row.

    Products that tie on the sort value are equally right, so we do not demand one
    particular tie order. A list is right when:
      - it has the expected length and no repeated product,
      - every product passes the row's filter,
      - its sequence of sort values equals the expected sequence of sort values.
    """
    by_id = {product.id: product for product in catalog}
    expected = expected_ids(spec, catalog)
    if len(returned_ids) != len(expected) or len(set(returned_ids)) != len(returned_ids):
        return False
    if any(i not in by_id or not passes_filter(by_id[i], spec) for i in returned_ids):
        return False
    expected_values = [sort_value(by_id[i], spec) for i in expected]
    returned_values = [sort_value(by_id[i], spec) for i in returned_ids]
    return expected_values == returned_values


@dataclass
class RetrievalScores:
    precision: float
    recall: float
    f1: float
    top_k_ok: bool | None  # None on rows without top_k


def score_retrieval(
    expected_spec: SearchSpec,
    catalog: list[Product],
    searches: list[SearchSpec],
    returned_ids: list[int],
) -> RetrievalScores:
    """Score the IDs one query returned (all its searches together) against the CSV row.

    Two rules beyond plain P/R/F1:
    - A row where nothing matches earns its 1.0 for returning nothing only if a search
      with the row's category actually ran. A parser that just asks a question gets 0.
    - On a top_k row whose answer is correct (see top_k_is_correct), tied products count
      as hits, so F1 is 1.0.
    """
    expected = set(expected_ids(expected_spec, catalog))
    returned = set(returned_ids)

    top_k_ok = None
    if expected_spec.top_k is not None:
        top_k_ok = top_k_is_correct(expected_spec, catalog, returned_ids)
        if top_k_ok:
            expected = returned

    if not expected and not returned:
        search_ran = any(search.category == expected_spec.category for search in searches)
        if not search_ran:
            return RetrievalScores(0.0, 0.0, 0.0, top_k_ok)

    precision, recall, f1 = precision_recall_f1(expected, returned)
    return RetrievalScores(precision, recall, f1, top_k_ok)


def _same_number(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 0.001


def filter_matches(expected: SearchSpec, got: SearchSpec | None) -> bool:
    """True when every CSV column of the extracted spec equals the expected one.

    Keywords are not compared: the CSV has no keywords column. `got` is None when the
    parser produced no search at all, which is a mismatch.
    """
    if got is None:
        return False
    return (
        got.category == expected.category
        and _same_number(got.price_min, expected.price_min)
        and _same_number(got.price_max, expected.price_max)
        and _same_number(got.rating_min, expected.rating_min)
        and got.sort_by == expected.sort_by
        and got.order == expected.order
        and got.top_k == expected.top_k
    )


# ---------------------------------------------------------------------------
# Reply language
# ---------------------------------------------------------------------------

# Short lists of common words. A word in both languages is left out of both lists
# ("a", "no", "me"), so each hit points to one language.
SPANISH_STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "y", "en", "que", "un", "una", "unos", "unas",
    "por", "para", "con", "es", "se", "lo", "al", "su", "sus", "mi", "tu", "como", "pero",
    "más", "hay", "puedo", "puedes", "sobre", "está", "son", "muy", "también", "sin",
    "tenemos", "vendemos", "siento", "ayudarte", "ayudar", "busco", "quieres", "te",
    "ofrecemos", "lamentablemente", "lamento", "tienda", "producto", "productos",
    "disponible", "disponibles", "aquí", "algo", "otro", "otra", "estos", "estas", "este",
    "esta", "esto", "qué", "cómo", "hola", "gracias", "presupuesto", "precio", "precios",
    "opciones", "encontré", "ni", "nos", "ya", "sí",
}  # fmt: skip
ENGLISH_STOPWORDS = {
    "the", "an", "and", "or", "of", "to", "in", "is", "are", "for", "with", "you", "your",
    "it", "that", "this", "we", "can", "on", "not", "have", "but", "do", "be", "at", "by",
    "our", "if", "what", "any", "i", "here", "there", "from", "so", "help", "sorry",
}  # fmt: skip

HEBREW_FIRST = "֐"
HEBREW_LAST = "׿"


def whole_word(phrase: str) -> str:
    """A regex that matches the phrase only when it is not glued to other letters or digits.

    So the title "Realme X" does not match inside "Realme XT".
    """
    return rf"(?<!\w){re.escape(phrase)}(?!\w)"


def remove_titles(text: str, titles: list[str]) -> str:
    """Blank out whole product titles (longest first) so their words are not counted."""
    for title in sorted(set(titles), key=len, reverse=True):
        text = re.sub(whole_word(title), " ", text)
    return text


def remove_title_words(text: str, titles: list[str]) -> str:
    """Blank out each single word of the titles, for replies that shorten a title.

    "מצאתי Gucci Bloom" names the product without its full title. Case matters, so
    "De" from a title is blanked but the Spanish "de" is not.
    """
    words = {word for title in titles for word in re.findall(r"\w+", title)}
    for word in sorted(words, key=len, reverse=True):
        text = re.sub(whole_word(word), " ", text)
    return text


def detect_language(reply: str, shown_titles: list[str]) -> str:
    """Return "he", "es" or "en". No detection library; the rules are from CLAUDE.md.

    The shown titles, whole and word by word, are removed first.
    he: most of the remaining letters are in Hebrew script.
    es: more Spanish than English stopwords (each ¿ and ¡ counts as a Spanish hit).
    Anything else is "en".
    """
    text = remove_title_words(remove_titles(reply, shown_titles), shown_titles)
    letters = [char for char in text if char.isalpha()]
    hebrew = [char for char in letters if HEBREW_FIRST <= char <= HEBREW_LAST]
    if letters and len(hebrew) > len(letters) / 2:
        return "he"

    # [^\W\d_]+ is "a run of letters", and it keeps accents like the ó in "dólares".
    words = re.findall(r"[^\W\d_]+", text.lower())
    spanish_hits = sum(1 for word in words if word in SPANISH_STOPWORDS)
    spanish_hits += text.count("¿") + text.count("¡")
    english_hits = sum(1 for word in words if word in ENGLISH_STOPWORDS)
    return "es" if spanish_hits > english_hits else "en"


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------

# A number: "1,234.56" (comma thousands) or "1500" or "4.98".
NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
CURRENCY_WORDS = r"(?:דולרים|דולר|dólares|dólar|dolares|dolar|dollars|dollar|bucks|USD)"
# Spaces and the invisible left-to-right / right-to-left marks that Hebrew text can carry.
SEPARATOR = r"[\s‎‏؜‪-‮⁦-⁩]*"
# "$30", "$ 30".
AMOUNT_AFTER_SIGN = re.compile(rf"\${SEPARATOR}({NUMBER})")
# "USD 777", "דולר 777".
AMOUNT_AFTER_WORD = re.compile(rf"{CURRENCY_WORDS}{SEPARATOR}({NUMBER})", re.IGNORECASE)
# "30$", "30 dólares", "1500 דולר". A "$" that starts the next amount ("30 $40") is not
# the sign for 30, hence the (?!...\d).
AMOUNT_BEFORE_WORD = re.compile(
    rf"({NUMBER}){SEPARATOR}(?:\$(?!{SEPARATOR}\d)|{CURRENCY_WORDS}\b)", re.IGNORECASE
)
AMOUNT_PATTERNS = [AMOUNT_AFTER_SIGN, AMOUNT_AFTER_WORD, AMOUNT_BEFORE_WORD]
PLAIN_NUMBER = re.compile(NUMBER)
# "10k", "2 grand".
THOUSANDS = re.compile(rf"({NUMBER})\s*(?:k|grand)\b", re.IGNORECASE)
BOUND_ALLOWANCE = 0.01


def to_float(text: str) -> float:
    return float(text.replace(",", ""))


def find_dollar_amounts(text: str) -> list[float]:
    """Every scored amount: after a "$", before a "$", or next to a currency word."""
    amounts = []
    for pattern in AMOUNT_PATTERNS:
        amounts += [to_float(match) for match in pattern.findall(text)]
    return amounts


def find_other_numbers(text: str) -> list[str]:
    """Numbers that are not dollar amounts (counts, ratings). These are printed, never scored."""
    for pattern in AMOUNT_PATTERNS:
        text = pattern.sub(" ", text)
    return PLAIN_NUMBER.findall(text)


def numbers_in_user_text(text: str) -> list[float]:
    """Numbers a user wrote: digits, "10k" or "2 grand" as thousands, and "a grand" as 1000."""
    numbers = [to_float(match) * 1000 for match in THOUSANDS.findall(text)]
    text = THOUSANDS.sub(" ", text)
    numbers += [to_float(match) for match in PLAIN_NUMBER.findall(text)]
    # "a grand" with no number in front of it.
    if re.search(r"\bgrand\b", text, re.IGNORECASE):
        numbers.append(1000.0)
    return numbers


def find_unshown_titles(
    text: str, shown_titles: list[str], catalog_titles: list[str]
) -> tuple[list[str], list[str]]:
    """Catalog titles that appear in the text although their product was not shown.

    Returns (scored, unscored). One-word titles ("Apple", "Water", "Sunglasses") are
    also ordinary words, so a hit on one is not scored, only returned to be printed.
    Shown titles are blanked out first (whole words only), so a short unshown title that
    is part of a longer shown title is not a false alarm. Matching is exact and
    case-sensitive, because titles must stay exactly as in the catalog.
    """
    text = remove_titles(text, shown_titles)
    scored, unscored = [], []
    for title in sorted(set(catalog_titles) - set(shown_titles)):
        if re.search(whole_word(title), text):
            (unscored if len(title.split()) == 1 else scored).append(title)
    return scored, unscored


@dataclass
class GroundingResult:
    bad_titles: list[str] = field(default_factory=list)
    bad_amounts: list[float] = field(default_factory=list)
    # Not scored. Printed beside the reply for Or to read.
    other_numbers: list[str] = field(default_factory=list)
    unscored_title_hits: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.bad_titles and not self.bad_amounts


def shown_products(result: TurnResult) -> list[Product]:
    """The products with a card in this turn."""
    return [product for outcome in result.outcomes for product in outcome.shown]


def check_grounding(
    result: TurnResult,
    user_turns: list[str],
    catalog_titles: list[str],
    shown: list[Product] | None = None,
) -> GroundingResult:
    """Score a reply with the Grounding rule in CLAUDE.md.

    `shown` is every product shown anywhere in the conversation, because a follow-up reply
    may talk about a product from an earlier turn. If not given, this turn's cards are used.
    Titles: no catalog title outside the shown products.
    Dollar amounts must be a shown price, a number from any user turn, or a bound of the
    current search (price_min or price_max, within 0.01 because "under $20" is stored as 19.99).
    """
    if shown is None:
        shown = shown_products(result)
    shown_titles = [product.title for product in shown]

    allowed_exact = [product.price for product in shown]
    for turn in user_turns:
        allowed_exact += numbers_in_user_text(turn)
    bounds = []
    for outcome in result.outcomes:
        for bound in (outcome.spec.price_min, outcome.spec.price_max):
            if bound is not None:
                bounds.append(bound)

    # Titles can contain digits, so blank them out before reading amounts and numbers.
    text = remove_titles(result.reply, shown_titles)

    bad_amounts = []
    for amount in find_dollar_amounts(text):
        # round(..., 2) keeps float noise (1399.99 - 1399.98 = 0.01000000000000227) out of the test.
        is_exact = any(round(abs(amount - value), 2) == 0 for value in allowed_exact)
        is_bound = any(round(abs(amount - bound), 2) <= BOUND_ALLOWANCE for bound in bounds)
        if not is_exact and not is_bound:
            bad_amounts.append(amount)

    bad_titles, unscored_hits = find_unshown_titles(result.reply, shown_titles, catalog_titles)
    return GroundingResult(
        bad_titles=bad_titles,
        bad_amounts=bad_amounts,
        other_numbers=find_other_numbers(text),
        unscored_title_hits=unscored_hits,
    )


# ---------------------------------------------------------------------------
# Behavioral set
# ---------------------------------------------------------------------------


def score_intent(result: TurnResult, case: dict[str, Any]) -> bool:
    return result.parsed.intent == case["expected_intent"]


def score_mode(result: TurnResult, case: dict[str, Any]) -> bool:
    """expected_mode is null for every intent but product_search, and the parser must match that."""
    return result.parsed.mode == case["expected_mode"]


def shown_categories(result: TurnResult) -> set[str]:
    return {product.category for product in shown_products(result)}


def score_category(result: TurnResult, case: dict[str, Any]) -> bool | None:
    """The categories of the cards shown this turn.

    all: they equal the expected categories (a missing or an extra category fails).
    any: they are a non-empty part of the expected categories.
    None (not applicable) when the case expects no categories.
    """
    expected = set(case["expected_categories"])
    if not expected:
        return None
    shown = shown_categories(result)
    if case["category_match"] == "any":
        return bool(shown) and shown <= expected
    return shown == expected


def loosened_fields(result: TurnResult) -> set[str]:
    return {name for outcome in result.outcomes for name in outcome.loosened}


def score_fallback(result: TurnResult, case: dict[str, Any]) -> bool:
    """The loosened fields must be exactly the expected one, or none when null is expected."""
    expected = {case["expect_fallback"]} if case["expect_fallback"] else set()
    return loosened_fields(result) == expected


def score_language(
    result: TurnResult, case: dict[str, Any], shown: list[Product] | None = None
) -> bool | None:
    """None (not applicable) when the case sets no expected_language."""
    expected = case.get("expected_language")
    if not expected:
        return None
    if shown is None:
        shown = shown_products(result)
    return detect_language(result.reply, [product.title for product in shown]) == expected


@dataclass
class CaseScores:
    intent_ok: bool
    mode_ok: bool
    category_ok: bool | None
    fallback_ok: bool
    language_ok: bool | None
    grounding: GroundingResult


def score_case(
    result: TurnResult,
    case: dict[str, Any],
    user_turns: list[str],
    catalog_titles: list[str],
    shown: list[Product] | None = None,
) -> CaseScores:
    """Score the last turn of a conversation. `shown` is every product shown in any turn."""
    return CaseScores(
        intent_ok=score_intent(result, case),
        mode_ok=score_mode(result, case),
        category_ok=score_category(result, case),
        fallback_ok=score_fallback(result, case),
        language_ok=score_language(result, case, shown),
        grounding=check_grounding(result, user_turns, catalog_titles, shown),
    )
