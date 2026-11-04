"""Ground truth checks. Expected IDs below were worked out by hand from tests/fixtures/catalog_sample.json."""

import ast
import json
from pathlib import Path

import pytest

from app.schemas import Product, SearchSpec
from evals import ground_truth
from evals.ground_truth import expected_ids, load_rows, row_to_spec

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"


@pytest.fixture(scope="module")
def catalog() -> list[Product]:
    with SAMPLE.open(encoding="utf-8") as file:
        return [Product.model_validate(item) for item in json.load(file)]


@pytest.fixture(scope="module")
def rows() -> dict[int, dict[str, str]]:
    return {int(row["id"]): row for row in load_rows()}


def ids_for_row(rows: dict[int, dict[str, str]], catalog: list[Product], row_id: int) -> list[int]:
    return expected_ids(row_to_spec(rows[row_id]), catalog)


def test_csv_has_69_rows_50_basic_and_19_hard(rows):
    difficulties = [row["difficulty"] for row in rows.values()]
    assert len(rows) == 69
    assert difficulties.count("basic") == 50
    assert difficulties.count("hard") == 19


def test_every_row_becomes_a_valid_spec(rows):
    for row in rows.values():
        row_to_spec(row)  # raises if a cell is not a number or a sort value


def test_hebrew_query_is_read_as_utf8(rows):
    assert rows[66]["query"] == "מחשבים ניידים עד 1500 דולר"


def test_row_66_laptops_up_to_1500_is_three_products(rows, catalog):
    # Hand check: laptops are 78 ($1999.99), 79 ($1799.99), 80 ($1399.99), 81 ($1099.99), 82 ($1499.99).
    # Up to 1500 inclusive keeps 80, 81, 82. Default order is rating, highest first:
    # 80 is 4.98, 81 is 2.86, 82 is 2.67.
    assert ids_for_row(rows, catalog, 66) == [80, 81, 82]


def test_row_1_empty_expected_set(rows, catalog):
    # Cheapest laptop is $1099.99, so "laptops under $1000" (max 999.99) matches nothing.
    assert ids_for_row(rows, catalog, 1) == []


def test_row_37_top_3_highest_rated_fragrances(rows, catalog):
    # Ratings: 6 is 4.37, 7 is 4.26, 9 is 3.96, 8 is 3.80, 10 is 2.74.
    assert ids_for_row(rows, catalog, 37) == [6, 7, 9]


def test_row_12_furniture_under_500(rows, catalog):
    # 13 ($299.99, rating 2.87) and 14 ($499.99, rating 4.88). Highest rating first puts 14 first.
    assert ids_for_row(rows, catalog, 12) == [14, 13]


def test_row_5_cheapest_tablet_is_the_samsung_galaxy_tab_white(rows, catalog):
    assert ids_for_row(rows, catalog, 5) == [161]


def test_row_3_smartphones_under_300_includes_the_exact_limit(rows, catalog):
    # 299.99 is inside max 299.99. Nine phones qualify, highest rating first.
    assert ids_for_row(rows, catalog, 3) == [127, 128, 125, 129, 135, 134, 122, 131, 121]


def test_price_ties_are_broken_by_lowest_id(catalog):
    # Phones 122, 127, 129, 131, 135 all cost $299.99.
    spec = SearchSpec(category="smartphones", price_min=299.99, price_max=299.99, sort_by="price", order="asc")
    assert expected_ids(spec, catalog) == [122, 127, 129, 131, 135]
    spec_desc = SearchSpec(category="smartphones", price_min=299.99, price_max=299.99, sort_by="price", order="desc")
    assert expected_ids(spec_desc, catalog) == [122, 127, 129, 131, 135]


def test_top_k_cuts_after_sorting(catalog):
    spec = SearchSpec(category="smartphones", sort_by="price", order="asc", top_k=2)
    # Cheapest are 128 ($149.99) and 121 ($199.99).
    assert expected_ids(spec, catalog) == [128, 121]


def test_no_top_k_means_no_cut(rows, catalog):
    # Row 8 asks for all fragrances and the fixture has five.
    assert len(ids_for_row(rows, catalog, 8)) == 5


def imported_names(path: str) -> set[str]:
    """Every dotted name a file imports. `from app import search` gives "app" and "app.search"."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def test_import_check_catches_from_app_import_search(tmp_path):
    # Proves the guard below can fail: this form slipped past the first version of it.
    sneaky = tmp_path / "sneaky.py"
    sneaky.write_text("from app import search\n", encoding="utf-8")
    assert "app.search" in imported_names(str(sneaky))


def test_ground_truth_does_not_import_search():
    assert "app.search" not in imported_names(ground_truth.__file__)
