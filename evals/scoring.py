"""Independent, pure evaluation math and checks. No production search imports."""

from collections import defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from math import log2
import re

from functools import lru_cache

from app.currency import UnsupportedCurrency
from app.schemas import CurrencyRate, Product, SearchOutcome, SearchSpec, TurnResult
from evals.datasets import FrozenRateProvider

INVARIANT_KEYS = (
    'catalog_card_fidelity', 'no_duplicates', 'no_known_prompt_leak', 'no_unshown_catalog_titles',
    'no_unsupported_dollar_amounts', 'exact_numeric_compliance',
    'parsed_exclusion_rule_compliance', 'alternative_disclosure',
)


def set_scores(expected: set[int], returned: set[int], executed: bool = True) -> dict:
    if not expected and not returned:
        return {"precision": float(executed), "recall": float(executed), "f1": float(executed)}
    hits = len(expected & returned)
    precision = hits / len(returned) if returned else 0.0
    recall = hits / len(expected) if expected else 0.0
    return {"precision": precision, "recall": recall,
            "f1": 2*precision*recall/(precision+recall) if precision+recall else 0.0}


def ranking_scores(returned: list[int], grades: dict[int, int], eligible_ids: set[int], k: int = 3,
                   exhaustive: bool = True) -> dict:
    """Unknown labels are not negatives. Full-catalog metrics need full judgments."""
    if k < 1:
        raise ValueError('k must be positive')
    if exhaustive and not eligible_ids <= grades.keys():
        raise ValueError('exhaustive metrics require judgments for every eligible product')
    direct = {i for i in eligible_ids if grades.get(i) == 2}
    first = returned[:k]
    unique_hits = len(set(first) & direct)
    judged = [i for i in first if i in grades]
    result = {"precision_at_k": unique_hits/k if len(judged) == len(first) else None,
              "shown_precision": unique_hits/len(first) if first and len(judged) == len(first) else None,
              "judged_fraction": len(judged)/len(first) if first else None}
    hits = len(set(returned[:10]) & direct)
    result.update({"hit_at_10": float(hits > 0) if exhaustive and direct else None,
                   "recall_at_10": hits/len(direct) if exhaustive and direct else None,
                   "recall_at_10_ceiling": min(10,len(direct))/len(direct) if exhaustive and direct else None,
                   "achievable_recall_at_10": hits/min(10,len(direct)) if exhaustive and direct else None})
    if exhaustive:
        ideal = sorted([grades.get(i, 0) for i in eligible_ids], reverse=True)[:k]
        ideal_dcg = sum((2**grade-1)/log2(n+2) for n,grade in enumerate(ideal))
        known = set()
        dcg = 0.0
        for n,identifier in enumerate(first):
            grade = grades.get(identifier, 0) if identifier in eligible_ids and identifier not in known else 0
            dcg += (2**grade-1)/log2(n+2)
            known.add(identifier)
        result["ndcg_at_k"] = dcg/ideal_dcg if ideal_dcg else None
        result["slot_coverage"] = unique_hits/min(k,len(direct)) if direct else None
    return result


def number(value):
    return None if value in (None, "") else float(value)


def expected_ids(case: dict, catalog) -> list[int]:
    """Legacy CSV oracle: independent of production filtering and ranking."""
    category = case.get("category")
    low, high, rating = (number(case.get(field)) for field in ("price_min", "price_max", "rating_min"))
    products = [p for p in catalog if (not category or p.category == category)
                and (low is None or p.price >= low) and (high is None or p.price <= high)
                and (rating is None or p.rating >= rating)]
    sort = case.get("sort_by")
    if sort:
        products.sort(key=lambda p: ((-1 if case.get("order")=="desc" else 1)*getattr(p,sort),p.id))
    else:
        products.sort(key=lambda p: (-p.rating,p.id))
    top = number(case.get("top_k"))
    return [p.id for p in (products[:int(top)] if top else products)]


def _same(left, right) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(left-right) < 0.00001


def unshown_catalog_titles(reply: str, catalog, shown: set[int]) -> list[str]:
    """Avoid prefix titles and shorter titles embedded in a shown product's name."""
    text = reply
    for product in sorted((p for p in catalog if p.id in shown), key=lambda p: len(p.title), reverse=True):
        text = re.sub(r'(?<!\w)' + re.escape(product.title) + r'(?!\w)', ' ', text)
    return [p.title for p in catalog if p.id not in shown and len(p.title.split()) > 1
            and re.search(r'(?<!\w)' + re.escape(p.title) + r'(?!\w)', text)]


