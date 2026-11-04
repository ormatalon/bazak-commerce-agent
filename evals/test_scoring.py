"""Scoring tests. They use hand-made TurnResult objects and the sample catalog: no pipeline, no model."""

import json
from pathlib import Path

import pytest

from app.schemas import (
    ConversationState,
    ParsedRequest,
    Product,
    SearchOutcome,
    SearchSpec,
    TurnResult,
)
from evals import scoring
from evals.scoring import (
    ENGLISH_STOPWORDS,
    SPANISH_STOPWORDS,
    check_grounding,
    detect_language,
    exact_match,
    filter_matches,
    precision_recall_f1,
    score_case,
)

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"


@pytest.fixture(scope="module")
def catalog() -> dict[int, Product]:
    with SAMPLE.open(encoding="utf-8") as file:
        return {item["id"]: Product.model_validate(item) for item in json.load(file)}


@pytest.fixture(scope="module")
def titles(catalog) -> list[str]:
    return [product.title for product in catalog.values()]


def make_result(
    reply: str,
    shown: list[Product],
    spec: SearchSpec | None = None,
    loosened: list[str] | None = None,
    intent: str = "product_search",
    mode: str | None = "new",
) -> TurnResult:
    """A fake TurnResult with one outcome, which is all the scoring reads."""
    outcome = SearchOutcome(
        spec=spec or SearchSpec(),
        products=shown,
        shown=shown,
        loosened=loosened or [],  # type: ignore[arg-type]
    )
    return TurnResult(
        parsed=ParsedRequest(intent=intent, mode=mode),  # type: ignore[arg-type]
        outcomes=[outcome],
        reply=reply,
        state=ConversationState(),
    )


# ---------------------------------------------------------------------------
# Deterministic scoring
# ---------------------------------------------------------------------------


def test_precision_recall_f1_perfect():
    assert precision_recall_f1({1, 2, 3}, {1, 2, 3}) == (1.0, 1.0, 1.0)


def test_precision_recall_f1_partial():
    precision, recall, f1 = precision_recall_f1({1, 2, 3, 4}, {3, 4, 5, 6})
    assert precision == 0.5
    assert recall == 0.5
    assert f1 == 0.5


def test_precision_recall_f1_no_overlap_is_zero():
    assert precision_recall_f1({1, 2}, {3}) == (0.0, 0.0, 0.0)


def test_both_empty_scores_one():
    assert precision_recall_f1(set(), set()) == (1.0, 1.0, 1.0)


def test_one_empty_scores_zero():
    assert precision_recall_f1(set(), {1}) == (0.0, 0.0, 0.0)
    assert precision_recall_f1({1}, set()) == (0.0, 0.0, 0.0)


def test_exact_match_needs_same_order():
    assert exact_match([6, 7, 9], [6, 7, 9])
    assert not exact_match([6, 7, 9], [7, 6, 9])
    assert not exact_match([6, 7, 9], [6, 7])


def test_filter_matches_compares_every_csv_column():
    expected = SearchSpec(category="laptops", price_max=1500)
    assert filter_matches(expected, SearchSpec(category="laptops", price_max=1500, keywords=["pc"]))
    assert not filter_matches(expected, SearchSpec(category="laptops", price_max=1499.99))
    assert not filter_matches(expected, SearchSpec(category="tablets", price_max=1500))
    assert not filter_matches(expected, SearchSpec(category="laptops", price_max=1500, rating_min=4))
    assert not filter_matches(expected, SearchSpec(category="laptops", price_max=1500, top_k=3))
    assert not filter_matches(expected, None)


def test_filter_matches_checks_sort_and_order():
    expected = SearchSpec(category="tablets", sort_by="price", order="asc", top_k=1)
    assert filter_matches(expected, SearchSpec(category="tablets", sort_by="price", order="asc", top_k=1))
    assert not filter_matches(expected, SearchSpec(category="tablets", sort_by="price", order="desc", top_k=1))


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def test_rating_written_as_a_price_fails(catalog, titles):
    huawei = catalog[80]  # price 1399.99, rating 4.98
    result = make_result("The Huawei Matebook X Pro costs $1,399.99 and is great at $4.98.", [huawei])
    grounding = check_grounding(result, ["laptops"], titles)
    assert grounding.bad_amounts == [4.98]
    assert not grounding.ok


def test_shown_price_passes(catalog, titles):
    result = make_result("Huawei Matebook X Pro is $1,399.99.", [catalog[80]])
    assert check_grounding(result, ["laptops"], titles).ok


def test_a_grand_in_the_user_turn_allows_1000(catalog, titles):
    result = make_result("Nothing fits under $1,000, here is the closest.", [catalog[81]])
    assert check_grounding(result, ["I have about a grand to spend"], titles).ok


def test_1000_fails_without_the_user_saying_it(catalog, titles):
    # The same reply as above, but the user never mentioned an amount.
    result = make_result("Nothing fits under $1,000, here is the closest.", [catalog[81]])
    assert check_grounding(result, ["laptops please"], titles).bad_amounts == [1000.0]


