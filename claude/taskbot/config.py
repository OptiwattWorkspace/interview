"""Configuration loading.

The config is a small JSON file, by default at ``~/.taskbot/config.json``.
It maps phone numbers to owner names and holds the handful of knobs worth
changing. See ``config.example.json``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".taskbot" / "config.json"
DEFAULT_DB_PATH = Path.home() / ".taskbot" / "tasks.db"
DEFAULT_CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"


class ConfigError(Exception):
    """Raised when the config file is missing or malformed."""


def normalize_handle(handle: str) -> str:
    """Reduce a phone number or email to a comparable form.

    iMessage handles arrive in whatever shape the sender's contact card
    happens to have: ``+15551234567``, ``(555) 123-4567``, ``555-1234``.
    Phone numbers collapse to their last 10 digits so those all match;
    email handles just lowercase.
    """
    handle = handle.strip()
    if "@" in handle:
        return handle.lower()
    digits = re.sub(r"\D", "", handle)
    return digits[-10:] if len(digits) >= 10 else digits


@dataclass
class Config:
    """Runtime configuration.

    Attributes:
        me: Owner name for messages sent from this Mac (``is_from_me = 1``).
        handles: Normalized handle -> owner name, for everyone else.
        trigger: Prefix that marks a message as a command.
        poll_seconds: How often to check chat.db for new messages.
        db_path: Where the task database lives.
        chat_db_path: Where Messages keeps its database.
        reply_to: Optional handle to always reply to, overriding the sender.
    """

    me: str = "casey"
    handles: dict[str, str] = field(default_factory=dict)
    trigger: str = "/"
    poll_seconds: float = 2.0
    db_path: Path = DEFAULT_DB_PATH
    chat_db_path: Path = DEFAULT_CHAT_DB
    reply_to: str | None = None

    @property
    def owners(self) -> list[str]:
        """Every known owner name, ``me`` first."""
        names = [self.me]
        for name in self.handles.values():
            if name not in names:
                names.append(name)
        return names

    def owner_for(self, handle: str | None, is_from_me: bool) -> str | None:
        """Resolve a message's sender to an owner name.

        Returns None for handles that aren't in the config, which is how
        messages from anyone but the two of you get ignored.
        """
        if is_from_me:
            return self.me
        if not handle:
            return None
        return self.handles.get(normalize_handle(handle))

    def resolve_owner_name(self, name: str) -> str | None:
        """Match a user-typed owner name case-insensitively.

        ``"MICHELLE"`` and ``"michelle"`` both resolve; ``"mich"`` does not.
        """
        name = name.strip().lower()
        for owner in self.owners:
            if owner.lower() == name:
                return owner
        return None


def load(path: Path | str | None = None) -> Config:
    """Load config from disk.

    Args:
        path: Config file location. Defaults to ``$TASKBOT_CONFIG`` if set,
            otherwise ``~/.taskbot/config.json``.

    Raises:
        ConfigError: If the file is missing, unparseable, or has no handles.
    """
    if path is None:
        path = os.environ.get("TASKBOT_CONFIG", DEFAULT_CONFIG_PATH)
    path = Path(path).expanduser()

    if not path.exists():
        raise ConfigError(
            f"No config at {path}.\n"
            f"Copy config.example.json there and fill in the phone numbers."
        )

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc

    return from_dict(raw)


def from_dict(raw: dict) -> Config:
    """Build a Config from a parsed JSON dict."""
    handles = {}
    for handle, owner in (raw.get("handles") or {}).items():
        handles[normalize_handle(handle)] = owner

    if not handles:
        raise ConfigError(
            "Config has no 'handles'. Add at least the other person's "
            "phone number so the bot knows who is texting it."
        )

    cfg = Config(
        me=raw.get("me", "casey"),
        handles=handles,
        trigger=raw.get("trigger", "/"),
        poll_seconds=float(raw.get("poll_seconds", 2.0)),
        db_path=Path(raw.get("db_path", DEFAULT_DB_PATH)).expanduser(),
        chat_db_path=Path(raw.get("chat_db_path", DEFAULT_CHAT_DB)).expanduser(),
        reply_to=raw.get("reply_to"),
    )

    if not cfg.trigger:
        raise ConfigError(
            "'trigger' cannot be empty — without a prefix the bot would try "
            "to interpret every message in the thread."
        )
    return cfg
