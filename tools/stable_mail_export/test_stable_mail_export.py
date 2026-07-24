#!/usr/bin/env python3
"""Offline tests for stable_mail_export using synthetic MailItem payloads.

These exercise the parts that don't need network access: defensive field
extraction, categorization, action/priority inference, and spreadsheet output.
Run: python test_stable_mail_export.py
"""
import os
import sys
import tempfile

import stable_mail_export as m

# Synthetic payloads modeled on the documented MailItem shape, with a few field
# name variations to prove the defensive extraction works.
SAMPLES = [
    {
        "id": "mi_check_1",
        "receivedAt": "2026-07-20T14:00:00Z",
        "sender": "Acme Corp Accounts Payable",
        "recipient": "Optiwatt Inc",
        "location": {"name": "San Francisco HQ"},
        "checks": [{"amount": "$1,250.00", "number": "4021"}],
        "tags": [{"name": "finance"}],
    },
    {
        "id": "mi_irs_1",
        "created_at": "2026-07-18T09:00:00Z",
        "senderName": "Internal Revenue Service",
        "dataExtractionResults": [{"label": "Notice", "value": "CP2000 Notice - respond by Aug 15, 2026"}],
    },
    {
        "id": "mi_bank_1",
        "receivedDate": "2026-07-15",
        "from": {"name": "Chase Bank"},
        "dataExtractionResults": [{"label": "Doc", "value": "Monthly account statement, balance $5,342.10"}],
    },
    {
        "id": "mi_util_1",
        "receivedAt": "2026-07-10T00:00:00Z",
        "sender": "PG&E",
        "extractedData": [{"value": "PAST DUE amount due $214.55 pay by 07/25/2026"}],
    },
    {
        "id": "mi_junk_1",
        "receivedAt": "2026-07-05T00:00:00Z",
        "sender": "Current Resident",
        "dataExtractionResults": [{"value": "You're pre-approved! Limited time offer, act now"}],
    },
    {
        "id": "mi_pkg_1",
        "receivedAt": "2026-07-03T00:00:00Z",
        "sender": "FedEx",
        "scanNoticeType": "package_received",
        "dataExtractionResults": [{"value": "Package tracking 7712 delivery pending"}],
    },
    {
        "id": "mi_ins_1",
        "receivedAt": "2026-07-01T00:00:00Z",
        "sender": "State Farm Insurance",
        "shredDetails": {"status": "processing"},
        "dataExtractionResults": [{"value": "Policy renewal coverage summary"}],
    },
]


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}")
    return cond


def main():
    ok = True

    # --- Field extraction across varying key names ---
    print("Field extraction:")
    ok &= check("nested location.name", m.as_text(m.field(SAMPLES[0], "location")) == "San Francisco HQ")
    ok &= check("senderName variant", m.field(SAMPLES[1], "sender") == "Internal Revenue Service")
    ok &= check("from.name variant", m.as_text(m.field(SAMPLES[2], "sender")) == "Chase Bank")
    ok &= check("created_at date fmt", m._fmt_date(m.field(SAMPLES[1], "received")) == "2026-07-18")
    ok &= check("tags flatten", m.tag_names(m.field(SAMPLES[0], "tags")) == ["finance"])

    # --- Categorization + actions ---
    print("Categorization & actions:")
    rows = [m.build_row(s, ocr_text="", scan_files=[], llm_key=None, llm_model="") for s in SAMPLES]
    by_id = {r["Mail Item ID"]: r for r in rows}

    ok &= check("check -> Check / Payment", by_id["mi_check_1"]["Category"] == "Check / Payment")
    ok &= check("check -> High priority", by_id["mi_check_1"]["Priority"] == "High")
    ok &= check("check amount detected", by_id["mi_check_1"]["Amount"] == "$1,250.00")

    ok &= check("IRS -> Government / Tax", by_id["mi_irs_1"]["Category"] == "Government / Tax")
    ok &= check("IRS -> High priority", by_id["mi_irs_1"]["Priority"] == "High")
    ok &= check("IRS due date parsed", by_id["mi_irs_1"]["Due Date"] == "Aug 15, 2026")

    ok &= check("Chase -> Financial / Banking", by_id["mi_bank_1"]["Category"] == "Financial / Banking")

    ok &= check("PG&E -> Utilities / Bills", by_id["mi_util_1"]["Category"] == "Utilities / Bills")
    ok &= check("past due -> High priority", by_id["mi_util_1"]["Priority"] == "High")
    ok &= check("util amount detected", by_id["mi_util_1"]["Amount"] == "$214.55")

    ok &= check("junk -> Marketing / Junk", by_id["mi_junk_1"]["Category"] == "Marketing / Junk")
    ok &= check("junk -> Low priority", by_id["mi_junk_1"]["Priority"] == "Low")

    ok &= check("FedEx -> Shipping / Package", by_id["mi_pkg_1"]["Category"] == "Shipping / Package")
    ok &= check("scan notice in action", "notice" in by_id["mi_pkg_1"]["Action Needed"].lower())

    ok &= check("State Farm -> Insurance", by_id["mi_ins_1"]["Category"] == "Insurance")
    ok &= check("shred noted", "shred" in by_id["mi_ins_1"]["Notes"].lower())

    # --- Pagination envelope parsing ---
    print("Pagination helpers:")
    ok &= check("extract data[]", m._extract_list({"data": [1, 2]}) == [1, 2])
    ok &= check("extract bare list", m._extract_list([1, 2]) == [1, 2])
    ok &= check("extract mailItems[]", m._extract_list({"mailItems": [{"id": "x"}]}) == [{"id": "x"}])
    ok &= check("next cursor nested", m._extract_next_cursor({"paging": {"cursors": {"after": "abc"}}}) == "abc")
    ok &= check("no cursor -> None", m._extract_next_cursor({"data": []}) is None)

    # --- Scan URL discovery ---
    print("Scan URL discovery:")
    urls = m.collect_scan_urls({"pdfUrl": "https://x.com/a.pdf", "misc": {"frontImageUrl": "https://x.com/b.png"}})
    ok &= check("finds pdf + image urls", set(urls) == {"https://x.com/a.pdf", "https://x.com/b.png"})

    # --- Spreadsheet output ---
    print("Spreadsheet output:")
    tmp = tempfile.mkdtemp()
    xlsx_path = os.path.join(tmp, "out.xlsx")
    wrote_xlsx = m.write_xlsx(rows, xlsx_path)
    if wrote_xlsx:
        ok &= check("xlsx written & non-empty", os.path.getsize(xlsx_path) > 0)
    else:
        print("  [SKIP] openpyxl not installed; testing CSV fallback")
    csv_path = os.path.join(tmp, "out.csv")
    m.write_csv(rows, csv_path)
    with open(csv_path) as fh:
        content = fh.read()
    ok &= check("csv has header", content.startswith("Received,Sender"))
    ok &= check("csv has all rows", content.count("\n") >= len(rows) + 1)

    print()
    if ok:
        print("ALL TESTS PASSED")
        return 0
    print("SOME TESTS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
