import json
import pytest

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
        if schema and schema.__name__ == 'TypeCheckResult':
            items = json.loads(messages[-1]['content'])['items']
            return json.dumps({'decisions': [{'item_id': item['item_id'], 'compatible': True, 'reason': 'Test product type matches'} for item in items]})
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


@pytest.mark.parametrize('limits,expected_ids', [
    ({'price_max': 50}, []),
    ({'price_max': 150}, [1]),
    ({'price_min': 600}, []),
    ({'rating_min': 4.5}, []),
])
def test_disallowed_alternatives_never_fill_missing_slots(limits, expected_ids):
    products, index = setup_index()
    parsed = {'intent': 'product_search', 'mode': 'new', 'searches': [{
        'directions': [{'query': 'laptop'}], 'allow_alternatives': False, **limits,
    }]}
    result = run_turn('Only within these limits; no alternatives', ConversationState(),
                      products, ['laptops', 'beauty'], fake_llm(parsed), index)
    outcome = result.outcomes[0]
    assert [p.id for p in outcome.shown] == expected_ids
    assert not any(c.alternative for c in outcome.cards)
    assert not outcome.has_more
    if not expected_ids:
        assert outcome.reason == 'numeric_conflict'


def test_strict_limits_survive_resume_refinement_and_pagination_until_reenabled():
    products, index = setup_index()

    def turn(message, state, parsed):
        return run_turn(message, state, products, ['laptops', 'beauty'], fake_llm(parsed), index)

    first = turn('Only laptops up to $350, show one', ConversationState(), {
        'intent': 'product_search', 'mode': 'new', 'searches': [{
            'directions': [{'query': 'laptop'}], 'price_max': 350,
            'top_k': 1, 'allow_alternatives': False,
        }],
    })
    restored = rebuild_state([{'metadata': json.dumps(turn_metadata(first))}])
    refined = turn('Sort cheapest first', restored, {
        'intent': 'product_search', 'mode': 'refine',
        'searches': [{'sort_by': 'price', 'order': 'asc'}],
    })
    assert refined.state.searches[0].allow_alternatives is False
    state = refined.state
    for expected in ([2], [3], []):
        more = turn('show more', state, {'intent': 'product_search', 'mode': 'show_more'})
        assert [p.id for p in more.outcomes[0].shown] == expected
        assert not any(c.alternative for c in more.outcomes[0].cards)
        state = more.state
    assert not more.outcomes[0].has_more

    allowed = turn('Alternatives are fine now; show all', state, {
        'intent': 'product_search', 'mode': 'refine',
        'searches': [{'allow_alternatives': True, 'show_all': True}],
    })
    assert allowed.state.searches[0].price_max == 350
    assert [p.id for p in allowed.outcomes[0].shown] == [1, 2, 3, 4, 5]
    assert [c.product.id for c in allowed.outcomes[0].cards if c.alternative] == [4, 5]
    assert 'Alternative outside your limits' in allowed.reply

    new = turn('New laptop request, up to $150', state, {
        'intent': 'product_search', 'mode': 'new',
        'searches': [{'directions': [{'query': 'laptop'}], 'price_max': 150}],
    })
    assert new.state.searches[0].allow_alternatives is None
    assert any(c.alternative for c in new.outcomes[0].cards)


def test_strict_limits_apply_only_to_their_independent_request():
    products, index = setup_index()
    parsed = {'intent': 'product_search', 'mode': 'new', 'searches': [
        {'directions': [{'query': 'laptop'}], 'price_max': 150, 'allow_alternatives': False},
        {'directions': [{'query': 'laptop'}], 'price_max': 150, 'allow_alternatives': True},
    ]}
    result = run_turn('Two independent requests', ConversationState(), products,
                      ['laptops', 'beauty'], fake_llm(parsed), index)
    assert [p.id for p in result.outcomes[0].shown] == [1]
    assert all(c.alternative for c in result.outcomes[1].cards)


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


def test_numeric_followup_keeps_current_message_and_previous_language():
    from app.schemas import ChatTurn, Direction, SearchSpec
    products, index = setup_index()
    state = ConversationState(history=[ChatTurn(role='user', text='מחשב נייד')],
                              searches=[SearchSpec(directions=[Direction(query='laptop')])])
    parsed = {'intent':'product_search','mode':'refine','searches':[{'price_max':200}]}
    underlying = fake_llm(parsed)
    response_contexts = []

    def llm(messages, schema):
        if schema is None:
            response_contexts.append(json.loads(messages[-1]['content']))
        return underlying(messages, schema)

    result = run_turn('200', state, products, ['laptops','beauty'], llm, index)
    assert response_contexts[0]['message'] == '200'
    assert response_contexts[0]['reply_language'] == 'Hebrew'
    assert result.state.searches[0].price_max == 200


