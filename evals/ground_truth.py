"""Expected product IDs for each deterministic row of datasets/.

This file works only from the datasets and the catalog. It must not import app/search.py,
so a bug in search() cannot hide on both sides of the comparison.

Run `python evals/ground_truth.py` to print the expected IDs for all 72 rows.
"""

import csv
import json
import sys
from pathlib import Path

# `python evals/ground_truth.py` puts only evals/ on the import path, so add the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.schemas import Product, SearchSpec  # noqa: E402

DETERMINISTIC_CSV = REPO_ROOT / "datasets" / "deterministic.csv"
HEBREW_JSONL = REPO_ROOT / "datasets" / "hebrew.jsonl"


def load_rows(path: Path = DETERMINISTIC_CSV) -> list[dict[str, str]]:
    """Read the CSV as a list of dicts. Empty cells stay as empty strings."""
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def is_hebrew_id(row_id: object) -> bool:
    """Lines of hebrew.jsonl get IDs like "h3", so they can't clash with the other datasets."""
    return str(row_id).startswith("h")


def load_hebrew_rows(path: Path = HEBREW_JSONL) -> list[dict[str, str]]:
    """The deterministic lines of hebrew.jsonl, in the shape of a CSV row: all text, null is empty."""
    rows = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            data = json.loads(line)
            if data["type"] == "deterministic":
                row = {key: "" if value is None else str(value) for key, value in data.items()}
                rows.append({**row, "id": f"h{data['id']}"})
    return rows


def load_all_rows() -> list[dict[str, str]]:
    """Every deterministic row of every dataset."""
    return load_rows() + load_hebrew_rows()


def _float_or_none(text: str) -> float | None:
    return float(text) if text.strip() else None


def row_to_spec(row: dict[str, str]) -> SearchSpec:
    """The filter a row says the agent should extract, as a SearchSpec.

    Keywords are left empty on purpose: the CSV has no keywords column.
    """
    sort_by = row["sort_by"].strip() or None
    order = row["order"].strip() or None
    top_k = row["top_k"].strip()
    return SearchSpec(
        category=row["category"].strip() or None,
        price_min=_float_or_none(row["price_min"]),
        price_max=_float_or_none(row["price_max"]),
        rating_min=_float_or_none(row["rating_min"]),
        sort_by=sort_by,  # type: ignore[arg-type]  # the CSV only holds price, rating or empty
        order=order,  # type: ignore[arg-type]  # the CSV only holds asc, desc or empty
        top_k=int(top_k) if top_k else None,
    )


def passes_filter(product: Product, spec: SearchSpec) -> bool:
    """True when the product is inside every bound the spec sets. All bounds are inclusive."""
    if spec.category is not None and product.category != spec.category:
        return False
    if spec.price_min is not None and product.price < spec.price_min:
        return False
    if spec.price_max is not None and product.price > spec.price_max:
        return False
    if spec.rating_min is not None and product.rating < spec.rating_min:
        return False
    return True


def sort_value(product: Product, spec: SearchSpec) -> float:
    """The number the spec sorts by: price if sort_by is price, otherwise rating."""
    return product.price if spec.sort_by == "price" else product.rating


def sort_products(products: list[Product], spec: SearchSpec) -> list[Product]:
    """Order the matches. Equal values are broken by the lowest ID, so the result is repeatable.

    The ID tie-break only makes this list the same every time. When scoring, products that
    tie on the sort value are equally right (see scoring.top_k_is_correct).

    With no sort_by the CSV has no keywords, so the default order is rating (highest first),
    as CLAUDE.md says. A sort_by with no order is read as ascending.
    """
    # No sort given: highest rating first, which is the same as sorting rating descending.
    descending = spec.order == "desc" if spec.sort_by is not None else True

    def sort_key(product: Product) -> tuple[float, int]:
        value = sort_value(product, spec)
        return (-value if descending else value, product.id)

    return sorted(products, key=sort_key)


def expected_ids(spec: SearchSpec, catalog: list[Product]) -> list[int]:
    """Expected product IDs, in order: filter, sort, then cut to top_k when it is set."""
    matches = [product for product in catalog if passes_filter(product, spec)]
    ordered = sort_products(matches, spec)
    if spec.top_k is not None:
        ordered = ordered[: spec.top_k]
    return [product.id for product in ordered]


def main() -> None:
    from app.catalog import load_catalog

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    catalog = load_catalog()
    for row in load_all_rows():
        spec = row_to_spec(row)
        ids = expected_ids(spec, catalog)
        print(f"{row['id']:>3} [{row['difficulty']}] {len(ids):>2} products  {row['query']}")
        print(f"      {ids}")


if __name__ == "__main__":
    main()
