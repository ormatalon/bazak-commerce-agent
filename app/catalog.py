"""Fetch the DummyJSON catalog once, cache it locally and load it into memory."""

from app.schemas import Product


def load_catalog() -> list[Product]:
    """Return every product, from the cache file when present."""
    raise NotImplementedError


def load_categories() -> list[str]:
    """Return the real category slugs, from the cache file when present."""
    raise NotImplementedError
