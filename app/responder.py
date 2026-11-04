"""Write a short grounded reply from the search outcomes."""

from app.schemas import LLM, ParsedRequest, SearchOutcome


def write_reply(
    message: str,
    parsed: ParsedRequest,
    outcomes: list[SearchOutcome],
    llm: LLM,
) -> str:
    """Make one LLM call. `message` is the user's latest message that contains words."""
    raise NotImplementedError
