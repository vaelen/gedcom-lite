# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Unit tests for the line tokenizer."""

from __future__ import annotations

import pytest

from gedcom_lite.core import _split_lines, _predominant_terminator, _tokenize


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_simple_line(self) -> None:
        t = _tokenize("1 NAME John /Smith/")
        assert t.level == 1
        assert t.xref is None
        assert t.tag == "NAME"
        assert t.payload == "John /Smith/"

    def test_record_line_with_xref(self) -> None:
        t = _tokenize("0 @I1@ INDI")
        assert t.level == 0
        assert t.xref == "@I1@"
        assert t.tag == "INDI"
        assert t.payload is None

    def test_no_payload(self) -> None:
        t = _tokenize("0 TRLR")
        assert t.level == 0
        assert t.tag == "TRLR"
        assert t.payload is None

    def test_pointer_payload(self) -> None:
        t = _tokenize("1 FAMS @F1@")
        assert t.tag == "FAMS"
        assert t.payload == "@F1@"

    def test_multi_digit_level(self) -> None:
        t = _tokenize("12 DEEP yes")
        assert t.level == 12
        assert t.tag == "DEEP"
        assert t.payload == "yes"

    def test_payload_with_spaces(self) -> None:
        t = _tokenize("1 ADDR 1 Main Street, Anytown")
        assert t.tag == "ADDR"
        assert t.payload == "1 Main Street, Anytown"

    def test_payload_with_leading_at_doubled(self) -> None:
        # Leading @ is doubled to @@ so it's not confused with a pointer.
        t = _tokenize("1 NOTE @@me is an example handle")
        assert t.tag == "NOTE"
        assert t.payload == "@@me is an example handle"

    def test_extension_tag(self) -> None:
        t = _tokenize("1 _SKYPEID someuser")
        assert t.tag == "_SKYPEID"
        assert t.payload == "someuser"

    def test_xref_with_special_chars(self) -> None:
        # GEDCOM 7 removed length limits; weird-but-legal xrefs should parse.
        t = _tokenize("0 @ABC.123_X@ INDI")
        assert t.xref == "@ABC.123_X@"

    # error paths

    def test_missing_level(self) -> None:
        with pytest.raises(ValueError):
            _tokenize("NAME John")

    def test_unterminated_xref(self) -> None:
        with pytest.raises(ValueError):
            _tokenize("0 @I1 INDI")

    def test_missing_space_after_xref(self) -> None:
        with pytest.raises(ValueError):
            _tokenize("0 @I1@INDI")

    def test_empty_tag_after_level(self) -> None:
        with pytest.raises(ValueError):
            _tokenize("0 ")


# ---------------------------------------------------------------------------
# _split_lines
# ---------------------------------------------------------------------------

class TestSplitLines:
    def test_lf(self) -> None:
        lines, terms = _split_lines("a\nb\nc\n")
        assert lines == ["a", "b", "c"]
        assert terms == ["\n", "\n", "\n"]

    def test_crlf(self) -> None:
        lines, terms = _split_lines("a\r\nb\r\n")
        assert lines == ["a", "b"]
        assert terms == ["\r\n", "\r\n"]

    def test_cr_only(self) -> None:
        lines, terms = _split_lines("a\rb\r")
        assert lines == ["a", "b"]
        assert terms == ["\r", "\r"]

    def test_mixed_terminators(self) -> None:
        lines, terms = _split_lines("a\nb\r\nc\rd")
        assert lines == ["a", "b", "c", "d"]
        assert terms == ["\n", "\r\n", "\r", ""]

    def test_blank_lines_dropped(self) -> None:
        lines, _ = _split_lines("a\n\nb\n")
        assert lines == ["a", "b"]

    def test_no_trailing_terminator(self) -> None:
        lines, terms = _split_lines("a\nb")
        assert lines == ["a", "b"]
        assert terms[-1] == ""


class TestPredominantTerminator:
    def test_picks_majority(self) -> None:
        assert _predominant_terminator(["\n", "\n", "\r\n"]) == "\n"
        assert _predominant_terminator(["\r\n", "\r\n", "\n"]) == "\r\n"

    def test_default_lf_when_empty(self) -> None:
        assert _predominant_terminator([""]) == "\n"
