import sqlite3

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
