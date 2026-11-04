"""One conversation turn with no Chainlit in it, so the UI, tests and evals share the same code."""

from app.schemas import LLM, ConversationState, Product, SearchOutcome, TurnResult


def run_turn(
    message: str,
    state: ConversationState,
    catalog: list[Product],
    categories: list[str],
    llm: LLM,
) -> TurnResult:
    """Parse, merge any refine, search with fallback, choose the cards and write the reply."""
    raise NotImplementedError


def show_more(
    state: ConversationState,
    catalog: list[Product],
) -> tuple[list[SearchOutcome], ConversationState]:
    """Next cards for the current searches, excluding shown IDs. Makes no LLM call."""
    raise NotImplementedError
