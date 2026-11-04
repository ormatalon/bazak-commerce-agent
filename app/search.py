"""Filter and rank the cached catalog in plain Python, with our own fallback."""

from app.schemas import Product, SearchOutcome, SearchSpec


def search(spec: SearchSpec, catalog: list[Product]) -> list[Product]:
    """Return every match, ranked, with no display cap and no fallback."""
    raise NotImplementedError


def search_with_fallback(spec: SearchSpec, catalog: list[Product]) -> SearchOutcome:
    """Run the search, loosening rating and then price if it returns nothing."""
    raise NotImplementedError
