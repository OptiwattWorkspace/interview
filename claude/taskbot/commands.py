"""Command parsing and reply generation.

This module is pure: text in, text out, with the store as the only side
effect. It has no idea iMessage exists, which is what lets the whole
command surface be tested without a Mac.
"""

from __future__ import annotations

import re
from datetime import date

from . import dates
from .config import Config
from .store import DOING, DONE, OPEN, Store

HELP = """Commands:
/tasks — open tasks
/tasks mine — just yours
/tasks all — include done
/add <task> [for <name>] [by <date>]
/done <n> · /doing <n> · /open <n>
/drop <n> — delete"""


def handle(
    text: str,
    sender: str,
    store: Store,
    cfg: Config,
    today: date | None = None,
) -> str | None:
    """Interpret one message and return the reply text.

    Args:
        text: The raw message body.
        sender: Owner name of whoever sent it.
        store: Task store to read and mutate.
        cfg: Runtime config, for owner-name resolution.
        today: Reference date for relative due dates.

    Returns:
        Reply text, or None if the message isn't a command and should be
        ignored entirely.
    """
    if not text:
        return None
    body = text.strip()
    if not body.startswith(cfg.trigger):
        return None

    body = body[len(cfg.trigger):].strip()
    if not body:
        return None

    verb, _, rest = body.partition(" ")
    verb = verb.lower()
    rest = rest.strip()
    today = today or date.today()

    if verb in ("tasks", "task", "list", "ls"):
        return _list(rest, sender, store, cfg)
    if verb in ("add", "new"):
        return _add(rest, sender, store, cfg, today)
    if verb in ("done", "doing", "open"):
        return _status(verb, rest, store)
    if verb in ("drop", "delete", "rm"):
        return _drop(rest, store)
    if verb in ("help", "?", "commands"):
        return HELP
    return f"Don't know '{verb}'. Text {cfg.trigger}help for the list."


def _list(rest: str, sender: str, store: Store, cfg: Config) -> str:
    """Handle /tasks with optional owner or 'all' filter."""
    rest = rest.strip().lower()
    owner: str | None = None
    include_done = False

    if rest in ("mine", "me"):
        owner = sender
    elif rest == "all":
        include_done = True
    elif rest:
        owner = cfg.resolve_owner_name(rest)
        if owner is None:
            return f"Don't know who '{rest}' is. Try: {', '.join(cfg.owners)}."

    tasks = store.list(owner=owner, include_done=include_done)
    if not tasks:
        who = f" for {owner}" if owner else ""
        return f"No open tasks{who}. Nice."
    return "\n".join(t.format() for t in tasks)


def _add(rest: str, sender: str, store: Store, cfg: Config, today: date) -> str:
    """Handle /add, pulling optional owner and due date out of the text."""
    if not rest:
        return f"What's the task? e.g. {cfg.trigger}add buy milk by friday"

    title, owner = _extract_owner(rest, cfg)
    title, due = _extract_due(title, today)
    title = title.strip(" ,.")

    if not title:
        return "That's all date and no task. What should I call it?"

    task = store.add(title=title, owner=owner or sender, due=due)
    return f"Added — {task.format()}"


def _extract_owner(text: str, cfg: Config) -> tuple[str, str | None]:
    """Pull a trailing or inline ``for <name>`` out of the text."""
    names = "|".join(re.escape(o) for o in cfg.owners)
    pattern = re.compile(rf"\bfor\s+({names})\b'?s?", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return text, None
    owner = cfg.resolve_owner_name(match.group(1))
    return text[: match.start()] + text[match.end():], owner


def _extract_due(text: str, today: date) -> tuple[str, date | None]:
    """Pull a trailing ``by|due|on <date>`` out of the text.

    Only strips the phrase if it actually parses as a date, so "buy milk
    on sale" keeps its words.
    """
    match = re.search(r"\b(?:by|due|on|before)\s+(.+)$", text, re.IGNORECASE)
    if match:
        parsed = dates.parse(match.group(1), today)
        if parsed:
            return text[: match.start()], parsed

    # Also allow a bare trailing date: "call the vet friday"
    words = text.split()
    for take in (2, 1):
        if len(words) > take:
            parsed = dates.parse(" ".join(words[-take:]), today)
            if parsed:
                return " ".join(words[:-take]), parsed
    return text, None


def _status(verb: str, rest: str, store: Store) -> str:
    """Handle /done, /doing and /open."""
    status = {"done": DONE, "doing": DOING, "open": OPEN}[verb]
    task_id = _parse_id(rest)
    if task_id is None:
        return f"Which one? e.g. /{verb} 3"

    task = store.set_status(task_id, status)
    if task is None:
        return f"No task {task_id}."
    if status == DONE:
        return f"Done — {task.title} ✓"
    return f"Updated — {task.format()}"


def _drop(rest: str, store: Store) -> str:
    """Handle /drop."""
    task_id = _parse_id(rest)
    if task_id is None:
        return "Which one? e.g. /drop 3"

    task = store.get(task_id)
    if task is None:
        return f"No task {task_id}."
    store.delete(task_id)
    return f"Deleted — {task.title}"


def _parse_id(rest: str) -> int | None:
    match = re.match(r"#?(\d+)", rest.strip())
    return int(match.group(1)) if match else None
