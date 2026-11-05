"""Plumbing tests for run_evals.py with fake parse, search and run_turn functions. No model, no key.

Many of these read the numbers in the summary table, because that is what gets quoted.
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from app.schemas import (
    ChatTurn,
    ConversationState,
    ParsedRequest,
    Product,
    SearchOutcome,
    SearchSpec,
    TurnResult,
)
from evals import run_evals
from evals.ground_truth import load_all_rows

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"
HEADER_OF_DET = run_evals.DETERMINISTIC_HEADER
HEADER_OF_BEH = run_evals.BEHAVIORAL_HEADER


def load_sample() -> dict[int, Product]:
    with SAMPLE.open(encoding="utf-8") as file:
        return {item["id"]: Product.model_validate(item) for item in json.load(file)}


def rows_by_id(*ids: str) -> list[dict[str, str]]:
    return [row for row in load_all_rows() if row["id"] in ids]


def det_cells(records) -> dict[str, dict[str, str]]:
    """The deterministic summary as {group: {column: cell}}."""
    return {
        cells[0]: dict(zip(HEADER_OF_DET, cells))
        for cells in run_evals.deterministic_table_rows(records)
    }


def beh_cells(records) -> dict[str, dict[str, str]]:
    return {
        cells[0]: dict(zip(HEADER_OF_BEH, cells))
        for cells in run_evals.behavioral_table_rows(records)
    }


def score_det(rows, parse_fn, search_fn, catalog_map):
    catalog = list(catalog_map.values())
    raws = run_evals.run_deterministic(rows, catalog, [], None, parse_fn, search_fn)
    return [run_evals.score_deterministic(raw, row, catalog) for raw, row in zip(raws, rows)]


def make_case(case_id, turns, **overrides):
    case = {
        "id": case_id,
        "case": "test",
        "turns": turns,
        "expected_intent": "product_search",
        "expected_mode": "new",
        "expected_categories": [],
        "category_match": None,
        "expect_fallback": None,
        "expected_behavior": "",
        "difficulty": "basic",
    }
    return {**case, **overrides}


def test_importing_run_evals_needs_no_key():
    # Reaching this line means the import at the top of the file worked with no .env.
    assert callable(run_evals.main)


# ---------------------------------------------------------------------------
# Deterministic set
# ---------------------------------------------------------------------------


def test_deterministic_scores_and_crashed_row_in_the_table():
    catalog = load_sample()
    rows = rows_by_id("1", "66")  # row 1 expects nothing, row 66 expects 80, 81, 82

    def fake_parse(query, history, previous, shown, categories, llm):
        if "1500" in query:
            spec = SearchSpec(category="laptops", price_max=1500)
            return ParsedRequest(intent="product_search", mode="new", searches=[spec])
        raise RuntimeError("model call failed")

    def fake_search(spec, products):
        return [catalog[80], catalog[81], catalog[82]]

    records = score_det(rows, fake_parse, fake_search, catalog)
    row_1, row_66 = records
    assert (row_66.scores.f1, row_66.filter_ok) == (1.0, True)
    # Row 1 expects nothing, but a failed call earns no credit.
    assert row_1.expected == []
    assert row_1.error is not None
    assert (row_1.scores.f1, row_1.filter_ok) == (0.0, False)

    # Row 1 is basic and row 66 is hard.
    cells = det_cells(records)
    assert (cells["basic"]["n"], cells["basic"]["F1"], cells["basic"]["errors"]) == ("1", "0.00", "1")
    assert (cells["hard"]["n"], cells["hard"]["F1"], cells["hard"]["errors"]) == ("1", "1.00", "0")
    assert cells["all"]["F1"] == "0.50"
    assert cells["all"]["filter match"] == "1/2 (50%)"


def test_a_parser_that_only_asks_questions_gets_zero_on_an_empty_row():
    catalog = load_sample()
    rows = rows_by_id("1")  # laptops under 1000: nothing matches

    def always_clarify(query, history, previous, shown, categories, llm):
        return ParsedRequest(intent="needs_clarification")

    (record,) = score_det(rows, always_clarify, lambda spec, products: [], catalog)
    assert record.scores.f1 == 0.0
    assert det_cells([record])["all"]["F1"] == "0.00"


def test_a_search_with_the_right_category_gets_one_on_an_empty_row():
    catalog = load_sample()
    rows = rows_by_id("1")

    def searches_laptops(query, history, previous, shown, categories, llm):
        spec = SearchSpec(category="laptops", price_max=999.99)
        return ParsedRequest(intent="product_search", mode="new", searches=[spec])

    (record,) = score_det(rows, searches_laptops, lambda spec, products: [], catalog)
    assert (record.scores.f1, record.filter_ok) == (1.0, True)


def test_top_k_row_accepts_a_tied_product_and_is_cut_to_top_k():
    catalog = load_sample()
    rows = rows_by_id("37")  # top 3 highest-rated fragrances: 6, 7, 9

    def fake_parse(query, history, previous, shown, categories, llm):
        spec = SearchSpec(category="fragrances", sort_by="rating", order="desc", top_k=3)
        return ParsedRequest(intent="product_search", mode="new", searches=[spec])

    def fake_search(spec, products):  # returns every match, as the real search() does
        return [catalog[i] for i in (6, 7, 9, 8, 10)]

    (record,) = score_det(rows, fake_parse, fake_search, catalog)
    assert record.returned == [6, 7, 9]
    cells = det_cells([record])["all"]
    assert cells["top_k correct"] == "1/1 (100%)"
    assert cells["filter match"] == "1/1 (100%)"


def test_two_searches_are_scored_as_a_union():
    catalog = load_sample()
    rows = rows_by_id("8")  # all fragrances: 6, 7, 8, 9, 10

    def two_searches(query, history, previous, shown, categories, llm):
        specs = [SearchSpec(category="fragrances", price_max=79.99), SearchSpec(category="fragrances", price_min=80)]
        return ParsedRequest(intent="product_search", mode="new", searches=specs)

    def fake_search(spec, products):
        return [catalog[i] for i in (6, 9, 10)] if spec.price_max else [catalog[i] for i in (7, 8)]

    (record,) = score_det(rows, two_searches, fake_search, catalog)
    assert sorted(record.returned) == [6, 7, 8, 9, 10]
    assert record.scores.f1 == 1.0
    assert not record.filter_ok  # but two searches are not the one search the row expects


def test_top_k_is_applied_to_each_search_separately():
    catalog = load_sample()
    rows = rows_by_id("8")

    def two_searches(query, history, previous, shown, categories, llm):
        specs = [SearchSpec(category="fragrances", top_k=1), SearchSpec(category="fragrances", top_k=2)]
        return ParsedRequest(intent="product_search", mode="new", searches=specs)

    def fake_search(spec, products):
        return [catalog[i] for i in (6, 7, 8, 9, 10)]

    raws = run_evals.run_deterministic(rows, list(catalog.values()), [], None, two_searches, fake_search)
    assert raws[0]["returned_ids"] == [6, 7]  # 1 from the first search, then 6 again (dropped) and 7


def test_parse_failures_are_counted_per_row():
    catalog = load_sample()
    rows = rows_by_id("1", "2")
    run_evals.start_counting_parse_failures()

    def fake_parse(query, history, previous, shown, categories, llm):
        if "laptops" in query:  # row 1: the parser fell back to the safe default and said so
            logging.getLogger("app.parser").warning("invalid model output, using the safe default")
        return ParsedRequest(intent="needs_clarification")

    records = score_det(rows, fake_parse, lambda spec, products: [], catalog)
    assert [r.parse_failures for r in records] == [1, 0]
    assert det_cells(records)["all"]["parse fails"] == "1"


# ---------------------------------------------------------------------------
# Behavioral set
# ---------------------------------------------------------------------------


def fake_turn_result(catalog, message, state, mode="new", shown_ids=(128,), reply="Realme C35 is $149.99."):
    shown = [catalog[i] for i in shown_ids]
    outcome = SearchOutcome(spec=SearchSpec(), products=shown, shown=shown)
    new_state = ConversationState(history=state.history + [ChatTurn(role="user", text=message)])
    return TurnResult(
        parsed=ParsedRequest(intent="product_search", mode=mode),
        outcomes=[outcome],
        reply=reply,
        state=new_state,
    )


def score_beh(cases, run_turn_fn, catalog_map):
    catalog = list(catalog_map.values())
    raws = run_evals.run_behavioral(cases, catalog, [], None, run_turn_fn)
    return [run_evals.score_behavioral(raw, case, catalog) for raw, case in zip(raws, cases)]


def test_behavioral_replays_turns_carrying_state_and_scores_the_last():
    catalog = load_sample()
    case = make_case(11, ["Show me phones", "cheaper ones"], expected_mode="refine",
                     expected_categories=["smartphones"], category_match="all")  # fmt: skip
    seen_history_lengths = []

    def fake_run_turn(message, state, products, categories, llm):
        seen_history_lengths.append(len(state.history))
        return fake_turn_result(catalog, message, state, mode="new" if not state.history else "refine")

    (record,) = score_beh([case], fake_run_turn, catalog)
    assert seen_history_lengths == [0, 1]  # state was carried to the second turn
    assert record.scores.mode_ok  # scored on the last turn, which was a refine
    cells = beh_cells([record])
    assert cells["multi-turn"]["n"] == "1"
    assert cells["all"]["mode (rows with a mode)"] == "1/1 (100%)"


def test_crashed_cases_stay_in_the_grounding_denominator():
    catalog = load_sample()
    cases = [make_case(i, ["laptops"]) for i in range(1, 4)]

    def broken_run_turn(message, state, products, categories, llm):
        raise TimeoutError("model timed out")

    records = score_beh(cases, broken_run_turn, catalog)
    assert all(r.scores is None and "TimeoutError" in r.error for r in records)
    cells = beh_cells(records)["all"]
    assert cells["grounded"] == "grounded 0 of 3, 3 not run"
    assert cells["intent"] == "0/3 (0%)"
    assert cells["parse fails"] == "0"


def test_one_crash_among_grounded_cases_shows_in_the_table():
    catalog = load_sample()
    cases = [make_case(1, ["a"]), make_case(2, ["b"]), make_case(3, ["c"])]

    def run_turn_fn(message, state, products, categories, llm):
        if message == "b":
            raise TimeoutError("model timed out")
        return fake_turn_result(catalog, message, state)

    records = score_beh(cases, run_turn_fn, catalog)
    assert beh_cells(records)["all"]["grounded"] == "grounded 2 of 3, 1 not run"


def test_mode_is_scored_only_on_rows_with_an_expected_mode():
    catalog = load_sample()
    cases = [
        make_case(1, ["a"], expected_mode="new"),
        make_case(2, ["b"], expected_intent="off_catalog", expected_mode=None),
    ]

    def run_turn_fn(message, state, products, categories, llm):
        return fake_turn_result(catalog, message, state)

    cells = beh_cells(score_beh(cases, run_turn_fn, catalog))["all"]
    assert cells["mode (rows with a mode)"] == "1/1 (100%)"  # not 1/2


def test_fallback_is_two_numbers():
    catalog = load_sample()
    cases = [
        make_case(1, ["a"], expect_fallback="price"),  # should fire
        make_case(2, ["b"]),  # should stay quiet
        make_case(3, ["c"]),  # should stay quiet
        make_case(4, ["d"], expected_intent="small_talk", expected_mode=None),  # not counted
    ]

    def run_turn_fn(message, state, products, categories, llm):
        result = fake_turn_result(catalog, message, state)
        if message in ("a", "b"):  # it fires on a (right) and on b (a false fire)
            result.outcomes[0].loosened = ["price"]
        return result

    cells = beh_cells(score_beh(cases, run_turn_fn, catalog))["all"]
    assert cells["fallback fired"] == "fired correctly 1/1"
    assert cells["no false fallback"] == "no false fire 1/2"


def test_earlier_turn_products_count_for_grounding():
    catalog = load_sample()
    case = make_case(22, ["Show me laptops", "something cheaper"], expected_mode="refine")

    def run_turn_fn(message, state, products, categories, llm):
        if not state.history:
            return fake_turn_result(catalog, message, state, shown_ids=(80,), reply="Huawei Matebook X Pro, $1,399.99.")
        reply = "Cheaper than the Huawei Matebook X Pro: Lenovo Yoga 920 at $1,099.99."
        return fake_turn_result(catalog, message, state, mode="refine", shown_ids=(81,), reply=reply)

    (record,) = score_beh([case], run_turn_fn, catalog)
    assert record.scores.grounding.ok


def test_behavioral_parse_failures_are_counted():
    catalog = load_sample()
    run_evals.start_counting_parse_failures()

    def run_turn_fn(message, state, products, categories, llm):
        logging.getLogger("app.parser").warning("invalid model output, using the safe default")
        return fake_turn_result(catalog, message, state)

    records = score_beh([make_case(1, ["a", "b"])], run_turn_fn, catalog)
    assert records[0].parse_failures == 2  # one per turn
    assert beh_cells(records)["all"]["parse fails"] == "1"  # one case had a failure


def test_report_builds_with_a_failed_case():
    catalog = load_sample()

    def broken_run_turn(message, state, products, categories, llm):
        raise TimeoutError("model timed out")

    records = score_beh([make_case(5, ["A flight to Tokyo"], expected_behavior="Politely says no")], broken_run_turn, catalog)
    report = run_evals.build_report([], records)
    assert "## Behavioral set (1 conversations)" in report
    assert "TimeoutError" in report


# ---------------------------------------------------------------------------
# Saving and re-scoring a run
# ---------------------------------------------------------------------------


def test_a_run_is_written_line_by_line_and_can_be_rescored(tmp_path):
    catalog_map = load_sample()
    catalog = list(catalog_map.values())
    rows = rows_by_id("66")
    case = make_case(1, ["laptops"], expected_categories=["smartphones"], category_match="all")
    path = tmp_path / "run.jsonl"
    writer = run_evals.RunWriter(path, total=2)

    def fake_parse(query, history, previous, shown, categories, llm):
        spec = SearchSpec(category="laptops", price_max=1500)
        return ParsedRequest(intent="product_search", mode="new", searches=[spec])

    def fake_search(spec, products):
        return [catalog_map[80], catalog_map[81], catalog_map[82]]

    def run_turn_fn(message, state, products, categories, llm):
        return fake_turn_result(catalog_map, message, state, shown_ids=(128,))

    run_evals.run_deterministic(rows, catalog, [], None, fake_parse, fake_search, writer)
    run_evals.run_behavioral([case], catalog, [], None, run_turn_fn, writer)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # one line per result, already on disk
    assert [json.loads(line)["kind"] for line in lines] == ["deterministic", "behavioral"]

    # Rescoring reads only the file: no parser, no search, no model.
    det_records = [run_evals.score_deterministic(raw, rows[0], catalog) for raw in run_evals.load_run(path)[:1]]
    assert det_records[0].scores.f1 == 1.0
    beh = run_evals.score_behavioral(run_evals.load_run(path)[1], case, catalog)
    assert beh.scores.category_ok is True  # smartphone 128 was shown


def test_hebrew_survives_the_jsonl_round_trip(tmp_path):
    catalog_map = load_sample()
    path = tmp_path / "run.jsonl"
    writer = run_evals.RunWriter(path, total=1)
    case = make_case(27, ["אני מחפש בשמים"], expected_language="he")

    def run_turn_fn(message, state, products, categories, llm):
        return fake_turn_result(catalog_map, message, state, reply="מצאתי בשמים")

    run_evals.run_behavioral([case], list(catalog_map.values()), [], None, run_turn_fn, writer)
    raw = run_evals.load_run(path)[0]
    assert raw["results"][0]["reply"] == "מצאתי בשמים"
    record = run_evals.score_behavioral(raw, case, list(catalog_map.values()))
    assert record.scores.language_ok is True


def test_results_md_is_not_overwritten_when_the_run_had_errors(tmp_path):
    results = tmp_path / "results.md"
    results.write_text("old good results", encoding="utf-8")
    run_path = tmp_path / "run_1.jsonl"

    saved = run_evals.save_report("new report with errors", run_path, has_errors=True, results_path=results)
    assert results.read_text(encoding="utf-8") == "old good results"
    assert saved == tmp_path / "run_1.md"
    assert saved.read_text(encoding="utf-8") == "new report with errors"

    saved = run_evals.save_report("clean report", run_path, has_errors=False, results_path=results)
    assert saved == results
    assert results.read_text(encoding="utf-8") == "clean report"


def test_a_run_that_stopped_early_counts_as_a_problem():
    clean = SimpleNamespace(error=None)
    full_det = [clean] * len(load_all_rows())
    full_beh = [clean] * len(run_evals.load_all_cases())
    assert run_evals.run_has_problems(full_det, full_beh) is False
    # A killed run leaves a shorter file with no errors in it.
    assert run_evals.run_has_problems(full_det[:-1], full_beh) is True
    assert run_evals.run_has_problems(full_det, full_beh[:-1]) is True
    assert run_evals.run_has_problems([SimpleNamespace(error="boom")] + full_det[1:], full_beh) is True


def test_the_run_covers_every_dataset_with_no_id_clashes():
    rows = load_all_rows()
    cases = run_evals.load_all_cases()
    assert len(rows) == 74
    assert len(cases) == 41
    assert len({row["id"] for row in rows}) == 74
    assert len({case["id"] for case in cases}) == 41
    assert sum(1 for row in rows if row["id"].startswith("h")) == 5
    assert sum(1 for case in cases if str(case["id"]).startswith("h")) == 5


def test_hebrew_lines_get_their_own_row_and_count_in_the_others():
    parsed = ParsedRequest(
        intent="product_search",
        mode="new",
        searches=[SearchSpec(category="womens-watches", price_max=999.99)],
    ).model_dump(mode="json")
    raws = [
        {"kind": "deterministic", "row_id": "h1", "parsed": parsed, "returned_ids": [], "error": None},
        {"kind": "deterministic", "row_id": "1", "parsed": parsed, "returned_ids": [], "error": None},
        {"kind": "behavioral", "case_id": "h8", "results": [], "error": "boom"},
        {"kind": "behavioral", "case_id": 1, "results": [], "error": "boom"},
    ]
    det, beh = run_evals.score_run(raws, list(load_sample().values()))

    det_table = det_cells(det)
    assert det_table["hebrew"]["n"] == "1"
    assert det_table["basic"]["n"] == "2"
    assert det_table["all"]["n"] == "2"

    beh_table = beh_cells(beh)
    assert beh_table["hebrew"]["n"] == "1"
    assert beh_table["hard"]["n"] == "1"
    assert beh_table["all"]["n"] == "2"

    # The Hebrew turns are printed for Or to read, like every other case.
    assert "יש לכם מחשב נייד" in "\n".join(run_evals.behavioral_report(beh))
