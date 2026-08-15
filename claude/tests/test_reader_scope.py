"""Conversation scoping.

These tests build a miniature chat.db with the same shape as the real
one and assert that the reader cannot see outside the allowed
conversations. This is the security property of the project, so it is
tested against the actual SQL rather than a mock.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from taskbot.imessage.reader import (
    APPLE_EPOCH,
    MessageReader,
    NoAllowedChats,
    apple_time_to_datetime,
)

MICHELLE = "+15551234567"
MOM = "+15559999999"
SPAM = "+18005551212"

SCHEMA = """
CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT);
CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
CREATE TABLE message (
    ROWID INTEGER PRIMARY KEY,
    guid TEXT,
    text TEXT,
    attributedBody BLOB,
    is_from_me INTEGER DEFAULT 0,
    date INTEGER,
    service TEXT,
    handle_id INTEGER
);
CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
"""


@pytest.fixture
def chat_db(tmp_path):
    """A fake chat.db with three conversations.

    chat 1: just Michelle
    chat 2: just Mom
    chat 3: Michelle + Mom (a group thread)
    """
    path = tmp_path / "chat.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    handles = {MICHELLE: 1, MOM: 2, SPAM: 3}
    for handle, rowid in handles.items():
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (?, ?)", (rowid, handle))

    for chat_id in (1, 2, 3):
        conn.execute("INSERT INTO chat (ROWID, guid) VALUES (?, ?)", (chat_id, f"c{chat_id}"))
    for chat_id, handle_id in [(1, 1), (2, 2), (3, 1), (3, 2)]:
        conn.execute(
            "INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (?, ?)",
            (chat_id, handle_id),
        )

    def add(rowid, chat_id, text, handle_id, is_from_me=0):
        conn.execute(
            "INSERT INTO message (ROWID, guid, text, is_from_me, date, service, "
            "handle_id) VALUES (?, ?, ?, ?, ?, 'iMessage', ?)",
            (rowid, f"m{rowid}", text, is_from_me, 700_000_000_000_000_000, handle_id),
        )
        conn.execute(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            (chat_id, rowid),
        )

    add(1, 1, "hey from michelle", 1)
    add(2, 1, "hey back", 1, is_from_me=1)
    add(3, 2, "private message from mom", 2)
    add(4, 3, "group thread message", 1)
    add(5, 1, "/tasks", 1)
    conn.commit()
    conn.close()
    return path


def test_reads_allowed_conversation(chat_db):
    reader = MessageReader(chat_db, [MICHELLE])
    texts = [m.text for m in reader.since(0)]
    assert texts == ["hey from michelle", "hey back", "/tasks"]


def test_excludes_other_peoples_threads(chat_db):
    reader = MessageReader(chat_db, [MICHELLE])
    texts = [m.text for m in reader.since(0)]
    assert "private message from mom" not in texts


def test_excludes_group_threads_with_outsiders(chat_db):
    """A group containing Michelle *and* someone else is still off limits."""
    reader = MessageReader(chat_db, [MICHELLE])
    texts = [m.text for m in reader.since(0)]
    assert "group thread message" not in texts


def test_group_included_when_all_participants_allowed(chat_db):
    reader = MessageReader(chat_db, [MICHELLE, MOM])
    texts = [m.text for m in reader.since(0)]
    assert "group thread message" in texts


def test_includes_own_sent_messages_in_scope(chat_db):
    reader = MessageReader(chat_db, [MICHELLE])
    sent = [m for m in reader.since(0) if m.is_from_me]
    assert [m.text for m in sent] == ["hey back"]


def test_since_respects_rowid_bookmark(chat_db):
    reader = MessageReader(chat_db, [MICHELLE])
    assert [m.text for m in reader.since(2)] == ["/tasks"]


def test_handle_format_is_normalized(chat_db):
    """Config can say (555) 123-4567 and still match +15551234567."""
    reader = MessageReader(chat_db, ["(555) 123-4567"])
    assert [m.text for m in reader.since(0)][0] == "hey from michelle"


def test_unknown_handle_raises_rather_than_reading_everything(chat_db):
    reader = MessageReader(chat_db, ["+15550000000"])
    with pytest.raises(NoAllowedChats):
        reader.since(0)


def test_empty_allowed_list_is_refused(chat_db):
    with pytest.raises(ValueError, match="at least one allowed handle"):
        MessageReader(chat_db, [])


def test_missing_database_is_clear(tmp_path):
    reader = MessageReader(tmp_path / "nope.db", [MICHELLE])
    with pytest.raises(FileNotFoundError, match="No Messages database"):
        reader.since(0)


def test_latest_rowid(chat_db):
    assert MessageReader(chat_db, [MICHELLE]).latest_rowid() == 5


def test_apple_time_conversion():
    # 2026-08-15T12:00:00Z expressed in Apple nanoseconds.
    target = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    nanos = int((target - APPLE_EPOCH).total_seconds() * 1_000_000_000)
    assert apple_time_to_datetime(nanos) == target


def test_apple_time_handles_legacy_seconds():
    target = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    seconds = int((target - APPLE_EPOCH).total_seconds())
    assert apple_time_to_datetime(seconds) == target


def test_apple_time_none():
    assert apple_time_to_datetime(None) is None
    assert apple_time_to_datetime(0) is None
