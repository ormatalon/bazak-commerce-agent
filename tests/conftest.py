"""Offline tests never export traces or make provider calls."""

import pytest


@pytest.fixture(autouse=True)
def disable_remote_tracing(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    monkeypatch.setattr('app.pipeline.record_turn',lambda *args, **kwargs: None)
