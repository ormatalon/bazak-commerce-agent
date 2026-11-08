"""Filter and rank the cached catalog in plain Python, with our own fallback."""

import re

from app.schemas import Product, SearchOutcome, SearchSpec


def words_of(text: str) -> list[str]:
    """Lower-case words of a text. Apostrophes are dropped, so "men's" and "mens" agree."""
    # [^\W_]+ is a run of letters or digits in any script, so a Hebrew keyword stays a
    # word (that matches nothing) instead of vanishing and letting everything through.
    return re.findall(r"[^\W_]+", text.lower().replace("'", ""))


def same_word(a: str, b: str) -> bool:
    """True for equal words, or words that differ only by a plural ending (s or es).

    Whole words only, so "car" does not match "card". The plural rule lets
    "laptop" find "laptops" and "sneaker" find "sneakers".
    """
    return a == b or a + "s" == b or b + "s" == a or a + "es" == b or b + "es" == a


def product_words(product: Product) -> list[str]:
    """The words a keyword is checked against: title, category and tags."""
    return words_of(" ".join([product.title, product.category, *product.tags]))


def keyword_match_count(keywords: list[str], product: Product) -> int:
    """How many of the keyword words the product matches."""
    found = product_words(product)
    count = 0
    for word in keywords:
        if any(same_word(word, f) for f in found):
            count += 1
    return count


def clean_keywords(keywords: list[str] | None) -> list[str]:
    """Split every keyword into single words, so "coffee table" counts "coffee" and "table" apart.

    Empty entries disappear, repeated words count once, and None means no keywords.
    """
    words = [word for keyword in (keywords or []) for word in words_of(keyword)]
    return list(dict.fromkeys(words))


def ranking_keywords(spec: SearchSpec) -> list[str]:
    """The keyword words that can tell the products of a search apart.

    With a category set, a word of the category's own name ("kitchen" in
    kitchen-accessories) matches every product in it, so it would rank nothing and give
    every product a card. Those words are dropped. Without a category every word counts.
    """
    words = clean_keywords(spec.keywords)
    if spec.category is None:
        return words
    category_words = words_of(spec.category)
    return [word for word in words if not any(same_word(word, c) for c in category_words)]


def is_excluded(spec: SearchSpec, product: Product) -> bool:
    """True when the product's title, brand or tags contain a word the shopper excluded.

    The brand matters: iPhone titles never say "Apple", but their brand does. The category
    is not checked: "phones but not Apple" must not drop every smartphone.
    """
    excluded = clean_keywords(spec.exclude_keywords)
    if not excluded:
        return False
    found = words_of(" ".join([product.title, product.brand or "", *product.tags]))
    return any(same_word(word, f) for word in excluded for f in found)


def passes_filters(spec: SearchSpec, product: Product) -> bool:
    """The hard filters: category, excluded words, price and rating. All bounds are inclusive.

    The fallback loosens only price and rating, so an exclusion always holds.
    """
    if spec.category is not None and product.category != spec.category:
        return False
    if is_excluded(spec, product):
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
    keywords = ranking_keywords(spec)

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


def relevant_products(spec: SearchSpec, products: list[Product]) -> list[Product]:
    """The products matching a keyword, or all of them when none do.

    For choosing cards and counting, not for search(): a keyword must not empty a category
    ("makeup" matches no beauty product), but one phone case should not come with two
    speakers just because they share its category.
    """
    keywords = ranking_keywords(spec)
    matching = [p for p in products if keyword_match_count(keywords, p) > 0]
    return matching or products


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


def nearest_first(spec: SearchSpec, products: list[Product]) -> list[Product]:
    """More keyword matches first (so "iphone rated above 5" shows iPhones), then nearest
    to the original limits. The sort is stable, so equal keys keep the order search() gave
    them (rating, then lowest ID).
    """
    keywords = ranking_keywords(spec)
    return sorted(
        products,
        key=lambda product: (-keyword_match_count(keywords, product), *distance_from_limits(spec, product)),
    )


def search_without(spec: SearchSpec, dropped: dict[str, None], catalog: list[Product]) -> list[Product]:
    """Search with some limits dropped. Unless the user chose a sort, nearest to the limits first."""
    products = search(spec.model_copy(update=dropped), catalog)
    return products if spec.sort_by is not None else nearest_first(spec, products)


def search_with_fallback(spec: SearchSpec, catalog: list[Product]) -> SearchOutcome:
    """Run the search, and if it returns nothing, loosen the rating or price limits.

    With one kind of limit, drop it. With both, drop whichever one finds something. If each
    finds something alone, nothing meets them together, so suggest one product for each:
    the nearest to the price limit that meets the rating, and the highest rated that meets
    the price. If neither finds anything alone, drop both.

    The category and keywords are never dropped: with no category that would
    return the whole catalog and present it as a match.
    """
    products = search(spec, catalog)
    if products:
        return SearchOutcome(spec=spec, products=products)

    # With no category and no keywords, loosening would return the whole catalog as a match.
    if spec.category is None and not clean_keywords(spec.keywords):
        return SearchOutcome(spec=spec, products=[], loosened=[])

    no_rating: dict[str, None] = {"rating_min": None}
    no_price: dict[str, None] = {"price_min": None, "price_max": None}
    has_rating = spec.rating_min is not None
    has_price = spec.price_min is not None or spec.price_max is not None

    meets_price = search_without(spec, no_rating, catalog) if has_rating else []
    meets_rating = search_without(spec, no_price, catalog) if has_price else []

    if meets_price and meets_rating:
        # The user's sort can't choose these: each one answers its own limit.
        suggestions = [nearest_first(spec, meets_rating)[0], nearest_first(spec, meets_price)[0]]
        return SearchOutcome(spec=spec, products=suggestions, loosened=["rating", "price"])
    if meets_price:
        return SearchOutcome(spec=spec, products=meets_price, loosened=["rating"])
    if meets_rating:
        return SearchOutcome(spec=spec, products=meets_rating, loosened=["price"])

    if has_rating and has_price:
        either = search_without(spec, {**no_rating, **no_price}, catalog)
        if either:
            return SearchOutcome(spec=spec, products=either, loosened=["rating", "price"])
    return SearchOutcome(spec=spec, products=[], loosened=[])
