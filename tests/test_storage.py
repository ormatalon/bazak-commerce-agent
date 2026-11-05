"""Saving and resuming chats, with a temporary database and a fake model. No network.

The data layer is Chainlit's own, so these tests save steps the way Chainlit would
(the same step dicts app/main.py's messages produce) and read them back through our subclass.
"""

import asyncio
import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest
from chainlit.context import init_http_context
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.user import User

import app.pipeline as pipeline
import app.storage as storage
from app.pipeline import (
    card_elements,
    metadata_of,
    more_metadata,
    rebuild_state,
    run_turn,
    show_more,
    turn_metadata,
)
from app.schemas import ConversationState, ParsedRequest, Product, SearchSpec
from app.storage import ChatDataLayer, check_login, load_login_settings, prepare_database

FIXTURE = Path(__file__).parent / "fixtures" / "catalog_sample.json"
CATALOG = [Product.model_validate(raw) for raw in json.loads(FIXTURE.read_text(encoding="utf-8"))]
CATEGORIES = sorted({p.category for p in CATALOG})


# --- helpers ----------------------------------------------------------------------------


def run(coro):
    return asyncio.run(coro)


def fake_llm_returning(parsed: ParsedRequest):
    def llm(messages, response_model=None):
        llm.calls.append(messages)
        return parsed.model_dump_json()

    llm.calls = []
    return llm


@pytest.fixture(autouse=True)
def fake_reply(monkeypatch):
    """The reply writer is another module's job: a fixed reply keeps these tests offline."""
    monkeypatch.setattr(pipeline, "write_reply", lambda message, parsed, outcomes, llm: f"reply to {message}")


def search_parse(*searches: SearchSpec, mode="new") -> ParsedRequest:
    return ParsedRequest(intent="product_search", mode=mode, searches=list(searches))


class Chat:
    """Plays what app/main.py does for one chat: run turns and save each message as a step."""

    def __init__(self, layer: ChatDataLayer, thread_id: str = "thread-1") -> None:
        self.layer = layer
        self.thread_id = thread_id
        self.state = ConversationState()
        self.number = 0
        self.user_id = ""

    async def start(self) -> None:
        init_http_context()
        user = await self.layer.create_user(User(identifier="local"))
        self.user_id = user.id
        await self.layer.update_thread(self.thread_id, name="chat", user_id=user.id)

    async def save(self, type_: str, output: str, metadata: dict | None = None) -> str:
        self.number += 1
        step_id = f"{self.thread_id}-step-{self.number}"
        await self.layer.create_step(
            {
                "id": step_id,
                "threadId": self.thread_id,
                "type": type_,
                "name": "User" if type_ == "user_message" else "Assistant",
                "output": output,
                "createdAt": f"2026-11-05T10:00:{self.number:02d}.000000Z",
                "streaming": False,
                "metadata": metadata or {},
                "tags": None,
            }
        )
        return step_id

    async def say(self, message: str, parsed: ParsedRequest) -> None:
        """A typed message: save it, run the turn, save the reply with its metadata."""
        await self.save("user_message", message)
        result = run_turn(message, self.state, CATALOG, CATEGORIES, fake_llm_returning(parsed))
        self.state = result.state
        await self.save("assistant_message", result.reply, turn_metadata(result))

    async def click_show_more(self) -> None:
        """The Show more button: cards with an empty message and no history."""
        outcomes, new_state = show_more(self.state, CATALOG)
        self.state = new_state
        await self.save("assistant_message", "", more_metadata(outcomes, new_state))


def same_cards(a: list[Product], b: list[Product]) -> bool:
    """Saved cards hold only the card fields, so compare those."""
    fields = pipeline.CARD_FIELDS
    return [p.model_dump(include=fields) for p in a] == [p.model_dump(include=fields) for p in b]


