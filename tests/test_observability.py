import json

import pytest

from app.monitoring import record_turn
from app.observability import redact, span


def test_redaction_covers_nested_llm_payload(monkeypatch):
    monkeypatch.setenv('TEST_API_KEY','private-example-value')
    payload={'messages':[{'content':'private-example-value email person@example.com'}], 'authorization':'Bearer credential'}
    exported=redact(payload)
    assert 'private-example-value' not in json.dumps(exported)
    assert 'person@example.com' not in json.dumps(exported)
    assert exported['authorization']=='[REDACTED]'


def test_failed_trace_initialization_does_not_repeat_operation(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING','true')
    import app.observability as observations
    monkeypatch.setattr(observations,'get_client',lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    calls=[]
    with span('test'):
        calls.append('one model operation')
    assert len(calls)==1


def test_exception_is_not_swallowed_when_tracing_disabled(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    with pytest.raises(ValueError):
        with span('test'):
            raise ValueError('failed operation')


def test_failure_journal_excludes_raw_message_and_credentials(tmp_path):
    path=tmp_path/'turns.jsonl'
    record_turn(None,'evaluation',10.0,error='TimeoutError',path=path)
    event=json.loads(path.read_text())
    assert event['error']=='TimeoutError'
    assert 'message' not in event and 'api_key' not in event
