"""Search, ranking and fallback over the 49-product sample catalog. No network.

Ids used below (from tests/fixtures/catalog_sample.json):
  laptops 78-82, tablets 159-161, beauty 1-5, fragrances 6-10, furniture 11-15,
  mens-shoes 88-92, smartphones 121-136, sunglasses 154-158.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import Product, SearchSpec
from app.search import search, search_with_fallback

SAMPLE = Path(__file__).parent / "fixtures" / "catalog_sample.json"

CATEGORIES = ["beauty", "fragrances", "furniture", "laptops", "mens-shoes", "smartphones", "sunglasses", "tablets"]


@pytest.fixture(scope="module")
def catalog() -> list[Product]:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in data]


def ids(products: list[Product]) -> list[int]:
    return [p.id for p in products]


def product(product_id: int, title: str) -> Product:
    """A small made-up product, for word-matching tests the sample catalog can't cover."""
    return Product(
        id=product_id, title=title, description="", category="misc", price=10.0, rating=4.0, tags=[]
    )


def run(catalog: list[Product], **fields: Any) -> list[Product]:
    return search(SearchSpec(**fields), catalog)


def fallback(catalog: list[Product], **fields: Any):
    return search_with_fallback(SearchSpec(**fields), catalog)


# ---------------------------------------------------------------- filters


def test_no_filters_returns_the_whole_catalog_with_no_cap(catalog: list[Product]) -> None:
    assert len(run(catalog)) == len(catalog) == 49


def test_category_filter(catalog: list[Product]) -> None:
    assert sorted(ids(run(catalog, category="laptops"))) == [78, 79, 80, 81, 82]


def test_category_with_no_products_returns_nothing(catalog: list[Product]) -> None:
    assert run(catalog, category="groceries") == []


def test_laptops_up_to_1500(catalog: list[Product]) -> None:
    result = run(catalog, category="laptops", price_max=1500, sort_by="price")
    assert [p.price for p in result] == [1099.99, 1399.99, 1499.99]


def test_price_max_equal_to_a_price_includes_it(catalog: list[Product]) -> None:
    # No laptop costs exactly 1500, so this uses a limit equal to a real price.
    result = run(catalog, category="laptops", price_max=1499.99, sort_by="price")
    assert [p.price for p in result] == [1099.99, 1399.99, 1499.99]


def test_price_max_just_below_a_price_excludes_it(catalog: list[Product]) -> None:
    result = run(catalog, category="laptops", price_max=1499.98)
    assert 82 not in ids(result)  # the 1499.99 laptop
    assert len(result) == 2


def test_price_min_is_inclusive(catalog: list[Product]) -> None:
    result = run(catalog, category="laptops", price_min=1799.99, sort_by="price")
    assert [p.price for p in result] == [1799.99, 1999.99]


def test_price_min_and_max_together(catalog: list[Product]) -> None:
    result = run(catalog, category="furniture", price_min=299.99, price_max=799.99, sort_by="price")
    assert [p.price for p in result] == [299.99, 499.99, 799.99]


def test_rating_min_is_inclusive(catalog: list[Product]) -> None:
    # Realme XT (130) is the only smartphone rated 4.58 or more.
    assert ids(run(catalog, category="smartphones", rating_min=4.58)) == [130]


def test_rating_min_just_above_a_rating_excludes_it(catalog: list[Product]) -> None:
    assert run(catalog, category="smartphones", rating_min=4.59) == []


def test_price_and_rating_filters_combine(catalog: list[Product]) -> None:
    result = run(catalog, category="smartphones", price_max=300, rating_min=4.2)
    # 128 ($149.99, 4.2) and 127 ($299.99, 4.25); 130 is rated higher but costs $349.99.
    assert sorted(ids(result)) == [127, 128]


def test_price_filter_works_without_a_category(catalog: list[Product]) -> None:
    result = run(catalog, price_max=20)
    assert sorted(ids(result)) == [1, 2, 3, 4, 5, 157]


def test_unknown_category_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValidationError):
        SearchSpec.model_validate({"category": "garden"}, context={"categories": CATEGORIES})


# ---------------------------------------------------------------- sorting


def test_cheapest_tablet_is_the_samsung_galaxy_tab_white(catalog: list[Product]) -> None:
    result = run(catalog, category="tablets", sort_by="price", order="asc", top_k=1)
    assert result[0].title == "Samsung Galaxy Tab White"
    assert result[0].price == 349.99


