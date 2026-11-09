import sqlite3
import asyncio

from app.storage import LoginSettings, check_login, ensure_schema, prepare_database


def test_schema_roundtrip_and_corrupt_file_recovery(tmp_path):
    path = tmp_path / 'chats.db'
    ensure_schema(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='steps'").fetchone()
    connection.close()
    path.write_bytes(b'not a sqlite database')
    assert prepare_database(path)
    assert path.with_name('chats.db.bak').read_bytes() == b'not a sqlite database'


def test_login_compares_both_values():
    settings = LoginSettings(username='local', password='private')
    assert check_login(settings, 'local', 'private')
    assert not check_login(settings, 'local', 'wrong')
    assert not check_login(settings, 'wrong', 'private')


def test_corruption_recovery_preserves_an_existing_backup(tmp_path):
    path = tmp_path/'chats.db'
    path.write_bytes(b'new corruption')
    existing = path.with_name('chats.db.bak')
    existing.write_bytes(b'previous backup')
    assert prepare_database(path)
    assert existing.read_bytes() == b'previous backup'
    assert [p.read_bytes() for p in tmp_path.glob('chats.db.*.bak')] == [b'new corruption']


def test_sql_roundtrip_and_errors_do_not_log_parameter_values(tmp_path,caplog):
    from app.storage import ChatDataLayer
    path=tmp_path/'chats.db'
    ensure_schema(path)
    async def scenario():
        layer=ChatDataLayer(path)
        try:
            inserted=await layer.execute_sql('INSERT INTO users (id, identifier, metadata) VALUES (:id, :name, :metadata)',
                                              {'id':'one','name':'local','metadata':'{}'})
            assert inserted == 1
            assert await layer.execute_sql('SELECT identifier FROM users WHERE id=:id',{'id':'one'}) == [{'identifier':'local'}]
            assert await layer.execute_sql('INSERT INTO missing_table (value) VALUES (:value)',{'value':'review-private-secret'}) is None
        finally:
            await layer.engine.dispose()
    asyncio.run(scenario())
    assert 'review-private-secret' not in caplog.text


def test_failed_file_recovery_does_not_announce_success(tmp_path,monkeypatch):
    from unittest.mock import AsyncMock
    import app.storage as storage
    path=tmp_path/'missing.db'
    monkeypatch.setattr(storage,'_open_chat',lambda: storage.OpenChat('thread','user','local'))
    def denied(path):
        raise PermissionError('denied')
    monkeypatch.setattr(storage,'ensure_schema',denied)
    async def scenario():
        layer=storage.ChatDataLayer(path)
        notice=AsyncMock()
        layer._show_notice=notice
        try:
            await layer._recover_deleted_file()
            assert layer._missing_file_notice_pending
            notice.assert_not_awaited()
        finally:
            await layer.engine.dispose()
    asyncio.run(scenario())
