"""The polling loop, with fake iMessage plumbing."""

from __future__ import annotations

from datetime import date

import pytest

from taskbot.bot import LAST_ROWID, Bot
from taskbot.imessage.reader import Message
from taskbot.imessage.sender import SendError

TODAY = date(2026, 8, 15)
MICHELLE = "+15551234567"


class FakeReader:
    """Stands in for chat.db."""

    def __init__(self, messages=None):
        self.messages = messages or []

    def latest_rowid(self):
        return max((m.rowid for m in self.messages), default=0)

    def since(self, rowid, limit=200):
        return [m for m in self.messages if m.rowid > rowid][:limit]


class FakeSender:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, handle, text):
        if self.fail:
            raise SendError("nope")
        self.sent.append((handle, text))


def msg(rowid, text, handle=MICHELLE, is_from_me=False):
    return Message(
        rowid=rowid,
        guid=f"g{rowid}",
        text=text,
        is_from_me=is_from_me,
        sent_at=None,
        service="iMessage",
        handle=handle,
    )


@pytest.fixture
def sender():
    return FakeSender()


def make_bot(cfg, store, messages, sender):
    return Bot(cfg, store, FakeReader(messages), sender)


# -- routing ------------------------------------------------------------


def test_replies_to_michelle(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "/tasks")], sender)
    bot.poll_once(TODAY)
    assert sender.sent == [(MICHELLE, "No open tasks. Nice.")]


def test_attributes_task_to_michelle(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "/add water the plants")], sender)
    bot.poll_once(TODAY)
    assert store.get(1).owner == "michelle"


def test_attributes_own_messages_to_me(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "/add mow the lawn", is_from_me=True)], sender)
    bot.poll_once(TODAY)
    assert store.get(1).owner == "casey"


def test_ignores_unknown_senders(cfg, store, sender):
    """Defense in depth — the reader already scopes, this scopes again."""
    bot = make_bot(cfg, store, [msg(1, "/tasks", handle="+18005551212")], sender)
    bot.poll_once(TODAY)
    assert sender.sent == []


def test_ignores_ordinary_conversation(cfg, store, sender):
    messages = [
        msg(1, "what do you want for dinner"),
        msg(2, "tasks for tomorrow are piling up"),
        msg(3, "love you"),
    ]
    bot = make_bot(cfg, store, messages, sender)
    bot.poll_once(TODAY)
    assert sender.sent == []


def test_ignores_messages_with_no_text(cfg, store, sender):
    """Attachments and reactions decode to None."""
    bot = make_bot(cfg, store, [msg(1, None)], sender)
    bot.poll_once(TODAY)
    assert sender.sent == []


def test_reply_to_override(cfg, store, sender):
    cfg.reply_to = "+15559998888"
    bot = make_bot(cfg, store, [msg(1, "/tasks", is_from_me=True, handle=None)], sender)
    bot.poll_once(TODAY)
    assert sender.sent[0][0] == "+15559998888"


def test_own_message_without_handle_or_reply_to_is_skipped(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "/tasks", is_from_me=True, handle=None)], sender)
    bot.poll_once(TODAY)
    assert sender.sent == []


# -- bookmark -----------------------------------------------------------


def test_advances_bookmark(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "hi"), msg(2, "/tasks")], sender)
    bot.poll_once(TODAY)
    assert store.get_state(LAST_ROWID) == "2"


def test_does_not_reprocess(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "/add buy milk")], sender)
    bot.poll_once(TODAY)
    bot.poll_once(TODAY)
    assert len(store.list()) == 1
    assert len(sender.sent) == 1


def test_catch_up_skips_history(cfg, store, sender):
    """A fresh install must not reply to every old message."""
    messages = [msg(i, "/tasks") for i in range(1, 6)]
    bot = make_bot(cfg, store, messages, sender)
    bot.catch_up()
    bot.poll_once(TODAY)
    assert sender.sent == []
    assert store.get_state(LAST_ROWID) == "5"


def test_bookmark_advances_past_ignored_messages(cfg, store, sender):
    bot = make_bot(cfg, store, [msg(1, "hey", handle="+18005551212")], sender)
    bot.poll_once(TODAY)
    assert store.get_state(LAST_ROWID) == "1"


# -- resilience ---------------------------------------------------------


def test_send_failure_does_not_stop_the_loop(cfg, store):
    failing = FakeSender(fail=True)
    bot = make_bot(cfg, store, [msg(1, "/tasks"), msg(2, "/tasks")], failing)
    bot.poll_once(TODAY)
    assert store.get_state(LAST_ROWID) == "2"


def test_send_failure_still_applies_the_change(cfg, store):
    """The task was added even though the confirmation didn't go out."""
    failing = FakeSender(fail=True)
    bot = make_bot(cfg, store, [msg(1, "/add buy milk")], failing)
    bot.poll_once(TODAY)
    assert len(store.list()) == 1


def test_one_bad_message_does_not_stop_the_batch(cfg, store, sender):
    class Exploding:
        """Duck-types Message but blows up when its text is read."""

        rowid = 2
        guid = "g2"
        is_from_me = False
        sent_at = None
        service = "iMessage"
        handle = MICHELLE

        @property
        def text(self):
            raise RuntimeError("boom")

    bad = Exploding()
    bot = make_bot(cfg, store, [msg(1, "/add first"), bad, msg(3, "/tasks")], sender)
    bot.poll_once(TODAY)
    assert store.get_state(LAST_ROWID) == "3"
    assert len(sender.sent) == 2


# -- end to end ---------------------------------------------------------


def test_conversation_across_polls(cfg, store, sender):
    reader = FakeReader()
    bot = Bot(cfg, store, reader, sender)

    reader.messages.append(msg(1, "/add book dentist by aug 20"))
    bot.poll_once(TODAY)

    reader.messages.append(msg(2, "/add fix garage door", is_from_me=True))
    bot.poll_once(TODAY)

    reader.messages.append(msg(3, "/tasks"))
    bot.poll_once(TODAY)

    assert sender.sent[-1][1] == (
        "1. book dentist | open | Aug 20 | michelle\n"
        "2. fix garage door | open | — | casey"
    )