def test_index_error_is_not_hidden_as_user_ambiguity():
    products, index = setup_index()
    def broken_index(vector):
        raise ValueError('invalid vector')
    index.similarities = broken_index
    state = ConversationState()
    parsed = {'intent':'product_search','mode':'new','searches':[{'directions':[{'query':'laptop'}]}]}
    with pytest.raises(ValueError, match='invalid vector'):
        run_turn('laptop', state, products, ['laptops'], fake_llm(parsed), index)
    assert not state.history and not state.searches


def test_structured_history_stays_bounded_after_resume():
    from app.parser import HISTORY_LIMIT
    from app.schemas import ChatTurn
    products, index = setup_index()
    state = ConversationState(history=[ChatTurn(role='user',text=f'message {i}') for i in range(20)])
    result = run_turn('hello',state,products,['laptops'],fake_llm({'intent':'small_talk'}),index)
    assert len(result.state.history) == HISTORY_LIMIT
    assert rebuild_state([{'metadata':turn_metadata(result)}]) == result.state


def test_corrupt_card_metadata_does_not_break_resume():
    from app.pipeline import card_elements
    assert card_elements([{'id':'x','metadata':{'app':2,'cards':None}}],'thread') == []
    assert card_elements([{'id':'x','metadata':{'app':2,'cards':[['bad']]}}],'thread') == []


def test_conversation_quote_is_pinned_across_refinement_and_resume():
    from decimal import Decimal
    from evals.datasets import FrozenRateProvider
    products, index = setup_index()
    base = FrozenRateProvider().get_rate('ILS')

    class Source:
        calls = 0

        def get_rate(self, code):
            self.calls += 1
            return base.model_copy(update={'units_per_usd': Decimal(self.calls + 2)})

    source = Source()
    parsed = {'intent':'product_search','mode':'new','searches':[{'directions':[{'query':'laptop'}], 'price_max':900,'currency':'ILS'}]}
    first = run_turn('laptop up to 900 shekels', ConversationState(), products, ['laptops'], fake_llm(parsed), index, rate_provider=source)
    restored = rebuild_state([{'metadata':json.dumps(turn_metadata(first))}])
    refined = run_turn('up to 600', restored, products, ['laptops'],
                       fake_llm({'intent':'product_search','mode':'refine','searches':[{'price_max':600}]}), index, rate_provider=source)
    more = run_turn('more', refined.state, products, ['laptops'], fake_llm({'intent':'product_search','mode':'show_more'}), index, rate_provider=source)
    assert source.calls == 1
    assert first.state.searches[0].price_max == 900 and refined.state.searches[0].price_max == 600
    assert refined.state.searches[0].currency == 'ILS'
    assert more.outcomes[0].exchange_rate == first.outcomes[0].exchange_rate == restored.exchange_rates['ILS']
    assert 'conversation rate' in more.reply
    fresh = run_turn('laptop', ConversationState(), products, ['laptops'], fake_llm(parsed), index, rate_provider=source)
    assert source.calls == 2
    assert fresh.outcomes[0].exchange_rate.units_per_usd == Decimal(4)


def test_currency_outage_does_not_commit_partial_quotes_or_change_searches():
    from app.currency import RateUnavailable
    from evals.datasets import FrozenRateProvider
    products, index = setup_index()

    class Source:
        def get_rate(self, code):
            if code == 'EUR':
                raise RateUnavailable('offline')
            return FrozenRateProvider().get_rate(code)

    parsed = {'intent':'product_search','mode':'new','searches':[
        {'directions':[{'query':'laptop'}], 'price_max':900,'currency':'ILS'},
        {'directions':[{'query':'laptop'}], 'price_max':500,'currency':'EUR'}]}
    state = ConversationState()
    result = run_turn('two laptops', state, products, ['laptops'], fake_llm(parsed), index, rate_provider=Source())
    assert result.parsed.intent == 'needs_clarification' and not result.outcomes
    assert 'US dollars' in result.reply
    assert not result.state.exchange_rates and not result.state.searches
    assert not state.history and not state.exchange_rates
