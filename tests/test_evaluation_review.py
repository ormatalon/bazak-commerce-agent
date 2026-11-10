"""Independent regression cases for review findings in evaluation and calibration."""

import json
from pathlib import Path
import sys

import pytest

from app.schemas import Card, ConversationState, Direction, ParsedRequest, Product, Relaxation, SearchOutcome, SearchSpec, TurnResult
from evals.calibrate import select_thresholds
from evals.datasets import load_cases, load_evidence
from evals.scoring import aggregate, ranking_scores, score_record, score_turn


def result_with(product, *, reply='', spec=None, alternative=False, changes=None, exact_ids=None):
    spec=spec or SearchSpec(directions=[Direction(query='product',categories=['test'])])
    outcome=SearchOutcome(spec=spec,cards=[Card(product=product,alternative=alternative,relaxations=changes or [])],
                          exact_ids=exact_ids if exact_ids is not None else [product.id])
    return TurnResult(parsed=ParsedRequest(intent='product_search',mode='new',searches=[spec]),
                      outcomes=[outcome],reply=reply,state=ConversationState(shown=[product]))


def test_rating_is_not_an_allowed_dollar_price():
    product=Product(id=1,title='Product',category='test',price=25,rating=4.8)
    result=result_with(product,reply='Product costs $4.50',spec=SearchSpec(rating_min=4.5))
    assert score_turn(result,{},[product])['no_unsupported_dollar_amounts'] == 0


def test_alternative_title_alone_does_not_prove_disclosure():
    product=Product(id=1,title='Product',category='test',price=25,rating=4)
    changes=[Relaxation(field='price_max',original=20,actual=25)]
    result=result_with(product,reply='Product costs $25.00.',alternative=True,changes=changes)
    assert score_turn(result,{},[product])['alternative_disclosure'] == 0
    result.reply='Alternative outside your limits: Product — $25.00; maximum $20.00.'
    assert score_turn(result,{},[product])['alternative_disclosure'] == 1


def test_top_k_tie_gets_full_credit_for_an_equivalent_product():
    products=[Product(id=i,title=f'Product {i}',category='test',price=10,rating=4) for i in (1,2)]
    spec=SearchSpec(directions=[Direction(query='product',categories=['test'])],sort_by='price',order='asc',top_k=1)
    result=result_with(products[1],spec=spec)
    case={'source':'deterministic','category':'test','sort_by':'price','order':'asc','top_k':1}
    scores=score_turn(result,case,products)
    assert scores['legacy_top_k_order'] == 1 and scores['legacy_f1'] == 1


def test_exhaustive_metrics_cannot_assume_unjudged_products_are_negative():
    with pytest.raises(ValueError,match='judgments'):
        ranking_scores([1],{1:2},{1,2})
    with pytest.raises(ValueError,match='positive'):
        ranking_scores([],{},{},k=0)


def test_failed_cases_remain_in_accuracy_denominators():
    case={'source':'behavioral','turns':['hello'],'expected_intent':'small_talk','expected_mode':None}
    failed=score_record({'case':case,'turns':[],'error':'TimeoutError'},[])
    combined=aggregate([failed,{'metrics':{'intent_accuracy':1.0}}])
    assert combined['intent_accuracy']['denominator'] == 2
    assert combined['intent_accuracy']['mean'] == 0.5


def test_scoring_error_can_be_recovered_without_a_model_call():
    result=TurnResult(parsed=ParsedRequest(intent='small_talk'),reply='Hello',state=ConversationState())
    record={'case':{'source':'behavioral','turns':['hello'],'expected_intent':'small_talk','expected_mode':None},
            'turns':[{'turn':0,'result':result.model_dump(mode='json')}],
            'error':'ValueError','error_stage':'scoring'}
    recovered=score_record(record,[])
    assert recovered['error'] is None and recovered['prior_scoring_error'] == 'ValueError'
    assert recovered['metrics']['execution_success'] == 1
    assert score_record(recovered,[])['metrics'] == recovered['metrics']


def test_loader_rejects_a_string_instead_of_conversation_turns(tmp_path):
    (tmp_path/'deterministic.csv').write_text('id,query\n',encoding='utf-8')
    for source in ('behavioral','adversarial','hebrew'):
        (tmp_path/f'{source}.jsonl').write_text('',encoding='utf-8')
    (tmp_path/'behavioral.jsonl').write_text(json.dumps({'id':1,'turns':'do not replay characters'}),encoding='utf-8')
    with pytest.raises(ValueError,match='invalid turns'):
        load_cases(tmp_path)


def write_evidence(directory: Path, rows, count):
    (directory/'metadata.json').write_text(json.dumps({'case_count':count,'git_sha':'test'}),encoding='utf-8')
    (directory/'cases.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')


def evidence_row(key='test:1'):
    return {'key':key,'case':{'turns':['hello']},'turns':[{'result':{}}],'error':None,'metrics':{'execution_success':1}}


def test_duplicate_and_incomplete_evidence_are_rejected(tmp_path):
    write_evidence(tmp_path,[evidence_row(),evidence_row()],2)
    with pytest.raises(ValueError,match='Duplicate'):
        load_evidence(tmp_path)
    write_evidence(tmp_path,[evidence_row()],2)
    with pytest.raises(ValueError,match='incomplete'):
        load_evidence(tmp_path)


def test_invalid_evidence_is_rejected_before_any_langsmith_operation(tmp_path,monkeypatch):
    import evals.langsmith_experiment as experiment
    write_evidence(tmp_path,[evidence_row()],2)
    def forbidden_client():
        raise AssertionError('A client must not be created for incomplete evidence')
    monkeypatch.setattr(experiment,'get_client',forbidden_client)
    monkeypatch.setattr(sys,'argv',['langsmith_experiment',str(tmp_path)])
    with pytest.raises(ValueError,match='incomplete'):
        experiment.main()


def test_calibration_cannot_certify_an_uninformative_index():
    rows=[{'z_score':0,'semantic_grade':grade,'informative':False} for grade in (0,2)]
    with pytest.raises(ValueError,match='No viable'):
        select_thresholds(rows)
    viable=select_thresholds([{'z_score':0,'semantic_grade':0},{'z_score':4,'semantic_grade':2}])
    assert viable['precision'] == 1 and viable['recall'] == 1
