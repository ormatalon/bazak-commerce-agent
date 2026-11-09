"""A complete turn independent of Chainlit, shared by UI and dataset replay."""

import json
from time import perf_counter

from pydantic import ValidationError

from app.catalog import category_tags
from app.currency import UnsupportedCurrency, convert_search
from app.fallback import search_with_fallback
from app.index import ProductIndex
from app.monitoring import record_turn
from app.observability import span, trace_id
from app.parser import merge_searches, parse_request
from app.product_type import check_product_types
from app.responder import is_hebrew, write_reply
from app.schemas import ChatTurn, ConversationState, LLM, ParsedRequest, SearchOutcome, TurnResult
from app.search import rank_all

METADATA_VERSION = 2
CARD_FIELDS = {"id", "title", "description", "price", "rating", "brand", "thumbnail", "category"}


def _unique(products):
    return list({p.id: p for p in products}.values())


def _language_message(message: str, state: ConversationState) -> str:
    if any(c.isalpha() for c in message):
        return message
    return next((t.text for t in reversed(state.history) if t.role == "user" and any(c.isalpha() for c in t.text)), message)


def _outcomes(specs, index: ProductIndex, seen: set[int], llm: LLM):
    outcomes = []
    query_cache = {}
    used = set(seen)
    converted = [convert_search(spec) for spec in specs]
    rankings = [rank_all(normalized, index, query_cache) for normalized, notes in converted]
    checked = check_product_types([normalized for normalized, notes in converted], rankings, llm, seen)
    for spec, (normalized, notes), ranked in zip(specs, converted, checked, strict=True):
        outcome = search_with_fallback(spec, normalized, index, used, query_cache, ranked=ranked)
        outcome.conversions = notes
        outcomes.append(outcome)
        used.update(p.id for p in outcome.shown)
    return outcomes


def _run_turn(message: str, state: ConversationState, catalog, categories: list[str], llm: LLM,
             index: ProductIndex, conversation_id: str | None = None, traffic: str = "application") -> TurnResult:
    started = perf_counter()
    metadata = {"conversation_id": conversation_id, "session_id": conversation_id,
                "traffic": traffic, "config_hash": index.config.fingerprint(), **index.identity}
    with span("shopping_turn", {"message": message}, metadata) as run:
        parsed = parse_request(message, state, categories, llm, category_tags(catalog))
        outcomes = []
        searches, shown = state.searches, state.shown
        currency_question = False
        if parsed.intent == "product_search":
            try:
                if parsed.mode == "show_more":
                    if not searches:
                        raise ValueError("nothing to show more of")
                    outcomes = _outcomes(searches, index, {p.id for p in shown}, llm)
                    shown = _unique(shown + [p for o in outcomes for p in o.shown])
                else:
                    specs = merge_searches(parsed, state.searches)
                    if not specs or any(not s.directions for s in specs):
                        raise ValueError("no positive product query")
                    outcomes = _outcomes(specs, index, set(), llm)
                    searches = specs
                    shown = _unique([p for o in outcomes for p in o.shown])
            except UnsupportedCurrency:
                outcomes = []
                parsed = ParsedRequest(intent="needs_clarification")
                currency_question = True
            except (ValueError, ValidationError):
                outcomes = []
                parsed = ParsedRequest(intent="needs_clarification")
        language_message = _language_message(message, state)
        if currency_question:
            reply = "אין שער שמור למטבע הזה. מה התקציב בדולרים?" if is_hebrew(language_message) else "I do not have a saved rate for that currency. What is your budget in US dollars?"
        else:
            reply = write_reply(language_message, parsed, outcomes, llm, categories)
        new_state = ConversationState(history=state.history + [ChatTurn(role="user", text=message), ChatTurn(role="assistant", text=reply)],
                                      searches=searches, shown=shown)
        result = TurnResult(parsed=parsed, outcomes=outcomes, reply=reply, state=new_state,
                            trace_id=str(run.id) if run is not None else None,
                            trace_context=run.to_headers() if run is not None else {},
                            timings={"total_ms": (perf_counter()-started)*1000})
        if run is not None:
            run.end(outputs={"intent": parsed.intent, "cards": [c.model_dump(mode="json") for o in outcomes for c in o.cards],
                             "reply": reply, "timings": result.timings})
        return result


def run_turn(message: str, state: ConversationState, catalog, categories: list[str], llm: LLM,
             index: ProductIndex, conversation_id: str | None = None, traffic: str = "application") -> TurnResult:
    """Record success/failure without swallowing pipeline errors or retrying calls."""
    started = perf_counter()
    try:
        result = _run_turn(message, state, catalog, categories, llm, index, conversation_id, traffic)
    except Exception as error:
        record_turn(None, traffic, (perf_counter()-started)*1000, type(error).__name__)
        raise
    record_turn(result, traffic, (perf_counter()-started)*1000)
    return result


def card_props(outcome: SearchOutcome) -> dict:
    return {"products": [{**c.product.model_dump(include=CARD_FIELDS), "alternative": c.alternative} for c in outcome.cards]}


def has_more(outcome: SearchOutcome) -> bool:
    return outcome.has_more


def metadata_of(step: dict) -> dict:
    metadata = step.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            return {}
    return metadata if isinstance(metadata, dict) else {}


def turn_metadata(result: TurnResult) -> dict:
    return {"app": METADATA_VERSION, "state": result.state.model_dump(mode="json"),
            "cards": [card_props(o)["products"] for o in result.outcomes if o.cards],
            "outcomes": [{"reason": o.reason, "cards": [c.model_dump(mode="json") for c in o.cards]} for o in result.outcomes],
            "trace_id": result.trace_id}


def rebuild_state(steps: list[dict]) -> ConversationState:
    for step in reversed(steps):
        metadata = metadata_of(step)
        if metadata.get("app") == METADATA_VERSION:
            try:
                return ConversationState.model_validate(metadata["state"])
            except (KeyError, ValidationError, TypeError):
                continue
    return ConversationState()


def card_elements(steps: list[dict], thread_id: str) -> list[dict]:
    elements = []
    for step in steps:
        if metadata_of(step).get("app") != METADATA_VERSION:
            continue
        for number, products in enumerate(metadata_of(step).get("cards", [])):
            elements.append({"id": f"{step['id']}-cards-{number}", "threadId": thread_id,
                             "type": "custom", "name": "ProductCards", "display": "inline",
                             "forId": step["id"], "props": {"products": products}, "mime": "application/json"})
    return elements
