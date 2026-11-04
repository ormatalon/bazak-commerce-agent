"""Run both eval sets and print a summary. One command: python evals/run_evals.py

Deterministic set (datasets/deterministic.csv): parse_request, then search(), with no
fallback and no display cap. Scored against evals/ground_truth.py.
Behavioral set (datasets/behavioral.jsonl): replay every turn through run_turn and
score the last one.

This makes real model calls, so only the Lead runs it (the key lives in the main folder's .env).
The app modules are imported inside main(), so importing this file needs no key and no network.
Results are also written to evals/results.md.
"""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
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
from evals.ground_truth import expected_ids, load_rows, row_to_spec  # noqa: E402
from evals.scoring import (  # noqa: E402
    CaseScores,
    exact_match,
    filter_matches,
    precision_recall_f1,
    score_case,
)

BEHAVIORAL_JSONL = REPO_ROOT / "datasets" / "behavioral.jsonl"
RESULTS_MD = Path(__file__).resolve().parent / "results.md"

ParseFn = Callable[[str, list[Any], list[SearchSpec], list[Product], list[str], LLM], ParsedRequest]
SearchFn = Callable[[SearchSpec, list[Product]], list[Product]]
RunTurnFn = Callable[[str, ConversationState, list[Product], list[str], LLM], TurnResult]


# ---------------------------------------------------------------------------
# Deterministic set
# ---------------------------------------------------------------------------


@dataclass
class DeterministicRecord:
    row: dict[str, str]
    expected: list[int]
    returned: list[int]
    got_spec: SearchSpec | None
    precision: float
    recall: float
    f1: float
    top_k_exact: bool | None  # None on rows without top_k
    filter_ok: bool
    error: str | None = None


def run_deterministic(
    rows: list[dict[str, str]],
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
    parse_fn: ParseFn,
    search_fn: SearchFn,
) -> list[DeterministicRecord]:
    records = []
    for row in rows:
        expected_spec = row_to_spec(row)
        expected = expected_ids(expected_spec, catalog)
        has_top_k = expected_spec.top_k is not None
        try:
            parsed = parse_fn(row["query"], [], [], [], categories, llm)
            # One query should give one search. Score the first; the filter check needs exactly one.
            got_spec = parsed.searches[0] if parsed.searches else None
            returned_products = search_fn(got_spec, catalog) if got_spec else []
            # search() returns every match with no display cap, so cut to top_k here.
            if got_spec and got_spec.top_k is not None:
                returned_products = returned_products[: got_spec.top_k]
            returned = [product.id for product in returned_products]
            precision, recall, f1 = precision_recall_f1(set(expected), set(returned))
            filter_ok = len(parsed.searches) == 1 and filter_matches(expected_spec, got_spec)
            records.append(
                DeterministicRecord(
                    row=row,
                    expected=expected,
                    returned=returned,
                    got_spec=got_spec,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    top_k_exact=exact_match(expected, returned) if has_top_k else None,
                    filter_ok=filter_ok,
                )
            )
        except Exception as error:  # noqa: BLE001 - one bad call must not lose the whole run
            records.append(
                DeterministicRecord(
                    row=row,
                    expected=expected,
                    returned=[],
                    got_spec=None,
                    precision=0.0,
                    recall=0.0,
                    f1=0.0,
                    top_k_exact=False if has_top_k else None,
                    filter_ok=False,
                    error=repr(error),
                )
            )
    return records


# ---------------------------------------------------------------------------
# Behavioral set
# ---------------------------------------------------------------------------


@dataclass
class BehavioralRecord:
    case: dict[str, Any]
    result: TurnResult | None
    scores: CaseScores | None
    error: str | None = None


def load_cases(path: Path = BEHAVIORAL_JSONL) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def run_behavioral(
    cases: list[dict[str, Any]],
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
    run_turn_fn: RunTurnFn,
) -> list[BehavioralRecord]:
    catalog_titles = [product.title for product in catalog]
    records = []
    for case in cases:
        try:
            state = ConversationState()
            result = None
            for turn in case["turns"]:
                result = run_turn_fn(turn, state, catalog, categories, llm)
                state = result.state  # carry the conversation into the next turn
            assert result is not None, "a case must have at least one turn"
            scores = score_case(result, case, case["turns"], catalog_titles)
            records.append(BehavioralRecord(case=case, result=result, scores=scores))
        except Exception as error:  # noqa: BLE001 - one bad call must not lose the whole run
            records.append(BehavioralRecord(case=case, result=None, scores=None, error=repr(error)))
    return records


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


