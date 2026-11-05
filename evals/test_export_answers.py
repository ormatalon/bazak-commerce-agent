"""The answer files cover every case. A sample catalog is enough: nothing here needs the network."""

import json
from pathlib import Path

from app.schemas import Product
from evals.export_answers import behavioral_answers, deterministic_answers
from evals.run_evals import load_all_cases

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"


def load_sample() -> list[Product]:
    with SAMPLE.open(encoding="utf-8") as file:
        return [Product.model_validate(item) for item in json.load(file)]


def test_every_deterministic_row_has_a_section_with_its_answer():
    text = deterministic_answers(load_sample())
    assert text.count("## Row ") == 74
    assert "## Row h1 [basic]: שעוני נשים מתחת ל-1000 דולר" in text
    # A row that matches nothing says so and shows the fallback's cheapest laptops.
    row_one = text.split("## Row 1 [basic]")[1].split("## Row")[0]
    assert "Expected products: none" in row_one
    assert "$1,099.99" in row_one


def test_every_behavioral_case_has_a_section_with_its_expected_fields():
    text = behavioral_answers(load_all_cases())
    assert text.count("## Case ") == 41
    assert "- User turn 2: $1500" in text
    assert "- Exact cards (product IDs): [14, 13]" in text
    assert "Expected behavior: Treats $1500 as the budget" in text
