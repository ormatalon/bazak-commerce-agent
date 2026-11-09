"""Optional, sanitized LangSmith spans. Export failures never retry a model call."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
from pathlib import Path
import re

from dotenv import dotenv_values

logger = logging.getLogger(__name__)
_client = None
_active_trace: ContextVar[str | None] = ContextVar("trace_id", default=None)


def redact(value):
    """Redact known secret values recursively before crossing the export boundary."""
    secrets = {v for k, v in os.environ.items() if any(s in k.upper() for s in ("KEY", "PASSWORD", "SECRET", "TOKEN")) and len(v) >= 5}
    secrets.update(v for k, v in dotenv_values(Path(__file__).resolve().parent.parent / ".env").items()
                   if v and any(s in k.upper() for s in ("KEY", "PASSWORD", "SECRET", "TOKEN")))

    def clean(item):
        if isinstance(item, dict):
            return {str(k): "[REDACTED]" if any(s in str(k).lower() for s in ("api_key", "password", "secret", "authorization", "access_token")) else clean(v)
                    for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v) for v in item]
        if isinstance(item, str):
            for secret in sorted(secrets, key=len, reverse=True):
                item = item.replace(secret, "[REDACTED]")
            item = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", item)
            return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", item)
        return item
    return clean(value)


def get_client():
    global _client
    if not os.getenv("LANGSMITH_API_KEY"):
        return None
    if _client is None:
        from langsmith import Client
        _client = Client(timeout_ms=1500, hide_inputs=redact, hide_outputs=redact,
                         hide_metadata=redact, run_ops_buffer_size=100,
                         run_ops_buffer_timeout_ms=500)
    return _client


@contextmanager
def span(name: str, inputs: dict | None = None, metadata: dict | None = None, run_type: str = "chain"):
    """Use the public trace context with bounded client export and nested context."""
    enabled = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    client = get_client() if enabled else None
    manager = None
    run = None
    if client is not None:
        try:
            from langsmith import trace
            manager = trace(name, run_type=run_type, inputs=redact(inputs or {}),
                            metadata=redact(metadata or {}), client=client)
            run = manager.__enter__()
        except Exception as error:
            logger.warning("Trace startup failed: %s", type(error).__name__)
            manager = None
    token = _active_trace.set(str(run.id) if run is not None else _active_trace.get())
    try:
        yield run
    except BaseException as error:
        if run is not None:
            # Do not export exception text; provider errors can contain request data.
            run.end(error=type(error).__name__)
        raise
    finally:
        _active_trace.reset(token)
        if manager is not None:
            try:
                manager.__exit__(None, None, None)
            except Exception as error:
                logger.warning("Trace export failed: %s", type(error).__name__)


def trace_id() -> str | None:
    return _active_trace.get()


def flush() -> None:
    if _client is not None:
        _client.flush()