def deterministic_report(records: list[DeterministicRecord]) -> list[str]:
    lines = [f"## Deterministic set ({len(records)} queries)", ""]
    groups = [("basic", [r for r in records if r.row["difficulty"] == "basic"])]
    groups += [("hard", [r for r in records if r.row["difficulty"] == "hard"]), ("all", records)]
    table_rows = []
    for name, group in groups:
        top_k_rows = [r for r in group if r.top_k_exact is not None]
        table_rows.append(
            [
                name,
                str(len(group)),
                mean([r.precision for r in group]),
                mean([r.recall for r in group]),
                mean([r.f1 for r in group]),
                percent(sum(1 for r in top_k_rows if r.top_k_exact), len(top_k_rows)),
                percent(sum(1 for r in group if r.filter_ok), len(group)),
                str(sum(1 for r in group if r.error)),
            ]
        )
    lines += table(
        ["set", "n", "precision", "recall", "F1", "top_k exact", "filter match", "errors"],
        table_rows,
    )
    lines += ["", "### Failures (any metric below perfect)", ""]
    failures = [
        r for r in records if r.f1 < 1 or r.top_k_exact is False or not r.filter_ok or r.error
    ]
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
            f"    P={r.precision:.2f} R={r.recall:.2f} F1={r.f1:.2f}  "
            f"expected {len(r.expected)} IDs, returned {len(r.returned)}; missing {missing}, extra {extra}"
        )
        if not r.filter_ok:
            lines.append(f"    expected filter: {filter_text(row_to_spec(row))}")
            lines.append(f"    extracted filter: {filter_text(r.got_spec)}")
        if r.top_k_exact is False:
            lines.append(f"    top_k order: expected {r.expected}, got {r.returned}")
    return lines


def filter_text(spec: SearchSpec | None) -> str:
    if spec is None:
        return "(no search)"
    names = ["category", "price_min", "price_max", "rating_min", "sort_by", "order", "top_k"]
    return ", ".join(f"{name}={getattr(spec, name)}" for name in names)


def behavioral_report(records: list[BehavioralRecord]) -> list[str]:
    lines = [f"## Behavioral set ({len(records)} conversations)", ""]
    groups = [("basic", [r for r in records if r.case["difficulty"] == "basic"])]
    groups += [("hard", [r for r in records if r.case["difficulty"] == "hard"]), ("all", records)]
    table_rows = []
    for name, group in groups:
        scored = [r.scores for r in group]  # None for a case that crashed
        # A crashed case counts as wrong on every metric that applies to it.
        intent = sum(1 for s in scored if s and s.intent_ok)
        mode = sum(1 for s in scored if s and s.mode_ok)
        fallback = sum(1 for s in scored if s and s.fallback_ok)
        category_cases = [r for r in group if r.case["expected_categories"]]
        category = sum(1 for r in category_cases if r.scores and r.scores.category_ok)
        language_cases = [r for r in group if r.case.get("expected_language")]
        language = sum(1 for r in language_cases if r.scores and r.scores.language_ok)
        replied = [r for r in group if r.scores]  # grounding needs a reply to check
        grounded = sum(1 for r in replied if r.scores.grounding.ok)
        table_rows.append(
            [
                name,
                str(len(group)),
                percent(intent, len(group)),
                percent(mode, len(group)),
                percent(category, len(category_cases)),
                percent(fallback, len(group)),
                f"{language}/{len(language_cases)}",
                percent(grounded, len(replied)),
                str(sum(1 for r in group if r.error)),
            ]
        )
    lines += table(
        ["set", "n", "intent", "mode", "category", "fallback", "language", "grounding", "errors"],
        table_rows,
    )

    lines += ["", "### Failures", ""]
    any_failure = False
    for r in records:
        problems = behavioral_problems(r)
        if problems:
            any_failure = True
            lines.append(f"- case {r.case['id']} [{r.case['difficulty']}] {r.case['case']}: {'; '.join(problems)}")
    if not any_failure:
        lines.append("None.")

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
    # Counts and ratings are not scored, so Or reads them here.
    lines.append(f"- other numbers in the reply (not scored): {record.scores.grounding.other_numbers}")
    lines.append("")
    return lines


def build_report(
    det_records: list[DeterministicRecord], beh_records: list[BehavioralRecord]
) -> str:
    lines = ["# Eval results", ""]
    lines += deterministic_report(det_records)
    lines += [""]
    lines += behavioral_report(beh_records)
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    # Imported here so that importing this file needs no key and no network.
    from app.catalog import load_catalog, load_categories
    from app.llm import openai_llm
    from app.parser import parse_request
    from app.pipeline import run_turn
    from app.search import search

    catalog = load_catalog()
    categories = load_categories()

    det_records = run_deterministic(
        load_rows(), catalog, categories, openai_llm, parse_request, search
    )
    beh_records = run_behavioral(load_cases(), catalog, categories, openai_llm, run_turn)

    report = build_report(det_records, beh_records)
    print(report)
    with RESULTS_MD.open("w", encoding="utf-8") as file:
        file.write(report)
    print(f"Saved to {RESULTS_MD}")


if __name__ == "__main__":
    main()
