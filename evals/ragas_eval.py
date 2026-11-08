"""Judge saved replies with Ragas: faithfulness, card relevance and reply relevance.

Run it in the evals virtualenv, on a run file that evals/run_evals.py saved:

    .venv-evals/Scripts/python evals/ragas_eval.py evals/runs/run_<time>.jsonl
    .venv-evals/Scripts/python evals/ragas_eval.py evals/runs/run_<time>.jsonl --cases 14 31 h8
    .venv-evals/Scripts/python evals/ragas_eval.py evals/runs/run_<time>.jsonl --metrics reply_relevance

It needs its own virtualenv (requirements-evals.txt), because Ragas can't share the app's
openai version. So it never runs the app. It only reads the replies a run already saved.
Only the last turn of each conversation is judged, as in run_evals.py. The relevance judges
see the whole conversation, because "cheaper ones" alone doesn't say what the shopper wants.

The three metrics, and why each one:

- faithfulness (Ragas Faithfulness, 2 calls): is every claim in the reply supported by
  what the responder was given? One call splits the reply into statements, one judges each
  statement. Score: the share of supported statements. Only search replies are judged: a
  question or a decline has no product facts behind it, and Ragas turns "what's your
  budget?" into a claim and rejects it. The context is built by the same functions
  app/responder.py uses, and leaves out the shopper's message, so "say they cost $1" can't
  count as support for a $1 price.
- card_relevance (Ragas ContextRelevance, 2 calls): do the shown products fit what the
  shopper asked for? Two judges rate 0, 1 or 2 and the score is their average, from 0 to 1.
  The judges see only the products, not the search filter, or "category: laptops" would
  make any laptop look relevant. A fallback scores low by design, and the report marks it.
- reply_relevance (Ragas DiscreteMetric, 1 call): does the reply respond to the latest
  message? Pass or fail. Every reply is judged: a clarifying question or a polite decline
  can respond well. Ragas's own Answer Relevancy needs an embedding model, and gpt-6-luna is
  the only model this project may call, so this is an LLM-only judge with our own wording.

The judge is gpt-6-luna too, so the model grades its own replies. Judges also vary between
runs: read a single low score next to its reasons before trusting it.
"""

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `from app...` works when run as a script

from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from ragas.llms import llm_factory  # noqa: E402
from ragas.metrics import DiscreteMetric  # noqa: E402
from ragas.metrics.collections import ContextRelevance, Faithfulness  # noqa: E402

# Private helpers on purpose: they are the exact text the responder receives as facts.
from app.responder import _format_request, _format_results  # noqa: E402
from app.schemas import ParsedRequest, SearchOutcome  # noqa: E402

MODEL = "gpt-6-luna"  # the only model this project may call, so it also judges
DATASETS = [
    ROOT / "datasets" / "behavioral.jsonl",
    ROOT / "datasets" / "hebrew.jsonl",
    ROOT / "datasets" / "adversarial.jsonl",
]
PARALLEL_CALLS = 4  # a few cases at once, to stay well inside the key's rate limit
RESULTS_MD = ROOT / "evals" / "ragas_results.md"  # written by a full run, like results.md
METRICS = ["faithfulness", "card_relevance", "reply_relevance"]
SETS = [
    "english basic", "english hard", "hebrew basic", "hebrew hard",
    "adversarial attack", "adversarial should_answer", "adversarial edge", "all",
]

# --- Loading ----------------------------------------------------------------------------


def load_cases() -> dict[str, dict[str, Any]]:
    """Every behavioral case by its id as a string, with the set it is reported in.

    The ids match what run_evals.py saves: Hebrew ones get an "h" ("h6") and adversarial
    ones an "a" ("a3"), because each file's ids restart at 1.
    """
    cases: dict[str, dict[str, Any]] = {}
    for path in DATASETS:
        with path.open(encoding="utf-8") as file:
            for line in file:
                case = json.loads(line)
                if path.stem == "hebrew":
                    if case["type"] != "behavioral":
                        continue  # hebrew.jsonl also holds deterministic rows
                    case_id, case["set"] = f"h{case['id']}", f"hebrew {case['difficulty']}"
                elif path.stem == "adversarial":
                    case_id, case["set"] = f"a{case['id']}", f"adversarial {case['type']}"
                else:
                    case_id, case["set"] = str(case["id"]), f"english {case['difficulty']}"
                cases[case_id] = case
    return cases


