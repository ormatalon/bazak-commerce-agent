"""The real gpt-6-luna client behind the LLM callable. Tests pass a fake instead."""

import logging
from threading import Lock

from dotenv import load_dotenv
from openai import OpenAI
from openai.lib import type_to_response_format_param
from pydantic import BaseModel

from app.config import ROOT

# The only model this project may call.
MODEL = "gpt-6-luna"

# Created on the first call, so importing this module needs no key.
_client: OpenAI | None = None
_client_lock = Lock()
logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    """Build the OpenAI client once. OPENAI_API_KEY comes from .env or the environment."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        load_dotenv(ROOT / ".env")
        # With no api_key argument the client reads OPENAI_API_KEY itself,
        # so the key never sits in a variable of ours, and is never printed or logged.
        # One retry, so a persistent error shows in about 2 minutes, not 3.
        client = OpenAI(timeout=60.0, max_retries=1)
        try:
            from app.observability import get_client, tracing_enabled
            tracing_client = get_client() if tracing_enabled() else None
            if tracing_client is not None:
                from langsmith.wrappers import wrap_openai
                client = wrap_openai(client, tracing_extra={"client": tracing_client})
        except Exception as error:
            logger.warning("Model tracing unavailable: %s", type(error).__name__)
        _client = client
    return _client


def openai_llm(
    messages: list[dict[str, str]],
    response_model: type[BaseModel] | None = None,
) -> str:
    """Call gpt-6-luna, with strict structured output when a response model is given.

    Returns the model's raw text. We do not use client.chat.completions.parse(),
    because it validates inside the SDK and would raise on a bad output. We want the
    raw text, so parse_request can validate it with the category list and fall back
    to the safe default.
    """
    client = _get_client()
    if response_model is None:
        completion = client.chat.completions.create(model=MODEL, messages=messages)
    else:
        # Builds {"type": "json_schema", "json_schema": {..., "strict": True}}
        # from the Pydantic model.
        response_format = type_to_response_format_param(response_model)
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format=response_format,
        )
    # content is None when the model refuses. Empty text then fails validation
    # in parse_request, which returns the safe default.
    return completion.choices[0].message.content or ""
