"""The polling loop.

Reads new messages, routes commands through :mod:`commands`, sends the
replies. The reader and sender are injected, so the whole loop can be
exercised in tests with fakes on a non-Mac machine.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from . import commands
from .config import Config
from .imessage.reader import Message, NoAllowedChats
from .imessage.sender import SendError
from .store import Store

log = logging.getLogger("taskbot")

LAST_ROWID = "last_rowid"


class Bot:
    """Routes iMessage traffic to and from the task store."""

    def __init__(self, cfg: Config, store: Store, reader, sender):
        self.cfg = cfg
        self.store = store
        self.reader = reader
        self.sender = sender

    # -- routing -------------------------------------------------------

    def reply_target(self, message: Message) -> str | None:
        """Decide which handle a reply goes to.

        A message from Michelle replies to Michelle. A message from this
        Mac has no counterparty handle attached, so it needs either an
        explicit ``reply_to`` in config or the handle already on the row.
        """
        if self.cfg.reply_to:
            return self.cfg.reply_to
        if message.handle:
            return message.handle
        return None

    def process(self, message: Message, today: date | None = None) -> str | None:
        """Handle one message. Returns the reply that was sent, if any."""
        owner = self.cfg.owner_for(message.handle, message.is_from_me)
        if owner is None:
            # Someone outside the household. Not our conversation.
            return None

        reply = commands.handle(
            message.text or "", owner, self.store, self.cfg, today
        )
        if reply is None:
            return None

        target = self.reply_target(message)
        if target is None:
            log.warning(
                "Command from %s but nowhere to reply — set 'reply_to' "
                "in config to the other person's number.",
                owner,
            )
            return None

        try:
            self.sender.send(target, reply)
        except SendError as exc:
            log.error("Could not send reply: %s", exc)
            return None
        log.info("%s: %s -> replied", owner, (message.text or "").strip())
        return reply

    # -- loop ----------------------------------------------------------

    def catch_up(self) -> int:
        """Skip past existing history so old texts don't get replayed.

        Called on first run only. Without it, a fresh install would work
        through every ``/tasks`` you have ever sent.
        """
        latest = self.reader.latest_rowid()
        self.store.set_state(LAST_ROWID, str(latest))
        return latest

    def poll_once(self, today: date | None = None) -> list[str]:
        """Process every message since the last one we saw."""
        last = int(self.store.get_state(LAST_ROWID, "0") or 0)
        messages = self.reader.since(last)
        replies = []
        for message in messages:
            try:
                reply = self.process(message, today)
            except Exception:
                # One malformed message must not kill the loop.
                log.exception("Failed on message %s", message.rowid)
                reply = None
            if reply:
                replies.append(reply)
            self.store.set_state(LAST_ROWID, str(message.rowid))
        return replies

    def run(self) -> None:
        """Poll forever."""
        if self.store.get_state(LAST_ROWID) is None:
            rowid = self.catch_up()
            log.info("Starting from message %s (ignoring earlier history).", rowid)

        log.info(
            "Listening. Text %stasks from a known number.", self.cfg.trigger
        )
        while True:
            try:
                self.poll_once()
            except (PermissionError, FileNotFoundError, NoAllowedChats) as exc:
                # These don't get better by retrying.
                log.error("%s", exc)
                return
            except Exception:
                log.exception("Poll failed; retrying.")
            time.sleep(self.cfg.poll_seconds)
