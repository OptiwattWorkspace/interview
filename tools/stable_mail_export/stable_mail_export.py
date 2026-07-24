#!/usr/bin/env python3
"""Download all mail from Stable (usestable.com), categorize it, and export a spreadsheet.

Stable exposes a REST API (https://api.usestable.com). This tool:

  1. Pages through every MailItem in your account via ``GET /v1/mail-items``.
  2. Optionally downloads the scanned PDF/image for each piece and its OCR text.
  3. Categorizes each piece (rule-based by default, or with Claude if ``--use-llm``).
  4. Derives the "action needed" plus a priority for each piece.
  5. Writes an .xlsx spreadsheet (falls back to .csv if openpyxl is unavailable),
     with a per-piece sheet and a summary sheet.

Auth is via the ``x-api-key`` header (get your key from the Stable dashboard:
Settings -> API, https://docs.usestable.com/reference/authentication).

The HTTP layer uses only the standard library, so the *download + categorize*
path has NO third-party dependencies. Install ``openpyxl`` for a real .xlsx
(otherwise you get a .csv). ``--use-llm`` additionally needs an Anthropic API key.

Example
-------
    export STABLE_API_KEY=sk_live_...
    python stable_mail_export.py --output my_mail.xlsx --download-dir ./scans

Because the Stable API's exact JSON field names are not fully published, every
field is read defensively (multiple candidate keys, nested paths). Run with
``--dump-json raw.json`` once to capture the real payload, then, if needed,
tweak the small ``FIELD_CANDIDATES`` map near the top of this file.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Configuration: defensive field lookups.
#
# The Stable "MailItem" object documents fields like scanNoticeType,
# shredDetails, checks, tags, dataExtractionResults, ocrResultUrls and location
# (https://docs.usestable.com/docs/the-mail-item-object), but not every exact
# JSON key is published. Each entry below is an ordered list of candidate keys
# (dot-paths allowed) tried in order; the first present, non-empty value wins.
# Adjust here if a real payload uses different names.
# ---------------------------------------------------------------------------
FIELD_CANDIDATES: dict[str, list[str]] = {
    "id": ["id", "mailItemId", "mail_item_id", "uuid"],
    "received": [
        "receivedAt", "received_at", "createdAt", "created_at",
        "scannedAt", "scanned_at", "date", "receivedDate",
    ],
    "sender": [
        "sender", "senderName", "sender_name", "fromName", "from_name",
        "from", "returnAddress.name", "return_address.name",
        "fromAddress.name", "senderAddress.name",
    ],
    "recipient": [
        "recipient", "recipientName", "recipient_name", "toName",
        "addressedTo", "addressed_to", "recipientAddress.name",
    ],
    "location": ["location.name", "locationName", "location_name", "location"],
    "status": ["status", "state"],
    "scan_notice_type": ["scanNoticeType", "scan_notice_type"],
    "shred_status": ["shredDetails.status", "shred_details.status", "shredStatus"],
    "tags": ["tags", "labels"],
    "checks": ["checks", "check"],
    "extraction": [
        "dataExtractionResults", "data_extraction_results",
        "extractedData", "extracted_data",
    ],
    "ocr_urls": ["ocrResultUrls", "ocr_result_urls", "ocrUrls"],
}

# Keys whose string values look like a downloadable scan/PDF/image URL.
SCAN_URL_HINTS = (
    "pdfurl", "pdf_url", "scanurl", "scan_url", "imageurl", "image_url",
    "fileurl", "file_url", "contenturl", "content_url", "downloadurl",
    "download_url", "front", "back", "envelopeurl", "envelope_url", "asseturl",
)

DEFAULT_BASE_URL = "https://api.usestable.com"
MAIL_ITEMS_PATH = "/v1/mail-items"
USER_AGENT = "stable-mail-export/1.0 (+https://github.com/OptiwattWorkspace/interview)"


# ---------------------------------------------------------------------------
# Small helpers for reading messy JSON defensively.
# ---------------------------------------------------------------------------
def _dig(obj: Any, path: str) -> Any:
    """Follow a dotted path through nested dicts; return None if any hop misses."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def field(item: dict, name: str) -> Any:
    """Return the first present, non-empty candidate value for a logical field."""
    for candidate in FIELD_CANDIDATES.get(name, []):
        value = _dig(item, candidate) if "." in candidate else item.get(candidate)
        if value not in (None, "", [], {}):
            return value
    return None


