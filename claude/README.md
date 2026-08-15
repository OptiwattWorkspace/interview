# taskbot

A shared task list for two people, driven entirely over iMessage. Text
`/tasks` in your existing thread and a reply comes back:

```
2. Fix garage door | doing | Aug 18 | casey
1. Book dentist | open | Aug 20 | michelle
3. Pay water bill | open | Aug 22 | casey
```

Each task is exactly four fields: **Task | Status | Date Due | Owner**.

No new phone number, no Twilio, no server. It runs on a Mac that has
Messages set up, reads new messages from the local Messages database,
and replies by driving Messages.app.

## Privacy scoping

The bot only reads the conversation(s) with the handles listed in your
config. The scoping is enforced in the SQL query itself — messages from
any other thread are never loaded into the process. A group thread that
includes anyone outside the configured handles is also excluded. If the
configured conversation can't be found, the bot stops rather than
falling back to reading anything wider. See `tests/test_reader_scope.py`
for the tests that pin this behavior.

Everything stays on the machine: the task list is a local SQLite file,
and no message content is sent anywhere.

## Requirements

- macOS with Messages signed in (this Mac must be receiving the texts)
- Python 3.10+
- No third-party packages at runtime; `pytest` to run tests

## Setup

1. **Full Disk Access** — System Settings → Privacy & Security →
   Full Disk Access → enable your terminal. Required to read
   `~/Library/Messages/chat.db`.

2. **Config:**

   ```
   python3 -m taskbot init
   ```

   Then edit `~/.taskbot/config.json`:

   ```json
   {
     "me": "casey",
     "handles": { "+15555555555": "michelle" },
     "trigger": "/"
   }
   ```

   Use the number exactly as it appears in Messages, country code
   included. Formatting differences are normalized automatically.

3. **Check the machine** — especially sending, which is the fragile
   part of this whole approach:

   ```
   python3 -m taskbot doctor --send-to <your own number>
   ```

   The first send prompts for Automation permission (allowing your
   terminal to control Messages). If the test message never arrives,
   stop here — your macOS version may not allow AppleScript sending,
   and the rest of the bot can't work around that.

4. **Run it:**

   ```
   python3 -m taskbot run
   ```

   Add `--dry-run` to print replies to the terminal instead of sending.

## Commands

Anything not starting with the trigger (`/` by default) is ignored, so
normal conversation never wakes the bot.

| Command | Effect |
| --- | --- |
| `/tasks` | List open tasks, soonest due first |
| `/tasks mine` | Just yours |
| `/tasks michelle` | Just Michelle's |
| `/tasks all` | Include finished tasks |
| `/add buy milk` | New task, owned by whoever sent it |
| `/add buy milk for michelle by friday` | With owner and due date |
| `/done 3` · `/doing 3` · `/open 3` | Change status |
| `/drop 3` | Delete |
| `/help` | Command list |

Dates understand `friday`, `next friday`, `tomorrow`, `aug 20`, `8/20`,
`in 2 weeks`, and similar. Anything unrecognized stays part of the task
title.

There's also a REPL that skips iMessage entirely — useful for testing:

```
python3 -m taskbot chat
```

## Keeping it running

The bot only works while the Mac is awake. To have launchd keep it
alive in the background, save this as
`~/Library/LaunchAgents/com.taskbot.plist` (fix the paths), then run
`launchctl load ~/Library/LaunchAgents/com.taskbot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.taskbot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string>
    <string>taskbot</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key><string>/PATH/TO/claude-taskbot</string>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>/tmp/taskbot.log</string>
</dict>
</plist>
```

## Known limitations

- **Sending is the weak point.** AppleScript control of Messages has
  been repeatedly restricted across macOS versions. `doctor --send-to`
  is the ground truth for whether it works on yours.
- **Mac asleep = bot offline.** Replies resume when it wakes.
- **Message text decoding** (`attributedBody`) is a reverse-engineered
  format. `doctor` reports how well it decodes your recent in-scope
  messages.
- Tapbacks, edits, and attachments are ignored (they carry no usable
  text).

## Tests

```
python3 -m pytest
```

No Mac required — the iMessage layer is faked in tests, and the
conversation-scoping guarantees are tested against a synthetic copy of
the Messages database schema.
