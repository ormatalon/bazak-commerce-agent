"""Fetch the DummyJSON catalog once, cache it locally and load it into memory."""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.schemas import Product

PRODUCTS_URL = "https://dummyjson.com/products?limit=0"
CATEGORIES_URL = "https://dummyjson.com/products/category-list"
# Found relative to this file, so it is the same wherever the app is started from.
CACHE_PATH = Path(__file__).resolve().parent.parent / "catalog_cache.json"
TIMEOUT_SECONDS = 15


class CatalogError(RuntimeError):
    """The catalog could not be loaded, so the app cannot start."""


def _fetch_json(url: str) -> Any:
    response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _fetch_raw() -> dict[str, Any]:
    """Download both lists. Raises CatalogError with a plain-words message."""
    try:
        products = _fetch_json(PRODUCTS_URL)["products"]
        categories = _fetch_json(CATEGORIES_URL)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise CatalogError(
            "Could not download the product catalog from dummyjson.com, and there is no "
            f"usable saved copy at {CACHE_PATH}. The app needs network access to fetch "
            f"the catalog; check the connection and start it again. Cause: {error!r}"
        ) from error
    return {"products": products, "categories": categories}


def _parse(raw: dict[str, Any]) -> tuple[list[Product], list[str]]:
    """Validate raw data. Raises ValueError (pydantic's errors are one), KeyError or TypeError."""
    products = [Product.model_validate(item) for item in raw["products"]]
    categories = raw["categories"]
    if not products or not isinstance(categories, list) or not categories or not all(isinstance(c, str) and c for c in categories):
        raise ValueError("catalog data is empty or has the wrong shape")
    if len({p.id for p in products}) != len(products) or any(p.category not in categories for p in products):
        raise ValueError("catalog IDs or category membership are inconsistent")
    return products, categories


def _read_cache() -> tuple[list[Product], list[str]] | None:
    """Return the cached catalog, or None when the file is missing, unreadable or malformed."""
    try:
        with CACHE_PATH.open(encoding="utf-8") as file:
            return _parse(json.load(file))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_cache(raw: dict[str, Any]) -> None:
    temporary: str | None = None
    try:
        handle, temporary = tempfile.mkstemp(dir=CACHE_PATH.parent, suffix=".json")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(raw, file, ensure_ascii=False)
        os.replace(temporary, CACHE_PATH)
    except OSError as error:
        # The catalog is already in hand, so keep going. Without a saved copy every
        # load downloads again, so warn instead of failing silently.
        print(f"Warning: could not save the catalog cache to {CACHE_PATH}: {error!r}", file=sys.stderr)
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass  # a cleanup failure must not discard the catalog in memory


def _load() -> tuple[list[Product], list[str]]:
    cached = _read_cache()
    if cached is not None:
        return cached
    raw = _fetch_raw()
    try:
        data = _parse(raw)
    except (ValueError, KeyError, TypeError) as error:
        raise CatalogError(f"dummyjson.com returned catalog data in an unexpected shape: {error}") from error
    _write_cache(raw)
    return data


def load_catalog() -> list[Product]:
    """Return every product, from the cache file when present."""
    return _load()[0]


def load_catalog_data() -> tuple[list[Product], list[str]]:
    """Load products and categories from the same fetch/cache snapshot."""
    return _load()


def load_categories() -> list[str]:
    """Return the real category slugs, from the cache file when present."""
    return _load()[1]


def category_tags(catalog: list[Product]) -> dict[str, list[str]]:
    """The distinct tags of each category's products, in lower case and sorted.

    They tell the parser what a category holds, which its slug alone can't: "groceries"
    says nothing about dog food, but its tags list "dog food" and "pet supplies". Built
    from the catalog, so they follow it if it changes.
    """
    tags: dict[str, set[str]] = {}
    for product in catalog:
        tags.setdefault(product.category, set()).update(tag.lower() for tag in product.tags)
    return {category: sorted(found) for category, found in tags.items()}
