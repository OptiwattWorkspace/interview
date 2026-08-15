"""Decode message text out of the ``attributedBody`` column.

Since macOS Ventura, most messages leave ``message.text`` NULL and store
their content in ``attributedBody`` — an archived ``NSAttributedString``
in Apple's legacy *typedstream* format. Fully parsing typedstream is a
project in itself; we only need the first string in the archive, which is
the message body.

Layout we care about, after the ``NSString`` class name:

    ... "NSString" ... 0x2b <length> <utf-8 bytes>

where ``<length>`` is a single byte below 0x80, or a 0x81/0x82 marker
followed by a little-endian 2- or 4-byte count.
"""

from __future__ import annotations

import re

_MARKER = b"\x2b"  # '+' — typedstream's tag for inline bytes


def decode(blob: bytes | None) -> str | None:
    """Extract the message body from an attributedBody blob.

    Args:
        blob: Raw bytes from the ``attributedBody`` column.

    Returns:
        The decoded text, or None if nothing could be recovered.
    """
    if not blob:
        return None

    text = _decode_typedstream(blob)
    if text is not None:
        return text
    return _salvage(blob)


def _decode_typedstream(blob: bytes) -> str | None:
    """Read the length-prefixed string that follows the NSString tag."""
    start = blob.find(b"NSString")
    if start == -1:
        return None

    pos = blob.find(_MARKER, start)
    if pos == -1 or pos + 1 >= len(blob):
        return None
    pos += 1

    length = blob[pos]
    pos += 1
    if length == 0x81:
        if pos + 2 > len(blob):
            return None
        length = int.from_bytes(blob[pos:pos + 2], "little")
        pos += 2
    elif length == 0x82:
        if pos + 4 > len(blob):
            return None
        length = int.from_bytes(blob[pos:pos + 4], "little")
        pos += 4
    elif length >= 0x80:
        # Some other multi-byte encoding we don't handle.
        return None

    if length == 0 or pos + length > len(blob):
        return None

    try:
        return blob[pos:pos + length].decode("utf-8")
    except UnicodeDecodeError:
        return None


# Archive scaffolding that must never be mistaken for message text.
_STRUCTURAL = (
    b"streamtyped",
    b"NSAttributedString",
    b"NSMutableAttributedString",
    b"NSMutableString",
    b"NSAttributeDictionary",
    b"NSDictionary",
    b"NSMutableDictionary",
    b"NSObject",
    b"NSNumber",
    b"NSValue",
    b"NSString",
    b"NSArray",
    b"NSFont",
    b"__kIM",
)


def _salvage(blob: bytes) -> str | None:
    """Last-ditch extraction for blobs the parser above can't read.

    Pulls the longest run of printable text between the NSString tag and
    the trailing attribute-run metadata. Lossy, and deliberately
    conservative: returning None is much better than returning archive
    scaffolding, which the command layer would then try to interpret.
    """
    start = blob.find(b"NSString")
    if start == -1:
        # Without the tag there is no reliable place to start reading.
        return None

    region = blob[start + len(b"NSString"):]
    for tail in _STRUCTURAL:
        cut = region.find(tail)
        if cut != -1:
            region = region[:cut]

    candidates = re.findall(rb"[\x20-\x7e\xc2-\xf4][\x20-\x7e\x80-\xbf]{3,}", region)
    for candidate in sorted(candidates, key=len, reverse=True):
        text = candidate.decode("utf-8", errors="ignore")
        # Drop leading typedstream punctuation ('+', quotes, padding).
        text = re.sub(r"^[^0-9A-Za-zÀ-￿]+", "", text).strip()
        if len(text) < 2 or any(tok.decode() in text for tok in _STRUCTURAL):
            continue
        return text
    return None
