"""Optional, sanitized LangSmith spans. Export failures never retry a model call."""

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any

from dotenv import dotenv_values

logger = logging.getLogger(__name__)
_client = None
_client_lock = Lock()


def tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "false").lower() == "true"


class SafeTrace:
    """Optional instrumentation must not turn a successful operation into a failure."""

    def __init__(self, run: Any):
        self._run = run

    @property
    def id(self):
        return self._run.id

    def end(self, **kwargs) -> None:
        try:
            self._run.end(**kwargs)
        except Exception as error:
            logger.warning("Trace completion failed: %s", type(error).__name__)

    def add_metadata(self, metadata: dict) -> None:
        try:
            self._run.add_metadata(redact(metadata))
        except Exception as error:
            logger.warning("Trace metadata failed: %s", type(error).__name__)

    def to_headers(self) -> dict[str, str]:
        try:
            return self._run.to_headers()
        except Exception as error:
            logger.warning("Trace context unavailable: %s", type(error).__name__)
            return {}


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
    with _client_lock:
        if _client is None:
            from langsmith import Client
            # The SDK already batches asynchronously; a second buffering layer is
            # unnecessary and complicates shutdown and failure handling.
            _client = Client(timeout_ms=1500, hide_inputs=redact, hide_outputs=redact, hide_metadata=redact)
    return _client


@contextmanager
def span(name: str, inputs: dict | None = None, metadata: dict | None = None, run_type: str = "chain"):
    """Use the public trace context with bounded client export and nested context."""
    try:
        client = get_client() if tracing_enabled() else None
    except Exception as error:
        logger.warning("Tracing unavailable: %s", type(error).__name__)
        client = None
    manager = None
    run = None
    if client is not None:
        try:
            from langsmith import trace
            manager = trace(name, run_type=run_type, inputs=redact(inputs or {}),
                            metadata=redact(metadata or {}), client=client)
            run = SafeTrace(manager.__enter__())
        except Exception as error:
            logger.warning("Trace startup failed: %s", type(error).__name__)
            manager = None
    try:
        yield run
    except BaseException as error:
        if run is not None:
            # Do not export exception text; provider errors can contain request data.
            run.end(error=type(error).__name__)
        raise
    finally:
        if manager is not None:
            try:
                manager.__exit__(None, None, None)
            except Exception as error:
                logger.warning("Trace export failed: %s", type(error).__name__)


def flush() -> bool:
    try:
        if _client is not None:
            _client.flush()
        return True
    except Exception as error:
        logger.warning("Trace flush failed: %s", type(error).__name__)
        return False
