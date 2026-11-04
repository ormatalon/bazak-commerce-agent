"""The shared contract: fixtures and dataset rows must fit the models."""

import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import ParsedRequest, Product, SearchSpec

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "catalog_sample.json"
DETERMINISTIC = ROOT / "datasets" / "deterministic.csv"
CATEGORIES = ["laptops", "tablets", "fragrances"]


def test_fixture_loads_as_products() -> None:
    products = [Product.model_validate(p) for p in json.loads(SAMPLE.read_text(encoding="utf-8"))]
    assert products
    assert products[0].warranty


def test_every_dataset_row_is_a_valid_spec() -> None:
    with DETERMINISTIC.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fields = ["category", "price_min", "price_max", "rating_min", "sort_by", "order", "top_k"]
            SearchSpec.model_validate({k: row[k] for k in fields if row[k]})


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchSpec.model_validate({"category": "flights"}, context={"categories": CATEGORIES})


def test_known_category_is_accepted() -> None:
    spec = SearchSpec.model_validate({"category": "laptops"}, context={"categories": CATEGORIES})
    assert spec.category == "laptops"


def test_rating_above_five_is_valid() -> None:
    assert SearchSpec(rating_min=5.01).rating_min == 5.01


def test_non_search_intent_needs_no_mode_or_searches() -> None:
    parsed = ParsedRequest(intent="small_talk")
    assert parsed.mode is None
    assert parsed.searches == []