def as_text(value: Any) -> str:
    """Flatten an arbitrary JSON value into human-readable text (for display/search)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(t for t in (as_text(v) for v in value) if t)
    if isinstance(value, dict):
        # Prefer common label/value shapes, else dump compact.
        for key in ("name", "label", "value", "text", "title"):
            if key in value:
                return as_text(value[key])
        return ", ".join(f"{k}={as_text(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    return str(value)


def flatten_extraction(results: Any) -> str:
    """Flatten dataExtractionResults (list of {label,value}) into 'label: value | …' text.

    Unlike as_text(), this keeps BOTH the label and the value so downstream
    keyword/amount/date matching sees the actual extracted content.
    """
    if not results:
        return ""
    parts: list[str] = []
    items = results if isinstance(results, list) else [results]
    for r in items:
        if isinstance(r, dict):
            label = as_text(r.get("label") or r.get("key") or r.get("name") or r.get("type") or "")
            value = as_text(r.get("value") or r.get("text") or "")
            if not value and not label:
                value = as_text(r)
            piece = f"{label}: {value}".strip(": ").strip()
            if piece:
                parts.append(piece)
        else:
            t = as_text(r)
            if t:
                parts.append(t)
    return " | ".join(parts)


def tag_names(tags: Any) -> list[str]:
    out: list[str] = []
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, dict):
                out.append(as_text(t.get("name") or t.get("label") or t))
    elif tags:
        out.append(as_text(tags))
    return [t for t in out if t]


def collect_scan_urls(item: dict) -> list[str]:
    """Walk the item and collect any string values that look like scan/asset URLs."""
    found: list[str] = []

    def walk(node: Any, key_hint: str = "") -> None:
        if isinstance(node, str):
            low = node.lower()
            if low.startswith("http") and (
                key_hint in SCAN_URL_HINTS
                or any(low.endswith(ext) for ext in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"))
                or any(h in key_hint for h in ("pdf", "scan", "image", "file", "download", "asset", "front", "back"))
            ):
                found.append(node)
        elif isinstance(node, list):
            for v in node:
                walk(v, key_hint)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, str(k).lower())

    walk(item)
    # De-dup, preserve order.
    seen: set[str] = set()
    unique = []
    for url in found:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


# ---------------------------------------------------------------------------
# HTTP client (stdlib only) with retry/backoff.
# ---------------------------------------------------------------------------
class StableClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, verbose: bool = False):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose

    def _log(self, *args: Any) -> None:
        if self.verbose:
            print("[stable]", *args, file=sys.stderr)

    def get(self, path: str, params: dict | None = None, retries: int = 5) -> Any:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(url, headers={
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        delay = 2.0
        for attempt in range(1, retries + 1):
            try:
                self._log("GET", url)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:500]
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    self._log(f"HTTP {e.code}, retry {attempt}/{retries} in {delay}s")
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f"Stable API {e.code} for {url}: {body}") from e
            except urllib.error.URLError as e:
                if attempt < retries:
                    self._log(f"network error {e.reason}, retry {attempt}/{retries} in {delay}s")
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f"Network error reaching {url}: {e.reason}") from e
        raise RuntimeError(f"Exhausted retries for {url}")

    def iter_mail_items(self, page_size: int = 100, max_items: int | None = None,
                        extra_params: dict | None = None) -> Iterable[dict]:
        """Yield every mail item, transparently handling cursor- or offset-based paging."""
        params = {"limit": page_size}
        if extra_params:
            params.update(extra_params)

        yielded = 0
        cursor: str | None = None
        offset = 0
        safety_pages = 10_000  # backstop against a broken next-cursor loop

        for _ in range(safety_pages):
            page_params = dict(params)
            if cursor is not None:
                page_params["cursor"] = cursor
            else:
                # Only send offset once we've moved past page one, so a
                # cursor-only API isn't confused by an unexpected offset=0.
                if offset:
                    page_params["offset"] = offset

            payload = self.get(MAIL_ITEMS_PATH, page_params)
            items = _extract_list(payload)
            if not items:
                break

            for it in items:
                if isinstance(it, dict):
                    yield it
                    yielded += 1
                    if max_items and yielded >= max_items:
                        return

            next_cursor = _extract_next_cursor(payload)
            if next_cursor:
                cursor = next_cursor
                continue

            # No cursor -> fall back to offset paging while pages stay full.
            if len(items) < page_size:
                break
            offset += len(items)


def _extract_list(payload: Any) -> list:
    """Find the list of mail items in a variety of response envelope shapes."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "mailItems", "mail_items", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
        # Fallback: first list-valued field.
        for value in payload.values():
            if isinstance(value, list):
                return value
    return []


