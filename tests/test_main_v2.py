"""Exercise real UI callbacks with fake startup dependencies and no server/model."""

import asyncio
import copy
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def ui(monkeypatch):
    from chainlit.config import config
    import app.catalog
    import app.embeddings
    import app.index
    import app.storage
    monkeypatch.setattr(config,'code',copy.deepcopy(config.code))
    monkeypatch.setattr(app.catalog,'load_catalog_data',lambda: ([],[]))
    monkeypatch.setattr(app.embeddings,'LocalEmbedder',lambda *args: object())
    monkeypatch.setattr(app.index,'ProductIndex',lambda *args: object())
    monkeypatch.setattr(app.storage,'load_login_settings',lambda *args: app.storage.LoginSettings('local','private'))
    monkeypatch.setattr(app.storage,'prepare_database',lambda *args: None)
    monkeypatch.delitem(sys.modules,'app.main',raising=False)
    module=importlib.import_module('app.main')
    values={}
    monkeypatch.setattr(module.cl,'user_session',SimpleNamespace(get=values.get,set=values.__setitem__))
    monkeypatch.setattr(module.cl,'context',SimpleNamespace(session=SimpleNamespace(thread_id='thread')))
    return module, values


def test_overlapping_messages_are_queued_not_dropped(ui,monkeypatch):
    module, values=ui
    events=[]
    async def handle(content):
        events.append('start:'+content)
        await asyncio.sleep(0)
        events.append('end:'+content)
    monkeypatch.setattr(module,'_handle_message',handle)
    async def scenario():
        await asyncio.gather(module.on_message(SimpleNamespace(content='first')),
                             module.on_message(SimpleNamespace(content='second')))
    asyncio.run(scenario())
    assert events == ['start:first','end:first','start:second','end:second']


def test_stale_show_more_does_not_consume_current_button_or_search(ui,monkeypatch):
    module, values=ui
    current=SimpleNamespace(id='current',remove=AsyncMock())
    stale=SimpleNamespace(id='stale',remove=AsyncMock())
    values['show_more_action']=current
    handle=AsyncMock()
    monkeypatch.setattr(module,'_handle_message',handle)
    asyncio.run(module.on_show_more(stale))
    handle.assert_not_awaited()
    stale.remove.assert_awaited_once()
    current.remove.assert_not_awaited()
    assert values['show_more_action'] is current


def test_model_result_is_not_delivered_to_a_different_resumed_chat(ui,monkeypatch):
    from app.schemas import ConversationState, ParsedRequest, TurnResult
    module, values=ui
    old_state=ConversationState()
    values['state']=old_state
    async def switched_chat(*args,**kwargs):
        module.cl.context.session.thread_id='another-thread'
        return TurnResult(parsed=ParsedRequest(intent='small_talk'),reply='old reply',state=ConversationState())
    monkeypatch.setattr(module.cl,'make_async',lambda function: switched_chat)
    def forbidden_message(*args,**kwargs):
        raise AssertionError('The old reply must not be sent into the new conversation')
    monkeypatch.setattr(module.cl,'Message',forbidden_message)
    asyncio.run(module._handle_message('hello'))
    assert values['state'] is old_state
