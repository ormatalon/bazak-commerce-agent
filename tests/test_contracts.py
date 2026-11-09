"""Contract checks without model calls or dataset scoring."""

import pytest
from pydantic import ValidationError

from app.schemas import Direction, ParsedRequest, SearchSpec
from evals.datasets import load_cases


def test_category_validation_and_empty_price_range():
    with pytest.raises(ValidationError):
        Direction.model_validate({"query": "shoe", "categories": ["invented"]}, context={"categories": ["shoes"]})
    with pytest.raises(ValidationError):
        SearchSpec(price_min=20, price_max=10)


def test_nonshopping_intent_cannot_show_stray_searches():
    parsed = ParsedRequest(intent="off_catalog", mode="new", searches=[SearchSpec()])
    assert parsed.mode is None and not parsed.searches


def test_all_source_case_identities_are_unique():
    cases = load_cases()
    assert len(cases) == 167
    assert len({c["key"] for c in cases}) == len(cases)
