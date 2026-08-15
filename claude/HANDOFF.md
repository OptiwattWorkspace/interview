# Handoff: finish setting up taskbot on this Mac

You are a Claude Code session running **locally on Casey's Mac**. A
previous cloud session built this project but could not run it, because
it needs this machine's Messages database and Messages.app. Your job is
to get it running here. The human you're working with is Casey
(casey@getoptiwatt.com); the other user is their girlfriend Michelle.

## What this is

A two-person task list driven entirely over iMessage. Casey and
Michelle text commands (`/tasks`, `/add buy milk by friday`, `/done 2`)
in their existing thread; the bot polls `~/Library/Messages/chat.db`,
parses commands, and replies through Messages.app via AppleScript.
Tasks are exactly four fields: Task | Status | Due | Owner.

Everything is in this directory (`claude/` inside the interview repo).
The code is complete and 128 tests pass (`python3 -m pytest tests/`).
Nothing has ever been run on a real Mac — that's the part you're here
to do.

## Facts you'd otherwise have to ask for

- Casey's owner name: `casey`
- Michelle's owner name: `michelle`, phone `+19259008174`
  (Casey provided this number for setup — treat it as config data,
  don't commit it; `config.json` and `*.db` are gitignored for this
  reason.)
- Trigger prefix: `/` (chosen so ordinary chat never fires the bot)
- Casey has already been told a test text will go out during setup.

## Setup sequence

Work through this in order. Each step has a known failure mode; all of
them are recoverable without code changes except possibly step 4.

1. **Write the config** to `~/.taskbot/config.json`:

   ```json
   {
     "me": "casey",
     "handles": { "+19259008174": "michelle" },
     "trigger": "/",
     "poll_seconds": 2.0,
     "reply_to": null
   }
   ```

2. **Run the environment check** from this directory:

   ```bash
   python3 -m taskbot doctor
   ```

   Expected failure on first run: chat.db unreadable → the terminal
   needs **Full Disk Access** (System Settings → Privacy & Security →
   Full Disk Access). Casey must toggle this by hand; macOS does not
   allow any process to grant it to itself. Rerun after.

   Also check the "Scoped to N conversation(s)" line. If it errors with
   `NoAllowedChats`, the number in the config doesn't match how it
   appears in Messages — query the handle table (read-only!) to see the
   exact format and adjust the config, not the code.

3. **Check text extraction.** Doctor samples recent in-scope messages
   and reports how many yielded text. A few empty ones are normal
   (reactions, attachments). If *most* are empty, the `attributedBody`
   decoder in `taskbot/imessage/attributed_body.py` doesn't match this
   macOS version's format — this is the one piece that was written
   against the documented format but never validated on real data.
   Debug it against real blobs before going further.

4. **The send test — this is the go/no-go for the whole project:**

   ```bash
   python3 -m taskbot doctor --send-to +19259008174
   ```

   macOS will pop an **Automation** permission dialog (terminal
   controlling Messages) — Casey must click Allow. Then confirm with
   Casey that the text actually arrived on Michelle's phone; osascript
   can report success without delivery.

   If sending fails outright on this macOS version (Apple has been
   tightening AppleScript access to Messages), **stop and tell Casey**
   — the fallback discussed was keeping iMessage for reading but
   replying via a different channel, and that's a design conversation,
   not something to improvise.

5. **Start it:**

   ```bash
   python3 -m taskbot run
   ```

   Have Casey text `/tasks` from their phone. First run deliberately
   skips all message history (`catch_up`) so old texts aren't replayed.
   `--dry-run` prints replies instead of sending, useful mid-debug.

6. **Make it survive reboots (optional, ask Casey).** A LaunchAgent
   works, but note: Full Disk Access granted to Terminal does **not**
   extend to a launchd-spawned python. The python binary itself (the
   real one it resolves to, not the symlink) needs FDA, and the
   Automation grant is per-app too. Expect one more round of permission
   dialogs. Log to `~/.taskbot/taskbot.log` and keep
   `KeepAlive`/`RunAtLoad` on.

## Architecture, one paragraph

`taskbot/imessage/reader.py` polls chat.db read-only (`immutable=1`),
scoped in SQL to conversations whose participants are all in the
config — never filter-after-read; `attributed_body.py` decodes the
typedstream blobs that hold message text on modern macOS;
`commands.py` is the pure text-in/text-out command layer (see
`/help`); `store.py` is SQLite (tasks + the last-seen-ROWID bookmark);
`bot.py` is the loop tying it together; `sender.py` sends via
osascript with the message body passed as argv, never interpolated
into the script. `doctor.py` checks the environment. Tests fake the
Mac-only parts, which is why they run anywhere.

## Rules the previous session committed to

- **Privacy scoping is load-bearing**: Casey explicitly asked that only
  the conversation with Michelle be read. The reader refuses to run
  unscoped, and excludes group chats containing anyone else. Don't
  weaken this to fix a bug; fix the bug.
- chat.db is opened read-only, always. Never write to it, never copy
  it elsewhere.
- The bot only acts on messages starting with the trigger prefix.
  Everything else in the thread is ignored and must stay ignored.
- Message content stays on this machine.

## Repo mechanics

This lives in the `OptiwattWorkspace/interview` repo (Casey's company
interview repo — an odd host, chosen for convenience) on branch
`claude/couple-task-texting-yec12s`. If you change code, commit to that
branch. `config.json` and `*.db` stay out of git.
