"""Contract checks without model calls or dataset scoring."""

import pytest
from pydantic import ValidationError

from app.schemas import Direction, ParsedRequest, Product, SearchSpec
from evals.datasets import load_cases


def test_category_validation_and_empty_price_range():
    with pytest.raises(ValidationError):
        Direction.model_validate({"query": "shoe", "categories": ["invented"]}, context={"categories": ["shoes"]})
    with pytest.raises(ValidationError):
        SearchSpec(price_min=20, price_max=10)
    with pytest.raises(ValidationError):
        SearchSpec(price_max=50, price_min_strict=True)


def test_nonshopping_intent_cannot_show_stray_searches():
    parsed = ParsedRequest(intent="off_catalog", mode="new", searches=[SearchSpec()])
    assert parsed.mode is None and not parsed.searches
    parsed = ParsedRequest.model_validate({'intent':'off_catalog','mode':'new',
        'searches':[{'directions':[{'query':'laptop','categories':['invented']}]}]},context={'categories':['laptops']})
    assert parsed.intent == 'off_catalog' and not parsed.searches


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf')])
def test_non_finite_numbers_are_not_valid_constraints_or_catalog_facts(value):
    with pytest.raises(ValidationError):
        SearchSpec(rating_min=value)
    with pytest.raises(ValidationError):
        Product(id=1,title='Product',category='test',price=1,rating=value)


def test_all_source_case_identities_are_unique():
    cases = load_cases()
    assert len(cases) == 167
    assert len({c["key"] for c in cases}) == len(cases)
