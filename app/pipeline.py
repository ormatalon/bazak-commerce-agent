"""One conversation turn with no Chainlit in it, so the UI, tests and evals share the same code."""

from typing import Any

from app.parser import MERGE_FIELDS, merge_refine, parse_request
from app.responder import write_reply
from app.schemas import (
    LLM,
    ChatTurn,
    ConversationState,
    ParsedRequest,
    Product,
    SearchOutcome,
    SearchSpec,
    TurnResult,
)
from app.search import search_with_fallback

# Cards shown per search unless the user asked for a number (top_k).
CARDS_PER_SEARCH = 3

# The fields the card element reads (public/elements/ProductCards.jsx).
CARD_FIELDS = {"id", "title", "description", "price", "rating", "brand", "thumbnail", "category"}


def card_props(outcome: SearchOutcome) -> dict[str, Any]:
    """The props app/main.py gives the ProductCards element for one outcome."""
    return {"products": [p.model_dump(include=CARD_FIELDS) for p in outcome.shown]}


def has_more(outcome: SearchOutcome) -> bool:
    """True when the outcome matched products that have no card yet."""
    return len(outcome.products) > len(outcome.shown)


def _search_is_empty(spec: SearchSpec) -> bool:
    """True when no search field is set. Run on it, this would match the whole catalog."""
    for name in MERGE_FIELDS:
        value = getattr(spec, name)
        if value is not None and value != []:
            return False
    return True


def _add_unique(shown: list[Product], new: list[Product]) -> list[Product]:
    """A new list: `shown` followed by the products in `new` that are not in it yet."""
    result = list(shown)
    known_ids = {p.id for p in result}
    for product in new:
        if product.id not in known_ids:
            result.append(product)
            known_ids.add(product.id)
    return result


def _words_message(message: str, history: list[ChatTurn]) -> str:
    """The latest user message with a letter in it, so answering "$300" keeps the language."""
    if any(c.isalpha() for c in message):
        return message
    for turn in reversed(history):
        if turn.role == "user" and any(c.isalpha() for c in turn.text):
            return turn.text
    return message


def _merge_refines(changes: list[SearchSpec], previous: list[SearchSpec]) -> list[SearchSpec]:
    """Apply each change to the previous search it names. With no previous search, to an empty one."""
    merged = []
    for change in changes:
        index = change.refines_index or 0
        if index < 0 or index >= len(previous):
            index = 0  # out of range: the model named a search that doesn't exist
        base = previous[index] if previous else SearchSpec()
        merged.append(merge_refine(base, change))
    return merged


def _run_searches(specs: list[SearchSpec], catalog: list[Product]) -> list[SearchOutcome]:
    """Search each spec with the fallback and choose its cards: the first top_k, or 3."""
    outcomes = []
    for spec in specs:
        outcome = search_with_fallback(spec, catalog)
        count = spec.top_k or CARDS_PER_SEARCH
        outcome.shown = outcome.products[:count]
        outcomes.append(outcome)
    return outcomes


def show_more(
    state: ConversationState,
    catalog: list[Product],
) -> tuple[list[SearchOutcome], ConversationState]:
    """Next cards for the current searches, excluding shown IDs. Makes no LLM call.

    state.searches stays as it is and history is not touched.
    """
    if not state.searches:
        return [], state

    shown_ids = {p.id for p in state.shown}
    outcomes = []
    new_cards: list[Product] = []
    for spec in state.searches:
        outcome = search_with_fallback(spec, catalog)
        # Everything still unseen. Cards from an earlier search in this loop count as seen.
        seen = shown_ids | {p.id for p in new_cards}
        outcome.products = [p for p in outcome.products if p.id not in seen]
        outcome.shown = outcome.products[:CARDS_PER_SEARCH]
        new_cards = _add_unique(new_cards, outcome.shown)
        outcomes.append(outcome)

    new_state = state.model_copy(update={"shown": _add_unique(state.shown, new_cards)})
    return outcomes, new_state


def run_turn(
    message: str,
    state: ConversationState,
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
) -> TurnResult:
    """Parse, merge any refine, search with fallback, choose the cards and write the reply.

    LLM errors are not caught here, so evals can see them. `state` is never changed:
    the new state is returned, so a caller that hits an error still has the old one.
    """
    parsed = parse_request(message, state.history, state.searches, state.shown, categories, llm)

    outcomes: list[SearchOutcome] = []
    searches = state.searches
    shown = state.shown

    if parsed.intent == "product_search":
        if parsed.mode == "show_more":
            outcomes, more_state = show_more(state, catalog)
            if not outcomes:
                parsed = ParsedRequest(intent="needs_clarification")  # nothing to show more of
            shown = more_state.shown
        else:
            if parsed.mode == "refine":
                specs = _merge_refines(parsed.searches, state.searches)
            else:
                specs = list(parsed.searches)
            if not specs or any(_search_is_empty(s) for s in specs):
                # Running it would match all 194 products and present them as a match.
                parsed = ParsedRequest(intent="needs_clarification")
            else:
                outcomes = _run_searches(specs, catalog)
                searches = specs
                shown = _add_unique([], [p for o in outcomes for p in o.shown])

    reply = write_reply(_words_message(message, state.history), parsed, outcomes, llm)

    history = state.history + [
        ChatTurn(role="user", text=message),
        ChatTurn(role="assistant", text=reply),
    ]
    new_state = ConversationState(history=history, searches=searches, shown=shown)
    return TurnResult(parsed=parsed, outcomes=outcomes, reply=reply, state=new_state)
