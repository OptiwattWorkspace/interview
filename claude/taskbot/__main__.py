"""Command line entry point: ``python -m taskbot <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from . import commands, config, doctor
from .bot import Bot
from .imessage.reader import MessageReader
from .imessage.sender import AppleScriptSender, ConsoleSender
from .store import Store

EXAMPLE = Path(__file__).parent.parent / "config.example.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="taskbot", description="A shared task list, driven over iMessage."
    )
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a starter config file")

    run = sub.add_parser("run", help="poll iMessage and reply (the daemon)")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="print replies instead of sending them",
    )

    doc = sub.add_parser("doctor", help="check that this Mac is set up")
    doc.add_argument(
        "--send-to",
        metavar="HANDLE",
        help="phone number or email to send a test message to",
    )

    chat = sub.add_parser(
        "chat", help="talk to the bot from the terminal, no iMessage involved"
    )
    chat.add_argument("text", nargs="*", help="a single command to run")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "init":
        return _init(args.config)

    try:
        cfg = config.load(args.config)
    except config.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("\nRun 'python -m taskbot init' to create one.", file=sys.stderr)
        return 1

    if args.command == "doctor":
        return doctor.main(cfg, args.send_to)
    if args.command == "chat":
        return _chat(cfg, args.text)
    if args.command == "run":
        return _run(cfg, args.dry_run)
    return 1


def _init(path: str | None) -> int:
    """Copy the example config into place."""
    target = Path(path).expanduser() if path else config.DEFAULT_CONFIG_PATH
    if target.exists():
        print(f"{target} already exists — leaving it alone.")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    if EXAMPLE.exists():
        shutil.copy(EXAMPLE, target)
    else:  # pragma: no cover - only if the package is installed oddly
        target.write_text(
            json.dumps(
                {
                    "me": "casey",
                    "handles": {"+15555555555": "michelle"},
                    "trigger": "/",
                },
                indent=2,
            )
        )
    print(f"Wrote {target}")
    print("Edit it to set the phone numbers, then run:")
    print("  python -m taskbot doctor --send-to <your number>")
    return 0


def _run(cfg: config.Config, dry_run: bool) -> int:
    """Start the polling loop."""
    sender = ConsoleSender() if dry_run else AppleScriptSender()
    # Only the configured handles' conversations are ever read.
    reader = MessageReader(cfg.chat_db_path, list(cfg.handles))
    with Store(cfg.db_path) as store:
        bot = Bot(cfg, store, reader, sender)
        try:
            bot.run()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


def _chat(cfg: config.Config, text: list[str]) -> int:
    """Drive the command layer directly — useful for testing on any OS."""
    with Store(cfg.db_path) as store:
        if text:
            reply = commands.handle(" ".join(text), cfg.me, store, cfg)
            print(reply if reply is not None else f"(not a command — "
                  f"commands start with '{cfg.trigger}')")
            return 0

        print(f"Type commands starting with '{cfg.trigger}'. Ctrl-C to quit.\n")
        while True:
            try:
                line = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return 0
            if not line:
                continue
            reply = commands.handle(line, cfg.me, store, cfg)
            print(reply if reply is not None else
                  f"(not a command — commands start with '{cfg.trigger}')")


if __name__ == "__main__":
    sys.exit(main())
