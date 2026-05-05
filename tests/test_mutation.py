# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for mutation primitives and round-trip fidelity under edits."""

from __future__ import annotations

from pathlib import Path

import pytest

from gedcom_lite import GedcomDocument


class TestSetPayload:
    def test_changes_only_targeted_line(self, examples_root: Path) -> None:
        path = examples_root / "gedcom70" / "maximal70.ged"
        raw = path.read_bytes().decode("utf-8-sig").splitlines()
        doc = GedcomDocument.parse(path)
        indi = next(r for r in doc.records if r.tag == "INDI")
        name = indi.find("NAME")
        assert name is not None
        name.set_payload("Test /Mutated/")
        out = doc.write().decode("utf-8-sig").splitlines()
        assert len(raw) == len(out), "line count must not change"
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(raw, out)) if a != b]
        assert len(diffs) == 1, f"expected exactly 1 line to differ, got {diffs}"
        assert "Test /Mutated/" in diffs[0][2]

    def test_set_to_empty_string(self, examples_root: Path) -> None:
        doc = GedcomDocument.parse(examples_root / "gedcom70" / "maximal70.ged")
        indi = doc.find_records("INDI")[0]
        name = indi.find("NAME")
        assert name is not None
        name.set_payload("")
        # Writer should still emit the line, just with no payload.
        out = doc.write().decode("utf-8-sig")
        assert "1 NAME\n" in out


class TestAddChild:
    def test_appends_new_substructure(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 TRLR\n")
        indi = doc.resolve("@I1@")
        indi.add_child("NAME", "Jane /Doe/")
        out = doc.write().decode("utf-8")
        assert "0 @I1@ INDI\n1 NAME Jane /Doe/\n" in out

    def test_correct_level(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 TRLR\n")
        indi = doc.resolve("@I1@")
        birt = indi.add_child("BIRT")
        date = birt.add_child("DATE", "1 JAN 1900")
        assert birt.level == 1
        assert date.level == 2
        out = doc.write().decode("utf-8")
        assert "1 BIRT\n2 DATE 1 JAN 1900\n" in out


class TestRemove:
    def test_removes_substructure(self) -> None:
        doc = GedcomDocument.parse(
            b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n1 NAME Jane /Doe/\n1 SEX F\n0 TRLR\n"
        )
        indi = doc.resolve("@I1@")
        sex = indi.find("SEX")
        sex.remove()
        out = doc.write().decode("utf-8")
        assert "1 NAME Jane /Doe/" in out
        assert "1 SEX" not in out

    def test_top_level_remove_raises(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 TRLR\n")
        indi = doc.resolve("@I1@")
        with pytest.raises(ValueError):
            indi.remove()


class TestAddRecord:
    def test_auto_xref_for_indi(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 TRLR\n")
        rec = doc.add_record("INDI")
        assert rec.xref == "@I1@"

    def test_auto_xref_for_fam(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 TRLR\n")
        rec = doc.add_record("FAM")
        assert rec.xref == "@F1@"

    def test_auto_xref_avoids_collision(self) -> None:
        doc = GedcomDocument.parse(
            b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 @I2@ INDI\n0 TRLR\n"
        )
        rec = doc.add_record("INDI")
        assert rec.xref == "@I3@"

    def test_explicit_xref(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 TRLR\n")
        rec = doc.add_record("INDI", xref="@MYID@")
        assert rec.xref == "@MYID@"

    def test_duplicate_xref_raises(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 TRLR\n")
        with pytest.raises(ValueError):
            doc.add_record("INDI", xref="@I1@")


class TestRemoveRecord:
    def test_basic(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n0 TRLR\n")
        doc.remove_record("@I1@")
        assert doc.resolve("@I1@") is None
        out = doc.write().decode("utf-8")
        assert "@I1@" not in out

    def test_unknown_xref_raises(self) -> None:
        doc = GedcomDocument.parse(b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 TRLR\n")
        with pytest.raises(KeyError):
            doc.remove_record("@MISSING@")


class TestInboundPointers:
    def test_finds_pointers_in_other_records(self) -> None:
        doc = GedcomDocument.parse(
            b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
            b"0 @I1@ INDI\n"
            b"0 @F1@ FAM\n1 HUSB @I1@\n"
            b"0 TRLR\n"
        )
        ptrs = doc.inbound_pointers("@I1@")
        assert len(ptrs) == 1
        assert ptrs[0].tag == "HUSB"

    def test_void_is_not_an_inbound_pointer(self) -> None:
        doc = GedcomDocument.parse(
            b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
            b"0 @I1@ INDI\n1 ASSO @VOID@\n"
            b"0 TRLR\n"
        )
        # @I1@ has no real inbound pointers, only a VOID outbound.
        assert doc.inbound_pointers("@I1@") == []
