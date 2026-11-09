import json

import numpy as np

from app.config import RetrievalConfig
from app.index import ProductIndex
from app.pipeline import rebuild_state, run_turn, turn_metadata
from app.schemas import ConversationState, Product


class Embedder:
    def encode(self, texts, query=False):
        return np.asarray([[1., 0.] for _ in texts], dtype=np.float32)


def setup_index():
    products = [Product(id=i, title=f'Laptop {i}', category='laptops', price=100*i, rating=4) for i in range(1, 6)]
    products += [Product(id=i, title=f'Other {i}', category='beauty', price=10, rating=3) for i in range(6, 16)]
    index = ProductIndex(products, Embedder(), RetrievalConfig(strong_threshold=0.5, borderline_threshold=0.1), cache=None)
    index.similarities = lambda vector: np.asarray([1.] * 5 + [0.] * 10)
    return products, index


def fake_llm(parsed):
    def llm(messages, schema):
        return json.dumps(parsed) if schema else 'Here are the relevant products.'
    return llm


def test_budget_alternatives_are_disclosed_and_state_is_preserved():
    products, index = setup_index()
    parsed = {'intent':'product_search', 'mode':'new', 'searches':[{'directions':[{'query':'laptop','categories':['laptops']}], 'price_max':150}]}
    result = run_turn('laptops up to $150', ConversationState(), products, ['laptops','beauty'], fake_llm(parsed), index)
    assert [p.id for p in result.outcomes[0].shown] == [1, 2, 3]
    assert result.outcomes[0].cards[0].alternative is False
    assert all(c.alternative for c in result.outcomes[0].cards[1:])
    assert 'Alternative outside your limits' in result.reply
    assert '$150.00' in result.reply
    assert result.state.searches[0].price_max == 150
    restored = rebuild_state([{'metadata': turn_metadata(result)}])
    assert restored == result.state
    more = run_turn('more', restored, products, ['laptops','beauty'], fake_llm({'intent':'product_search','mode':'show_more'}), index)
    assert [p.id for p in more.outcomes[0].shown] == [4,5]
    assert 'Alternative outside your limits' in more.reply
    assert more.state.searches[0].price_max == 150


def test_explicit_exclusion_never_relaxes():
    products, index = setup_index()
    parsed = {'intent':'product_search','mode':'new','searches':[{'directions':[{'query':'laptop','categories':['laptops']}], 'exclude':['laptop'], 'price_max':1}]}
    result = run_turn('no laptops', ConversationState(), products, ['laptops','beauty'], fake_llm(parsed), index)
    assert not result.outcomes[0].cards
    assert result.outcomes[0].reason == 'exclusion_conflict'


def test_unknown_currency_asks_without_cards():
    products, index = setup_index()
    parsed = {'intent':'product_search','mode':'new','searches':[{'directions':[{'query':'laptop'}], 'price_max':50,'currency':'ZZZ'}]}
    result = run_turn('laptop for 50 ZZZ', ConversationState(), products, ['laptops','beauty'], fake_llm(parsed), index)
    assert not result.outcomes and 'US dollars' in result.reply


def test_show_more_pages_beyond_ten_and_honors_global_price_sort():
    from app.schemas import Direction, SearchSpec
    from app.search import search
    products, index = setup_index()
    index.products = [Product(id=i, title='Laptop', category='laptops', price=200-i, rating=4) for i in range(1, 21)]
    # Every product is relevant. Earlier semantic rank differs from ascending price.
    from app.schemas import Candidate
    import app.search as retrieval
    original = retrieval.rank_all
    retrieval.rank_all = lambda *args: [[Candidate(product=p, direction=0, similarity=1, z_score=3, category_boost=0, score=1, zone='strong', relevant=True, reason='accepted') for p in index.products]]
    try:
        spec = SearchSpec(directions=[Direction(query='laptop')], sort_by='price', order='asc')
        assert [c.product.id for c in search(spec,index)] == list(range(20,0,-1))
        assert [c.product.id for c in search(spec,index,seen=set(range(10,21)))] == list(range(9,0,-1))
    finally:
        retrieval.rank_all = original
