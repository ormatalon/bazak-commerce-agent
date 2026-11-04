"""Turn a user message and recent history into a structured search."""

from app.schemas import LLM, ChatTurn, ParsedRequest, Product, SearchSpec


def parse_request(
    message: str,
    history: list[ChatTurn],
    previous_searches: list[SearchSpec],
    shown: list[Product],
    categories: list[str],
    llm: LLM,
) -> ParsedRequest:
    """Make one LLM call and validate it, returning the safe default if it's invalid."""
    raise NotImplementedError


def merge_refine(previous: SearchSpec, change: SearchSpec) -> SearchSpec:
    """Copy the previous search, overwrite non-null fields and drop clear_fields."""
    raise NotImplementedError