def test_search_ignores_top_k(catalog: list[Product]) -> None:
    # top_k is applied by callers, so search() still returns all 3 tablets.
    assert len(run(catalog, category="tablets", top_k=1)) == 3


def test_price_sort_descending(catalog: list[Product]) -> None:
    result = run(catalog, category="laptops", sort_by="price", order="desc")
    assert ids(result) == [78, 79, 82, 80, 81]


def test_sort_by_price_with_no_order_means_cheapest_first(catalog: list[Product]) -> None:
    assert ids(run(catalog, category="laptops", sort_by="price")) == [81, 80, 82, 79, 78]


def test_sort_by_rating_with_no_order_means_highest_first(catalog: list[Product]) -> None:
    assert ids(run(catalog, category="tablets", sort_by="rating")) == [160, 161, 159]


def test_sort_by_rating_ascending(catalog: list[Product]) -> None:
    assert ids(run(catalog, category="tablets", sort_by="rating", order="asc")) == [159, 161, 160]


def test_explicit_sort_beats_keyword_count(catalog: list[Product]) -> None:
    # "oppo" matches 125, 126 and 127, but the price sort puts the cheaper Realme C35 first.
    result = run(catalog, category="smartphones", keywords=["oppo"], sort_by="price")
    assert ids(result)[0] == 128  # Realme C35, $149.99


def test_default_order_is_rating_highest_first(catalog: list[Product]) -> None:
    assert ids(run(catalog, category="tablets")) == [160, 161, 159]


def test_keyword_count_still_breaks_ties_under_an_explicit_sort(catalog: list[Product]) -> None:
    # Five phones cost $299.99. Without the keyword Vivo V9 (135, rated 3.6) would come after 127 and 129.
    result = run(
        catalog, category="smartphones", keywords=["vivo"], price_min=299.99, price_max=299.99, sort_by="price"
    )
    assert ids(result) == [135, 127, 129, 122, 131]


def test_price_ties_are_broken_by_rating_then_id(catalog: list[Product]) -> None:
    # Five smartphones cost $299.99: 122 (3.41), 127 (4.25), 129 (3.7), 131 (3.3), 135 (3.6).
    result = run(catalog, category="smartphones", price_min=299.99, price_max=299.99, sort_by="price")
    assert ids(result) == [127, 129, 135, 122, 131]


def test_rating_tie_is_broken_by_lowest_id_whatever_the_catalog_order(catalog: list[Product]) -> None:
    # Men's shoes 88 and 91 are both rated 4.77. The catalog is reversed so that
    # only the ID tie-break, and not the catalog order, can put 88 before 91.
    result = search(SearchSpec(category="mens-shoes"), list(reversed(catalog)))
    assert ids(result) == [90, 88, 91, 92, 89]


def test_rating_tie_with_an_explicit_rating_sort(catalog: list[Product]) -> None:
    result = search(SearchSpec(category="mens-shoes", sort_by="rating", order="desc"), list(reversed(catalog)))
    assert ids(result)[:3] == [90, 88, 91]


# ---------------------------------------------------------------- keywords


def test_keywords_never_exclude_within_a_category(catalog: list[Product]) -> None:
    # None of the 5 beauty products contains "makeup", yet all 5 come back.
    result = run(catalog, category="beauty", keywords=["makeup"])
    assert sorted(ids(result)) == [1, 2, 3, 4, 5]


def test_keywords_do_not_pull_in_other_categories(catalog: list[Product]) -> None:
    result = run(catalog, category="laptops", keywords=["oppo"])
    assert sorted(ids(result)) == [78, 79, 80, 81, 82]


def test_keyword_matches_rank_first_within_a_category(catalog: list[Product]) -> None:
    result = run(catalog, category="smartphones", keywords=["oppo", "pro"])
    # 126 (Oppo F19 Pro Plus) matches both; then 127, 123 and 125 match one, by rating.
    assert ids(result)[:4] == [126, 127, 123, 125]
    assert len(result) == 16


def test_keywords_are_case_insensitive(catalog: list[Product]) -> None:
    lower = run(catalog, category="smartphones", keywords=["oppo"])
    upper = run(catalog, category="smartphones", keywords=["OPPO"])
    assert ids(lower) == ids(upper)
    assert ids(upper)[:3] == [127, 125, 126]


def test_keywords_without_a_category_must_match_at_least_one(catalog: list[Product]) -> None:
    result = run(catalog, keywords=["oppo", "vivo"])
    assert ids(result) == [136, 127, 125, 135, 126, 134]