def _extract_next_cursor(payload: Any) -> str | None:
    """Locate a next-page cursor across common pagination envelope shapes."""
    if not isinstance(payload, dict):
        return None
    for path in (
        "nextCursor", "next_cursor", "cursor", "next",
        "paging.next", "paging.cursor", "paging.cursors.after",
        "meta.nextCursor", "meta.next_cursor", "pagination.nextCursor",
        "pagination.cursor",
    ):
        val = _dig(payload, path)
        if isinstance(val, str) and val:
            return val
    # hasMore flag with an explicit cursor field elsewhere.
    has_more = payload.get("hasMore") or payload.get("has_more")
    if has_more:
        for path in ("endCursor", "end_cursor", "lastId", "last_id"):
            val = _dig(payload, path)
            if isinstance(val, str) and val:
                return val
    return None


# ---------------------------------------------------------------------------
# Categorization + action inference (rule-based).
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    # (category, keyword substrings). Order matters — earlier wins ties.
    ("Government / Tax", (
        "irs", "internal revenue", "department of revenue", "franchise tax",
        "tax board", "ftb", "state of ", "county of", "city of", "dmv",
        "social security", "medicare.gov", "secretary of state", "uscis",
        "notice of", "1099", "w-2", "w2", "ein", "audit", "summons", "jury",
    )),
    ("Legal", (
        "law offices", "attorney", "llp", "legal", "court", "subpoena",
        "lawsuit", "litigation", "notary", "settlement", "cease and desist",
    )),
    ("Financial / Banking", (
        "bank", "chase", "wells fargo", "bank of america", "citibank",
        "capital one", "american express", "amex", "visa", "mastercard",
        "credit union", "brokerage", "fidelity", "schwab", "vanguard",
        "statement", "account", "credit card", "loan", "mortgage", "stripe",
        "paypal", "quickbooks", "invoice", "wire transfer",
    )),
    ("Insurance", (
        "insurance", "geico", "state farm", "allstate", "progressive",
        "policy", "claim", "premium", "coverage", "blue cross", "aetna",
        "cigna", "unitedhealth", "kaiser", "humana",
    )),
    ("Healthcare / Medical", (
        "medical", "health", "hospital", "clinic", "pharmacy", "doctor",
        "patient", "lab results", "prescription", "dental", "explanation of benefits",
        "eob", "physician",
    )),
    ("Utilities / Bills", (
        "electric", "utility", "utilities", "water district", "gas company",
        "pg&e", "comcast", "xfinity", "at&t", "verizon", "t-mobile",
        "internet", "past due", "amount due", "payment due", "bill",
    )),
    ("Shipping / Package", (
        "usps", "ups", "fedex", "dhl", "tracking", "package", "shipment",
        "delivery", "parcel",
    )),
    ("Marketing / Junk", (
        "offer", "promotion", "sale", "coupon", "advertis", "newsletter",
        "you're pre-approved", "pre-approved", "limited time", "act now",
        "solicitation", "presorted standard", "current resident",
    )),
]

# Categories treated as time-sensitive for priority scoring.
HIGH_PRIORITY_CATS = {"Government / Tax", "Legal"}
MEDIUM_PRIORITY_CATS = {"Financial / Banking", "Insurance", "Healthcare / Medical", "Utilities / Bills"}

