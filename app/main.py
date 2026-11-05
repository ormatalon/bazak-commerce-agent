"""Chainlit entry point. Run with: chainlit run app/main.py"""

import logging
import os
import sqlite3
import sys
from pathlib import Path

# chainlit run only puts app/ on the import path, so `from app...` needs the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

# Read .env before anything needs a value from it (Chainlit reads CHAINLIT_AUTH_SECRET
# when someone logs in). An explicit path: the default would search parent folders.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import chainlit as cl  # noqa: E402
from chainlit.types import ThreadDict  # noqa: E402

import app.storage as storage  # noqa: E402
from app.catalog import CatalogError, load_catalog, load_categories  # noqa: E402
from app.llm import openai_llm  # noqa: E402
from app.pipeline import (  # noqa: E402
    card_props,
    has_more,
    more_metadata,
    rebuild_state,
    run_turn,
    show_more,
    turn_metadata,
)
from app.schemas import ConversationState, SearchOutcome  # noqa: E402

logger = logging.getLogger("app.main")

# Fixed texts. The error text never includes the exception, which can hold request details.
ERROR_TEXT = "Sorry, something went wrong while handling your message. Please try again."
NO_MORE_TEXT = "There are no more products to show."

# --- Startup: stop with a plain message if something the app needs is missing -------------
# Nothing below prints a login value, only the names of missing ones.

try:
    LOGIN = storage.load_login_settings(os.environ)
except storage.LoginConfigError as error:
    raise SystemExit(str(error)) from None

# Load the catalog once, when the app starts. Without it the app cannot work.
try:
    CATALOG = load_catalog()
    CATEGORIES = load_categories()
except CatalogError as error:
    raise SystemExit(str(error)) from None

# Create the chat database, or start a new one if the old file is damaged.
try:
    DB_NOTICE = storage.prepare_database(storage.DB_PATH)
except (OSError, sqlite3.Error) as error:
    raise SystemExit(
        f"Could not open the chat database at {storage.DB_PATH} ({type(error).__name__}). "
        "Close anything else using it and check the folder is writable."
    ) from None
if DB_NOTICE:
    print(DB_NOTICE, file=sys.stderr)
_notice_shown = False  # the notice goes into the first new chat only


@cl.password_auth_callback
def authenticate(username: str, password: str) -> cl.User | None:
    """The one fixed local user. Chainlit needs a login to show past chats."""
    if storage.check_login(LOGIN, username, password):
        return cl.User(identifier=LOGIN.username)
    return None


@cl.data_layer
def data_layer() -> storage.ChatDataLayer:
    """Save chats in SQLite. Chainlit calls this once, the first time it needs the database."""
    return storage.ChatDataLayer(storage.DB_PATH)


async def send_notice(text: str) -> None:
    """A message that is shown but not saved: errors and notices are not part of a chat."""
    message = cl.Message(content=text)
    message.persisted = True  # tells Chainlit it is already saved, so it skips the write
    await message.send()


@cl.on_chat_start
async def on_chat_start() -> None:
    """Every new chat starts with an empty conversation. It lives on the server, in the session."""
    global _notice_shown
    cl.user_session.set("state", ConversationState())
    if DB_NOTICE and not _notice_shown:
        _notice_shown = True
        await send_notice(DB_NOTICE)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Rebuild the conversation from the saved messages. The cards are redrawn by the data layer.

    There is no "Show more" button after a resume. Typing "show more" works, because the
    searches and the shown products are rebuilt.
    """
    cl.user_session.set("state", rebuild_state(thread["steps"]))  # type: ignore[arg-type]


async def remove_button(action: cl.Action) -> None:
    """Take a "Show more" button off the screen. Best effort: a button that is already gone is fine."""
    try:
        await action.remove()
    except Exception as error:
        logger.warning("Could not remove the Show more button: %s", type(error).__name__)


async def remove_old_buttons(clicked: cl.Action | None = None) -> None:
    """Remove the button remembered in the session, and the clicked one if it is another button."""
    stored = cl.user_session.get("show_more_action")
    cl.user_session.set("show_more_action", None)
    if stored is not None:
        await remove_button(stored)
    if clicked is not None and (stored is None or clicked.id != stored.id):
        await remove_button(clicked)  # a stale button from an earlier turn


async def send_cards(msg: cl.Message, outcomes: list[SearchOutcome]) -> None:
    """One card element per outcome that has cards, then a "Show more" button if products remain.

    The message is sent first, because Message.send sends its elements concurrently,
    before the message exists in the UI. The button goes last, so it sits under the cards.
    """
    for outcome in outcomes:
        if outcome.shown:
            cards = cl.CustomElement(name="ProductCards", props=card_props(outcome))
            await cards.send(for_id=msg.id)

    if any(has_more(o) for o in outcomes):
        # The payload is empty on purpose: the server's session state decides what comes next.
        button = cl.Action(name="show_more", payload={}, label="Show more")
        await button.send(for_id=msg.id)
        cl.user_session.set("show_more_action", button)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Run one turn off the event loop, then send the reply and the cards."""
    await remove_old_buttons()  # an older button must not act on this turn's searches
    state = cl.user_session.get("state") or ConversationState()
    try:
        # run_turn blocks on the model, so run it in a thread or the whole app freezes.
        result = await cl.make_async(run_turn)(message.content, state, CATALOG, CATEGORIES, openai_llm)
    except Exception as error:
        # Keep the old state and the app running. Log only the type, never the text.
        logger.warning("Turn failed: %s", type(error).__name__)
        await send_notice(ERROR_TEXT)
        return

    cl.user_session.set("state", result.state)
    # The metadata is saved with the message: it is what a resumed chat is rebuilt from.
    msg = cl.Message(content=result.reply, metadata=turn_metadata(result))
    await msg.send()
    await send_cards(msg, result.outcomes)


@cl.action_callback("show_more")
async def on_show_more(action: cl.Action) -> None:
    """Add the next cards with no model call and no reply text."""
    await remove_old_buttons(action)  # one click, one use: a second click finds no button
    state = cl.user_session.get("state")
    if state is None:  # e.g. a button left over from before the server restarted
        await send_notice(NO_MORE_TEXT)
        return

    # show_more is a quick filter over 194 products, so it runs right here with no await
    # between reading the state and saving the new one. Two quick clicks therefore can't
    # both read the same state and show the same cards twice.
    outcomes, new_state = show_more(state, CATALOG)
    if not any(o.shown for o in outcomes):
        await send_notice(NO_MORE_TEXT)
        return
    cl.user_session.set("state", new_state)

    # The message has no text: the cards are the answer, so no language is needed.
    msg = cl.Message(content="", metadata=more_metadata(outcomes, new_state))
    await msg.send()
    await send_cards(msg, outcomes)