def test_keywords_without_a_category_rank_by_match_count(catalog: list[Product]) -> None:
    result = run(catalog, keywords=["oppo", "pro"])
    assert ids(result)[0] == 126  # matches both keywords
    assert 128 not in ids(result)  # Realme C35 matches neither


def test_unknown_keyword_without_a_category_returns_nothing(catalog: list[Product]) -> None:
    assert run(catalog, keywords=["console"]) == []


def test_keyword_must_be_a_whole_word(catalog: list[Product]) -> None:
    # "phone" is inside "smartphones" and "iPhone". It is a word in the full catalog
    # (product 108), but no sample product has it, so the result is empty only because
    # the fixture has no mobile-accessories.
    assert run(catalog, keywords=["phone"]) == []


def test_keyword_matches_a_plural_form(catalog: list[Product]) -> None:
    # "laptop" finds the category word "laptops" as well as "Laptop" in a title.
    assert sorted(ids(run(catalog, keywords=["laptop"]))) == [78, 79, 80, 81, 82]
    # "sneaker" finds "Sneakers" in the titles of 91 and 92.
    assert ids(run(catalog, keywords=["sneaker"])) == [91, 92]


def test_keyword_with_an_apostrophe_matches_the_slug(catalog: list[Product]) -> None:
    # "men's" becomes "mens", the first word of the category "mens-shoes".
    assert sorted(ids(run(catalog, keywords=["men's"]))) == [88, 89, 90, 91, 92]


def test_multi_word_keyword_counts_each_word_separately(catalog: list[Product]) -> None:
    # "nail polish": product 5 has both words, so it is the only match.
    assert ids(run(catalog, keywords=["nail polish"])) == [5]
    # "nail powder": "nail" is only in 5 and "powder" only in 3. Each word counts on its
    # own, so both match once and the higher rating (3, 4.64) comes first.
    assert ids(run(catalog, keywords=["nail powder"])) == [3, 5]


def test_multi_word_keyword_ranks_within_a_category(catalog: list[Product]) -> None:
    # "table" is in the title and tag of the bedside table (13), the only match.
    assert ids(run(catalog, category="furniture", keywords=["coffee table"]))[0] == 13
    # Samsung phones match "samsung"; "phone" matches no word. Realme XT is rated higher
    # but matches nothing, so it must not come first.
    result = run(catalog, category="smartphones", keywords=["samsung phone"])
    assert ids(result)[:3] == [132, 131, 133]


def test_multi_word_keyword_without_a_category_needs_one_word(catalog: list[Product]) -> None:
    # "running" matches nothing, "shoes" matches the category word of all five.
    assert ids(run(catalog, keywords=["running shoes"])) == [90, 88, 91, 92, 89]


def test_keywords_in_other_scripts_stay_as_words_and_match_nothing(catalog: list[Product]) -> None:
    assert run(catalog, keywords=["טלפון"]) == []
    # With a category they only rank, so nothing is excluded.
    assert len(run(catalog, category="tablets", keywords=["טלפון"])) == 3


def test_keywords_are_checked_against_tags(catalog: list[Product]) -> None:
    # "eyewear" is only in the tags of the five sunglasses, not in a title or category.
    assert sorted(ids(run(catalog, keywords=["eyewear"]))) == [154, 155, 156, 157, 158]
    # "perfume" is only in the tag "perfumes" of the fragrances (plus the plural rule).
    assert sorted(ids(run(catalog, keywords=["perfume"]))) == [6, 7, 8, 9, 10]


def test_es_plural_in_both_directions() -> None:
    dress = product(1, "Red Dress")
    watch = product(2, "Gold Watch")
    small = [dress, watch]
    assert ids(search(SearchSpec(keywords=["dresses"]), small)) == [1]
    assert ids(search(SearchSpec(keywords=["watches"]), small)) == [2]
    other = [product(3, "Red Dresses"), product(4, "Gold Watches")]
    assert ids(search(SearchSpec(keywords=["dress"]), other)) == [3]
    assert ids(search(SearchSpec(keywords=["watch"]), other)) == [4]


def test_s_plural_keyword_finds_a_singular_title(catalog: list[Product]) -> None:
    # "suns" finds "Sun" in the titles of 154 and 155.
    assert ids(run(catalog, keywords=["suns"])) == [154, 155]


def test_empty_keyword_entries_are_dropped(catalog: list[Product]) -> None:
    assert ids(run(catalog, keywords=["", "oppo"])) == [127, 125, 126]