DUE_DATE_RE = re.compile(
    r"(?:due\s*(?:date|by|on)?|pay\s*by|deadline|respond\s*by|expires?)\s*[:\-]?\s*"
    r"([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")


def classify(text: str, tags: list[str], has_check: bool, scan_notice: Any) -> tuple[str, str]:
    """Return (category, matched_keyword) from combined text + tags."""
    haystack = (text + " " + " ".join(tags)).lower()

    # A physical check is unambiguous and high value.
    if has_check:
        return "Check / Payment", "check present"

    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in haystack:
                return category, kw

    # Tags may already carry a category from Stable's own tagging.
    if tags:
        return "Tagged: " + tags[0], "tag"

    return "Uncategorized", ""


def infer_action(category: str, text: str, has_check: bool, scan_notice: Any,
                 shred_status: Any, amount: str | None, due_date: str | None) -> tuple[str, str]:
    """Return (action_needed, priority) — priority in {High, Medium, Low}."""
    bits: list[str] = []
    priority = "Low"

    if has_check:
        amt = f" ({amount})" if amount else ""
        bits.append(f"Deposit or forward check{amt}")
        priority = "High"
    if scan_notice:
        bits.append(f"Scan notice: {as_text(scan_notice)} — request/review full scan")
        priority = _bump(priority, "Medium")
    if shred_status and str(shred_status).lower() in ("processing", "requested", "pending"):
        bits.append("Shred in progress — confirm when complete")

    if category in HIGH_PRIORITY_CATS:
        bits.append("Time-sensitive — review and respond")
        priority = "High"
    elif category in MEDIUM_PRIORITY_CATS:
        if due_date or "due" in text.lower() or "past due" in text.lower():
            bits.append(f"Pay / respond by {due_date}" if due_date else "Check due date and pay")
            priority = _bump(priority, "High" if "past due" in text.lower() else "Medium")
        else:
            bits.append("Review document")
            priority = _bump(priority, "Medium")
    elif category == "Marketing / Junk":
        bits.append("Likely junk — shred/discard unless recognized")
    elif category == "Shipping / Package":
        bits.append("Package/shipping notice — arrange pickup or forward")
        priority = _bump(priority, "Medium")

    if due_date and not any("by" in b for b in bits):
        bits.append(f"Due: {due_date}")

    if not bits:
        bits.append("Review")

    return "; ".join(dict.fromkeys(bits)), priority  # dedup, keep order


def _bump(current: str, candidate: str) -> str:
    order = {"Low": 0, "Medium": 1, "High": 2}
    return candidate if order[candidate] > order[current] else current


# ---------------------------------------------------------------------------
# Optional: Claude-powered categorization for higher quality.
# ---------------------------------------------------------------------------
def classify_with_llm(text: str, sender: str, tags: list[str], api_key: str,
                      model: str = "claude-sonnet-5") -> dict | None:
    """Ask Claude to categorize + summarize + suggest an action. Returns dict or None."""
    prompt = (
        "You triage scanned physical mail for a business. Given the mail piece "
        "below, respond with STRICT JSON only (no prose) with keys: "
        '"category" (one of: Government / Tax, Legal, Financial / Banking, '
        "Insurance, Healthcare / Medical, Utilities / Bills, Shipping / Package, "
        "Check / Payment, Marketing / Junk, Personal, Uncategorized), "
        '"summary" (<=15 words), "action_needed" (<=20 words), '
        '"priority" (High, Medium, or Low).\n\n'
        f"Sender: {sender}\nTags: {', '.join(tags)}\n"
        f"OCR / extracted text:\n{text[:4000]}"
    )
    body = json.dumps({
        "model": model,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data.get("content", [])
        raw = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except Exception as e:  # noqa: BLE001 - LLM is best-effort; fall back to rules.
        print(f"[warn] LLM classify failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Downloading scans + OCR text.
# ---------------------------------------------------------------------------
def download_url(url: str, dest_path: str, api_key: str | None = None) -> bool:
    headers = {"User-Agent": USER_AGENT}
    # Stable asset URLs are typically pre-signed; only add the key if it's a Stable host.
    if api_key and "usestable.com" in url:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, "wb") as fh:
            fh.write(resp.read())
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[warn] failed to download {url}: {e}", file=sys.stderr)
        return False


def fetch_ocr_text(urls: Any, api_key: str) -> str:
    """OCR result URLs point at text/JSON describing the mail exterior. Concatenate them."""
    texts: list[str] = []
    if not isinstance(urls, list):
        urls = [urls] if urls else []
    for url in urls:
        if not isinstance(url, str):
            continue
        try:
            headers = {"User-Agent": USER_AGENT}
            if "usestable.com" in url:
                headers["x-api-key"] = api_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "replace")
            try:  # OCR payload may be JSON — pull out any text values.
                texts.append(as_text(json.loads(raw)))
            except json.JSONDecodeError:
                texts.append(raw)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] OCR fetch failed for {url}: {e}", file=sys.stderr)
    return "\n".join(t for t in texts if t)