def normalized_bounds(spec: SearchSpec, rate: CurrencyRate | None = None) -> dict[str, float | None] | None:
    """Independent arithmetic using the recorded quote, never today's API rate."""
    code = (spec.currency or 'USD').strip().upper()
    units_per_usd = Decimal(1)
    if code != 'USD' and (spec.price_min is not None or spec.price_max is not None):
        if rate is None or rate.currency != code:
            return None
        units_per_usd = rate.units_per_usd
    bounds = {}
    for field in ('price_min', 'price_max', 'rating_min'):
        value = getattr(spec, field)
        if value is None:
            bounds[field] = None
            continue
        units = units_per_usd if field != 'rating_min' else Decimal(1)
        cents = Decimal(str(value)) * 100 / units
        minimum = field != 'price_max'
        strict = bool(getattr(spec, field + '_strict'))
        rounding = ROUND_CEILING if minimum else ROUND_FLOOR
        integer = cents.to_integral_value(rounding=rounding)
        if strict and integer == cents:
            integer += 1 if minimum else -1
        bounds[field] = float(integer / 100)
    return bounds


@lru_cache(maxsize=1)
def _legacy_rates() -> FrozenRateProvider:
    return FrozenRateProvider()


def recorded_rate(outcome: SearchOutcome) -> CurrencyRate | None:
    if outcome.exchange_rate is not None or 'exchange_rate' in outcome.model_fields_set:
        return outcome.exchange_rate
    # Archives made before API rates used this exact fixture. Only those old
    # records may omit provenance; new records must carry their actual quote.
    try:
        return _legacy_rates().get_rate(outcome.spec.currency or 'USD')
    except UnsupportedCurrency:
        return None


def passes_bounds(product: Product, bounds: dict) -> bool:
    return ((bounds['price_min'] is None or product.price >= bounds['price_min'])
            and (bounds['price_max'] is None or product.price <= bounds['price_max'])
            and (bounds['rating_min'] is None or product.rating >= bounds['rating_min']))


def disclosure_matches(card, reply: str) -> bool:
    if card.alternative != bool(card.relaxations):
        return False
    if not card.alternative:
        return True
    prefixes = (f'Alternative outside your limits: {card.product.title} — ',
                f'חלופה מחוץ למגבלות: {card.product.title} — ')
    lines = [line for line in reply.splitlines() if line.startswith(prefixes)]
    for line in lines:
        values = []
        for change in card.relaxations:
            if change.field == 'rating_min':
                values.extend((f'{change.original:g}', f'{change.actual:g}'))
            else:
                values.extend((f'${change.original:,.2f}', f'${change.actual:,.2f}'))
        if all(value in line for value in values):
            return True
    return False


def top_k_matches(case: dict, catalog: list[Product], returned: list[int]) -> bool:
    by_id = {p.id: p for p in catalog}
    expected = expected_ids(case, catalog)
    eligible = set(expected_ids({**case, 'top_k': None}, catalog))
    if len(returned) != len(expected) or len(set(returned)) != len(returned) or not set(returned) <= eligible:
        return False
    field = 'price' if case.get('sort_by') == 'price' else 'rating'
    return [getattr(by_id[i], field) for i in returned] == [getattr(by_id[i], field) for i in expected]


