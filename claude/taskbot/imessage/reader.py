"""Read new messages out of the Messages database.

Two constraints shape this module.

First, it opens chat.db strictly read-only. Messages holds this database
open with a WAL lock while it runs, and corrupting your own message
history to save a task list would be a poor trade.

Second, and more importantly: it never reads messages outside the
conversations you have explicitly allowed. The scoping is done in SQL,
not by filtering afterward, so text from other threads is never loaded
into this process at all. If the allowed conversations can't be
resolved, the reader returns nothing — it never falls back to reading
everything.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import normalize_handle
from . import attributed_body

log = logging.getLogger("taskbot")

# Apple's epoch for these timestamps is 2001-01-01, not 1970-01-01.
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

# Every participant of every chat, so we can pick the allowed ones.
_CHAT_PARTICIPANTS = """
SELECT c.ROWID AS chat_id, h.id AS handle
FROM chat c
JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
JOIN handle h ON h.ROWID = chj.handle_id
"""

# Note the chat_id filter: this is the scoping guarantee.
_MESSAGES = """
SELECT DISTINCT
    m.ROWID          AS rowid,
    m.guid           AS guid,
    m.text           AS text,
    m.attributedBody AS attributed_body,
    m.is_from_me     AS is_from_me,
    m.date           AS date,
    m.service        AS service,
    h.id             AS handle
FROM message m
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
LEFT JOIN handle h ON m.handle_id = h.ROWID
WHERE m.ROWID > ? AND cmj.chat_id IN ({placeholders})
ORDER BY m.ROWID
LIMIT ?
"""

_MAX_ROWID = "SELECT COALESCE(MAX(ROWID), 0) FROM message"


class NoAllowedChats(Exception):
    """Raised when none of the allowed handles map to a conversation."""


@dataclass
class Message:
    """One row from the Messages database, with the text resolved."""

    rowid: int
    guid: str
    text: str | None
    is_from_me: bool
    sent_at: datetime | None
    service: str | None
    handle: str | None


def apple_time_to_datetime(value: int | None) -> datetime | None:
    """Convert a Messages timestamp to a timezone-aware datetime.

    Handles both the modern nanosecond timestamps and the older
    second-resolution ones that appear in long-lived databases.
    """
    if not value:
        return None
    seconds = value / 1_000_000_000 if value > 1e11 else float(value)
    try:
        return APPLE_EPOCH + timedelta(seconds=seconds)
    except (OverflowError, OSError):
        return None


class MessageReader:
    """Polls chat.db for new messages in an explicit set of conversations.

    Args:
        chat_db_path: Location of the Messages database.
        allowed_handles: Phone numbers or emails whose conversations may
            be read. Only chats whose participants are entirely within
            this set are considered — a group thread that includes a
            third person is excluded, even though it includes an allowed
            handle.
    """

    def __init__(self, chat_db_path: Path | str, allowed_handles: list[str]):
        self.path = Path(chat_db_path).expanduser()
        self.allowed = {normalize_handle(h) for h in allowed_handles if h}
        if not self.allowed:
            raise ValueError(
                "MessageReader needs at least one allowed handle. Refusing "
                "to read the Messages database unscoped."
            )
        self._chat_ids: list[int] | None = None

    def _connect(self) -> sqlite3.Connection:
        """Open chat.db read-only.

        ``immutable=1`` tells SQLite the file won't change underneath us,
        which lets us read without taking any lock at all — important,
        because Messages.app holds its own.
        """
        if not self.path.exists():
            raise FileNotFoundError(
                f"No Messages database at {self.path}. "
                f"This only works on macOS with Messages set up."
            )
        try:
            conn = sqlite3.connect(
                f"file:{self.path}?mode=ro&immutable=1", uri=True
            )
        except sqlite3.OperationalError as exc:
            raise PermissionError(
                f"Can't open {self.path}: {exc}\n"
                f"Grant Full Disk Access to your terminal in "
                f"System Settings > Privacy & Security > Full Disk Access."
            ) from exc
        conn.row_factory = sqlite3.Row
        return conn

    # -- scoping -------------------------------------------------------

    def allowed_chat_ids(self, conn: sqlite3.Connection | None = None) -> list[int]:
        """Chat IDs this reader is permitted to read, resolved once.

        A chat qualifies only if every one of its participants is an
        allowed handle. That excludes group threads containing anyone
        else, which is the case worth being careful about.
        """
        if self._chat_ids is not None:
            return self._chat_ids

        owned = conn or self._connect()
        try:
            rows = owned.execute(_CHAT_PARTICIPANTS).fetchall()
        finally:
            if conn is None:
                owned.close()

        participants: dict[int, set[str]] = {}
        for row in rows:
            participants.setdefault(row["chat_id"], set()).add(
                normalize_handle(row["handle"] or "")
            )

        self._chat_ids = sorted(
            chat_id
            for chat_id, people in participants.items()
            if people and people <= self.allowed
        )
        if not self._chat_ids:
            raise NoAllowedChats(
                f"No conversation found with {', '.join(sorted(self.allowed))}. "
                f"Check the number in your config matches the one in Messages "
                f"(including country code)."
            )
        return self._chat_ids

    # -- reading -------------------------------------------------------

    def latest_rowid(self) -> int:
        """The highest message ROWID in the database.

        Deliberately unscoped: this reads a single integer and no message
        content. Using the global maximum as the starting bookmark means
        the poller never has to walk back over other people's rows.
        """
        conn = self._connect()
        try:
            return conn.execute(_MAX_ROWID).fetchone()[0]
        finally:
            conn.close()

    def since(self, rowid: int, limit: int = 200) -> list[Message]:
        """Fetch allowed messages with a ROWID greater than ``rowid``."""
        conn = self._connect()
        try:
            chat_ids = self.allowed_chat_ids(conn)
            query = _MESSAGES.format(
                placeholders=",".join("?" * len(chat_ids))
            )
            rows = conn.execute(
                query, (rowid, *chat_ids, limit)
            ).fetchall()
        finally:
            conn.close()
        return [self._to_message(r) for r in rows]

    @staticmethod
    def _to_message(row: sqlite3.Row) -> Message:
        text = row["text"]
        if not text:
            text = attributed_body.decode(row["attributed_body"])
        return Message(
            rowid=row["rowid"],
            guid=row["guid"],
            text=text,
            is_from_me=bool(row["is_from_me"]),
            sent_at=apple_time_to_datetime(row["date"]),
            service=row["service"],
            handle=row["handle"],
        )
