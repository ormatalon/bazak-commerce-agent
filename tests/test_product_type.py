"""The new node rejects wrong types without weakening numeric/exclusion rules."""

import json
from types import SimpleNamespace

import pytest

from app.fallback import search_with_fallback
from app.product_type import BATCH_SIZE, ProductTypeCheckError, check_product_types
from app.schemas import Candidate, Direction, LLM, Product, SearchSpec


def candidate(identifier: int, title: str = "Laptop", price: float = 200) -> Candidate:
    return Candidate(product=Product(id=identifier, title=title, category="inventory", price=price, rating=4),
                     direction=0, similarity=0.9, z_score=3, category_boost=0, score=0.9,
                     zone="strong", relevant=True, reason="accepted")


def checker(accepted: set[int], calls: list) -> LLM:
    def llm(messages, schema):
        items = json.loads(messages[-1]["content"])["items"]
        calls.append(items)
        return json.dumps({"decisions": [{"item_id": item["item_id"],
                           "compatible": item["product"]["id"] in accepted,
                           "reason": "Product type assessed from catalog evidence"} for item in items]})
    return llm


def test_wrong_type_rejected_even_when_similarity_is_strong():
    spec = SearchSpec(directions=[Direction(query="gaming console")])
    original = candidate(1, "Basketball")
    checked = check_product_types([spec], [[[original]]], checker(set(), []))
    assert not checked[0][0][0].relevant
    assert checked[0][0][0].type_compatible is False
    assert original.relevant  # the ranking input is not mutated


def test_fallback_cannot_reintroduce_a_rejected_product():
    spec = SearchSpec(directions=[Direction(query="laptop")], price_max=100)
    calls = []
    checked = check_product_types([spec], [[[candidate(1, "Basketball", 90), candidate(2)]]], checker({2}, calls))
    # Price is deliberately absent from the type-check payload: code owns budgets.
    assert all("price" not in item["product"] for item in calls[0])
    index = SimpleNamespace(config=SimpleNamespace(candidate_window=10))
    outcome = search_with_fallback(spec, spec, index, ranked=checked[0])
    assert [card.product.id for card in outcome.cards] == [2]
    assert outcome.cards[0].alternative
    assert outcome.cards[0].relaxations[0].field == "price_max"


@pytest.mark.parametrize("response", ["not json", '{"decisions": []}',
    '{"decisions": [{"item_id": 99, "compatible": true, "reason": "invented ID"}]}',
    '{"decisions": [{"item_id": 0, "compatible": true, "reason": "ok"}, {"item_id": 0, "compatible": false, "reason": "duplicate"}]}'])
def test_invalid_missing_invented_or_duplicate_verdicts_fail_closed(response):
    spec = SearchSpec(directions=[Direction(query="laptop")])
    with pytest.raises(ProductTypeCheckError):
        check_product_types([spec], [[[candidate(1)]]], lambda messages, schema: response)


def test_batching_preserves_inventory_and_deduplicates_queries():
    spec = SearchSpec(directions=[Direction(query="laptop")])
    items = [candidate(i) for i in range(BATCH_SIZE+5)]
    calls = []
    checked = check_product_types([spec, spec], [[items], [items]], checker(set(range(BATCH_SIZE+5)), calls))
    assert [len(batch) for batch in calls] == [BATCH_SIZE, 5]
    assert all(c.relevant for groups in checked for group in groups for c in group)


def test_excluded_seen_and_weak_products_never_trigger_type_calls():
    spec = SearchSpec(directions=[Direction(query="laptop")], exclude=["leather"])
    weak = candidate(3).model_copy(update={"relevant": False, "zone": "weak"})
    calls = []
    checked = check_product_types([spec], [[[candidate(1, "Leather Laptop"), candidate(2), weak]]], checker(set(), calls), seen={2})
    assert not calls
    index = SimpleNamespace(config=SimpleNamespace(candidate_window=10))
    outcome = search_with_fallback(spec, spec, index, seen={2}, ranked=checked[0])
    assert not outcome.cards
