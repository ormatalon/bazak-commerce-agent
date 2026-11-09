"""One conversation turn with no Chainlit in it, so the UI, tests and evals share the same code."""

import json
from typing import Any

from pydantic import ValidationError

from app.catalog import category_tags
from app.parser import merge_refine, parse_request, search_is_empty
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
from app.search import relevant_products, search_with_fallback

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


def _card_candidates(outcome: SearchOutcome) -> list[Product]:
    """The products that may get a card next: those matching a keyword, when any do.

    Not when both limits were loosened: those products answer the limits, not the keywords,
    so a backpack can still be the suggestion for "a bag".
    """
    if len(outcome.loosened) == 2:
        return outcome.products
    return relevant_products(outcome.spec, outcome.products)


def _run_searches(specs: list[SearchSpec], catalog: list[Product]) -> list[SearchOutcome]:
    """Search each spec with the fallback and choose its cards: all, the first top_k, or 3."""
    outcomes = []
    for spec in specs:
        outcome = search_with_fallback(spec, catalog)
        candidates = _card_candidates(outcome)
        outcome.total = len(candidates)
        count = len(candidates) if spec.show_all else spec.top_k or CARDS_PER_SEARCH
        outcome.shown = candidates[:count]
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
        outcome.total = len(_card_candidates(outcome))
        # Everything still unseen. Cards from an earlier search in this loop count as seen.
        seen = shown_ids | {p.id for p in new_cards}
        outcome.products = [p for p in outcome.products if p.id not in seen]
        outcome.shown = _card_candidates(outcome)[:CARDS_PER_SEARCH]
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
    parsed = parse_request(
        message, state.history, state.searches, state.shown, categories, llm, category_tags(catalog)
    )

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
            if not specs or any(search_is_empty(s) for s in specs):
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


# --- Saving and resuming a chat -------------------------------------------------------
#
# Every assistant message is saved with a small `metadata` dict (built below). When a chat
# is resumed, `rebuild_state` reads those dicts back and `card_elements` redraws the cards.
# Nothing here imports Chainlit, so tests can run it on plain dicts.

# Marks metadata written by this app. A message without it (an error or notice) is skipped.
METADATA_VERSION = 1


def message_metadata(
    outcomes: list[SearchOutcome],
    state: ConversationState,
    parsed: ParsedRequest | None,
    in_history: bool,
) -> dict[str, Any]:
    """What to save with one assistant message, so a resumed chat can rebuild itself.

    Only what was SHOWN is saved, never `outcome.products` (everything that matched),
    which can be most of the catalog. `parsed` is None for a "Show more" button click.
    """
    metadata: dict[str, Any] = {
        "app": METADATA_VERSION,
        # False for a "Show more" button click: it adds cards but no turn of conversation.
        "in_history": in_history,
        # One list of cards per search that has cards. Each list is one card element.
        "cards": [card_props(o)["products"] for o in outcomes if o.shown],
    }
    # A product search also stores the current searches. Typed or clicked "show more" keeps
    # the old shown cards and adds to them; any other search replaces them (as run_turn does).
    if parsed is None or parsed.intent == "product_search":
        metadata["searches"] = [s.model_dump(mode="json") for s in state.searches]
        metadata["replace_shown"] = parsed is not None and parsed.mode != "show_more"
    return metadata


def turn_metadata(result: TurnResult) -> dict[str, Any]:
    """Metadata for the reply to a typed message."""
    return message_metadata(result.outcomes, result.state, result.parsed, in_history=True)


def more_metadata(outcomes: list[SearchOutcome], state: ConversationState) -> dict[str, Any]:
    """Metadata for the cards a "Show more" click added. They are not part of the history."""
    return message_metadata(outcomes, state, None, in_history=False)


def metadata_of(step: dict[str, Any]) -> dict[str, Any]:
    """A step's metadata as a dict. SQLite hands it back as a JSON string."""
    metadata = step.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
    return metadata if isinstance(metadata, dict) else {}


def rebuild_state(steps: list[dict[str, Any]]) -> ConversationState:
    """Rebuild the conversation state from a saved chat's steps, oldest first.

    History comes from the user and assistant text. `searches` and `shown` come from the
    assistant messages' metadata. A step that can't be read is skipped, so one bad row
    can't stop a chat from resuming.
    """
    history: list[ChatTurn] = []
    searches: list[SearchSpec] = []
    shown: list[Product] = []
    pending_user: str | None = None

    for step in steps:
        if step.get("type") == "user_message":
            pending_user = step.get("output") or ""
            continue
        if step.get("type") != "assistant_message":
            continue
        metadata = metadata_of(step)
        if metadata.get("app") != METADATA_VERSION:
            continue  # an error or notice, not a reply
        try:
            cards = [Product.model_validate(c) for group in metadata.get("cards", []) for c in group]
            new_searches = (
                [SearchSpec.model_validate(s) for s in metadata["searches"]]
                if "searches" in metadata
                else None
            )
        except (ValidationError, TypeError):
            pending_user = None
            continue
        if new_searches is not None:
            searches = new_searches
        # Same rule as run_turn: a new or refined search replaces the shown cards, "show more" adds.
        shown = _add_unique([] if metadata.get("replace_shown") else shown, cards)
        if metadata.get("in_history") and pending_user is not None:
            history += [
                ChatTurn(role="user", text=pending_user),
                ChatTurn(role="assistant", text=step.get("output") or ""),
            ]
        pending_user = None

    return ConversationState(history=history, searches=searches, shown=shown)


def card_elements(steps: list[dict[str, Any]], thread_id: str) -> list[dict[str, Any]]:
    """Chainlit element dicts that redraw the saved cards under their messages.

    Chainlit would store elements itself only with a file storage provider, which we don't
    use. The cards are in the messages' metadata, so we rebuild the elements from there.
    """
    elements = []
    for step in steps:
        groups = metadata_of(step).get("cards")
        if step.get("type") != "assistant_message" or not isinstance(groups, list):
            continue
        for number, products in enumerate(groups):
            elements.append(
                {
                    # Fixed, so the same chat always gets the same element IDs.
                    "id": f"{step['id']}-cards-{number}",
                    "threadId": thread_id,
                    "type": "custom",
                    "name": "ProductCards",
                    "display": "inline",
                    "forId": step["id"],
                    "props": {"products": products},
                    "mime": "application/json",
                }
            )
    return elements
