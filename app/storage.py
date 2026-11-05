"""Where chats are saved (SQLite, through Chainlit's own data layer) and the one fixed login.

Chainlit's SQLAlchemy data layer does the saving. It expects us to create its tables
(SCHEMA below) and it swallows every database error, so this file adds three things:
the tables and the startup checks, a small subclass that makes a failed write visible,
and the login settings. The pure rebuild of a resumed chat is in app/pipeline.py.
"""

import hmac
import logging
import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chainlit as cl
from chainlit.context import ChainlitContextException
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.session import WebsocketSession
from chainlit.types import ThreadDict
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.pipeline import card_elements, metadata_of

logger = logging.getLogger("app.storage")

# Found relative to this file, so it is the same wherever the app is started from.
DB_PATH = Path(__file__).resolve().parent.parent / "chat.db"

SAVE_FAILED_TEXT = (
    "Your last message could not be saved, so it may be missing from your past chats. "
    "You can keep chatting here."
)
FILE_MISSING_TEXT = (
    "The file with your past chats disappeared, so I started a new, empty one. "
    "This chat is being saved from now on, and you can keep chatting here."
)
# The sidebar needs a name for a chat whose first message was in the deleted file.
RESTORED_CHAT_NAME = "Restored chat"

# The tables Chainlit's data layer reads and writes. SQLite has no UUID or JSON type,
# so those columns are TEXT (Chainlit stores JSON as text). Column names are quoted
# because Chainlit quotes them too, and "end" is a reserved word.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT NOT NULL,
    "createdAt" TEXT
);
CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "metadata" TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "threadId" TEXT,
    "parentId" TEXT,
    "command" TEXT,
    "modes" TEXT,
    "streaming" INTEGER,
    "waitForAnswer" INTEGER,
    "isError" INTEGER,
    "metadata" TEXT,
    "tags" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" TEXT,
    "showInput" TEXT,
    "defaultOpen" INTEGER,
    "autoCollapse" INTEGER,
    "language" TEXT,
    "icon" TEXT
);
CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "type" TEXT,
    "chainlitKey" TEXT,
    "url" TEXT,
    "objectKey" TEXT,
    "name" TEXT,
    "display" TEXT,
    "size" TEXT,
    "language" TEXT,
    "page" INTEGER,
    "autoPlay" INTEGER,
    "playerConfig" TEXT,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT
);
CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT,
    "threadId" TEXT,
    "value" INTEGER,
    "comment" TEXT
);
"""


# --- The database file -------------------------------------------------------------------


def ensure_schema(path: Path) -> None:
    """Create the file and any missing table. Safe to run again: nothing is overwritten."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
    finally:
        connection.close()


def _check_file(path: Path) -> None:
    """Open the file and read all of it. Raises sqlite3.DatabaseError if it is damaged."""
    connection = sqlite3.connect(path)
    try:
        # quick_check reads every page. Garbage fails right here with "not a database".
        rows = connection.execute("PRAGMA quick_check").fetchall()
        if rows != [("ok",)]:
            raise sqlite3.DatabaseError("quick_check found a problem")
    finally:
        connection.close()


def prepare_database(path: Path = DB_PATH) -> str | None:
    """Make sure a healthy database with all tables exists. Run once at startup.

    - Missing file: created.
    - Damaged file: renamed to <name>.bak (an older .bak is replaced) and a fresh file
      is started. The returned text tells the user, because the old chats are gone from view.
    - Any other problem (file locked, folder not writable) is raised as is, because
      moving a healthy file away would be worse than stopping.
    Returns the notice for the user, or None when nothing needed fixing.
    """
    notice = None
    if path.exists():
        try:
            _check_file(path)
        except sqlite3.OperationalError:
            raise  # locked, unreadable, no permission: not proof of damage
        except sqlite3.DatabaseError:
            backup = path.with_name(path.name + ".bak")
            os.replace(path, backup)
            logger.warning("The chat database was damaged. Saved it as %s and started a new one.", backup.name)
            notice = (
                "The file with your past chats was damaged, so I started a new, empty one. "
                f"The old file was kept as {backup.name} next to the app."
            )
    ensure_schema(path)
    return notice


@dataclass(frozen=True)
class OpenChat:
    """The chat a write belongs to, and who owns it."""

    thread_id: str
    user_id: str
    user_identifier: str


def restore_owner(path: Path, chat: OpenChat) -> None:
    """Put back the user and the open chat after the file was deleted.

    Chainlit links a chat to its user only on the chat's first message, and looks up a user
    only at login. Without these rows the chat would be saved but never reach the sidebar.
    """
    now = datetime.now(UTC).isoformat()
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(
                'INSERT OR IGNORE INTO users ("id", "identifier", "metadata", "createdAt") VALUES (?, ?, ?, ?)',
                (chat.user_id, chat.user_identifier, "{}", now),
            )
            connection.execute(
                'INSERT OR IGNORE INTO threads ("id", "createdAt", "name", "userId", "userIdentifier") '
                "VALUES (?, ?, ?, ?, ?)",
                (chat.thread_id, now, RESTORED_CHAT_NAME, chat.user_id, chat.user_identifier),
            )
    finally:
        connection.close()


def _open_chat() -> OpenChat | None:
    """The chat this write belongs to, or None when it comes from outside a chat, such as a login."""
    try:
        session = cl.context.session
    except ChainlitContextException:
        return None
    user_id = getattr(session.user, "id", None)
    if not isinstance(session, WebsocketSession) or user_id is None:
        return None
    return OpenChat(session.thread_id, user_id, session.user.identifier)