# ---------------------------------------------------------------------------
# Row building.
# ---------------------------------------------------------------------------
COLUMNS = [
    "Received", "Sender", "Recipient", "Location", "Category", "Summary",
    "Action Needed", "Priority", "Amount", "Due Date", "Tags", "Status",
    "Scan File", "Mail Item ID", "Notes",
]


def build_row(item: dict, ocr_text: str, scan_files: list[str],
              llm_key: str | None, llm_model: str) -> dict:
    item_id = as_text(field(item, "id"))
    sender = as_text(field(item, "sender"))
    recipient = as_text(field(item, "recipient"))
    location = as_text(field(item, "location"))
    status = as_text(field(item, "status"))
    tags = tag_names(field(item, "tags"))
    scan_notice = field(item, "scan_notice_type")
    shred_status = field(item, "shred_status")
    checks = field(item, "checks")
    has_check = bool(checks)
    extraction_text = flatten_extraction(field(item, "extraction"))
    checks_text = as_text(checks) if has_check else ""

    received_raw = field(item, "received")
    received = _fmt_date(received_raw)

    combined = "\n".join(filter(None, [
        sender, recipient, extraction_text, checks_text, ocr_text, " ".join(tags),
    ]))

    amount_match = AMOUNT_RE.search(combined)
    amount = amount_match.group(0) if amount_match else ""
    due_match = DUE_DATE_RE.search(combined)
    due_date = due_match.group(1) if due_match else ""

    if llm_key:
        llm = classify_with_llm(combined, sender, tags, llm_key, llm_model)
    else:
        llm = None

    if llm:
        category = llm.get("category", "Uncategorized")
        summary = llm.get("summary", "")
        action = llm.get("action_needed", "")
        priority = llm.get("priority", "Low")
        if has_check and "check" not in category.lower():
            category = "Check / Payment"
    else:
        category, _kw = classify(combined, tags, has_check, scan_notice)
        action, priority = infer_action(
            category, combined, has_check, scan_notice, shred_status, amount, due_date
        )
        summary = _short_summary(sender, extraction_text or ocr_text)

    notes_bits = []
    if scan_notice:
        notes_bits.append(f"scanNotice={as_text(scan_notice)}")
    if shred_status:
        notes_bits.append(f"shred={as_text(shred_status)}")
    if has_check:
        notes_bits.append(f"checks={as_text(checks)}")

    return {
        "Received": received,
        "Sender": sender,
        "Recipient": recipient,
        "Location": location,
        "Category": category,
        "Summary": summary,
        "Action Needed": action,
        "Priority": priority,
        "Amount": amount,
        "Due Date": due_date,
        "Tags": ", ".join(tags),
        "Status": status,
        "Scan File": "; ".join(scan_files),
        "Mail Item ID": item_id,
        "Notes": "; ".join(notes_bits),
    }


def _fmt_date(raw: Any) -> str:
    if not raw:
        return ""
    s = str(raw)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.replace("+00:00", "Z"), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Epoch millis/seconds?
    if s.isdigit():
        ts = int(s)
        if ts > 1e12:
            ts /= 1000
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return s[:10]


