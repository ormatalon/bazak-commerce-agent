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


def test_off_catalog_can_never_carry_a_search() -> None:
    parsed = ParsedRequest(intent="off_catalog", mode="new", searches=[SearchSpec(category="laptops")])
    assert parsed.mode is None
    assert parsed.searches == []


def test_unset_keywords_are_null_so_a_refine_can_keep_them() -> None:
    assert SearchSpec().keywords is None


def test_clear_fields_only_accepts_real_fields() -> None:
    assert SearchSpec(clear_fields=["price_max"]).clear_fields == ["price_max"]
    with pytest.raises(ValidationError):
        SearchSpec(clear_fields=["price"])


def test_top_k_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SearchSpec(top_k=0)


def test_unknown_category_inside_a_parsed_request_is_rejected() -> None:
    raw = '{"intent": "product_search", "mode": "new", "searches": [{"category": "flights"}]}'
    with pytest.raises(ValidationError):
        ParsedRequest.model_validate_json(raw, context={"categories": CATEGORIES})


def test_strict_schema_has_no_default_or_minimum_keys() -> None:
    from openai.lib._pydantic import to_strict_json_schema

    text = json.dumps(to_strict_json_schema(ParsedRequest))
    assert '"default"' not in text
    assert "exclusiveMinimum" not in text
