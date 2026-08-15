"""Send messages through Messages.app via AppleScript.

This is the fragile half of the project. There is no supported send API;
driving Messages.app with AppleScript is the only route, and Apple has
tightened it over successive macOS releases. Run ``python -m taskbot
doctor --send-to <number>`` to confirm it works on your machine before
trusting it.

The message body is passed as an argv item rather than interpolated into
the script source, so message content can never be parsed as AppleScript.
"""

from __future__ import annotations

import subprocess
from typing import Protocol

# `on run argv` keeps the text out of the script body entirely.
_SCRIPT = """
on run argv
    set targetHandle to item 1 of argv
    set messageText to item 2 of argv
    tell application "Messages"
        try
            set targetService to 1st account whose service type = iMessage
            set targetBuddy to participant targetHandle of targetService
            send messageText to targetBuddy
        on error errMsg number errNum
            -- Fall back to whatever service the handle is already on,
            -- which covers SMS-relayed threads on some configurations.
            set targetBuddy to participant targetHandle
            send messageText to targetBuddy
        end try
    end tell
end run
"""


class SendError(Exception):
    """Raised when Messages.app refuses or fails to send."""


class Sender(Protocol):
    """Anything that can deliver a reply. Lets tests skip AppleScript."""

    def send(self, handle: str, text: str) -> None: ...


class AppleScriptSender:
    """Sends via Messages.app. macOS only."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def send(self, handle: str, text: str) -> None:
        """Send ``text`` to ``handle``.

        Raises:
            SendError: If osascript is missing, times out, or Messages
                returns an error.
        """
        try:
            result = subprocess.run(
                ["osascript", "-", handle, text],
                input=_SCRIPT,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise SendError("osascript not found — this only runs on macOS.") from exc
        except subprocess.TimeoutExpired as exc:
            raise SendError(
                "Messages.app didn't respond within "
                f"{self.timeout}s. Is it running and unlocked?"
            ) from exc

        if result.returncode != 0:
            raise SendError(
                f"osascript failed ({result.returncode}): "
                f"{result.stderr.strip() or 'no error output'}\n"
                f"Check System Settings > Privacy & Security > Automation "
                f"and allow your terminal to control Messages."
            )


class ConsoleSender:
    """Prints instead of sending. For dry runs and tests."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, handle: str, text: str) -> None:
        self.sent.append((handle, text))
        print(f"[would send to {handle}]\n{text}\n")
