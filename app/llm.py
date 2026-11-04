"""The real gpt-6-luna client behind the LLM callable. Tests pass a fake instead."""

from pydantic import BaseModel


def openai_llm(
    messages: list[dict[str, str]],
    response_model: type[BaseModel] | None = None,
) -> str:
    """Call gpt-6-luna, with structured output when a response model is given."""
    raise NotImplementedError