def load_runs(run_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Every turn's saved result, per behavioral case that ran without an error."""
    runs: dict[str, list[dict[str, Any]]] = {}
    with run_path.open(encoding="utf-8") as file:
        for line in file:
            raw = json.loads(line)
            if raw["kind"] == "behavioral" and not raw["error"] and raw["results"]:
                runs[str(raw["case_id"])] = raw["results"]
    return runs


# --- What the judges see -----------------------------------------------------------------

# The responder's system prompt tells it what a "loosened" line means. The judge doesn't
# see that prompt, so without this line it rejects "the cards are the closest products",
# which the fallback's ordering makes true.
LOOSENED_MEANING = (
    "A 'loosened' line means nothing matched those limits, and the shown products of that "
    "search are the closest products to them."
)
# The responder knows each shown product appears as a card; the judge doesn't. Without
# this, "see the cards" is marked unsupported in almost every reply, at random.
CARDS_MEANING = "Every shown product appears to the shopper as a product card under the reply."


# Added to Ragas's statement-splitting instruction. Without it, Ragas also turns the reply's
# pleasantries into claims ("the answer invites the shopper to look at the cards", "found
# sunglasses for the trip") and rejects them, burying the real findings. The trade-off: a
# false opinion like "perfect for your trip" is no longer checked. Prices and products are.
PRODUCT_CLAIMS_ONLY = """
Keep only statements that claim something checkable about the store's products or search
results: product names, prices, ratings, descriptions, brand, availability, shipping,
warranty, returns, how many products match, whether anything matched, and which products
are the closest. Leave out the shopper's own goals or occasion (a trip, a gift), pointers
to the cards, greetings and offers to help. If no such statement is left, return an empty
list."""


def conversation(turns: list[str], results: list[dict[str, Any]]) -> str:
    """The shopper's messages and the earlier replies, ending with the latest message."""
    lines = []
    for i, text in enumerate(turns):
        lines.append(f"Shopper: {text}")
        if i < len(turns) - 1:  # the last reply is the one being judged
            lines.append(f"Assistant: {results[i]['reply']}")
    return "\n".join(lines)


def is_search(turn: dict[str, Any]) -> bool:
    """A reply about search results: the only kind with product claims to check."""
    return turn["parsed"]["intent"] == "product_search"


def shown_products(turn: dict[str, Any]) -> list[dict[str, Any]]:
    return [product for outcome in turn["outcomes"] for product in outcome["shown"]]


def loosened(turn: dict[str, Any]) -> list[str]:
    return [limit for outcome in turn["outcomes"] for limit in outcome["loosened"]]


def responder_facts(turn: dict[str, Any]) -> list[str]:
    """The request summary and the results, as the responder received them."""
    parsed = ParsedRequest.model_validate(turn["parsed"])
    outcomes = [SearchOutcome.model_validate(o) for o in turn["outcomes"]]
    facts = [_format_request(parsed, outcomes), _format_results(parsed, outcomes)]
    if any(o.shown for o in outcomes):
        facts.append(CARDS_MEANING)
    if any(o.loosened for o in outcomes):
        facts.append(LOOSENED_MEANING)
    return facts


def product_cards(turn: dict[str, Any]) -> list[str]:
    """What the shopper sees on each card, and nothing about how the search was built."""
    return [
        f"{p['title']} | category: {p['category']} | ${p['price']:,.2f} | {p['description']}"
        for p in shown_products(turn)
    ]


REPLY_RELEVANCE_PROMPT = """\
You are checking one reply of a shopping assistant for an online store.

The conversation, ending with the shopper's latest message:
{conversation}

The assistant's reply to that latest message:
{response}

Does the reply respond to what the shopper asked in the latest message, read in the
context of the conversation? These all count as responding: showing or describing products
for the request, saying nothing matched and offering the closest products, asking one
clarifying question when the request is unclear, politely declining something a store
cannot do, and a short friendly answer to small talk. It fails if it ignores the latest
message, answers a different request, or drifts to something the shopper didn't ask about.
Do not judge whether facts or prices are true; that is checked separately.
Answer "pass" or "fail"."""


# --- Judging -----------------------------------------------------------------------------


def skipped(label: str) -> dict[str, Any]:
    """A metric that doesn't apply to this reply, with the reason shown in the report."""
    return {"value": None, "label": label, "notes": []}


async def judge_faithfulness(metric: Faithfulness, latest: str, turn: dict[str, Any]) -> dict[str, Any]:
    """Ragas's two steps, called one by one so the failing statements can be printed.

    This is what Faithfulness.ascore does, minus collapsing the verdicts into one number.
    It gets only the latest message, not the whole conversation: given the conversation,
    Ragas also extracts statements about the chat itself ("the assistant invites the
    shopper to look at the cards"), which no product fact can support.
    """
    if not is_search(turn):
        return skipped("no search")
    statements = await metric._create_statements(latest, turn["reply"])
    verdicts = await metric._create_verdicts(statements, "\n".join(responder_facts(turn))) if statements else None
    if not verdicts or not verdicts.statements:
        return {"value": math.nan, "label": "no claims", "notes": []}
    supported = sum(1 for v in verdicts.statements if v.verdict)
    notes = [f"unsupported: {v.statement}\n  - judge's reason: {v.reason}" for v in verdicts.statements if not v.verdict]
    return {"value": supported / len(verdicts.statements), "notes": notes}


async def judge_cards(metric: ContextRelevance, talk: str, turn: dict[str, Any]) -> dict[str, Any]:
    if not shown_products(turn):
        return skipped("no cards")
    result = await metric.ascore(user_input=talk, retrieved_contexts=product_cards(turn))
    notes = [f"cards: {', '.join(p['title'] for p in shown_products(turn))}"]
    if loosened(turn):
        notes.append(f"fallback: {', '.join(loosened(turn))} loosened, so a low score is expected")
    return {"value": float(result.value), "notes": notes}


async def judge_reply(metric: DiscreteMetric, llm: Any, talk: str, turn: dict[str, Any]) -> dict[str, Any]:
    result = await metric.ascore(llm=llm, conversation=talk, response=turn["reply"])
    return {"value": 1.0 if result.value == "pass" else 0.0, "notes": [f"judge's reason: {result.reason}"]}


async def score_all(
    cases: dict[str, dict[str, Any]], runs: dict[str, list[dict[str, Any]]], ids: list[str], metrics: list[str]
) -> list[dict[str, Any]]:
    llm = llm_factory(MODEL, client=AsyncOpenAI())
    faithfulness = Faithfulness(llm=llm)
    prompt = faithfulness.statement_generator_prompt
    prompt.instruction = prompt.instruction + PRODUCT_CLAIMS_ONLY  # this instance only
    cards = ContextRelevance(llm=llm)
    reply = DiscreteMetric(name="reply_relevance", prompt=REPLY_RELEVANCE_PROMPT, allowed_values=["pass", "fail"])
    gate = asyncio.Semaphore(PARALLEL_CALLS)

    async def one(case_id: str) -> dict[str, Any]:
        case, results = cases[case_id], runs[case_id]
        turn, talk = results[-1], conversation(case["turns"], results)
        row: dict[str, Any] = {"id": case_id, "set": case["set"], "talk": talk, "reply": turn["reply"]}
        jobs = {
            "faithfulness": lambda: judge_faithfulness(faithfulness, case["turns"][-1], turn),
            "card_relevance": lambda: judge_cards(cards, talk, turn),
            "reply_relevance": lambda: judge_reply(reply, llm, talk, turn),
        }
        async with gate:
            for name in metrics:
                try:
                    row[name] = await jobs[name]()
                except Exception as error:  # noqa: BLE001 - one bad call must not lose the run
                    row[name] = {"value": None, "label": "error", "error": type(error).__name__, "notes": []}
        return row

    return await asyncio.gather(*(one(case_id) for case_id in ids))


def estimate_calls(runs: dict[str, list[dict[str, Any]]], ids: list[str], metrics: list[str]) -> int:
    calls = 0
    for case_id in ids:
        turn = runs[case_id][-1]
        calls += 2 * ("faithfulness" in metrics and is_search(turn))
        calls += 2 * ("card_relevance" in metrics and bool(shown_products(turn)))
        calls += "reply_relevance" in metrics
    return calls


# --- Report ------------------------------------------------------------------------------


def format_value(name: str, result: dict[str, Any]) -> str:
    if result.get("error"):
        return f"error ({result['error']})"
    if result["value"] is None or math.isnan(result["value"]):
        return result.get("label", "no claims")
    if name == "reply_relevance":
        return "pass" if result["value"] == 1.0 else "fail"
    return f"{result['value']:.2f}"


def summary_cell(name: str, results: list[dict[str, Any]]) -> str:
    """The mean, and how many judged replies fell below a perfect score."""
    values = [r["value"] for r in results if r["value"] is not None and not math.isnan(r["value"])]
    if not values:
        return "n/a"
    below = sum(1 for v in values if v < 1.0)
    if name == "reply_relevance":
        return f"{len(values) - below}/{len(values)} pass"
    return f"{sum(values) / len(values):.2f} ({below} of {len(values)} below 1.0)"


def report(rows: list[dict[str, Any]], metrics: list[str]) -> str:
    """A summary per set, the cases below a perfect score per metric, then every score."""
    lines = ["## Summary", ""]
    lines.append("| set | cases | " + " | ".join(metrics) + " | errors |")
    lines.append("| --- | --- | " + " | ".join("---" for _ in metrics) + " | --- |")
    for set_name in SETS:
        group = [r for r in rows if set_name == "all" or r["set"] == set_name]
        if not group:
            continue
        cells = [summary_cell(name, [r[name] for r in group]) for name in metrics]
        errors = sum(1 for r in group for name in metrics if r[name].get("error"))
        lines.append(f"| {set_name} | {len(group)} | " + " | ".join(cells) + f" | {errors} |")

    for name in metrics:
        lines += ["", f"## {name}: below a perfect score, or an error", ""]
        flagged = [
            r for r in rows
            if r[name].get("error") or (r[name]["value"] is not None and not math.isnan(r[name]["value"]) and r[name]["value"] < 1.0)
        ]
        if not flagged:
            lines.append("None.")
        for r in flagged:
            lines.append(f"### case {r['id']} [{r['set']}]: {format_value(name, r[name])}")
            lines += [f"    {line}" for line in r["talk"].splitlines()]
            lines.append(f"- reply: {r['reply']}")
            lines += [f"- {note}" for note in r[name]["notes"]]
            lines.append("")

    lines += ["", "## Every case", "", "| case | set | " + " | ".join(metrics) + " |"]
    lines.append("| --- | --- | " + " | ".join("---" for _ in metrics) + " |")
    lines += [f"| {r['id']} | {r['set']} | " + " | ".join(format_value(n, r[n]) for n in metrics) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # replies can be in Hebrew
    load_dotenv(ROOT / ".env")  # AsyncOpenAI reads OPENAI_API_KEY itself; it is never printed
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("run", type=Path, help="an evals/runs/*.jsonl file saved by run_evals.py")
    cli.add_argument("--cases", nargs="*", help="only these case ids, e.g. 14 31 h8")
    cli.add_argument("--metrics", nargs="*", choices=METRICS, default=METRICS, help="default: all three")
    args = cli.parse_args()

    cases, runs = load_cases(), load_runs(args.run)
    ids = [i for i in (args.cases or list(runs)) if i in runs and i in cases]
    missing = [i for i in (args.cases or []) if i not in ids]
    if missing:
        print(f"Not in this run, or not a behavioral case: {', '.join(missing)}")
    metrics = [m for m in METRICS if m in args.metrics]  # always in the same order
    print(f"Judging {len(ids)} replies with {MODEL}, about {estimate_calls(runs, ids, metrics)} model calls.\n")
    text = report(asyncio.run(score_all(cases, runs, ids, metrics)), metrics)
    print(text)

    # Only a full run replaces the saved results, so a quick check can't overwrite them.
    if args.cases or metrics != METRICS:
        print(f"A run with --cases or --metrics is not saved. Run without them to update {RESULTS_MD.name}.")
        return
    header = f"# Ragas results\n\nRun file: `{args.run.name}`, judged by {MODEL}.\n\n"
    RESULTS_MD.write_text(header + text, encoding="utf-8")
    print(f"Saved to {RESULTS_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
