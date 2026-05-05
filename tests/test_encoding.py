# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Encoding detection tests for ``_detect_and_decode``."""

from __future__ import annotations

from gedcom_lite.core import (
    UTF8_BOM,
    UTF16_BE_BOM,
    UTF16_LE_BOM,
    _detect_and_decode,
)


def _make_5_5_5_text(char: str = "UTF-8") -> str:
    return (
        "0 HEAD\n"
        "1 GEDC\n"
        "2 VERS 5.5.5\n"
        "2 FORM LINEAGE-LINKED\n"
        "3 VERS 5.5.5\n"
        f"1 CHAR {char}\n"
        "0 TRLR\n"
    )


def _make_7_text() -> str:
    return "0 HEAD\n1 GEDC\n2 VERS 7.0\n0 TRLR\n"


class TestEncodingDetection:
    def test_utf8_bom(self) -> None:
        raw = UTF8_BOM + _make_7_text().encode("utf-8")
        d = _detect_and_decode(raw)
        assert d.encoding == "utf-8-sig"
        assert d.bom == UTF8_BOM
        assert "0 HEAD" in d.text
        # BOM is stripped from decoded text.
        assert not d.text.startswith("﻿")

    def test_utf8_no_bom(self) -> None:
        raw = _make_7_text().encode("utf-8")
        d = _detect_and_decode(raw)
        assert d.encoding == "utf-8"
        assert d.bom == b""

    def test_ascii_when_declared(self) -> None:
        raw = _make_5_5_5_text(char="ASCII").encode("ascii")
        d = _detect_and_decode(raw)
        assert d.encoding == "ascii"
        assert d.declared_char == "ASCII"

    def test_utf16_le_bom(self) -> None:
        raw = UTF16_LE_BOM + _make_5_5_5_text().encode("utf-16-le")
        d = _detect_and_decode(raw)
        assert d.encoding == "utf-16-le"
        assert d.bom == UTF16_LE_BOM
        assert "0 HEAD" in d.text

    def test_utf16_be_bom(self) -> None:
        raw = UTF16_BE_BOM + _make_5_5_5_text().encode("utf-16-be")
        d = _detect_and_decode(raw)
        assert d.encoding == "utf-16-be"
        assert d.bom == UTF16_BE_BOM
        assert "0 HEAD" in d.text

    def test_unicode_declared_means_utf16(self) -> None:
        # Legacy 5.5.1 convention: CHAR UNICODE without BOM = UTF-16 LE.
        raw = _make_5_5_5_text(char="UNICODE").encode("utf-16-le")
        d = _detect_and_decode(raw)
        assert d.encoding == "utf-16-le"
        assert d.declared_char == "UNICODE"

    def test_ansel_declared(self) -> None:
        from gedcom_lite.ansel import encode_ansel

        text = _make_5_5_5_text(char="ANSEL")
        raw = encode_ansel(text)
        d = _detect_and_decode(raw)
        assert d.encoding == "ansel"
        assert d.declared_char == "ANSEL"

    def test_declared_char_extracted_from_header(self) -> None:
        raw = _make_5_5_5_text(char="UTF-8").encode("utf-8")
        d = _detect_and_decode(raw)
        # UTF-8 with explicit CHAR=UTF-8 should read it back.
        assert d.declared_char == "UTF-8"