def assert_same_state(rebuilt: ConversationState, original: ConversationState) -> None:
    assert rebuilt.history == original.history
    assert rebuilt.searches == original.searches
    assert same_cards(rebuilt.shown, original.shown)


@pytest.fixture
def db_path(tmp_path) -> Path:
    path = tmp_path / "chat.db"
    prepare_database(path)
    return path


# --- save and reload --------------------------------------------------------------------


def test_a_saved_chat_reloads_with_its_cards_and_parsed_metadata(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("laptops", search_parse(SearchSpec(category="laptops")))

        # Chainlit's own read hands the metadata back as a JSON string (the trap in PLAN.md).
        raw = await SQLAlchemyDataLayer.get_thread(layer, "thread-1")
        assert isinstance(raw["steps"][1]["metadata"], str)
        assert raw["elements"] == []  # no storage provider: Chainlit keeps no elements

        thread = await layer.get_thread("thread-1")
        assert [s["type"] for s in thread["steps"]] == ["user_message", "assistant_message"]
        assert isinstance(thread["steps"][1]["metadata"], dict)
        assert thread["steps"][1]["output"] == "reply to laptops"

        # The cards come back as elements under the assistant message, with props as a dict.
        [element] = thread["elements"]
        assert element["name"] == "ProductCards" and element["type"] == "custom"
        assert element["forId"] == thread["steps"][1]["id"]
        assert [p["title"] for p in element["props"]["products"]] == [p.title for p in chat.state.shown]
        assert set(element["props"]["products"][0]) == pipeline.CARD_FIELDS
        await layer.engine.dispose()

    run(go())


def test_the_empty_text_show_more_message_and_its_cards_survive(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("laptops", search_parse(SearchSpec(category="laptops")))
        await chat.click_show_more()

        thread = await layer.get_thread("thread-1")
        more = thread["steps"][-1]
        assert more["output"] == ""
        assert more["metadata"]["in_history"] is False
        assert len(thread["elements"]) == 2
        assert thread["elements"][1]["forId"] == more["id"]
        assert len(thread["elements"][1]["props"]["products"]) == 2  # the other 2 laptops
        await layer.engine.dispose()

    run(go())


def test_only_what_was_shown_is_saved_not_everything_that_matched(db_path):
    result = run_turn(
        "phones",
        ConversationState(),
        CATALOG,
        CATEGORIES,
        fake_llm_returning(search_parse(SearchSpec(category="smartphones"))),
    )
    assert len(result.outcomes[0].products) == 16
    metadata = turn_metadata(result)
    saved_ids = [card["id"] for group in metadata["cards"] for card in group]
    assert saved_ids == [p.id for p in result.outcomes[0].shown]  # 3 cards, none of the other 13
    assert set(metadata) == {"app", "in_history", "cards", "searches", "replace_shown"}


# --- rebuilding the state ---------------------------------------------------------------


def test_rebuild_matches_the_live_state_including_show_more_cards(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("phones", search_parse(SearchSpec(category="smartphones")))
        await chat.click_show_more()
        await chat.click_show_more()
        await chat.say("thanks", ParsedRequest(intent="small_talk"))
        await chat.say("show more", ParsedRequest(intent="product_search", mode="show_more"))

        thread = await layer.get_thread("thread-1")
        rebuilt = rebuild_state(thread["steps"])
        assert_same_state(rebuilt, chat.state)
        assert len(rebuilt.shown) == 12  # 3 + 3 + 3 + 3, all kept
        # Button clicks add cards but no history: two typed turns... three, with "show more".
        assert [t.text for t in rebuilt.history if t.role == "user"] == ["phones", "thanks", "show more"]
        await layer.engine.dispose()

    run(go())


def test_a_new_search_replaces_the_shown_cards_and_a_refine_keeps_its_filters(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("phones", search_parse(SearchSpec(category="smartphones")))
        await chat.click_show_more()
        await chat.say("laptops under 1500", search_parse(SearchSpec(category="laptops", price_max=1500)))
        await chat.say("cheaper", search_parse(SearchSpec(price_max=1200), mode="refine"))

        rebuilt = rebuild_state((await layer.get_thread("thread-1"))["steps"])
        assert_same_state(rebuilt, chat.state)
        assert rebuilt.searches == [SearchSpec(category="laptops", price_max=1200)]
        assert {p.category for p in rebuilt.shown} == {"laptops"}
        await layer.engine.dispose()

    run(go())


def test_follow_up_refine_after_a_rebuild_keeps_the_category(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("phones", search_parse(SearchSpec(category="smartphones")))
        rebuilt = rebuild_state((await layer.get_thread("thread-1"))["steps"])
        await layer.engine.dispose()
        return rebuilt, chat.state

    rebuilt, live = run(go())
    llm = fake_llm_returning(search_parse(SearchSpec(price_max=250), mode="refine"))
    result = run_turn("cheaper ones", rebuilt, CATALOG, CATEGORIES, llm)

    assert result.state.searches == [SearchSpec(category="smartphones", price_max=250)]
    assert result.outcomes[0].shown and all(p.price <= 250 for p in result.outcomes[0].shown)
    # The parser was given the rebuilt context: previous search, shown prices and history.
    prompt = llm.calls[0][-1]["content"]
    assert "smartphones" in prompt
    assert f"{live.shown[0].title} ($" in prompt
    assert "phones" in prompt


def test_typed_show_more_after_a_resume_shows_new_cards_only(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("phones", search_parse(SearchSpec(category="smartphones")))
        await chat.click_show_more()
        rebuilt = rebuild_state((await layer.get_thread("thread-1"))["steps"])
        await layer.engine.dispose()
        return rebuilt

    rebuilt = run(go())
    seen = {p.id for p in rebuilt.shown}
    assert len(seen) == 6
    llm = fake_llm_returning(ParsedRequest(intent="product_search", mode="show_more"))
    result = run_turn("show more", rebuilt, CATALOG, CATEGORIES, llm)
    new = {p.id for p in result.outcomes[0].shown}
    assert len(new) == 3 and not new & seen
    assert result.state.searches == rebuilt.searches


def test_rebuild_skips_errors_notices_and_a_failed_turn():
    steps = [
        {"type": "user_message", "output": "phones"},
        {"type": "assistant_message", "output": "reply", "metadata": json.dumps(
            {"app": 1, "in_history": True, "cards": [], "searches": [{"category": "smartphones"}], "replace_shown": True})},
        # A notice has no metadata: not history.
        {"type": "assistant_message", "output": "The file with your past chats was damaged", "metadata": "{}"},
        # A turn that failed: the user message was saved, but no reply followed.
        {"type": "user_message", "output": "this one failed"},
        {"type": "user_message", "output": "hi"},
        {"type": "assistant_message", "output": "hello", "metadata": {"app": 1, "in_history": True, "cards": []}},
        # A step with unreadable metadata is skipped, not fatal.
        {"type": "user_message", "output": "x"},
        {"type": "assistant_message", "output": "y", "metadata": "{not json"},
        {"type": "assistant_message", "output": "z", "metadata": {"app": 1, "cards": [[{"id": "bad"}]]}},
    ]
    state = rebuild_state(steps)
    assert [t.text for t in state.history] == ["phones", "reply", "hi", "hello"]
    assert state.searches == [SearchSpec(category="smartphones")]


def test_a_button_message_and_an_untagged_message_never_join_the_history():
    steps = [
        {"type": "user_message", "output": "a question whose reply failed"},
        # A "Show more" click: cards, but not part of the conversation.
        {"type": "assistant_message", "output": "", "metadata": {"app": 1, "in_history": False, "cards": []}},
        {"type": "user_message", "output": "another question"},
        # Not written by this app (no "app" marker), so it is ignored even if it claims history.
        {"type": "assistant_message", "output": "stray", "metadata": {"in_history": True, "cards": []}},
    ]
    assert rebuild_state(steps).history == []


def test_rebuild_of_an_empty_chat_is_an_empty_state():
    assert rebuild_state([]) == ConversationState()


def test_metadata_of_accepts_a_string_a_dict_or_garbage():
    assert metadata_of({"metadata": '{"a": 1}'}) == {"a": 1}
    assert metadata_of({"metadata": {"a": 1}}) == {"a": 1}
    assert metadata_of({"metadata": "{broken"}) == {}
    assert metadata_of({}) == {}


def test_card_elements_have_fixed_ids():
    steps = [{"id": "s9", "type": "assistant_message", "metadata": {"cards": [[{"id": 1}], [{"id": 2}]]}}]
    ids = [e["id"] for e in card_elements(steps, "t")]
    assert ids == ["s9-cards-0", "s9-cards-1"]


# --- the database file ------------------------------------------------------------------


def test_a_missing_database_is_created(tmp_path):
    path = tmp_path / "chat.db"
    assert prepare_database(path) is None
    connection = sqlite3.connect(path)
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    connection.close()
    assert {"users", "threads", "steps", "elements", "feedbacks"} <= tables


def test_a_healthy_database_is_left_alone(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("INSERT INTO users (id, identifier, metadata) VALUES ('1', 'local', '{}')")
    connection.commit()
    connection.close()

    assert prepare_database(db_path) is None
    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
    connection.close()


def test_a_corrupted_database_is_backed_up_and_replaced(tmp_path):
    path = tmp_path / "chat.db"
    path.write_bytes(b"this is not a sqlite file" * 100)

    notice = prepare_database(path)

    assert notice and "damaged" in notice and "chat.db.bak" in notice
    assert (tmp_path / "chat.db.bak").read_bytes() == b"this is not a sqlite file" * 100
    assert prepare_database(path) is None  # the new file is healthy
    # And it works.
    async def go():
        layer = ChatDataLayer(path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("hi", ParsedRequest(intent="small_talk"))
        assert len((await layer.get_thread("thread-1"))["steps"]) == 2
        await layer.engine.dispose()

    run(go())


def test_a_locked_database_is_not_mistaken_for_a_damaged_one(db_path):
    holder = sqlite3.connect(db_path, timeout=0.1)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            prepare_database(db_path)
    finally:
        holder.rollback()
        holder.close()
    assert db_path.exists() and not (db_path.parent / "chat.db.bak").exists()


def test_deleting_the_file_while_the_app_runs_is_possible_and_the_next_write_recreates_it(db_path):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("hi", ParsedRequest(intent="small_talk"))

        os.remove(db_path)  # on Windows this fails if a connection is still open
        assert not db_path.exists()

        # The first write finds no tables, recreates them and tries again, so it is not lost.
        saved = await layer.execute_sql(
            'INSERT INTO threads ("id", "name") VALUES (:id, :name)', {"id": "t-new", "name": "first write"}
        )
        assert saved == 1
        assert await layer.execute_sql('SELECT "name" FROM threads WHERE "id" = \'t-new\'', {}) == [
            {"name": "first write"}
        ]

        await chat.save("user_message", "after the delete")
        thread = await layer.get_thread("thread-1")
        assert [s["output"] for s in thread["steps"]] == ["after the delete"]
        assert not layer._failure_reported  # the user was not bothered: it recovered
        await layer.engine.dispose()

    run(go())


# --- failed writes ----------------------------------------------------------------------


class FakeMessage:
    sent: list["FakeMessage"] = []

    def __init__(self, content: str) -> None:
        self.content = content
        self.persisted = False

    async def send(self) -> None:
        FakeMessage.sent.append(self)


@pytest.fixture
def sent_messages(monkeypatch) -> list[FakeMessage]:
    FakeMessage.sent = []
    monkeypatch.setattr(storage.cl, "Message", FakeMessage)
    return FakeMessage.sent


def test_a_failed_write_shows_one_error_and_the_chat_keeps_working(db_path, sent_messages, monkeypatch):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()

        # Every statement fails, as on a full disk. Chainlit's base class returns None for that.
        async def failing(self, query, parameters):
            return None

        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", failing)
        await chat.say("phones", search_parse(SearchSpec(category="smartphones")))  # must not raise
        await chat.say("laptops", search_parse(SearchSpec(category="laptops")))

        assert len(sent_messages) == 1  # one message per outage, not one per statement
        assert sent_messages[0].content == storage.SAVE_FAILED_TEXT
        assert sent_messages[0].persisted is True  # the notice is not itself saved
        assert "disk" not in sent_messages[0].content and "Error" not in sent_messages[0].content
        # The live chat is unaffected.
        assert chat.state.searches == [SearchSpec(category="laptops")]
        await layer.engine.dispose()

    run(go())


def test_the_error_is_shown_again_after_saving_worked_in_between(db_path, sent_messages, monkeypatch):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        real = SQLAlchemyDataLayer.execute_sql

        async def failing(self, query, parameters):
            return None

        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", failing)
        await chat.save("user_message", "one")
        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", real)
        await chat.save("user_message", "two")
        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", failing)
        await chat.save("user_message", "three")
        assert len(sent_messages) == 2
        await layer.engine.dispose()

    run(go())


def test_a_real_write_failure_on_a_read_only_file_is_reported(db_path, sent_messages):
    async def go():
        layer = ChatDataLayer(db_path)
        chat = Chat(layer)
        await chat.start()
        await chat.say("hi", ParsedRequest(intent="small_talk"))
        assert sent_messages == []

        os.chmod(db_path, stat.S_IREAD)  # on Windows this sets the read-only attribute
        try:
            await chat.save("user_message", "cannot be written")
            assert len(sent_messages) == 1
            # Reading still works, so the old chat is still there.
            assert len((await layer.get_thread("thread-1"))["steps"]) == 2
        finally:
            os.chmod(db_path, stat.S_IWRITE | stat.S_IREAD)
            await layer.engine.dispose()

    run(go())


def test_a_failed_read_is_logged_not_shown_to_the_user(db_path, sent_messages, monkeypatch):
    async def go():
        layer = ChatDataLayer(db_path)

        async def failing(self, query, parameters):
            return None

        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", failing)
        assert await layer.execute_sql("SELECT 1", {}) is None
        assert sent_messages == []
        await layer.engine.dispose()

    run(go())


# --- login ------------------------------------------------------------------------------

GOOD = {"APP_USERNAME": "local", "APP_PASSWORD": "pässword", "CHAINLIT_AUTH_SECRET": "s3cret-value"}


def test_login_settings_load_and_the_secret_is_not_kept():
    settings = load_login_settings(GOOD)
    assert (settings.username, settings.password) == ("local", "pässword")
    assert "s3cret-value" not in repr(settings)


def test_a_missing_login_value_is_named_and_no_value_is_printed():
    for name in GOOD:
        env = {k: v for k, v in GOOD.items() if k != name}
        with pytest.raises(storage.LoginConfigError) as error:
            load_login_settings(env)
        assert name in str(error.value)
        assert not any(value in str(error.value) for value in env.values())


def test_an_empty_login_value_counts_as_missing():
    with pytest.raises(storage.LoginConfigError, match="APP_PASSWORD"):
        load_login_settings({**GOOD, "APP_PASSWORD": "  "})


def test_check_login_needs_both_to_match():
    settings = load_login_settings(GOOD)
    assert check_login(settings, "local", "pässword")
    assert not check_login(settings, "local", "wrong")
    assert not check_login(settings, "other", "pässword")
    assert not check_login(settings, "", "")
    assert not check_login(settings, "local", "pässwor")
