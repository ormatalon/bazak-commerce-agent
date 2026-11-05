"""Write the expected answers of every dataset to readable files in datasets/answers/.

Run after changing a dataset: python evals/export_answers.py

Nothing reads these files. They exist so Or can see what each case expects. The expected
products come from evals/ground_truth.py. The suggestions for a row that matches nothing
come from the app's own fallback, so they show what the app does, not an independent answer.
"""

import sys
from pathlib import Path
from typing import Any

# `python evals/export_answers.py` puts only evals/ on the import path, so add the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.pipeline import CARDS_PER_SEARCH  # noqa: E402
from app.schemas import Product, SearchSpec  # noqa: E402
from app.search import search_with_fallback  # noqa: E402
from evals.ground_truth import expected_ids, load_all_rows, row_to_spec  # noqa: E402
from evals.run_evals import load_all_cases  # noqa: E402

ANSWERS_DIR = REPO_ROOT / "datasets" / "answers"
FILTER_FIELDS = ["category", "price_min", "price_max", "rating_min", "sort_by", "order", "top_k"]


def product_line(product: Product) -> str:
    return f"- #{product.id} {product.title}, ${product.price:,.2f}, rated {product.rating}"


def filter_text(spec: SearchSpec) -> str:
    return ", ".join(f"{name}={getattr(spec, name)}" for name in FILTER_FIELDS if getattr(spec, name) is not None)


def deterministic_answers(catalog: list[Product]) -> str:
    """One section per row: the filter, the expected products, and any suggestions."""
    by_id = {product.id: product for product in catalog}
    lines = ["# Expected answers: deterministic rows", ""]
    for row in load_all_rows():
        spec = row_to_spec(row)
        ids = expected_ids(spec, catalog)
        lines += [f"## Row {row['id']} [{row['difficulty']}]: {row['query']}", ""]
        lines += [f"Filter: {filter_text(spec)}", ""]
        if ids:
            lines += [f"Expected products ({len(ids)}):", ""]
            lines += [product_line(by_id[i]) for i in ids]
        else:
            outcome = search_with_fallback(spec, catalog)
            suggestions = outcome.products[: spec.top_k or CARDS_PER_SEARCH]
            lines += ["Expected products: none. The reply should say nothing matches.", ""]
            lines += [f"Suggestions from the app's fallback (loosened: {', '.join(outcome.loosened) or 'nothing'}):", ""]
            lines += [product_line(p) for p in suggestions] or ["- none"]
        lines.append("")
    return "\n".join(lines)


def behavioral_answers(cases: list[dict[str, Any]]) -> str:
    """One section per conversation: the turns and everything it expects."""
    lines = ["# Expected answers: behavioral cases", ""]
    for case in cases:
        lines += [f"## Case {case['id']} [{case['difficulty']}]: {case['case']}", ""]
        lines += [f"- User turn {number}: {turn}" for number, turn in enumerate(case["turns"], start=1)]
        lines += [
            f"- Intent: {case['expected_intent']}",
            f"- Mode: {case['expected_mode']}",
            f"- Categories: {case['expected_categories'] or 'none'} (match: {case['category_match']})",
            f"- Fallback: {case['expect_fallback']}",
            f"- Reply language: {case.get('expected_language') or 'not checked'}",
            f"- Expected behavior: {case['expected_behavior']}",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    from app.catalog import load_catalog

    ANSWERS_DIR.mkdir(exist_ok=True)
    catalog = load_catalog()
    with (ANSWERS_DIR / "deterministic.md").open("w", encoding="utf-8") as file:
        file.write(deterministic_answers(catalog))
    with (ANSWERS_DIR / "behavioral.md").open("w", encoding="utf-8") as file:
        file.write(behavioral_answers(load_all_cases()))
    print(f"Wrote the expected answers to {ANSWERS_DIR}")


if __name__ == "__main__":
    main()