def _short_summary(sender: str, text: str) -> str:
    base = (text or "").strip().replace("\n", " ")
    base = re.sub(r"\s+", " ", base)
    if base:
        return (base[:90] + "…") if len(base) > 90 else base
    return f"Mail from {sender}" if sender else "Scanned mail piece"


# ---------------------------------------------------------------------------
# Spreadsheet output.
# ---------------------------------------------------------------------------
def write_xlsx(rows: list[dict], path: str) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return False

    wb = Workbook()

    # --- Summary sheet ---
    summary = wb.active
    summary.title = "Summary"
    cat_counts: dict[str, int] = {}
    prio_counts: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    action_needed = 0
    for r in rows:
        cat_counts[r["Category"]] = cat_counts.get(r["Category"], 0) + 1
        prio_counts[r["Priority"]] = prio_counts.get(r["Priority"], 0) + 1
        if r["Action Needed"] and r["Action Needed"] != "Review":
            action_needed += 1

    bold = Font(bold=True, size=12)
    summary["A1"] = "Stable Mail Export — Summary"
    summary["A1"].font = Font(bold=True, size=14)
    summary["A3"] = "Total mail pieces"
    summary["B3"] = len(rows)
    summary["A4"] = "Pieces needing action"
    summary["B4"] = action_needed
    summary["A6"] = "By priority"
    summary["A6"].font = bold
    row_i = 7
    for prio in ("High", "Medium", "Low"):
        summary[f"A{row_i}"] = prio
        summary[f"B{row_i}"] = prio_counts.get(prio, 0)
        row_i += 1
    row_i += 1
    summary[f"A{row_i}"] = "By category"
    summary[f"A{row_i}"].font = bold
    row_i += 1
    for cat, cnt in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        summary[f"A{row_i}"] = cat
        summary[f"B{row_i}"] = cnt
        row_i += 1
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 12

    # --- Mail sheet ---
    ws = wb.create_sheet("Mail")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    ws.append(COLUMNS)
    for col_idx, _ in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(vertical="center")

    prio_fill = {
        "High": PatternFill("solid", fgColor="F4CCCC"),
        "Medium": PatternFill("solid", fgColor="FCE5CD"),
        "Low": PatternFill("solid", fgColor="D9EAD3"),
    }
    prio_col = COLUMNS.index("Priority") + 1
    for r in rows:
        ws.append([r.get(c, "") for c in COLUMNS])
        cell = ws.cell(row=ws.max_row, column=prio_col)
        if cell.value in prio_fill:
            cell.fill = prio_fill[cell.value]

    # Column widths (bounded) + niceties.
    widths = {c: len(c) for c in COLUMNS}
    for r in rows:
        for c in COLUMNS:
            widths[c] = max(widths[c], min(60, len(str(r.get(c, "")))))
    for col_idx, name in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = min(60, widths[name] + 2)
    for col in ("Summary", "Action Needed", "Notes"):
        letter = get_column_letter(COLUMNS.index(col) + 1)
        for row_cells in ws[letter]:
            row_cells.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{ws.max_row}"

    wb.save(path)
    return True


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in COLUMNS})


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------
def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80] or "item"


