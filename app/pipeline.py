"""A complete turn independent of Chainlit, shared by UI and dataset replay."""

import json
from time import perf_counter

from pydantic import ValidationError

from app.catalog import category_tags
from app.config import source_revision
from app.currency import UnsupportedCurrency, convert_search
from app.fallback import search_with_fallback
from app.index import ProductIndex
from app.monitoring import record_turn
from app.observability import span
from app.parser import CurrencyRefinementError, HISTORY_LIMIT, merge_searches, parse_request, PROMPT_VERSION as PARSER_VERSION
from app.product_type import check_product_types, PROMPT_VERSION as TYPE_VERSION
from app.responder import is_hebrew, write_reply
from app.schemas import ChatTurn, ConversationState, LLM, ParsedRequest, Product, SearchOutcome, SearchSpec, TurnResult
from app.search import rank_all

METADATA_VERSION = 2
CARD_FIELDS = {"id", "title", "description", "price", "rating", "brand", "thumbnail", "category"}


def _unique(products: list[Product]) -> list[Product]:
    return list({p.id: p for p in products}.values())


def _language_message(message: str, state: ConversationState) -> str:
    if any(c.isalpha() for c in message):
        return message
    return next((t.text for t in reversed(state.history) if t.role == "user" and any(c.isalpha() for c in t.text)), message)


def _outcomes(specs: list[SearchSpec], converted: list[tuple[SearchSpec, list[str]]],
              index: ProductIndex, seen: set[int], llm: LLM) -> list[SearchOutcome]:
    outcomes = []
    query_cache = {}
    used = set(seen)
    rankings = [rank_all(normalized, index, query_cache) for normalized, notes in converted]
    checked = check_product_types([normalized for normalized, notes in converted], rankings, llm, seen)
    for spec, (normalized, notes), ranked in zip(specs, converted, checked, strict=True):
        outcome = search_with_fallback(spec, normalized, index, used, query_cache, ranked=ranked)
        outcome.conversions = notes
        outcomes.append(outcome)
        used.update(p.id for p in outcome.shown)
    return outcomes


def _run_turn(message: str, state: ConversationState, catalog: list[Product], categories: list[str], llm: LLM,
             index: ProductIndex, conversation_id: str | None = None, traffic: str = "application") -> TurnResult:
    started = perf_counter()
    metadata = {"conversation_id": conversation_id, "session_id": conversation_id,
                "traffic": traffic, "git_sha": source_revision(), "parser_version": PARSER_VERSION,
                "product_type_version": TYPE_VERSION, "config_hash": index.config.fingerprint(), **index.identity}
    with span("shopping_turn", {"message": message}, metadata) as run:
        parsed = parse_request(message, state, categories, llm, category_tags(catalog))
        outcomes = []
        searches, shown = state.searches, state.shown
        question: str | None = None
        hebrew = is_hebrew(_language_message(message, state))
        if parsed.intent == "product_search":
            try:
                if parsed.mode == "show_more":
                    if not searches:
                        raise ValueError("nothing to show more of")
                    specs = searches
                else:
                    specs = merge_searches(parsed, state.searches)
                if not specs or any(not s.directions for s in specs):
                    raise ValueError("no positive product query")
                converted = [convert_search(spec) for spec in specs]
            except UnsupportedCurrency:
                parsed = ParsedRequest(intent="needs_clarification")
                question = "אין שער שמור למטבע הזה. מה התקציב בדולרים?" if hebrew else "I do not have a saved rate for that currency. What is your budget in US dollars?"
            except CurrencyRefinementError:
                parsed = ParsedRequest(intent="needs_clarification")
                question = "מה טווח המחירים המלא במטבע החדש?" if hebrew else "What is the complete price range in the new currency?"
            except ValueError:
                parsed = ParsedRequest(intent="needs_clarification")
            else:
                # Runtime/model/index errors must reach callers, not masquerade as
                # shopper ambiguity. Only request preparation is handled above.
                more = parsed.mode == "show_more"
                outcomes = _outcomes(specs, converted, index, {p.id for p in shown} if more else set(), llm)
                searches = specs
                cards = [p for outcome in outcomes for p in outcome.shown]
                shown = _unique(shown + cards if more else cards)
        reply = question or write_reply(message, parsed, outcomes, llm, categories, hebrew=hebrew)
        history = state.history + [ChatTurn(role="user", text=message), ChatTurn(role="assistant", text=reply)]
        new_state = ConversationState(history=history[-HISTORY_LIMIT:],
                                      searches=searches, shown=shown)
        result = TurnResult(parsed=parsed, outcomes=outcomes, reply=reply, state=new_state,
                            trace_id=str(run.id) if run is not None else None,
                            trace_context=run.to_headers() if run is not None else {},
                            timings={"total_ms": (perf_counter()-started)*1000})
        if run is not None:
            run.end(outputs={"intent": parsed.intent, "cards": [c.model_dump(mode="json") for o in outcomes for c in o.cards],
                             "reply": reply, "timings": result.timings})
        return result


def run_turn(message: str, state: ConversationState, catalog: list[Product], categories: list[str], llm: LLM,
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
        if not step.get("id") or metadata_of(step).get("app") != METADATA_VERSION:
            continue
        groups = metadata_of(step).get("cards")
        if not isinstance(groups, list):
            continue
        for number, products in enumerate(groups):
            if not isinstance(products, list) or not products:
                continue
            try:
                for product in products:
                    Product.model_validate(product)
            except ValidationError:
                continue
            elements.append({"id": f"{step['id']}-cards-{number}", "threadId": thread_id,
                             "type": "custom", "name": "ProductCards", "display": "inline",
                             "forId": step["id"], "props": {"products": products}, "mime": "application/json"})
    return elements