def score_turn(result: TurnResult, case: dict, catalog: list[Product]) -> dict:
    """Observable checks only. Unknown semantic correctness remains None."""
    by_id = {p.id:p for p in catalog}
    cards = [c for o in result.outcomes for c in o.cards]
    identifiers = [c.product.id for c in cards]
    facts_ok = all(c.product.id in by_id and c.product.model_dump() == by_id[c.product.id].model_dump() for c in cards)
    metrics = {"catalog_card_fidelity": float(facts_ok),
               "no_duplicates": float(len(identifiers)==len(set(identifiers))),
               "intent_accuracy": float(result.parsed.intent==case["expected_intent"]) if case.get("expected_intent") else None,
               "mode_accuracy": float(result.parsed.mode==case.get("expected_mode")) if "expected_mode" in case else None,
               "semantic_grounding_reviewed": None, "task_success_reviewed": None}
    expected_categories = set(case.get("expected_categories", []))
    shown_categories = {c.product.category for c in cards}
    match = case.get("category_match")
    metrics["legacy_category_accuracy"] = (float(shown_categories==expected_categories) if match=="all" else
        float(bool(shown_categories) and shown_categories <= expected_categories) if match=="any" else None)
    forbidden = set(case.get("forbidden_card_ids", []))
    metrics["forbidden_card_compliance"] = float(not (forbidden & set(identifiers))) if forbidden else None
    required = set(case.get("required_card_ids", []))
    metrics["required_cards_present"] = float(required <= set(identifiers)) if required else None
    if "expected_card_ids" in case:
        metrics["legacy_expected_cards"] = float(set(identifiers) == set(case["expected_card_ids"]))
    if "min_cards" in case:
        metrics["minimum_cards"] = float(len(identifiers) >= case["min_cards"])
    if case.get("expected_language"):
        # Remove product names so English catalog titles do not bias Hebrew replies.
        text=result.reply
        for p in catalog:
            text=text.replace(p.title, '')
        letters=[c for c in text if c.isalpha()]
        language='he' if letters and sum('\u0590'<=c<='\u05ff' for c in letters)>len(letters)/2 else 'en'
        metrics["language_accuracy"]=float(language==case['expected_language'])
    # Structured disclosure plus literal presence is evidence of code disclosure only.
    metrics['alternative_disclosure']=float(all(disclosure_matches(c, result.reply) for c in cards))
    if 'expect_fallback' in case:
        actual={r.field for c in cards for r in c.relaxations}
        expected=case['expect_fallback']
        expected=set() if expected is None else ({'price','rating'} if expected=='both' else set(expected if isinstance(expected,list) else [expected]))
        actual={"rating" if f=='rating_min' else "price" for f in actual}
        metrics['legacy_fallback_accuracy']=float(actual==expected)
    normalized=[]
    for outcome in result.outcomes:
        bounds = normalized_bounds(outcome.spec, recorded_rate(outcome))
        if bounds is not None:
            normalized.append((outcome, bounds))
    numeric_ok=True; exclusions_ok=True
    for outcome,bounds in normalized:
        for card in outcome.cards:
            p=card.product
            if not card.alternative:
                numeric_ok &= passes_bounds(p, bounds)
    for outcome in result.outcomes:
        for card in outcome.cards:
            p=card.product
            text=' '.join(re.findall(r'\w+', ' '.join([p.title,p.description,p.brand or '',p.category,*p.tags]).casefold()))
            exclusions_ok &= not any(' '+ ' '.join(re.findall(r'\w+',term.casefold())) +' ' in ' '+text+' ' for term in outcome.spec.exclude or [] if term.strip())
    exact_cards = [card for card in cards if not card.alternative]
    metrics['exact_numeric_compliance']=float(numeric_ok) if exact_cards and len(normalized)==len(result.outcomes) else None
    metrics['parsed_exclusion_rule_compliance']=float(exclusions_ok) if cards else None
    allowed_amounts={p.price for p in result.state.shown}
    for outcome,bounds in normalized:
        allowed_amounts.update(bounds[field] for field in ('price_min','price_max') if bounds[field] is not None)
        allowed_amounts.update(value for value in (outcome.spec.price_min,outcome.spec.price_max) if value is not None)
    dollar_amounts=[float(s.replace(',','')) for s in re.findall(r'\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)',result.reply)]
    metrics['no_unsupported_dollar_amounts']=float(all(any(_same(value,allowed) for allowed in allowed_amounts) for value in dollar_amounts))
    # Title and amount checks catch known violations; they do not prove grounding.
    shown={c.product.id for c in cards} | {p.id for p in result.state.shown}
    unseen_titles=unshown_catalog_titles(result.reply,catalog,shown)
    metrics['no_unshown_catalog_titles']=float(not unseen_titles)
    leak_terms=['you extract shopping intent','return structured json only','system prompt:','v2-parser-1']
    version_leak = re.search(r'\bv2-(?:parser|responder|product-type)-\d+\b', result.reply.casefold())
    metrics['no_known_prompt_leak']=float(not version_leak and not any(t in result.reply.casefold() for t in leak_terms))
    is_deterministic=case.get('source')=='deterministic' or case.get('type')=='deterministic'
    if is_deterministic:
        labeled_bounds={field:number(case.get(field)) for field in ('price_min','price_max','rating_min')}
        exact_cards=[c for c in cards if not c.alternative]
        metrics['labeled_exact_numeric_compliance']=(float(all(passes_bounds(c.product,labeled_bounds) for c in exact_cards))
            if exact_cards and any(v is not None for v in labeled_bounds.values()) else None)
        expected=expected_ids(case,catalog)
        returned=list(dict.fromkeys(i for o in result.outcomes for i in o.exact_ids))
        top=number(case.get('top_k'))
        if top: returned=returned[:int(top)]
        executed = any(case.get('category') in direction.categories for outcome in result.outcomes for direction in outcome.spec.directions or [])
        top_ok = top_k_matches(case,catalog,returned) and (bool(expected) or executed) if top else None
        retrieval=set_scores(set(returned) if top_ok else set(expected),set(returned),executed)
        metrics.update({'legacy_'+key:value for key,value in retrieval.items()})
        if normalized:
            outcome,bounds=normalized[0]
            categories={slug for d in outcome.spec.directions or [] for slug in d.categories}
            numeric_fields=all(_same(number(case.get(f)),bounds[f]) for f in bounds)
            options=all((case.get(f) or None)==getattr(outcome.spec,f) for f in ('sort_by','order'))
            metrics['numeric_sort_count_exact_match']=float(numeric_fields and options and _same(number(case.get('top_k')),outcome.spec.top_k))
            metrics['legacy_category_guess']=float(case.get('category') in categories)
        else:
            metrics['numeric_sort_count_exact_match']=0.0
        if top:
            metrics['legacy_top_k_order']=float(top_ok)
    return metrics


