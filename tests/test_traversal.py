# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ancestry / descendancy traversal helpers."""

from __future__ import annotations

from gedcom_lite import (
    GedcomDocument,
    ancestors_of,
    children_of,
    descendants_of,
    parents_of,
)


def _three_generation_doc() -> GedcomDocument:
    """A small synthetic family tree:
        @I1@ (grandfather) + @I2@ (grandmother)  -- @F1@
            └── @I3@ (parent)
        @I3@ (parent) + @I4@ (other parent)  -- @F2@
            └── @I5@ (child)
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Grandpa /A/\n1 SEX M\n1 FAMS @F1@\n"
        b"0 @I2@ INDI\n1 NAME Grandma /B/\n1 SEX F\n1 FAMS @F1@\n"
        b"0 @I3@ INDI\n1 NAME Parent /A/\n1 FAMC @F1@\n1 FAMS @F2@\n"
        b"0 @I4@ INDI\n1 NAME Parent /C/\n1 FAMS @F2@\n"
        b"0 @I5@ INDI\n1 NAME Child /A/\n1 FAMC @F2@\n"
        b"0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I3@\n"
        b"0 @F2@ FAM\n1 HUSB @I3@\n1 WIFE @I4@\n1 CHIL @I5@\n"
        b"0 TRLR\n"
    )
    return GedcomDocument.parse(src)


class TestParents:
    def test_parents_of_grandchild(self) -> None:
        doc = _three_generation_doc()
        child = doc.resolve("@I5@")
        parents = parents_of(doc, child)
        xrefs = sorted(p.xref for p in parents)
        assert xrefs == ["@I3@", "@I4@"]

    def test_parents_of_root_is_empty(self) -> None:
        doc = _three_generation_doc()
        grandfather = doc.resolve("@I1@")
        assert parents_of(doc, grandfather) == []


class TestChildren:
    def test_children_of_grandfather(self) -> None:
        doc = _three_generation_doc()
        gf = doc.resolve("@I1@")
        kids = children_of(doc, gf)
        xrefs = sorted(c.xref for c in kids)
        assert xrefs == ["@I3@"]

    def test_children_of_leaf_is_empty(self) -> None:
        doc = _three_generation_doc()
        child = doc.resolve("@I5@")
        assert children_of(doc, child) == []


class TestAncestors:
    def test_full_chain(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        anc = ancestors_of(doc, c)
        xrefs = sorted(a.xref for a in anc)
        assert xrefs == ["@I1@", "@I2@", "@I3@", "@I4@"]

    def test_depth_limit(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        anc = ancestors_of(doc, c, depth=1)
        xrefs = sorted(a.xref for a in anc)
        assert xrefs == ["@I3@", "@I4@"]


class TestDescendants:
    def test_full_chain(self) -> None:
        doc = _three_generation_doc()
        gf = doc.resolve("@I1@")
        des = descendants_of(doc, gf)
        xrefs = sorted(d.xref for d in des)
        assert xrefs == ["@I3@", "@I5@"]

    def test_depth_limit(self) -> None:
        doc = _three_generation_doc()
        gf = doc.resolve("@I1@")
        des = descendants_of(doc, gf, depth=1)
        xrefs = sorted(d.xref for d in des)
        assert xrefs == ["@I3@"]
