"""Independent, pure evaluation math and checks. No production search imports."""

from collections import defaultdict
from math import log2
import re


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


def score_turn(result, case: dict, catalog) -> dict:
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
    if case.get("expected_language"):
        # Remove product names so English catalog titles do not bias Hebrew replies.
        text=result.reply
        for p in catalog:
            text=text.replace(p.title, '')
        letters=[c for c in text if c.isalpha()]
        language='he' if letters and sum('\u0590'<=c<='\u05ff' for c in letters)>len(letters)/2 else 'en'
        metrics["language_accuracy"]=float(language==case['expected_language'])
    # Structured disclosure plus literal presence is evidence of code disclosure only.
    metrics['alternative_disclosure']=float(all(c.product.title in result.reply for c in cards if c.alternative))
    if case.get('expect_fallback') is not None:
        actual={r.field for c in cards for r in c.relaxations}
        expected=case['expect_fallback']
        expected=set(expected if isinstance(expected,list) else [expected])
        actual={"rating" if f=='rating_min' else "price" for f in actual}
        metrics['legacy_fallback_accuracy']=float(actual==expected)
    normalized=[]
    # Independently normalize predicted bounds using dated rate DATA, not app arithmetic.
    from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
    from app.currency import UNITS_PER_DOLLAR
    for outcome in result.outcomes:
        spec=outcome.spec
        rate=UNITS_PER_DOLLAR.get((spec.currency or 'USD').upper())
        if rate is None:
            continue
        bounds={}
        for field in ('price_min','price_max','rating_min'):
            value=getattr(spec,field)
            if value is None:
                bounds[field]=None; continue
            cents=Decimal(str(value))*100/(Decimal(rate) if field!='rating_min' else 1)
            minimum=field!='price_max'; strict=bool(getattr(spec,field+'_strict'))
            integer=cents.to_integral_value(rounding=ROUND_FLOOR if (minimum and strict) or (not minimum and not strict) else ROUND_CEILING)
            if strict: integer+=1 if minimum else -1
            bounds[field]=float(integer/100)
        normalized.append((outcome,bounds))
    numeric_ok=True; exclusions_ok=True
    for outcome,bounds in normalized:
        for card in outcome.cards:
            p=card.product
            if not card.alternative:
                numeric_ok &= all(bounds[f] is None or (getattr(p,'rating' if f=='rating_min' else 'price') <= bounds[f] if f=='price_max' else getattr(p,'rating' if f=='rating_min' else 'price') >= bounds[f]) for f in bounds)
            text=' '.join(re.findall(r'\w+', ' '.join([p.title,p.description,p.brand or '',p.category,*p.tags]).casefold()))
            exclusions_ok &= not any(' '+ ' '.join(re.findall(r'\w+',term.casefold())) +' ' in ' '+text+' ' for term in outcome.spec.exclude or [] if term.strip())
    metrics['exact_numeric_compliance']=float(numeric_ok) if cards else None
    metrics['parsed_exclusion_rule_compliance']=float(exclusions_ok) if cards else None
    allowed_amounts={p.price for p in result.state.shown}
    for outcome,bounds in normalized:
        allowed_amounts.update(value for value in bounds.values() if value is not None)
        allowed_amounts.update(value for value in (outcome.spec.price_min,outcome.spec.price_max) if value is not None)
    dollar_amounts=[float(s.replace(',','')) for s in re.findall(r'\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)',result.reply)]
    metrics['no_unsupported_dollar_amounts']=float(all(any(abs(value-allowed)<0.011 for allowed in allowed_amounts) for value in dollar_amounts))
    # Title and amount checks catch known violations; they do not prove grounding.
    shown={c.product.id for c in cards} | {p.id for p in result.state.shown}
    unseen_titles=[p.title for p in catalog if p.id not in shown and len(p.title.split())>1 and p.title in result.reply]
    metrics['no_unshown_catalog_titles']=float(not unseen_titles)
    leak_terms=['you extract shopping intent','return structured json only','system prompt:','v2-parser-1']
    metrics['no_known_prompt_leak']=float(not any(t in result.reply.casefold() for t in leak_terms))
    is_deterministic=case.get('source')=='deterministic' or case.get('type')=='deterministic'
    if is_deterministic:
        expected=expected_ids(case,catalog)
        returned=list(dict.fromkeys(i for o in result.outcomes for i in o.exact_ids))
        top=number(case.get('top_k'))
        if top: returned=returned[:int(top)]
        retrieval=set_scores(set(expected),set(returned), bool(result.outcomes))
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
            expected_values=[(by_id[i].price if case.get('sort_by')=='price' else by_id[i].rating) for i in expected]
            actual_values=[(by_id[i].price if case.get('sort_by')=='price' else by_id[i].rating) for i in returned]
            metrics['legacy_top_k_order']=float(len(set(returned))==len(expected) and set(returned)<=set(expected_ids({**case,'top_k':None},catalog)) and actual_values==expected_values)
    return metrics


def aggregate(rows: list[dict]) -> dict:
    groups=defaultdict(list)
    for row in rows:
        for key,value in row.get('metrics',{}).items():
            if isinstance(value,(float,int)):
                groups[key].append(float(value))
    return {key:{'mean':sum(values)/len(values),'numerator':sum(values),'denominator':len(values)} for key,values in sorted(groups.items())}