def test_10k_and_2_grand_in_the_user_turn(catalog, titles):
    result = make_result("Up to $10,000 and also $2,000.", [catalog[81]])
    assert check_grounding(result, ["under 10k, or maybe 2 grand"], titles).ok


def test_bound_allowance_of_one_cent(catalog, titles):
    spec = SearchSpec(category="laptops", price_max=1399.98)
    result = make_result("Laptops up to $1,399.99.", [catalog[81]], spec=spec)
    assert check_grounding(result, ["laptops"], titles).ok


def test_two_cents_from_a_bound_fails(catalog, titles):
    spec = SearchSpec(category="laptops", price_max=1399.98)
    result = make_result("Laptops up to $1,400.00.", [catalog[81]], spec=spec)
    assert check_grounding(result, ["laptops"], titles).bad_amounts == [1400.0]


def test_stored_under_20_bound_allows_20(catalog, titles):
    # "under $20" is stored as 19.99, and the reply may say $20.
    spec = SearchSpec(price_max=19.99)
    result = make_result("Nothing under $20.", [catalog[81]], spec=spec)
    assert check_grounding(result, ["under $20"], titles).ok


def test_currency_word_amount_not_from_prices_or_user_fails(catalog, titles):
    result = make_result("Las gafas cuestan 30 dólares.", [catalog[154]])  # 154 costs 29.99
    grounding = check_grounding(result, ["Busco gafas de sol"], titles)
    assert grounding.bad_amounts == [30.0]


def test_currency_word_amount_from_the_user_turn_passes(catalog, titles):
    result = make_result("Mostrando gafas por menos de 30 dólares.", [catalog[154]])
    assert check_grounding(result, ["Busco gafas de sol por menos de 30 dólares"], titles).ok


def test_hebrew_currency_word_follows_the_same_rule(catalog, titles):
    reply = "הנה מחשבים עד 1500 דולר, אבל יש גם אחד ב-900 דולר"
    result = make_result(reply, [catalog[80]], spec=SearchSpec(price_max=1500))
    grounding = check_grounding(result, ["מחשבים ניידים עד 1500 דולר"], titles)
    assert grounding.bad_amounts == [900.0]


def test_dollar_sign_after_the_number(catalog, titles):
    result = make_result("It costs 30$ or 29.99$.", [catalog[154]])
    assert check_grounding(result, ["hi"], titles).bad_amounts == [30.0]


def test_comma_after_an_amount_is_not_part_of_it(catalog, titles):
    result = make_result("Prices: $29.99, $24.99 and $19.99.", [catalog[154], catalog[155], catalog[157]])
    assert check_grounding(result, ["sunglasses"], titles).ok


def test_counts_are_not_scored_but_are_collected(catalog, titles):
    shown = [catalog[80], catalog[81], catalog[82]]
    reply = "We have 5 laptops; here are 3: Huawei Matebook X Pro, Lenovo Yoga 920, New DELL XPS 13 9300 Laptop."
    grounding = check_grounding(make_result(reply, shown), ["laptops"], titles)
    assert grounding.ok
    assert grounding.other_numbers == ["5", "3"]  # the digits inside the titles are not listed


def test_unshown_title_fails(catalog, titles):
    result = make_result("Also consider the Lenovo Yoga 920.", [catalog[80]])
    assert check_grounding(result, ["laptops"], titles).bad_titles == ["Lenovo Yoga 920"]


def test_shown_title_passes(catalog, titles):
    result = make_result("Try the Lenovo Yoga 920.", [catalog[81]])
    assert check_grounding(result, ["laptops"], titles).ok


def test_title_is_not_matched_inside_a_longer_title(catalog, titles):
    # "Realme X" is a title, but the reply names "Realme XT", which is shown.
    result = make_result("The Realme XT is a good pick.", [catalog[130]])
    assert check_grounding(result, ["phones"], titles).ok


def test_unshown_short_title_inside_a_longer_unshown_title_is_found(catalog, titles):
    result = make_result("The Realme XT is a good pick.", [catalog[80]])
    assert check_grounding(result, ["phones"], titles).bad_titles == ["Realme XT"]


def test_only_shown_products_count_not_all_products(catalog, titles):
    # Product 81 matched the search but was not shown, so naming it is not grounded.
    spec = SearchSpec(category="laptops")
    outcome = SearchOutcome(spec=spec, products=[catalog[80], catalog[81]], shown=[catalog[80]])
    result = TurnResult(
        parsed=ParsedRequest(intent="product_search", mode="new"),
        outcomes=[outcome],
        reply="Lenovo Yoga 920 is cheaper.",
        state=ConversationState(),
    )
    assert check_grounding(result, ["laptops"], titles).bad_titles == ["Lenovo Yoga 920"]


def test_reply_with_no_numbers_or_titles_is_grounded(titles):
    result = make_result("Sorry, we don't carry flights.", [], intent="off_catalog", mode=None)
    assert check_grounding(result, ["A flight to Tokyo"], titles).ok


