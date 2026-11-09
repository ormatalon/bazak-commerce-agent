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


def test_actual_sdk_export_boundary_is_sanitized(monkeypatch):
    from langsmith import Client
    monkeypatch.setenv('TEST_API_KEY','private-export-value')
    captured=[]
    monkeypatch.setattr(Client,'_create_run',lambda self, payload, **kwargs: captured.append(payload))
    client=Client(api_url='http://localhost:1984',api_key='local-test',auto_batch_tracing=False,
                  hide_inputs=redact,hide_outputs=redact,hide_metadata=redact)
    client.create_run('redaction-check',{'messages':[{'content':'private-export-value'}]},'chain',
                      outputs={'reply':'private-export-value'},extra={'metadata':{'password':'private-export-value'}})
    assert len(captured)==1
    assert 'private-export-value' not in json.dumps(captured,default=str)


def test_trace_updates_headers_and_shutdown_cannot_break_the_body(monkeypatch):
    from types import SimpleNamespace
    import langsmith
    import app.observability as observations
    def broken(*args, **kwargs):
        raise RuntimeError('export unavailable')
    raw = SimpleNamespace(id='trace',end=broken,add_metadata=broken,to_headers=broken)
    class Manager:
        def __enter__(self):
            return raw
        def __exit__(self,*args):
            broken()
    monkeypatch.setenv('LANGSMITH_TRACING','true')
    monkeypatch.setattr(observations,'get_client',lambda: object())
    monkeypatch.setattr(langsmith,'trace',lambda *args,**kwargs: Manager())
    with span('test') as run:
        run.end(outputs={'ok':True})
        run.add_metadata({'key':'value'})
        assert run.to_headers() == {}
    with pytest.raises(ValueError,match='original failure'):
        with span('test'):
            raise ValueError('original failure')


def test_optional_model_tracing_failure_keeps_the_openai_client(monkeypatch):
    import app.llm as llm
    import app.observability as observations
    client = object()
    monkeypatch.setattr(llm,'_client',None)
    monkeypatch.setattr(llm,'OpenAI',lambda **kwargs: client)
    monkeypatch.setenv('LANGSMITH_TRACING','true')
    def broken():
        raise RuntimeError('tracing unavailable')
    monkeypatch.setattr(observations,'get_client',broken)
    assert llm._get_client() is client
    assert llm._get_client() is client
