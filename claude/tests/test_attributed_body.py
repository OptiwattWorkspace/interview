"""attributedBody decoding.

The blobs here are synthesized to match the layout Messages produces.
They are not captured from a real database, so passing tests prove the
parser handles the documented format — not that the format is identical
on every macOS version. ``python -m taskbot doctor`` is what validates
this against real data.
"""

from __future__ import annotations

from taskbot.imessage.attributed_body import decode

PREFIX = (
    b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01\x40\x84\x84\x84"
    b"\x12NSAttributedString\x00\x84\x84\x08NSObject\x00\x85\x92"
    b"\x84\x84\x84\x08NSString\x01\x94\x84\x01"
)
SUFFIX = b"\x86\x84\x02iI\x01\x00\x84\x84\x0cNSDictionary\x00"


def blob(text: str) -> bytes:
    """Build a typedstream blob carrying ``text``."""
    encoded = text.encode("utf-8")
    if len(encoded) < 0x80:
        length = bytes([len(encoded)])
    elif len(encoded) < 0x10000:
        length = b"\x81" + len(encoded).to_bytes(2, "little")
    else:
        length = b"\x82" + len(encoded).to_bytes(4, "little")
    return PREFIX + b"\x2b" + length + encoded + SUFFIX


def test_decodes_short_message():
    assert decode(blob("/tasks")) == "/tasks"


def test_decodes_sentence():
    text = "can you add pick up dry cleaning by friday"
    assert decode(blob(text)) == text


def test_decodes_emoji():
    assert decode(blob("done ✓ 🎉")) == "done ✓ 🎉"


def test_decodes_accented_text():
    assert decode(blob("café résumé")) == "café résumé"


def test_decodes_long_message_with_two_byte_length():
    text = "x" * 500
    assert decode(blob(text)) == text


def test_decodes_very_long_message_with_four_byte_length():
    text = "y" * 70_000
    assert decode(blob(text)) == text


def test_multibyte_character_at_length_boundary():
    """Length is in bytes, not characters — an easy off-by-one."""
    text = "é" * 100
    assert decode(blob(text)) == text


def test_none_returns_none():
    assert decode(None) is None


def test_empty_returns_none():
    assert decode(b"") is None


def test_blob_without_nsstring_returns_none():
    assert decode(b"\x04\x0bstreamtyped\x81\xe8\x03") is None


def test_truncated_blob_does_not_raise():
    assert decode(blob("hello")[:20]) is None


def test_declared_length_past_end_of_blob():
    """A corrupt length must not read past the buffer."""
    bad = PREFIX + b"\x2b" + b"\x81" + (9999).to_bytes(2, "little") + b"short"
    assert decode(bad) in (None, "short")


def test_salvage_recovers_text_when_structure_is_unexpected():
    """When the length prefix is missing, fall back to scraping."""
    weird = b"\x04\x0bstreamtyped" + b"NSString" + b"\x00\x00" + \
        b"pick up the package" + b"__kIMMessagePartAttributeName"
    assert "pick up the package" in (decode(weird) or "")


def test_salvage_returns_none_on_binary_noise():
    noise = b"NSString" + bytes(range(0, 16)) + b"__kIM"
    assert decode(noise) is None