# ---------------------------------------------------------------------------
# Reply language
# ---------------------------------------------------------------------------


def test_hebrew_reply_with_english_titles_is_he(catalog):
    shown = [catalog[78], catalog[82]]
    reply = "Apple MacBook Pro 14 Inch Space Grey, New DELL XPS 13 9300 Laptop מצאתי"
    # With the titles in, the Latin letters would win. Without them only Hebrew is left.
    assert detect_language(reply, [p.title for p in shown]) == "he"


def test_hebrew_reply_is_he_even_without_titles():
    assert detect_language("מצאתי כמה בשמים שיכולים להתאים לאשתך", []) == "he"


def test_spanish_reply_is_es():
    reply = "Lo siento, no vendemos vuelos, pero puedo ayudarte con productos de la tienda."
    assert detect_language(reply, []) == "es"


def test_english_reply_is_en():
    assert detect_language("Sorry, we do not carry flights, but I can help with products.", []) == "en"


def test_english_titles_in_a_spanish_reply_do_not_flip_it(catalog):
    title = catalog[80].title
    reply = f"Aquí tienes el {title} que es una buena opción para ti con ese presupuesto."
    assert detect_language(reply, [title]) == "es"


def test_stopword_lists_share_no_word():
    assert SPANISH_STOPWORDS & ENGLISH_STOPWORDS == set()


# ---------------------------------------------------------------------------
# Behavioral scoring
# ---------------------------------------------------------------------------


def case(**overrides) -> dict:
    base = {
        "id": 1,
        "turns": ["laptops"],
        "expected_intent": "product_search",
        "expected_mode": "new",
        "expected_categories": ["laptops"],
        "category_match": "all",
        "expect_fallback": None,
        "expected_behavior": "",
        "difficulty": "basic",
    }
    return {**base, **overrides}


def test_intent_and_mode(catalog, titles):
    result = make_result("Here you go.", [catalog[80]], intent="product_search", mode="refine")
    scores = score_case(result, case(), ["laptops"], titles)
    assert scores.intent_ok
    assert not scores.mode_ok


def test_null_expected_mode_needs_null_mode(titles):
    result = make_result("Sorry.", [], intent="off_catalog", mode=None)
    scores = score_case(result, case(expected_intent="off_catalog", expected_mode=None, expected_categories=[]), [], titles)
    assert scores.intent_ok and scores.mode_ok
    assert scores.category_ok is None  # no categories expected, so not scored


def test_category_all_needs_every_category(catalog, titles):
    both = case(expected_categories=["laptops", "mobile-accessories"], category_match="all")
    only_laptops = make_result("ok", [catalog[80]])
    assert score_case(only_laptops, both, [], titles).category_ok is False


def test_category_any_needs_one(catalog, titles):
    either = case(expected_categories=["furniture", "home-decoration"], category_match="any")
    result = make_result("ok", [catalog[14]])  # furniture
    assert score_case(result, either, [], titles).category_ok is True
    other = make_result("ok", [catalog[80]])  # laptops
    assert score_case(other, either, [], titles).category_ok is False


def test_category_counts_shown_products_across_outcomes(catalog, titles):
    outcomes = [
        SearchOutcome(spec=SearchSpec(category="laptops"), products=[catalog[80]], shown=[catalog[80]]),
        SearchOutcome(spec=SearchSpec(category="sunglasses"), products=[catalog[154]], shown=[catalog[154]]),
    ]
    result = TurnResult(
        parsed=ParsedRequest(intent="product_search", mode="new"),
        outcomes=outcomes,
        reply="ok",
        state=ConversationState(),
    )
    both = case(expected_categories=["laptops", "sunglasses"], category_match="all")
    assert score_case(result, both, [], titles).category_ok is True


def test_fallback_expected_price(catalog, titles):
    expected_price = case(expect_fallback="price")
    assert score_case(make_result("ok", [catalog[81]], loosened=["price"]), expected_price, [], titles).fallback_ok
    assert not score_case(make_result("ok", [catalog[81]], loosened=["rating"]), expected_price, [], titles).fallback_ok
    assert not score_case(make_result("ok", [catalog[81]]), expected_price, [], titles).fallback_ok


def test_fallback_null_means_nothing_loosened(catalog, titles):
    assert score_case(make_result("ok", [catalog[81]]), case(), [], titles).fallback_ok
    assert not score_case(make_result("ok", [catalog[81]], loosened=["price"]), case(), [], titles).fallback_ok


def test_language_scored_only_when_expected(catalog, titles):
    result = make_result("מצאתי מחשבים", [catalog[80]])
    assert score_case(result, case(), [], titles).language_ok is None
    assert score_case(result, case(expected_language="he"), [], titles).language_ok is True
    assert score_case(result, case(expected_language="es"), [], titles).language_ok is False


def test_scoring_module_does_not_import_search_or_pipeline():
    source = Path(scoring.__file__).read_text(encoding="utf-8")
    assert "app.search" not in source
    assert "app.pipeline" not in source
