# Stable Mail Export

Download **all** your mail from [Stable](https://www.usestable.com) (usestable.com),
categorize each piece, figure out the action needed, and export it to a
spreadsheet.

Stable scans your physical mail and exposes it through a REST API. This tool
walks every mail item in your account, downloads the scans, classifies each
piece (bank statement, IRS notice, check, junk, …), infers what you need to do
about it, and writes a formatted `.xlsx` (with a summary tab) — or a `.csv` if
`openpyxl` isn't installed.

## Why this is a standalone script

This lives in the interview repo only as a convenient home. It does **not**
touch the Django app or the frontend — it's a self-contained CLI you can copy
anywhere. The HTTP layer uses only the Python standard library, so the core
download + categorize path has **no third-party dependencies**. `openpyxl` is
optional (nicer output); an Anthropic API key is optional (`--use-llm`).

> **Note on networking:** Claude Code's *web/cloud* environment runs behind a
> locked-down proxy that blocks `usestable.com`, so this script must be run
> where the network is open — your laptop, a server, or a local Claude Code
> session. It cannot reach Stable from inside a restricted cloud sandbox.

## Setup

```bash
cd tools/stable_mail_export
pip install -r requirements.txt          # optional but recommended (xlsx output)
export STABLE_API_KEY=sk_live_...         # from Stable dashboard → Settings → API
```

Get your API key from the Stable dashboard and see
[Stable's auth docs](https://docs.usestable.com/reference/authentication)
(auth is a single `x-api-key` header).

## Usage

```bash
# Simplest: download everything, categorize, write stable_mail_export.xlsx
python stable_mail_export.py

# Choose output + where scans are saved
python stable_mail_export.py -o mail_2026.xlsx --download-dir ./scans

# Only mail since a date; skip downloading files (metadata only, faster)
python stable_mail_export.py --since 2026-01-01 --no-download

# Smarter categorization + action summaries using Claude
export ANTHROPIC_API_KEY=sk-ant-...
python stable_mail_export.py --use-llm

# Capture the raw API payload once (handy if a field looks wrong)
python stable_mail_export.py --dump-json raw.json --max-items 5 -v
```

Run `python stable_mail_export.py --help` for all flags.

## What you get

A spreadsheet with two sheets:

- **Summary** — total pieces, how many need action, and breakdowns by priority
  and by category.
- **Mail** — one row per piece, sorted by priority then date, with columns:

  | Column | Meaning |
  |---|---|
  | Received | Date the piece was received/scanned |
  | Sender / Recipient | Parsed from the mail exterior |
  | Location | Which Stable address received it |
  | Category | Government / Tax, Financial / Banking, Insurance, Healthcare, Utilities / Bills, Legal, Shipping / Package, Check / Payment, Marketing / Junk, Uncategorized |
  | Summary | Short description |
  | Action Needed | e.g. "Deposit check ($1,250.00)", "Time-sensitive — review and respond", "Pay by 07/25/2026", "Likely junk — shred" |
  | Priority | High / Medium / Low (color-coded), auto-escalated for checks, tax, legal, and past-due bills |
  | Amount / Due Date | Auto-extracted from the text when present |
  | Tags / Status / Notes | Stable tags, scan-notice and shred status |
  | Scan File | Filename(s) of the downloaded scan(s) |
  | Mail Item ID | Stable's id, for cross-reference |

## How categorization works

By default it's **rule-based** — fast, free, offline, and deterministic:
keyword matching over the sender, Stable's extracted data, OCR text, and tags,
plus regexes for dollar amounts and due dates. Checks, IRS/tax, and legal mail
are auto-flagged High priority; past-due bills escalate too.

With `--use-llm`, each piece is instead sent to Claude for a category, a
one-line summary, an action, and a priority — better on ambiguous mail, at the
cost of API calls. If an LLM call fails it falls back to the rule-based result.

## Field mapping / robustness

Stable's public docs describe the MailItem object
([reference](https://docs.usestable.com/docs/the-mail-item-object)) but don't
pin down every exact JSON key. The tool reads each field defensively, trying
several candidate names (see `FIELD_CANDIDATES` at the top of
`stable_mail_export.py`). If your account returns a field under a different
name, run once with `--dump-json` and adjust that small map — no other changes
needed. Pagination auto-detects cursor- or offset-style responses.

## Tests

Offline tests (no network needed) cover field extraction, categorization,
action/priority inference, pagination parsing, and spreadsheet output:

```bash
python test_stable_mail_export.py
```