@pytest.mark.parametrize("keywords", [None, [], [""], ["  ", "!!"]])
def test_empty_keywords_mean_no_keywords(catalog: list[Product], keywords: list[str] | None) -> None:
    with_category = run(catalog, category="tablets", keywords=keywords)
    assert ids(with_category) == [160, 161, 159]
    # With no category they filter nothing out either, so the other filters decide.
    assert len(run(catalog, keywords=keywords, price_max=20)) == 6


# ---------------------------------------------------------------- fallback


def test_no_category_and_no_keywords_never_loosens(catalog: list[Product]) -> None:
    # Loosening would return the whole catalog and call it a match.
    for fields in [{"rating_min": 5.01}, {"price_max": 0.5}, {"price_max": 0.5, "rating_min": 5.01}]:
        outcome = fallback(catalog, **fields)
        assert outcome.products == []
        assert outcome.loosened == []


def test_blank_keywords_and_no_category_never_loosen(catalog: list[Product]) -> None:
    outcome = fallback(catalog, keywords=["", "  "], rating_min=5.01)
    assert outcome.products == []
    assert outcome.loosened == []


def test_hebrew_keyword_without_a_category_finds_nothing_in_fallback(catalog: list[Product]) -> None:
    outcome = fallback(catalog, keywords=["טלפון"], price_max=10)
    assert outcome.products == []
    assert outcome.loosened == []


def test_search_itself_does_not_fall_back(catalog: list[Product]) -> None:
    assert run(catalog, category="laptops", price_max=10) == []


def test_no_fallback_when_the_search_has_results(catalog: list[Product]) -> None:
    spec = SearchSpec(category="laptops", price_max=1500)
    outcome = search_with_fallback(spec, catalog)
    assert outcome.loosened == []
    assert ids(outcome.products) == ids(search(spec, catalog))
    assert len(outcome.products) == 3
    assert outcome.shown == []


def test_price_max_is_loosened_cheapest_first(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="laptops", price_max=10)
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [81, 80, 82, 79, 78]
    assert [p.price for p in outcome.products] == [1099.99, 1399.99, 1499.99, 1799.99, 1999.99]


def test_the_outcome_spec_is_the_search_as_asked(catalog: list[Product]) -> None:
    spec = SearchSpec(category="laptops", price_max=10, rating_min=1)
    outcome = search_with_fallback(spec, catalog)
    assert outcome.spec == SearchSpec(category="laptops", price_max=10, rating_min=1)
    assert outcome.spec.price_max == 10


def test_price_min_is_loosened_most_expensive_first(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="laptops", price_min=5000)
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [78, 79, 82, 80, 81]


def test_price_gap_between_both_limits_orders_by_nearest(catalog: list[Product]) -> None:
    # No laptop costs between $1,200 and $1,300. 80 ($1,399.99) is $99.99 above the
    # range and 81 ($1,099.99) is $100.01 below it, so 80 is the nearest.
    outcome = fallback(catalog, category="laptops", price_min=1200, price_max=1300)
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [80, 81, 82, 79, 78]


def test_rating_is_loosened_highest_rating_first(catalog: list[Product]) -> None:
    # No keywords, so only the nearest-to-the-limit rule orders these.
    outcome = fallback(catalog, category="smartphones", rating_min=5.01)
    assert outcome.loosened == ["rating"]
    assert len(outcome.products) == 16
    assert ids(outcome.products)[:3] == [130, 132, 136]
    assert [p.rating for p in outcome.products] == sorted((p.rating for p in outcome.products), reverse=True)


def test_loosened_results_put_keyword_matches_before_the_nearest_rating(catalog: list[Product]) -> None:
    # "apple" matches the four iPhones. Realme XT (130, 4.58) is nearest to the limit
    # but does not match, so it comes after them. Among the iPhones, nearest rating first.
    outcome = fallback(catalog, category="smartphones", keywords=["apple"], rating_min=5.01)
    assert outcome.loosened == ["rating"]
    assert len(outcome.products) == 16
    assert ids(outcome.products)[:7] == [123, 122, 121, 124, 130, 132, 136]


def test_iphone_rated_above_5_shows_iphones_first_without_a_category(catalog: list[Product]) -> None:
    outcome = fallback(catalog, keywords=["iphone"], rating_min=5.01)
    assert outcome.loosened == ["rating"]
    assert ids(outcome.products) == [123, 122, 121, 124]


