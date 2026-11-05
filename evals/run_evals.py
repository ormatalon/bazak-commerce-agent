"""Run both eval sets and print a summary. One command: python evals/run_evals.py

Deterministic set (datasets/deterministic.csv): parse_request, then search(), with no
fallback and no display cap. Scored against evals/ground_truth.py.
Behavioral set (datasets/behavioral.jsonl): replay every turn through run_turn and
score the last one.
datasets/hebrew.jsonl has lines of both kinds. They are scored the same way, count in
the basic, hard and all rows, and also get a row of their own.

This makes real model calls (about 160), so only the Lead runs it (the key lives in the
main folder's .env). The app modules are imported inside main(), so importing this file
needs no key and no network.

To protect the paid run, each raw result is appended to evals/runs/run_<time>.jsonl
straight after its call. The report is built from that file, so a scoring bug can be
fixed and the run re-scored for free:

    python evals/run_evals.py --rescore evals/runs/run_<time>.jsonl
"""

import argparse
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# `python evals/run_evals.py` puts only evals/ on the import path, so add the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.schemas import (  # noqa: E402
    LLM,
    ConversationState,
    ParsedRequest,
    Product,
    SearchSpec,
    TurnResult,
)
from evals.ground_truth import (  # noqa: E402
    HEBREW_JSONL,
    expected_ids,
    is_hebrew_id,
    load_all_rows,
    row_to_spec,
)
from evals.scoring import (  # noqa: E402
    CaseScores,
    RetrievalScores,
    filter_matches,
    score_case,
    score_retrieval,
)

BEHAVIORAL_JSONL = REPO_ROOT / "datasets" / "behavioral.jsonl"
RUNS_DIR = Path(__file__).resolve().parent / "runs"
RESULTS_MD = Path(__file__).resolve().parent / "results.md"

ParseFn = Callable[[str, list[Any], list[SearchSpec], list[Product], list[str], LLM], ParsedRequest]
SearchFn = Callable[[SearchSpec, list[Product]], list[Product]]
RunTurnFn = Callable[[str, ConversationState, list[Product], list[str], LLM], TurnResult]
RecordFn = Callable[[dict[str, Any]], None]


# ---------------------------------------------------------------------------
# Counting the parser's safe-default fallbacks
# ---------------------------------------------------------------------------


class ParseFailureCounter(logging.Handler):
    """Counts the warnings app.parser logs when it gives up and returns the safe default.

    Why: a row that expects needs_clarification would score correct on garbage output.
    """

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno == logging.WARNING:
            self.count += 1


PARSE_FAILURES = ParseFailureCounter()


def start_counting_parse_failures() -> None:
    logger = logging.getLogger("app.parser")
    if PARSE_FAILURES not in logger.handlers:
        logger.addHandler(PARSE_FAILURES)


# ---------------------------------------------------------------------------
# Running: each function returns raw dicts, which are also written to the JSONL file
# ---------------------------------------------------------------------------


def run_deterministic(
    rows: list[dict[str, str]],
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
    parse_fn: ParseFn,
    search_fn: SearchFn,
    on_record: RecordFn | None = None,
) -> list[dict[str, Any]]:
    raws = []
    for row in rows:
        failures_before = PARSE_FAILURES.count
        raw: dict[str, Any] = {"kind": "deterministic", "row_id": row["id"], "parsed": None,
                               "returned_ids": [], "error": None}  # fmt: skip
        try:
            parsed = parse_fn(row["query"], [], [], [], categories, llm)
            raw["parsed"] = parsed.model_dump(mode="json")
            # Score every search together: the union of their products, no repeats.
            returned_ids: list[int] = []
            for spec in parsed.searches:
                products = search_fn(spec, catalog)
                # search() returns every match with no display cap, so cut to top_k here.
                if spec.top_k is not None:
                    products = products[: spec.top_k]
                returned_ids += [p.id for p in products if p.id not in returned_ids]
            raw["returned_ids"] = returned_ids
        except Exception as error:  # noqa: BLE001 - one bad call must not lose the whole run
            raw["error"] = repr(error)
        raw["parse_failures"] = PARSE_FAILURES.count - failures_before
        raws.append(raw)
        if on_record:
            on_record(raw)
    return raws