# --- The data layer -----------------------------------------------------------------------


def _is_write(query: str) -> bool:
    return query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))


class ChatDataLayer(SQLAlchemyDataLayer):
    """Chainlit's SQLAlchemy data layer with four changes.

    1. No connection stays open between statements (NullPool). On Windows an open
       connection locks the file, so it could not be deleted or replaced while the app runs.
    2. A failed statement is retried once after recreating any missing table, and a failed
       WRITE tells the user in the chat. Chainlit runs its writes as background tasks and
       the base class swallows database errors, so without this a failure is silent.
    3. A file deleted while the app runs is noticed before SQLite can recreate it empty.
       The user and the open chat are put back, and the user is told once.
    4. A resumed thread gets its card elements back, rebuilt from the messages' metadata
       (Chainlit's own element storage needs a file provider, so create_element does nothing).
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        super().__init__(conninfo=f"sqlite+aiosqlite:///{db_path.as_posix()}")
        self.db_path = db_path
        self.engine = create_async_engine(self._conninfo, poolclass=NullPool)
        self.async_session = sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)  # type: ignore
        # True after a failed write was reported, so one outage gives one message.
        self._failure_reported = False
        # True from finding the file gone until a chat is open to say so in.
        self._missing_file_notice_pending = False

    async def execute_sql(self, query: str, parameters: dict) -> Any:
        """Run one statement. The base class returns None when it failed (and logged why)."""
        await self._recover_deleted_file()
        result = await super().execute_sql(query, parameters)
        if result is None:
            # The file may have been deleted or replaced while the app runs: make the
            # tables again and try once more.
            try:
                ensure_schema(self.db_path)
            except (sqlite3.Error, OSError) as error:
                logger.warning("Could not recreate the chat database: %s", type(error).__name__)
            else:
                result = await super().execute_sql(query, parameters)

        if _is_write(query):
            if result is None:
                await self._report_failed_write()
            else:
                self._failure_reported = False  # saving works again
        return result

    async def _recover_deleted_file(self) -> None:
        """If the file is gone, make it again, then tell the user once a chat is open.

        No await between the check and the rows being back, so of several writes running
        together only the first one does this, and none can save a chat before its owner.
        """
        chat = _open_chat()
        if not self.db_path.exists():
            logger.warning("The chat database file disappeared. Starting a new one.")
            self._missing_file_notice_pending = True
            try:
                ensure_schema(self.db_path)
                if chat is not None:
                    restore_owner(self.db_path, chat)
            except (sqlite3.Error, OSError) as error:
                logger.warning("Could not recreate the chat database: %s", type(error).__name__)
        if self._missing_file_notice_pending and chat is not None:
            self._missing_file_notice_pending = False
            await self._show_notice(FILE_MISSING_TEXT)

    async def _report_failed_write(self) -> None:
        """Show one short error in the chat. The chat itself keeps working."""
        logger.warning("A chat write failed, so this chat may not be saved.")
        if self._failure_reported:
            return
        self._failure_reported = True
        await self._show_notice(SAVE_FAILED_TEXT)

    async def _show_notice(self, text: str) -> None:
        """A message in the chat that is not saved itself, or a failure would just repeat."""
        try:
            message = cl.Message(content=text)
            message.persisted = True
            await message.send()
        except Exception as error:  # e.g. no chat open (a write during login)
            logger.warning("Could not show a storage notice: %s", type(error).__name__)

    async def create_element(self, element: Any) -> None:
        """Do nothing. Without a file storage provider Chainlit can't keep elements anyway
        (and logs a warning for each one). Our cards are rebuilt from message metadata."""
        return None

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        """The saved thread, with metadata as dicts and the product cards added back."""
        thread = await super().get_thread(thread_id)
        if thread is None:
            return None
        for step in thread["steps"]:
            step["metadata"] = metadata_of(step)  # SQLite returns it as a JSON string
        extra = card_elements(thread["steps"], thread_id)  # type: ignore[arg-type]
        thread["elements"] = list(thread.get("elements") or []) + extra  # type: ignore[assignment,list-item]
        return thread


# --- Login ---------------------------------------------------------------------------------

LOGIN_VARIABLES = ("APP_USERNAME", "APP_PASSWORD", "CHAINLIT_AUTH_SECRET")


class LoginConfigError(RuntimeError):
    """A login value is missing from the environment. The text names it, never its value."""


@dataclass(frozen=True)
class LoginSettings:
    username: str
    password: str


def load_login_settings(environ: Mapping[str, str]) -> LoginSettings:
    """Read the fixed login. Stops with the NAMES of whatever is missing or empty.

    CHAINLIT_AUTH_SECRET is checked here too, but not kept: Chainlit reads it itself to
    sign the login cookie.
    """
    missing = [name for name in LOGIN_VARIABLES if not environ.get(name, "").strip()]
    if missing:
        raise LoginConfigError(
            f"These values are missing in .env: {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in "
            "(create the secret with: chainlit create-secret)."
        )
    return LoginSettings(username=environ["APP_USERNAME"], password=environ["APP_PASSWORD"])


def check_login(settings: LoginSettings, username: str, password: str) -> bool:
    """True when both match. compare_digest takes the same time wherever they differ.

    Both comparisons always run, so the answer does not reveal which one was wrong.
    Bytes, because compare_digest on text only accepts ASCII.
    """
    username_ok = hmac.compare_digest(username.encode("utf-8"), settings.username.encode("utf-8"))
    password_ok = hmac.compare_digest(password.encode("utf-8"), settings.password.encode("utf-8"))
    return username_ok and password_ok
