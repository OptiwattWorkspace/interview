"""Environment checks.

Everything here exists because the pieces this project depends on —
Full Disk Access, the attributedBody format, AppleScript sending — fail
in ways that are silent or misleading. Run this before assuming the bot
is broken.

Like the reader, these checks stay inside the allowed conversations.
Nothing here samples the database at large.
"""

from __future__ import annotations

import platform
import sqlite3
import sys

from .config import Config
from .imessage.reader import MessageReader, NoAllowedChats
from .imessage.sender import AppleScriptSender, SendError

OK = "\033[32m✓\033[0m"
BAD = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"


def run(cfg: Config, send_to: str | None = None) -> int:
    """Run all checks. Returns a process exit code."""
    failures = 0

    print("taskbot doctor\n")

    if platform.system() != "Darwin":
        print(f"{BAD} Not macOS ({platform.system()}).")
        print("   Reading iMessage requires a Mac with Messages set up.")
        failures += 1
    else:
        print(f"{OK} macOS {platform.mac_ver()[0]}")

    failures += _check_chat_db(cfg)

    print(f"\n{OK} Task database: {cfg.db_path}")
    print(f"{OK} Owners: {', '.join(cfg.owners)}")
    print(f"{OK} Trigger: {cfg.trigger}tasks")

    if send_to:
        failures += _check_send(send_to)
    else:
        print(
            f"\n{WARN} Skipped the send test. This is the check that "
            f"actually matters —\n   rerun with --send-to <your number> "
            f"to verify AppleScript can send."
        )

    print()
    if failures:
        print(f"{failures} problem(s) found.")
    else:
        print("All checks passed.")
    return 1 if failures else 0


def _check_chat_db(cfg: Config) -> int:
    """Verify chat.db is readable, correctly scoped, and decodable."""
    handles = [h for h in cfg.handles]
    try:
        reader = MessageReader(cfg.chat_db_path, handles)
    except ValueError as exc:
        print(f"{BAD} {exc}")
        return 1

    try:
        chat_ids = reader.allowed_chat_ids()
    except FileNotFoundError as exc:
        print(f"{BAD} {exc}")
        return 1
    except PermissionError as exc:
        print(f"{BAD} {exc}")
        return 1
    except sqlite3.DatabaseError as exc:
        print(f"{BAD} {cfg.chat_db_path} is unreadable: {exc}")
        print("   Grant Full Disk Access to your terminal and try again.")
        return 1
    except NoAllowedChats as exc:
        print(f"{BAD} {exc}")
        return 1

    who = ", ".join(sorted(set(cfg.handles.values())))
    print(f"{OK} Messages database readable")
    print(
        f"{OK} Scoped to {len(chat_ids)} conversation(s) with {who} "
        f"— no other threads are read"
    )

    # The real test: can we recover text from recent messages in scope?
    return _check_extraction(reader)


def _check_extraction(reader: MessageReader) -> int:
    """Sample recent in-scope messages and see if text comes out."""
    latest = reader.latest_rowid()
    # Walk back until we have a sample or run out of database.
    window = 500
    messages = []
    while window <= 64_000 and not messages:
        messages = reader.since(max(latest - window, 0), limit=100)
        window *= 4

    if not messages:
        print(f"{WARN} No recent messages in scope to test extraction against.")
        return 0

    with_text = sum(1 for m in messages if m.text)
    missing = len(messages) - with_text

    print(
        f"{OK if not missing else WARN} Text extraction on {len(messages)} "
        f"in-scope message(s): {with_text} readable, {missing} empty"
    )
    if missing:
        print(
            "   Empty ones are usually attachments, reactions or edits, "
            "which are\n   safely ignored. If the count is high, the "
            "attributedBody decoder\n   needs work on your macOS version."
        )
    return 0


def _check_send(handle: str) -> int:
    """Try an actual send. The go/no-go for the whole approach."""
    print(f"\nSending a test message to {handle}...")
    try:
        AppleScriptSender().send(handle, "taskbot: send test ✓")
    except SendError as exc:
        print(f"{BAD} Send failed.\n   {exc}")
        return 1
    print(f"{OK} Send reported success — check that it actually arrived.")
    return 0


def main(cfg: Config, send_to: str | None = None) -> int:
    return run(cfg, send_to)


if __name__ == "__main__":  # pragma: no cover
    from . import config

    sys.exit(main(config.load()))