def run_behavioral(
    cases: list[dict[str, Any]],
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
    run_turn_fn: RunTurnFn,
    on_record: RecordFn | None = None,
) -> list[dict[str, Any]]:
    raws = []
    for case in cases:
        failures_before = PARSE_FAILURES.count
        raw: dict[str, Any] = {"kind": "behavioral", "case_id": case["id"], "results": [], "error": None}
        try:
            state = ConversationState()
            for turn in case["turns"]:
                result = run_turn_fn(turn, state, catalog, categories, llm)
                state = result.state  # carry the conversation into the next turn
                raw["results"].append(result.model_dump(mode="json"))
        except Exception as error:  # noqa: BLE001 - one bad call must not lose the whole run
            raw["error"] = repr(error)
        raw["parse_failures"] = PARSE_FAILURES.count - failures_before
        raws.append(raw)
        if on_record:
            on_record(raw)
    return raws


class RunWriter:
    """Appends each raw result to the JSONL file, then prints one progress line."""

    def __init__(self, path: Path, total: int) -> None:
        self.path = path
        self.total = total
        self.done = 0

    def __call__(self, raw: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(raw, ensure_ascii=False) + "\n")
        self.done += 1
        name = f"row {raw['row_id']}" if raw["kind"] == "deterministic" else f"case {raw['case_id']}"
        status = f"ERROR {raw['error']}" if raw["error"] else "ok"
        print(f"[{self.done}/{self.total}] {raw['kind']} {name}: {status}", flush=True)


def load_run(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def load_cases(path: Path = BEHAVIORAL_JSONL) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def load_hebrew_cases(path: Path = HEBREW_JSONL) -> list[dict[str, Any]]:
    """The behavioral lines of hebrew.jsonl, with IDs like "h6"."""
    lines = load_cases(path)
    return [{**line, "id": f"h{line['id']}"} for line in lines if line["type"] == "behavioral"]


def load_all_cases() -> list[dict[str, Any]]:
    """Every behavioral case of every dataset."""
    return load_cases() + load_hebrew_cases()


# ---------------------------------------------------------------------------
# Scoring the raw results
# ---------------------------------------------------------------------------


@dataclass
class DeterministicRecord:
    row: dict[str, str]
    expected: list[int]
    returned: list[int]
    searches: list[SearchSpec]
    scores: RetrievalScores
    filter_ok: bool
    parse_failures: int
    error: str | None = None


def score_deterministic(raw: dict[str, Any], row: dict[str, str], catalog: list[Product]) -> DeterministicRecord:
    expected_spec = row_to_spec(row)
    expected = expected_ids(expected_spec, catalog)
    failures = raw.get("parse_failures", 0)
    if raw["error"]:
        # A failed call earns no credit, even on a row where nothing is expected.
        top_k_ok = False if expected_spec.top_k is not None else None
        return DeterministicRecord(row, expected, [], [], RetrievalScores(0.0, 0.0, 0.0, top_k_ok),
                                   False, failures, raw["error"])  # fmt: skip
    searches = ParsedRequest.model_validate(raw["parsed"]).searches
    returned = raw["returned_ids"]
    scores = score_retrieval(expected_spec, catalog, searches, returned)
    # One query should give exactly one search with exactly the CSV's filter.
    filter_ok = len(searches) == 1 and filter_matches(expected_spec, searches[0])
    return DeterministicRecord(row, expected, returned, searches, scores, filter_ok, failures)


@dataclass
class BehavioralRecord:
    case: dict[str, Any]
    result: TurnResult | None
    scores: CaseScores | None
    parse_failures: int
    error: str | None = None


def score_behavioral(raw: dict[str, Any], case: dict[str, Any], catalog: list[Product]) -> BehavioralRecord:
    failures = raw.get("parse_failures", 0)
    if raw["error"] or len(raw["results"]) != len(case["turns"]):
        return BehavioralRecord(case, None, None, failures, raw["error"] or "not all turns ran")
    results = [TurnResult.model_validate(r) for r in raw["results"]]
    last = results[-1]
    # A reply may talk about a product shown in any turn of the conversation.
    shown_anywhere = [p for r in results for o in r.outcomes for p in o.shown]
    titles = [product.title for product in catalog]
    scores = score_case(last, case, case["turns"], titles, shown_anywhere)
    return BehavioralRecord(case, last, scores, failures)


def score_run(
    raws: list[dict[str, Any]], catalog: list[Product]
) -> tuple[list[DeterministicRecord], list[BehavioralRecord]]:
    rows = {row["id"]: row for row in load_all_rows()}
    cases = {case["id"]: case for case in load_all_cases()}
    det, beh = [], []
    for raw in raws:
        if raw["kind"] == "deterministic":
            det.append(score_deterministic(raw, rows[raw["row_id"]], catalog))
        elif raw["kind"] == "behavioral":
            beh.append(score_behavioral(raw, cases[raw["case_id"]], catalog))
    return det, beh


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def percent(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.0f}%)" if total else "n/a"


