"""Plumbing tests for run_evals.py with fake parse, search and run_turn functions. No model, no key."""

import json
from pathlib import Path

from app.schemas import ChatTurn, ConversationState, ParsedRequest, Product, SearchOutcome, SearchSpec, TurnResult
from evals import run_evals
from evals.ground_truth import load_rows

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"


def load_sample() -> dict[int, Product]:
    with SAMPLE.open(encoding="utf-8") as file:
        return {item["id"]: Product.model_validate(item) for item in json.load(file)}


def test_importing_run_evals_needs_no_key():
    # Reaching this line means the import at the top of the file worked with no .env.
    assert callable(run_evals.main)


def test_deterministic_records_scores_and_errors():
    catalog = load_sample()
    rows = [row for row in load_rows() if row["id"] in ("1", "66")]

    def fake_parse(query, history, previous, shown, categories, llm):
        if "1500" in query:
            return ParsedRequest(
                intent="product_search", mode="new", searches=[SearchSpec(category="laptops", price_max=1500)]
            )
        raise RuntimeError("model call failed")

    def fake_search(spec, products):
        return [catalog[80], catalog[81], catalog[82]]

    records = run_evals.run_deterministic(rows, list(catalog.values()), [], None, fake_parse, fake_search)
    row_1, row_66 = records
    assert (row_66.f1, row_66.filter_ok) == (1.0, True)
    # Row 1 expects nothing, but a failed call earns no credit.
    assert row_1.expected == []
    assert row_1.error is not None
    assert (row_1.f1, row_1.filter_ok) == (0.0, False)


def test_deterministic_top_k_is_cut_and_compared_in_order():
    catalog = load_sample()
    rows = [row for row in load_rows() if row["id"] == "37"]  # top 3 highest-rated fragrances

    def fake_parse(query, history, previous, shown, categories, llm):
        spec = SearchSpec(category="fragrances", sort_by="rating", order="desc", top_k=3)
        return ParsedRequest(intent="product_search", mode="new", searches=[spec])

    def fake_search(spec, products):  # returns every match, as the real search() does
        return [catalog[i] for i in (6, 7, 9, 8, 10)]

    (record,) = run_evals.run_deterministic(rows, list(catalog.values()), [], None, fake_parse, fake_search)
    assert record.returned == [6, 7, 9]
    assert record.top_k_exact is True
    assert record.filter_ok


def test_behavioral_replays_turns_carrying_state_and_scores_the_last():
    catalog = load_sample()
    case = {
        "id": 11,
        "case": "follow_up",
        "turns": ["Show me phones", "cheaper ones"],
        "expected_intent": "product_search",
        "expected_mode": "refine",
        "expected_categories": ["smartphones"],
        "category_match": "all",
        "expect_fallback": None,
        "expected_behavior": "",
        "difficulty": "basic",
    }
    seen_history_lengths = []

    def fake_run_turn(message, state, products, categories, llm):
        seen_history_lengths.append(len(state.history))
        mode = "new" if not state.history else "refine"
        outcome = SearchOutcome(spec=SearchSpec(), products=[catalog[128]], shown=[catalog[128]])
        new_state = ConversationState(history=state.history + [ChatTurn(role="user", text=message)])
        return TurnResult(
            parsed=ParsedRequest(intent="product_search", mode=mode),
            outcomes=[outcome],
            reply="Realme C35 is $149.99.",
            state=new_state,
        )

    (record,) = run_evals.run_behavioral([case], list(catalog.values()), [], None, fake_run_turn)
    assert seen_history_lengths == [0, 1]  # state was carried to the second turn
    assert record.scores is not None
    assert record.scores.mode_ok  # scored on the last turn, which was a refine
    assert record.scores.grounding.ok


def test_behavioral_failure_is_recorded_not_raised():
    case = {
        "id": 5,
        "case": "off_catalog",
        "turns": ["A flight to Tokyo"],
        "expected_intent": "off_catalog",
        "expected_mode": None,
        "expected_categories": [],
        "category_match": None,
        "expect_fallback": None,
        "expected_behavior": "",
        "difficulty": "basic",
    }

    def broken_run_turn(message, state, products, categories, llm):
        raise TimeoutError("model timed out")

    (record,) = run_evals.run_behavioral([case], [], [], None, broken_run_turn)
    assert record.scores is None
    assert "TimeoutError" in record.error


def test_report_builds_with_a_failed_case():
    case = {
        "id": 5,
        "case": "off_catalog",
        "turns": ["A flight to Tokyo"],
        "expected_intent": "off_catalog",
        "expected_mode": None,
        "expected_categories": [],
        "category_match": None,
        "expect_fallback": None,
        "expected_behavior": "Politely says no",
        "difficulty": "basic",
    }

    def broken_run_turn(message, state, products, categories, llm):
        raise TimeoutError("model timed out")

    beh = run_evals.run_behavioral([case], [], [], None, broken_run_turn)
    report = run_evals.build_report([], beh)
    assert "## Behavioral set (1 conversations)" in report
    assert "TimeoutError" in report
