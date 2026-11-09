"""Fill missing slots with disclosed nearest alternatives, preserving exclusions."""

from app.index import ProductIndex
from app.observability import span
from app.schemas import Candidate, Card, Product, Relaxation, SearchOutcome, SearchSpec
from app.search import eligible_lists, merge_directions, rank_all


def _changes(product: Product, spec: SearchSpec) -> list[Relaxation]:
    changes = []
    for field, actual in (("rating_min", product.rating), ("price_min", product.price), ("price_max", product.price)):
        original = getattr(spec, field)
        if original is not None and ((field != "price_max" and actual < original) or (field == "price_max" and actual > original)):
            changes.append(Relaxation(field=field, original=original, actual=actual))
    return changes


def _relaxed_candidates(spec: SearchSpec, ranked: list[list[Candidate]], seen: set[int]) -> list[Candidate]:
    # Stage 1: rating-only alternatives before any price relaxation.
    no_rating = spec.model_copy(update={"rating_min": None})
    groups = eligible_lists(no_rating, ranked, seen)
    if not spec.sort_by:
        for group in groups:
            group.sort(key=lambda c: (-c.product.rating, -c.score, c.product.id))
    rating = merge_directions(groups) if spec.rating_min is not None else []
    used = seen | {c.product.id for c in rating}

    # Stage 2: one price bound at a time. The opposite bound remains in force.
    groups = [[] for _ in ranked]
    for field in ("price_min", "price_max"):
        if getattr(spec, field) is None:
            continue
        relaxed = no_rating.model_copy(update={field: None})
        for number, candidates in enumerate(eligible_lists(relaxed, ranked, used)):
            groups[number].extend(candidates)
    for group in groups:
        group.sort(key=lambda c: (sum(abs(r.actual-r.original) for r in _changes(c.product, spec) if r.field.startswith("price")),
                                  -c.score, c.product.id))
    return rating + merge_directions(groups)


def search_with_fallback(original: SearchSpec, normalized: SearchSpec, index: ProductIndex,
                         seen: set[int] | None = None, query_cache: dict | None = None,
                         ranked: list[list[Candidate]] | None = None) -> SearchOutcome:
    seen = seen or set()
    if ranked is None:
        ranked = rank_all(normalized, index, query_cache)
    exact = merge_directions(eligible_lists(normalized, ranked, seen))
    exact_ids = [c.product.id for c in exact]
    count = normalized.top_k or 3
    with span("fallback", {"exact_count": len(exact), "requested": count}) as run:
        alternatives = _relaxed_candidates(normalized, ranked, seen | set(exact_ids))
        selected = exact + alternatives
        page = selected if normalized.show_all else selected[:count]
        cards = []
        for candidate in page:
            changes = _changes(candidate.product, normalized)
            cards.append(Card(product=candidate.product, relaxations=changes, alternative=bool(changes)))
        reason = "alternatives" if any(c.alternative for c in cards) else "exact"
        if not cards:
            unlimited = normalized.model_copy(update={"price_min": None, "price_max": None, "rating_min": None})
            if merge_directions(eligible_lists(unlimited, ranked, seen)):
                reason = "numeric_conflict"
            elif seen and merge_directions(eligible_lists(unlimited, ranked)):
                reason = "exhausted"
            elif any(c.relevant for group in ranked for c in group):
                reason = "exclusion_conflict"
            else:
                reason = "relevance_uncertain"
        outcome = SearchOutcome(spec=original, cards=cards, exact_ids=exact_ids,
                                total=len(selected), has_more=len(selected) > len(page), reason=reason,
                                candidates=[c for group in ranked for c in group[:index.config.candidate_window]])
        if run is not None:
            run.end(outputs={"reason": reason, "cards": [c.model_dump(mode="json") for c in cards]})
        return outcome
