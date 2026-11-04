"""Catalog loading and caching. No test touches the network: httpx.get is faked."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app import catalog
from app.schemas import Product

SAMPLE = Path(__file__).parent / "fixtures" / "catalog_sample.json"


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self._data


def sample_products() -> list[dict[str, Any]]:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def sample_categories() -> list[str]:
    return sorted({p["category"] for p in sample_products()})


@pytest.fixture
def cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the loader at a temporary cache file, so the real one is never touched."""
    path = tmp_path / "catalog_cache.json"
    monkeypatch.setattr(catalog, "CACHE_PATH", path)
    return path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fake the API with the sample data. The list records each URL requested."""
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        requested.append(url)
        if url == catalog.PRODUCTS_URL:
            return FakeResponse({"products": sample_products(), "total": len(sample_products())})
        if url == catalog.CATEGORIES_URL:
            return FakeResponse(sample_categories())
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(catalog.httpx, "get", fake_get)
    return requested


def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(url: str, **kwargs: Any) -> FakeResponse:
        raise httpx.ConnectError("network is blocked in this test")

    monkeypatch.setattr(catalog.httpx, "get", fail)


def test_load_catalog_returns_products(cache_path: Path, calls: list[str]) -> None:
    products = catalog.load_catalog()
    assert len(products) == len(sample_products())
    assert all(isinstance(p, Product) for p in products)


def test_products_have_the_expected_fields(cache_path: Path, calls: list[str]) -> None:
    first = catalog.load_catalog()[0]
    assert first.id == 1
    assert first.title == "Essence Mascara Lash Princess"
    assert first.category == "beauty"
    assert first.price == 9.99
    assert first.rating == 2.56
    assert first.tags == ["beauty", "mascara"]
    assert first.thumbnail.startswith("https://")
    # camelCase names in the API are mapped to our snake_case fields.
    assert first.availability == "In Stock"
    assert first.warranty == "1 week warranty"


def test_categories_match_products(cache_path: Path, calls: list[str]) -> None:
    categories = catalog.load_categories()
    assert categories == sample_categories()
    assert all(p.category in categories for p in catalog.load_catalog())


def test_first_load_writes_the_cache_file(cache_path: Path, calls: list[str]) -> None:
    assert not cache_path.exists()
    catalog.load_catalog()
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(saved["products"]) == len(sample_products())
    assert saved["categories"] == sample_categories()


def test_loads_from_the_cache_without_the_network(
    cache_path: Path, calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog.load_catalog()  # first run fills the cache
    block_network(monkeypatch)
    assert len(catalog.load_catalog()) == len(sample_products())
    assert catalog.load_categories() == sample_categories()


def test_fetches_once_for_both_loaders(cache_path: Path, calls: list[str]) -> None:
    catalog.load_catalog()
    catalog.load_categories()
    assert calls == [catalog.PRODUCTS_URL, catalog.CATEGORIES_URL]


def test_failed_fetch_with_no_cache_raises_a_clear_error(
    cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    block_network(monkeypatch)
    with pytest.raises(catalog.CatalogError) as error:
        catalog.load_catalog()
    message = str(error.value)
    assert "Could not download" in message
    assert "network access once" in message
    assert not cache_path.exists()


def test_http_error_status_also_raises_the_clear_error(
    cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ServerError(FakeResponse):
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("500", request=httpx.Request("GET", "x"), response=httpx.Response(500))

    monkeypatch.setattr(catalog.httpx, "get", lambda url, **kwargs: ServerError({}))
    with pytest.raises(catalog.CatalogError, match="network access once"):
        catalog.load_categories()


@pytest.mark.parametrize(
    "garbage",
    [
        "{ this is not json",
        "[]",
        '{"products": [{"id": 1}], "categories": ["beauty"]}',  # product missing fields
        '{"products": [], "categories": []}',
        "",
    ],
)
def test_corrupted_cache_triggers_a_refetch(cache_path: Path, calls: list[str], garbage: str) -> None:
    cache_path.write_text(garbage, encoding="utf-8")
    assert len(catalog.load_catalog()) == len(sample_products())
    assert calls == [catalog.PRODUCTS_URL, catalog.CATEGORIES_URL]
    # The bad file was replaced by a good one.
    assert len(json.loads(cache_path.read_text(encoding="utf-8"))["products"]) == len(sample_products())


def test_corrupted_cache_and_failed_fetch_raises_the_clear_error(
    cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path.write_text("{ not json", encoding="utf-8")
    block_network(monkeypatch)
    with pytest.raises(catalog.CatalogError, match="network access once"):
        catalog.load_catalog()


def test_cache_path_is_the_repo_root_and_not_the_current_folder() -> None:
    assert catalog.CACHE_PATH.name == "catalog_cache.json"
    assert catalog.CACHE_PATH.parent == Path(catalog.__file__).resolve().parent.parent