def mean(values: list[float]) -> str:
    return f"{sum(values) / len(values):.2f}" if values else "n/a"


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    """A markdown table, which reads fine in the console too."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


DETERMINISTIC_HEADER = ["set", "n", "precision", "recall", "F1", "top_k correct", "filter match",
                        "errors", "parse fails"]  # fmt: skip


def deterministic_table_rows(records: list[DeterministicRecord]) -> list[list[str]]:
    """One row of cells per group (basic, hard, all). Tests read these cells."""
    groups = [
        ("basic", [r for r in records if r.row["difficulty"] == "basic"]),
        ("hard", [r for r in records if r.row["difficulty"] == "hard"]),
        ("all", records),
        ("hebrew", [r for r in records if is_hebrew_id(r.row["id"])]),
    ]
    table_rows = []
    for name, group in groups:
        top_k_rows = [r for r in group if r.scores.top_k_ok is not None]
        table_rows.append(
            [
                name,
                str(len(group)),
                mean([r.scores.precision for r in group]),
                mean([r.scores.recall for r in group]),
                mean([r.scores.f1 for r in group]),
                percent(sum(1 for r in top_k_rows if r.scores.top_k_ok), len(top_k_rows)),
                percent(sum(1 for r in group if r.filter_ok), len(group)),
                str(sum(1 for r in group if r.error)),
                str(sum(1 for r in group if r.parse_failures)),
            ]
        )
    return table_rows


def filter_text(spec: SearchSpec | None) -> str:
    if spec is None:
        return "(no search)"
    names = ["category", "price_min", "price_max", "rating_min", "sort_by", "order", "top_k"]
    return ", ".join(f"{name}={getattr(spec, name)}" for name in names)


def deterministic_report(records: list[DeterministicRecord]) -> list[str]:
    lines = [f"## Deterministic set ({len(records)} queries)", ""]
    lines += table(DETERMINISTIC_HEADER, deterministic_table_rows(records))
    lines += ["", "### Failures (any metric below perfect)", ""]
    failures = [
        r for r in records
        if r.scores.f1 < 1 or r.scores.top_k_ok is False or not r.filter_ok or r.error
    ]  # fmt: skip
    if not failures:
        lines.append("None.")
    for r in failures:
        row = r.row
        lines.append(f"- row {row['id']} [{row['difficulty']}] {row['query']}")
        if r.error:
            lines.append(f"    ERROR: {r.error}")
            continue
        missing = sorted(set(r.expected) - set(r.returned))
        extra = sorted(set(r.returned) - set(r.expected))
        lines.append(
            f"    P={r.scores.precision:.2f} R={r.scores.recall:.2f} F1={r.scores.f1:.2f}  "
            f"expected {len(r.expected)} IDs, returned {len(r.returned)}; missing {missing}, extra {extra}"
        )
        if not r.filter_ok:
            lines.append(f"    expected filter: {filter_text(row_to_spec(row))}")
            extracted = " | ".join(filter_text(s) for s in r.searches) or "(no search)"
            lines.append(f"    extracted filter ({len(r.searches)} searches): {extracted}")
        if r.scores.top_k_ok is False:
            lines.append(f"    top_k answer is wrong: expected {r.expected}, got {r.returned}")
    parse_failed = [r.row["id"] for r in records if r.parse_failures]
    lines += ["", f"Parser returned the safe default on rows: {parse_failed or 'none'}"]
    return lines


BEHAVIORAL_HEADER = ["set", "n", "intent", "mode (rows with a mode)", "category", "fallback fired",
                     "no false fallback", "exact cards", "language", "grounded", "parse fails"]  # fmt: skip


def behavioral_table_rows(records: list[BehavioralRecord]) -> list[list[str]]:
    """One row of cells per group. A crashed case counts as wrong on every metric. Tests read these cells."""
    groups = [
        ("basic", [r for r in records if r.case["difficulty"] == "basic"]),
        ("hard", [r for r in records if r.case["difficulty"] == "hard"]),
        ("all", records),
        ("multi-turn", [r for r in records if len(r.case["turns"]) > 1]),
        ("hebrew", [r for r in records if is_hebrew_id(r.case["id"])]),
    ]
    table_rows = []
    for name, group in groups:
        intent = sum(1 for r in group if r.scores and r.scores.intent_ok)

        mode_cases = [r for r in group if r.case["expected_mode"]]
        mode = sum(1 for r in mode_cases if r.scores and r.scores.mode_ok)

        category_cases = [r for r in group if r.case["expected_categories"]]
        category = sum(1 for r in category_cases if r.scores and r.scores.category_ok)

        # Fallback is two questions. Did it fire when it should? Did it stay quiet when it should?
        fired_cases = [r for r in group if r.case["expect_fallback"]]
        fired = sum(1 for r in fired_cases if r.scores and r.scores.fallback_ok)
        quiet_cases = [
            r for r in group
            if r.case["expected_intent"] == "product_search" and not r.case["expect_fallback"]
        ]  # fmt: skip
        quiet = sum(1 for r in quiet_cases if r.scores and r.scores.fallback_ok)

        card_cases = [r for r in group if r.case.get("expected_card_ids")]
        cards = sum(1 for r in card_cases if r.scores and r.scores.cards_ok)

        language_cases = [r for r in group if r.case.get("expected_language")]
        language = sum(1 for r in language_cases if r.scores and r.scores.language_ok)

        # Against the whole group, so crashes cannot shrink the denominator.
        grounded = sum(1 for r in group if r.scores and r.scores.grounding.ok)
        not_run = sum(1 for r in group if r.scores is None)

        table_rows.append(
            [
                name,
                str(len(group)),
                percent(intent, len(group)),
                percent(mode, len(mode_cases)),
                percent(category, len(category_cases)),
                f"fired correctly {fired}/{len(fired_cases)}",
                f"no false fire {quiet}/{len(quiet_cases)}",
                f"{cards}/{len(card_cases)}",
                f"{language}/{len(language_cases)}",
                f"grounded {grounded} of {len(group)}, {not_run} not run",
                str(sum(1 for r in group if r.parse_failures)),
            ]
        )
    return table_rows


def behavioral_report(records: list[BehavioralRecord]) -> list[str]:
    lines = [f"## Behavioral set ({len(records)} conversations)", ""]
    lines += table(BEHAVIORAL_HEADER, behavioral_table_rows(records))

    lines += ["", "### Failures", ""]
    any_failure = False
    for r in records:
        problems = behavioral_problems(r)
        if problems:
            any_failure = True
            lines.append(f"- case {r.case['id']} [{r.case['difficulty']}] {r.case['case']}: {'; '.join(problems)}")
    if not any_failure:
        lines.append("None.")
    parse_failed = [r.case["id"] for r in records if r.parse_failures]
    lines += ["", f"Parser returned the safe default on cases: {parse_failed or 'none'}"]

    lines += ["", "### Replies, to read beside expected_behavior", ""]
    for r in records:
        lines += reply_block(r)
    return lines


def behavioral_problems(record: BehavioralRecord) -> list[str]:
    if record.error:
        return [f"ERROR {record.error}"]
    scores, result, case = record.scores, record.result, record.case
    assert scores is not None and result is not None
    problems = []
    if not scores.intent_ok:
        problems.append(f"intent {result.parsed.intent!r}, expected {case['expected_intent']!r}")
    if not scores.mode_ok:
        problems.append(f"mode {result.parsed.mode!r}, expected {case['expected_mode']!r}")
    if scores.category_ok is False:
        shown = sorted({p.category for o in result.outcomes for p in o.shown})
        problems.append(
            f"category shown {shown}, expected {case['category_match']} of {case['expected_categories']}"
        )
    if not scores.fallback_ok:
        loosened = sorted({name for o in result.outcomes for name in o.loosened})
        problems.append(f"fallback loosened {loosened}, expected {case['expect_fallback']!r}")
    if scores.cards_ok is False:
        shown_ids = sorted(p.id for o in result.outcomes for p in o.shown)
        problems.append(f"cards shown {shown_ids}, expected exactly {sorted(case['expected_card_ids'])}")
    if scores.language_ok is False:
        problems.append(f"reply language is not {case['expected_language']!r}")
    if not scores.grounding.ok:
        problems.append(
            f"NOT GROUNDED: unshown titles {scores.grounding.bad_titles}, "
            f"ungrounded amounts {scores.grounding.bad_amounts}"
        )
    return problems


def reply_block(record: BehavioralRecord) -> list[str]:
    case = record.case
    lines = [f"#### case {case['id']} [{case['difficulty']}] {case['case']}"]
    for number, turn in enumerate(case["turns"], start=1):
        lines.append(f"- user turn {number}: {turn}")
    lines.append(f"- expected_behavior: {case['expected_behavior']}")
    if record.error or record.result is None or record.scores is None:
        lines += [f"- ERROR: {record.error}", ""]
        return lines
    result = record.result
    shown = [f"{p.title} (${p.price})" for o in result.outcomes for p in o.shown]
    lines.append(f"- cards shown: {shown if shown else 'none'}")
    lines.append(f"- reply: {result.reply}")
    # Counts, ratings and one-word product names are not scored, so Or reads them here.
    grounding = record.scores.grounding
    lines.append(f"- other numbers in the reply (not scored): {grounding.other_numbers}")
    lines.append(f"- one-word product names in the reply, unshown (not scored): {grounding.unscored_title_hits}")
    lines.append("")
    return lines


def build_report(det_records: list[DeterministicRecord], beh_records: list[BehavioralRecord]) -> str:
    lines = ["# Eval results", ""]
    lines += deterministic_report(det_records)
    lines += [""]
    lines += behavioral_report(beh_records)
    return "\n".join(lines) + "\n"


def run_has_problems(det_records: list[Any], beh_records: list[Any]) -> bool:
    """True when results.md must be left alone: a call failed, or the run stopped early.

    A run killed halfway leaves a shorter file with no errors in it, and its scores would
    look like real ones.
    """
    if any(r.error for r in det_records) or any(r.error for r in beh_records):
        return True
    return len(det_records) != len(load_all_rows()) or len(beh_records) != len(load_all_cases())


def save_report(
    report: str, run_path: Path, has_errors: bool, results_path: Path = RESULTS_MD
) -> Path:
    """Write results.md, unless the run had errors: then save next to the run file instead."""
    path = run_path.with_suffix(".md") if has_errors else results_path
    with path.open("w", encoding="utf-8") as file:
        file.write(report)
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    cli = argparse.ArgumentParser(description="Run the evals, or re-score a saved run for free.")
    cli.add_argument("--rescore", type=Path, help="an evals/runs/*.jsonl file; makes no model calls")
    args = cli.parse_args()

    from app.catalog import load_catalog, load_categories

    catalog = load_catalog()

    if args.rescore:
        run_path = args.rescore
    else:
        # Imported here so that importing this file needs no key and no network.
        from app.llm import openai_llm
        from app.parser import parse_request
        from app.pipeline import run_turn
        from app.search import search

        categories = load_categories()
        rows, cases = load_all_rows(), load_all_cases()
        RUNS_DIR.mkdir(exist_ok=True)
        run_path = RUNS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        writer = RunWriter(run_path, total=len(rows) + len(cases))
        start_counting_parse_failures()
        run_deterministic(rows, catalog, categories, openai_llm, parse_request, search, writer)
        run_behavioral(cases, catalog, categories, openai_llm, run_turn, writer)

    # The report comes from the saved file, the same path --rescore takes.
    det_records, beh_records = score_run(load_run(run_path), catalog)
    report = build_report(det_records, beh_records)
    has_errors = run_has_problems(det_records, beh_records)
    saved_to = save_report(report, run_path, has_errors)  # written before printing
    print(report)
    print(f"Raw results: {run_path}")
    if has_errors:
        print(f"The run had errors or stopped early, so evals/results.md was left alone. Report saved to {saved_to}")
    else:
        print(f"Saved to {saved_to}")


if __name__ == "__main__":
    main()
