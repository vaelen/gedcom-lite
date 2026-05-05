# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""ANSEL codec tests."""

from __future__ import annotations

import unicodedata

from gedcom_lite.ansel import decode_ansel, encode_ansel


class TestDecode:
    def test_pure_ascii_passes_through(self) -> None:
        assert decode_ansel(b"hello world") == "hello world"

    def test_combining_diaeresis_before_base(self) -> None:
        # ANSEL: 0xE8 (diaeresis combining) then 0x75 (u) → "ü"
        assert decode_ansel(b"M\xe8ull" + b"er") == "Müller"

    def test_combining_acute(self) -> None:
        # 0xE2 = acute. "Béland" = B é(0xE2 e) l a n d
        assert decode_ansel(b"B\xe2eland") == "Béland"

    def test_precomposed_special(self) -> None:
        # 0xA5 = Æ
        assert decode_ansel(b"\xa5sop") == "Æsop"

    def test_unknown_byte_is_replacement(self) -> None:
        # 0x80 isn't in our table.
        result = decode_ansel(b"x\x80y")
        assert "�" in result

    def test_orphan_combining_at_end_dropped(self) -> None:
        # Combining mark with no base after it should not produce a fake char.
        result = decode_ansel(b"abc\xe8")
        assert result.startswith("abc")


class TestEncode:
    def test_pure_ascii_passes_through(self) -> None:
        assert encode_ansel("hello world") == b"hello world"

    def test_combining_marks_emit_before_base(self) -> None:
        encoded = encode_ansel("Müller")
        # First non-ASCII byte should be 0xE8 (diaeresis), positioned BEFORE the u.
        assert encoded == b"M\xe8uller"

    def test_acute_e(self) -> None:
        assert encode_ansel("Béland") == b"B\xe2eland"

    def test_precomposed_uses_table(self) -> None:
        # Æ should map to 0xA5 directly, not decompose.
        assert encode_ansel("Æsop") == b"\xa5sop"

    def test_unmappable_falls_back_to_question_mark(self) -> None:
        # Snowman ☃ has no ANSEL mapping nor decomposition.
        encoded = encode_ansel("a☃b")
        assert encoded == b"a?b"

    def test_round_trip_preserves_text_after_nfc(self) -> None:
        for sample in [
            "Hans Müller",
            "Béland",
            "Élise",
            "Æsop and Œuvre",
            "café résumé naïve",
        ]:
            roundtripped = decode_ansel(encode_ansel(sample))
            # Decode produces NFC; original may be NFC already, but compare in NFC.
            assert roundtripped == unicodedata.normalize("NFC", sample)
