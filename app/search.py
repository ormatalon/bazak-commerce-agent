"""Filter and rank the cached catalog in plain Python, with our own fallback."""

import re
from typing import Literal

from app.schemas import Product, SearchOutcome, SearchSpec


def words_of(text: str) -> list[str]:
    """Lower-case words of a text. Apostrophes are dropped, so "men's" and "mens" agree."""
    return re.findall(r"[a-z0-9]+", text.lower().replace("'", ""))


def same_word(a: str, b: str) -> bool:
    """True for equal words, or words that differ only by a plural ending (s or es).

    Whole words only, so "car" does not match "card". The plural rule lets
    "laptop" find "laptops" and "sneaker" find "sneakers".
    """
    return a == b or a + "s" == b or b + "s" == a or a + "es" == b or b + "es" == a


def product_words(product: Product) -> list[str]:
    """The words a keyword is checked against: title, category and tags."""
    return words_of(" ".join([product.title, product.category, *product.tags]))


def keyword_match_count(keywords: list[list[str]], product: Product) -> int:
    """How many keywords the product matches. A keyword matches when all its words are found."""
    found = product_words(product)
    count = 0
    for keyword in keywords:
        if all(any(same_word(word, f) for f in found) for word in keyword):
            count += 1
    return count


def clean_keywords(keywords: list[str] | None) -> list[list[str]]:
    """Split each keyword into words and drop the ones with no words. None means no keywords."""
    split = [words_of(keyword) for keyword in (keywords or [])]
    return [words for words in split if words]


def passes_filters(spec: SearchSpec, product: Product) -> bool:
    """The hard filters: category, price and rating. All bounds are inclusive."""
    if spec.category is not None and product.category != spec.category:
        return False
    if spec.price_min is not None and product.price < spec.price_min:
        return False
    if spec.price_max is not None and product.price > spec.price_max:
        return False
    if spec.rating_min is not None and product.rating < spec.rating_min:
        return False
    return True


def sort_direction(spec: SearchSpec) -> int:
    """1 for ascending, -1 for descending. A sort with no order means cheapest or highest rated."""
    order = spec.order
    if order is None:
        order = "asc" if spec.sort_by == "price" else "desc"
    return 1 if order == "asc" else -1


def search(spec: SearchSpec, catalog: list[Product]) -> list[Product]:
    """Return every match, ranked, with no display cap and no fallback."""
    keywords = clean_keywords(spec.keywords)

    # Pair each product that passes the filters with its keyword-match count.
    matches: list[tuple[Product, int]] = []
    for product in catalog:
        if not passes_filters(spec, product):
            continue
        count = keyword_match_count(keywords, product)
        # With a category, keywords only rank. With none, at least one must match.
        if spec.category is None and keywords and count == 0:
            continue
        matches.append((product, count))

    def rank(item: tuple[Product, int]) -> tuple[float, int, float, int]:
        product, count = item
        # An explicit sort comes first. Without one this part is 0 for every product.
        primary = 0.0
        if spec.sort_by == "price":
            primary = product.price * sort_direction(spec)
        elif spec.sort_by == "rating":
            primary = product.rating * sort_direction(spec)
        # Then more keyword matches, higher rating, and finally the lowest ID.
        return (primary, -count, -product.rating, product.id)

    matches.sort(key=rank)
    return [product for product, _ in matches]


def distance_from_limits(spec: SearchSpec, product: Product) -> tuple[float, float]:
    """How far a product is outside the original price and rating limits (0 when inside).

    Price counts first, then rating. A bound that was not set gives 0.
    """
    price_gap = 0.0
    if spec.price_max is not None and product.price > spec.price_max:
        price_gap = product.price - spec.price_max
    if spec.price_min is not None and product.price < spec.price_min:
        price_gap = spec.price_min - product.price
    rating_gap = 0.0
    if spec.rating_min is not None and product.rating < spec.rating_min:
        rating_gap = spec.rating_min - product.rating
    return (price_gap, rating_gap)


def search_with_fallback(spec: SearchSpec, catalog: list[Product]) -> SearchOutcome:
    """Run the search, loosening rating and then price if it returns nothing.

    The category and keywords are never dropped: with no category that would
    return the whole catalog and present it as a match.
    """
    products = search(spec, catalog)
    if products:
        return SearchOutcome(spec=spec, products=products)

    loosened: list[Literal["rating", "price"]] = []
    loose_spec = spec

    # Stage 1: drop the rating limit (only if there was one).
    if spec.rating_min is not None:
        loose_spec = loose_spec.model_copy(update={"rating_min": None})
        loosened.append("rating")
        products = search(loose_spec, catalog)

    # Stage 2: also drop the price limits (only if there were any).
    if not products and (spec.price_min is not None or spec.price_max is not None):
        loose_spec = loose_spec.model_copy(update={"price_min": None, "price_max": None})
        loosened.append("price")
        products = search(loose_spec, catalog)

    if not products:
        return SearchOutcome(spec=spec, products=[], loosened=[])

    # Unless the user chose a sort, put the products nearest to the original limits first.
    # The sort is stable, so equal distances keep the order search() gave them.
    if spec.sort_by is None:
        products.sort(key=lambda product: distance_from_limits(spec, product))

    return SearchOutcome(spec=spec, products=products, loosened=loosened)
