"""Fetch the DummyJSON catalog once, cache it locally and load it into memory."""

import json
import sys
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
    categories = list(raw["categories"])
    if not products or not categories or not all(isinstance(c, str) for c in categories):
        raise ValueError("catalog data is empty or has the wrong shape")
    return products, categories


def _read_cache() -> tuple[list[Product], list[str]] | None:
    """Return the cached catalog, or None when the file is missing, unreadable or malformed."""
    try:
        with CACHE_PATH.open(encoding="utf-8") as file:
            return _parse(json.load(file))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_cache(raw: dict[str, Any]) -> None:
    try:
        with CACHE_PATH.open("w", encoding="utf-8") as file:
            json.dump(raw, file, ensure_ascii=False)
    except OSError as error:
        # The catalog is already in hand, so keep going. Without a saved copy every
        # load downloads again, so warn instead of failing silently.
        print(f"Warning: could not save the catalog cache to {CACHE_PATH}: {error!r}", file=sys.stderr)


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


def load_categories() -> list[str]:
    """Return the real category slugs, from the cache file when present."""
    return _load()[1]
