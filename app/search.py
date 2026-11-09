"""Numeric filtering and semantic relevance, without LLM or fallback decisions."""

import re
import unicodedata

import numpy as np

from app.index import ProductIndex
from app.observability import span
from app.schemas import Candidate, Product, SearchSpec


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def excluded(product: Product, terms: list[str] | None) -> bool:
    text = " " + normalize(" ".join([product.title, product.description, product.brand or "", product.category, *product.tags])) + " "
    return any(" " + normalize(term) + " " in text for term in terms or [] if normalize(term))


def passes_numeric(product: Product, spec: SearchSpec) -> bool:
    return ((spec.price_min is None or product.price >= spec.price_min)
            and (spec.price_max is None or product.price <= spec.price_max)
            and (spec.rating_min is None or product.rating >= spec.rating_min))


def rank_all(spec: SearchSpec, index: ProductIndex, query_cache: dict | None = None) -> list[list[Candidate]]:
    """Compute relative scores on the WHOLE catalog, independently of price filters."""
    cache = query_cache if query_cache is not None else {}
    result = []
    for number, direction in enumerate(spec.directions or []):
        if direction.query not in cache:
            cache[direction.query] = index.embedder.encode([direction.query], query=True)[0]
        with span("rank_direction", {"query": direction.query}, {"direction": number}) as run:
            similarities = index.similarities(cache[direction.query])
            std = float(np.std(similarities))
            z_scores = (similarities - similarities.mean()) / std if std > 1e-8 else np.zeros_like(similarities)
            candidates = []
            for product, similarity, z_score in zip(index.products, similarities, z_scores):
                matched = product.category in direction.categories
                if std <= 1e-8:
                    zone = "uninformative"
                elif z_score >= index.config.strong_threshold:
                    zone = "strong"
                elif z_score >= index.config.borderline_threshold:
                    zone = "borderline"
                else:
                    zone = "weak"
                relevant = zone == "strong" or (zone == "borderline" and matched)
                boost = index.config.category_boost if matched else 0.0
                candidates.append(Candidate(product=product, direction=number,
                    similarity=float(similarity), z_score=float(z_score), category_boost=boost,
                    score=float(similarity)+boost, zone=zone, relevant=relevant,
                    reason="accepted" if relevant else "relative_relevance_rejected"))
            candidates.sort(key=lambda c: (-c.score, c.product.id))
            if run is not None:
                run.end(outputs={"candidates": [c.model_dump(mode="json") for c in candidates[:index.config.candidate_window]],
                                 "qualified": sum(c.relevant for c in candidates), "std": std})
            result.append(candidates)
    return result


def eligible_lists(spec: SearchSpec, ranked: list[list[Candidate]], seen: set[int] | None = None) -> list[list[Candidate]]:
    with span("filter", {"directions": len(ranked)}) as run:
        result = []
        for candidates in ranked:
            eligible = [c for c in candidates if c.relevant and c.product.id not in (seen or set())
                        and not excluded(c.product, spec.exclude) and passes_numeric(c.product, spec)]
            if spec.sort_by:
                descending = spec.order == "desc"
                eligible.sort(key=lambda c: ((-1 if descending else 1) * getattr(c.product, spec.sort_by), c.product.id))
            result.append(eligible)
        if run is not None:
            run.end(outputs={"eligible_counts": [len(items) for items in result]})
        return result


def merge_directions(groups: list[list[Candidate]]) -> list[Candidate]:
    """Round-robin across query directions, without comparing their raw scores."""
    merged = []
    known = set()
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position < len(group) and group[position].product.id not in known:
                candidate = group[position]
                known.add(candidate.product.id)
                merged.append(candidate)
    return merged


def search(spec: SearchSpec, index: ProductIndex, seen: set[int] | None = None,
           query_cache: dict | None = None) -> list[Candidate]:
    """All exact matches, with no display cap and no fallback. Spec must be in USD."""
    return merge_directions(eligible_lists(spec, rank_all(spec, index, query_cache), seen))