def guess_ext(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        if path.endswith(ext):
            return ext
    return ".pdf"


def run(args: argparse.Namespace) -> int:
    api_key = args.api_key or os.environ.get("STABLE_API_KEY")
    if not api_key:
        print("ERROR: provide --api-key or set STABLE_API_KEY.", file=sys.stderr)
        return 2

    llm_key = None
    if args.use_llm:
        llm_key = args.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        if not llm_key:
            print("ERROR: --use-llm needs --anthropic-key or ANTHROPIC_API_KEY.", file=sys.stderr)
            return 2

    client = StableClient(api_key, base_url=args.base_url, verbose=args.verbose)

    extra: dict[str, Any] = {}
    if args.since:
        # Sent as a hint; also filtered client-side below in case the API ignores it.
        extra["createdAtStart"] = args.since
        extra["since"] = args.since

    print("Fetching mail items from Stable…", file=sys.stderr)
    raw_items: list[dict] = []
    try:
        for item in client.iter_mail_items(page_size=args.page_size, max_items=args.max_items,
                                            extra_params=extra or None):
            raw_items.append(item)
            if args.verbose and len(raw_items) % 50 == 0:
                print(f"  …{len(raw_items)} items", file=sys.stderr)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Retrieved {len(raw_items)} mail items.", file=sys.stderr)

    if args.dump_json:
        with open(args.dump_json, "w", encoding="utf-8") as fh:
            json.dump(raw_items, fh, indent=2, default=str)
        print(f"Wrote raw payload -> {args.dump_json}", file=sys.stderr)

    if args.since:
        raw_items = [it for it in raw_items if (str(field(it, "received") or "")[:10] >= args.since)]
        print(f"{len(raw_items)} items on/after {args.since}.", file=sys.stderr)

    download_dir = None
    if not args.no_download:
        download_dir = args.download_dir
        os.makedirs(download_dir, exist_ok=True)

    rows: list[dict] = []
    for idx, item in enumerate(raw_items, start=1):
        item_id = sanitize(as_text(field(item, "id")) or str(idx))

        ocr_text = ""
        if not args.no_ocr:
            ocr_text = fetch_ocr_text(field(item, "ocr_urls"), api_key)

        scan_files: list[str] = []
        if download_dir is not None:
            for i, url in enumerate(collect_scan_urls(item)):
                fname = f"{item_id}" + (f"_{i}" if i else "") + guess_ext(url)
                dest = os.path.join(download_dir, fname)
                if download_url(url, dest, api_key):
                    scan_files.append(fname)

        rows.append(build_row(item, ocr_text, scan_files, llm_key, args.llm_model))
        if args.verbose:
            print(f"  processed {idx}/{len(raw_items)}: {rows[-1]['Category']}", file=sys.stderr)

    # Sort: highest priority first, then most recent.
    prio_order = {"High": 0, "Medium": 1, "Low": 2}
    rows.sort(key=lambda r: (prio_order.get(r["Priority"], 3), _sort_date_key(r["Received"])))

    out = args.output
    if write_xlsx(rows, out):
        print(f"\nWrote spreadsheet -> {out}", file=sys.stderr)
    else:
        csv_out = os.path.splitext(out)[0] + ".csv"
        write_csv(rows, csv_out)
        print(f"\nopenpyxl not installed; wrote CSV -> {csv_out}", file=sys.stderr)
        print("(install openpyxl for a formatted .xlsx: pip install openpyxl)", file=sys.stderr)

    needing = sum(1 for r in rows if r["Action Needed"] and r["Action Needed"] != "Review")
    print(f"Done: {len(rows)} pieces, {needing} needing action.", file=sys.stderr)
    return 0


def _sort_date_key(d: str) -> str:
    return d if d else "0000-00-00"  # blanks last within a priority tier


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download, categorize, and export Stable (usestable.com) mail to a spreadsheet.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--api-key", help="Stable API key (or set STABLE_API_KEY).")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Stable API base URL.")
    p.add_argument("--output", "-o", default="stable_mail_export.xlsx", help="Output spreadsheet path.")
    p.add_argument("--download-dir", default="./stable_mail_scans", help="Where to save scan files.")
    p.add_argument("--no-download", action="store_true", help="Do not download scan files.")
    p.add_argument("--no-ocr", action="store_true", help="Do not fetch OCR text (faster, less accurate).")
    p.add_argument("--page-size", type=int, default=100, help="Items per API page.")
    p.add_argument("--max-items", type=int, default=None, help="Cap total items (for testing).")
    p.add_argument("--since", help="Only include mail on/after this date (YYYY-MM-DD).")
    p.add_argument("--dump-json", help="Also write the raw API payload to this file (for debugging fields).")
    p.add_argument("--use-llm", action="store_true", help="Use Claude to categorize (needs ANTHROPIC_API_KEY).")
    p.add_argument("--anthropic-key", help="Anthropic API key for --use-llm (or set ANTHROPIC_API_KEY).")
    p.add_argument("--llm-model", default="claude-sonnet-5", help="Model id for --use-llm.")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose progress logging.")
    return p


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