def test_equal_distance_on_a_loosened_search_keeps_the_normal_order(catalog: list[Product]) -> None:
    # Phones cost 149.99, 199.99, 249.99 (x2), 299.99 (x5) ... Equal prices are equally far
    # from the $100 limit, so they fall back to rating, highest first: 125 (3.94) before 134
    # (3.5), and 127, 129, 135, 122, 131 for the $299.99 phones.
    outcome = search_with_fallback(SearchSpec(category="smartphones", price_max=100), list(reversed(catalog)))
    assert outcome.loosened == ["price"]
    assert ids(outcome.products)[:9] == [128, 121, 125, 134, 127, 129, 135, 122, 131]


def test_rating_stage_keeps_the_price_limit(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="smartphones", price_max=300, rating_min=4.9)
    assert outcome.loosened == ["rating"]
    assert len(outcome.products) > 0
    assert all(p.price <= 300 for p in outcome.products)
    # Smartphones above $300 exist, so the limit really was applied.
    assert any(p.price > 300 for p in search(SearchSpec(category="smartphones"), catalog))


def test_price_is_loosened_only_after_rating_did_not_help(catalog: list[Product]) -> None:
    # The best laptop is rated 4.98, so rating_min=4.99 fails; price_max=10 fails too.
    outcome = fallback(catalog, category="laptops", price_max=10, rating_min=4.99)
    assert outcome.loosened == ["rating", "price"]
    assert ids(outcome.products) == [81, 80, 82, 79, 78]


def test_two_limits_that_never_meet_suggest_one_product_for_each(catalog: list[Product]) -> None:
    # 130 ($349.99, 4.58) is the only phone rated 4.5 or more. 127 ($299.99, 4.25) is the
    # highest rated at $300 or less, ahead of the cheaper 128 ($149.99, 4.2).
    outcome = fallback(catalog, category="smartphones", price_max=300, rating_min=4.5)
    assert outcome.loosened == ["rating", "price"]
    assert ids(outcome.products) == [130, 127]


def test_the_suggestion_that_meets_the_rating_is_the_cheapest_with_it(catalog: list[Product]) -> None:
    # Rated 4.2 or more and over $300: 132 ($499.99, 4.4), 136 ($499.99, 4.26), 130 ($349.99, 4.58).
    # With a $100 limit, none costs that little, and 130 is the nearest to it.
    outcome = fallback(catalog, category="smartphones", price_max=100, rating_min=4.2)
    assert outcome.loosened == ["price"]
    assert all(p.rating >= 4.2 for p in outcome.products)
    assert outcome.products[0].price == min(p.price for p in outcome.products)


def test_the_users_sort_does_not_choose_the_two_suggestions(catalog: list[Product]) -> None:
    outcome = fallback(
        catalog, category="smartphones", price_max=300, rating_min=4.5, sort_by="price", order="asc"
    )
    assert ids(outcome.products) == [130, 127]


def test_a_limit_that_works_alone_keeps_all_its_products(catalog: list[Product]) -> None:
    # Every laptop is rated 1 or more and none costs $10, so only the price limit is dropped.
    outcome = fallback(catalog, category="laptops", price_max=10, rating_min=1)
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [81, 80, 82, 79, 78]


def test_rating_alone_is_not_loosened_when_there_is_no_rating_limit(catalog: list[Product]) -> None:
    assert fallback(catalog, category="laptops", price_max=10).loosened == ["price"]


def test_the_users_sort_is_kept_when_loosening(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="laptops", price_max=10, sort_by="rating", order="desc")
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [80, 79, 78, 81, 82]


def test_loosening_never_drops_the_category(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="laptops", price_max=10, rating_min=5.01)
    assert len(outcome.products) == 5
    assert {p.category for p in outcome.products} == {"laptops"}


def test_loosening_never_drops_the_keywords(catalog: list[Product]) -> None:
    # No category, so the keyword is the only thing keeping the Oppo phones apart from the catalog.
    outcome = fallback(catalog, keywords=["oppo"], price_max=1)
    assert outcome.loosened == ["price"]
    assert ids(outcome.products) == [125, 127, 126]


def test_unmatched_keyword_without_a_category_returns_nothing(catalog: list[Product]) -> None:
    outcome = fallback(catalog, keywords=["console"])
    assert outcome.products == []
    assert outcome.shown == []
    assert outcome.loosened == []


def test_nothing_found_even_after_loosening(catalog: list[Product]) -> None:
    outcome = fallback(catalog, keywords=["console"], price_max=10, rating_min=5)
    assert outcome.products == []
    assert outcome.loosened == []
    assert outcome.spec.price_max == 10


def test_category_with_no_products_stays_empty_after_loosening(catalog: list[Product]) -> None:
    outcome = fallback(catalog, category="groceries", price_max=1)
    assert outcome.products == []
    assert outcome.loosened == []
