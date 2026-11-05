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
from pathlib import Path
from typing import Any

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
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


# --- The data layer -----------------------------------------------------------------------


def _is_write(query: str) -> bool:
    return query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))


class ChatDataLayer(SQLAlchemyDataLayer):
    """Chainlit's SQLAlchemy data layer with three changes.

    1. No connection stays open between statements (NullPool). On Windows an open
       connection locks the file, so it could not be deleted or replaced while the app runs.
    2. A failed statement is retried once after recreating any missing table, and a failed
       WRITE tells the user in the chat. Chainlit runs its writes as background tasks and
       the base class swallows database errors, so without this a failure is silent.
    3. A resumed thread gets its card elements back, rebuilt from the messages' metadata
       (Chainlit's own element storage needs a file provider, so create_element does nothing).
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        super().__init__(conninfo=f"sqlite+aiosqlite:///{db_path.as_posix()}")
        self.db_path = db_path
        self.engine = create_async_engine(self._conninfo, poolclass=NullPool)
        self.async_session = sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)  # type: ignore
        # True after a failed write was reported, so one outage gives one message.
        self._failure_reported = False

    async def execute_sql(self, query: str, parameters: dict) -> Any:
        """Run one statement. The base class returns None when it failed (and logged why)."""
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

    async def _report_failed_write(self) -> None:
        """Show one short error in the chat. The chat itself keeps working."""
        logger.warning("A chat write failed, so this chat may not be saved.")
        if self._failure_reported:
            return
        self._failure_reported = True
        try:
            message = cl.Message(content=SAVE_FAILED_TEXT)
            message.persisted = True  # an error notice is not saved, or it would fail again
            await message.send()
        except Exception as error:  # e.g. no chat open (a write during login)
            logger.warning("Could not show the save error: %s", type(error).__name__)

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
