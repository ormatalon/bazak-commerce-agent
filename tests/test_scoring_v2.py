import pytest

from evals.scoring import aggregate, ranking_scores, set_scores


def test_empty_set_needs_an_executed_search():
    assert set_scores(set(),set(),False)['f1']==0
    assert set_scores(set(),set())['f1']==1
    assert set_scores({1,2},{2,3})['f1']==0.5


def test_recall_ceiling_and_duplicates():
    grades={i:2 for i in range(20)}
    result=ranking_scores(list(range(10)),grades,set(grades))
    assert result['recall_at_10']==0.5
    assert result['achievable_recall_at_10']==1
    duplicate=ranking_scores([0,0,0],grades,set(grades))
    assert duplicate['precision_at_k']==pytest.approx(1/3)
    assert duplicate['ndcg_at_k']<1


def test_unknown_judgments_do_not_become_negative_labels():
    result=ranking_scores([1,2,3],{1:2},{1,2,3},exhaustive=False)
    assert result['precision_at_k'] is None
    assert result['recall_at_10'] is None
    assert aggregate([{'metrics':{'x':None}},{'metrics':{'x':0}}])['x']['denominator']==1


def test_behavior_labels_include_quiet_fallback_and_card_counts():
    from app.schemas import ConversationState, ParsedRequest, TurnResult
    from evals.scoring import score_turn
    result = TurnResult(parsed=ParsedRequest(intent='small_talk'), reply='Hello', state=ConversationState())
    metrics = score_turn(result, {'expect_fallback':None, 'expected_card_ids':[], 'min_cards':1}, [])
    assert metrics['legacy_fallback_accuracy'] == 1
    assert metrics['legacy_expected_cards'] == 1
    assert metrics['minimum_cards'] == 0


def test_grounding_title_check_ignores_prefixes_and_embedded_titles():
    from app.schemas import Product
    from evals.scoring import unshown_catalog_titles
    products=[Product(id=i,title=title,category='test',price=1,rating=4) for i,title in
              [(1,'Realme X'),(2,'Realme XT'),(3,'Watch Gold'),(4,'Watch Gold for Women')]]
    assert unshown_catalog_titles('Realme XT and Watch Gold for Women',products,{2,4})==[]
    assert unshown_catalog_titles('Realme X',products,{2})==['Realme X']
