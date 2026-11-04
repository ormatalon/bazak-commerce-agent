"""Chainlit entry point. Run with: chainlit run app/main.py"""

import logging
import sys
from pathlib import Path

# chainlit run only puts app/ on the import path, so `from app...` needs the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chainlit as cl  # noqa: E402

from app.catalog import CatalogError, load_catalog, load_categories  # noqa: E402
from app.llm import openai_llm  # noqa: E402
from app.pipeline import card_props, has_more, run_turn, show_more  # noqa: E402
from app.schemas import ConversationState, SearchOutcome  # noqa: E402

logger = logging.getLogger("app.main")

# Fixed texts. The error text never includes the exception, which can hold request details.
ERROR_TEXT = "Sorry, something went wrong while handling your message. Please try again."
NO_MORE_TEXT = "There are no more products to show."

# Load the catalog once, when the app starts. Without it the app cannot work, so stop
# with the loader's plain-words message instead of a traceback.
try:
    CATALOG = load_catalog()
    CATEGORIES = load_categories()
except CatalogError as error:
    raise SystemExit(str(error)) from None


@cl.on_chat_start
async def on_chat_start() -> None:
    """Every chat starts with an empty conversation. It lives on the server, in the session."""
    cl.user_session.set("state", ConversationState())


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
        await cl.Message(content=ERROR_TEXT).send()
        return

    cl.user_session.set("state", result.state)
    msg = cl.Message(content=result.reply)
    await msg.send()
    await send_cards(msg, result.outcomes)


@cl.action_callback("show_more")
async def on_show_more(action: cl.Action) -> None:
    """Add the next cards with no model call and no reply text."""
    await remove_old_buttons(action)  # one click, one use: a second click finds no button
    state = cl.user_session.get("state")
    if state is None:  # e.g. a button left over from before the server restarted
        await cl.Message(content=NO_MORE_TEXT).send()
        return

    # show_more is a quick filter over 194 products, so it runs right here with no await
    # between reading the state and saving the new one. Two quick clicks therefore can't
    # both read the same state and show the same cards twice.
    outcomes, new_state = show_more(state, CATALOG)
    if not any(o.shown for o in outcomes):
        await cl.Message(content=NO_MORE_TEXT).send()
        return
    cl.user_session.set("state", new_state)

    # The message has no text: the cards are the answer, so no language is needed.
    msg = cl.Message(content="")
    await msg.send()
    await send_cards(msg, outcomes)