def failure_metrics(case: dict) -> dict:
    """An execution failure is a failed applicable accuracy case, never excluded."""
    metrics = {'execution_success': 0.0}
    if case.get('expected_intent'):
        metrics['intent_accuracy'] = 0.0
    if 'expected_mode' in case:
        metrics['mode_accuracy'] = 0.0
    if case.get('source') == 'deterministic' or case.get('type') == 'deterministic':
        metrics.update({key: 0.0 for key in ('legacy_precision', 'legacy_recall', 'legacy_f1', 'numeric_sort_count_exact_match')})
        if number(case.get('top_k')):
            metrics['legacy_top_k_order'] = 0.0
    if case.get('category_match') in ('all', 'any'):
        metrics['legacy_category_accuracy'] = 0.0
    for label, key in (('required_card_ids', 'required_cards_present'),
                       ('expected_card_ids', 'legacy_expected_cards'), ('min_cards', 'minimum_cards'), ('expected_language', 'language_accuracy')):
        if label in case and case[label] is not None:
            metrics[key] = 0.0
    return metrics


def score_record(record: dict, catalog: list[Product]) -> dict:
    """One scoring path for live replay and free re-scoring of saved predictions."""
    row = {**record, 'turns': [dict(turn) for turn in record['turns']]}
    if row.get('error_stage') == 'scoring' and len(row['turns']) == len(row['case']['turns']):
        row['prior_scoring_error'] = row['error']
        row['error'] = None
        row['error_stage'] = None
    results = []
    for turn in row['turns']:
        result = TurnResult.model_validate(turn['result'])
        results.append(result)
        turn['metrics'] = score_turn(result, row['case'], catalog)
    if row['error']:
        metrics = failure_metrics(row['case'])
    else:
        if len(results) != len(row['case']['turns']):
            raise ValueError('Successful record must contain every conversation turn')
        metrics = dict(row['turns'][-1]['metrics'])
        metrics['execution_success'] = 1.0
    for key in INVARIANT_KEYS:
        values = [turn['metrics'][key] for turn in row['turns'] if turn['metrics'].get(key) is not None]
        metrics[key] = min(values) if values else None
    overlay = row.get('v2_expectation')
    if overlay:
        case = {**row['case'], **overlay}
        scores = failure_metrics(case) if row['error'] else score_turn(results[-1], case, catalog)
        prefix = 'v2_' if overlay.get('review_status') == 'reviewed' else 'v2_draft_'
        metrics.update({prefix + key: value for key, value in scores.items()
                        if key in ('intent_accuracy', 'mode_accuracy', 'legacy_category_accuracy')})
    row['metrics'] = metrics
    return row


def aggregate(rows: list[dict]) -> dict:
    groups=defaultdict(list)
    for row in rows:
        for key,value in row.get('metrics',{}).items():
            if isinstance(value,(float,int)):
                if not math.isfinite(value):
                    raise ValueError(f'Non-finite metric: {key}')
                groups[key].append(float(value))
    return {key:{'mean':sum(values)/len(values),'numerator':sum(values),'denominator':len(values)} for key,values in sorted(groups.items())}
