# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ancestry / descendancy traversal helpers."""

from __future__ import annotations

from gedcom_lite import (
    GedcomDocument,
    ahnentafel,
    ancestors_of,
    ancestors_of_with_generation,
    children_of,
    descendants_of,
    descendants_of_with_generation,
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


def _multi_famc_doc() -> GedcomDocument:
    """An individual @I1@ with two FAMC entries pointing to two distinct
    sets of parents (@F1@ primary, @F2@ secondary).
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Subject /S/\n1 FAMC @F1@\n1 FAMC @F2@\n"
        b"0 @I2@ INDI\n1 NAME Primary Father /P/\n1 SEX M\n1 FAMS @F1@\n"
        b"0 @I3@ INDI\n1 NAME Primary Mother /P/\n1 SEX F\n1 FAMS @F1@\n"
        b"0 @I4@ INDI\n1 NAME Secondary Father /S/\n1 SEX M\n1 FAMS @F2@\n"
        b"0 @I5@ INDI\n1 NAME Secondary Mother /S/\n1 SEX F\n1 FAMS @F2@\n"
        b"0 @F1@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I1@\n"
        b"0 @F2@ FAM\n1 HUSB @I4@\n1 WIFE @I5@\n1 CHIL @I1@\n"
        b"0 TRLR\n"
    )
    return GedcomDocument.parse(src)


def _cousin_marriage_doc() -> GedcomDocument:
    """A cousin marriage where @I1@'s common ancestor is reachable at
    two different depths through different paths.

        @I9@ (root)
          ├── @I7@ (parent of cousin A)
          │     └── @I3@ (cousin A → father of @I1@)
          └── @I8@ (parent of cousin B)
                └── @I4@ (cousin B → mother of @I1@)

    Plus a direct extra link: @I9@ also directly fathers @I3@'s spouse — no,
    keep it simple: @I9@ is a great-grandparent on one side and a grandparent
    on the other (we wire @I9@ as direct parent of @I4@ for asymmetry).

    Final shape:
        @I1@ (subject) FAMC @F0@
        @F0@: @I3@ + @I4@ → @I1@
        @I3@ FAMC @F1@; @F1@: @I5@ + @I6@ → @I3@
        @I4@ FAMC @F2@; @F2@: @I9@ + @I8@ → @I4@   (so @I9@ is grandparent on mom side: gen 2)
        @I5@ FAMC @F3@; @F3@: @I9@ + @I7@ → @I5@   (so @I9@ is great-grandparent on dad side: gen 3)

    Shortest-path generation for @I9@ should be 2.
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Subject //\n1 FAMC @F0@\n"
        b"0 @I3@ INDI\n1 NAME Father //\n1 FAMC @F1@\n1 FAMS @F0@\n"
        b"0 @I4@ INDI\n1 NAME Mother //\n1 FAMC @F2@\n1 FAMS @F0@\n"
        b"0 @I5@ INDI\n1 NAME PaternalGF //\n1 FAMC @F3@\n1 FAMS @F1@\n"
        b"0 @I6@ INDI\n1 NAME PaternalGM //\n1 FAMS @F1@\n"
        b"0 @I7@ INDI\n1 NAME GreatGM //\n1 FAMS @F3@\n"
        b"0 @I8@ INDI\n1 NAME MaternalGM //\n1 FAMS @F2@\n"
        b"0 @I9@ INDI\n1 NAME Common //\n1 FAMS @F2@\n1 FAMS @F3@\n"
        b"0 @F0@ FAM\n1 HUSB @I3@\n1 WIFE @I4@\n1 CHIL @I1@\n"
        b"0 @F1@ FAM\n1 HUSB @I5@\n1 WIFE @I6@\n1 CHIL @I3@\n"
        b"0 @F2@ FAM\n1 HUSB @I9@\n1 WIFE @I8@\n1 CHIL @I4@\n"
        b"0 @F3@ FAM\n1 HUSB @I9@\n1 WIFE @I7@\n1 CHIL @I5@\n"
        b"0 TRLR\n"
    )
    return GedcomDocument.parse(src)


def _descent_filter_doc() -> GedcomDocument:
    """A child @I5@ who is listed as CHIL of two families, but whose primary
    FAMC is @F2@ (not @F1@). When @I1@ asks for descendants with
    primary_famc_only=True, @I5@ should be excluded.
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME ClaimantParent //\n1 SEX M\n1 FAMS @F1@\n"
        b"0 @I2@ INDI\n1 NAME ClaimantSpouse //\n1 SEX F\n1 FAMS @F1@\n"
        b"0 @I3@ INDI\n1 NAME PrimaryFather //\n1 SEX M\n1 FAMS @F2@\n"
        b"0 @I4@ INDI\n1 NAME PrimaryMother //\n1 SEX F\n1 FAMS @F2@\n"
        b"0 @I5@ INDI\n1 NAME DisputedChild //\n1 FAMC @F2@\n1 FAMC @F1@\n"
        b"0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I5@\n"
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

    def test_parents_multi_famc_returns_all_by_default(self) -> None:
        doc = _multi_famc_doc()
        subject = doc.resolve("@I1@")
        xrefs = sorted(p.xref for p in parents_of(doc, subject))
        assert xrefs == ["@I2@", "@I3@", "@I4@", "@I5@"]

    def test_parents_multi_famc_primary_only(self) -> None:
        doc = _multi_famc_doc()
        subject = doc.resolve("@I1@")
        xrefs = sorted(p.xref for p in parents_of(doc, subject, primary_famc_only=True))
        assert xrefs == ["@I2@", "@I3@"]


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

    def test_children_primary_famc_filter_excludes(self) -> None:
        doc = _descent_filter_doc()
        claimant = doc.resolve("@I1@")
        # Default: includes @I5@.
        assert sorted(c.xref for c in children_of(doc, claimant)) == ["@I5@"]
        # primary_famc_only: excludes @I5@ because their primary FAMC is @F2@.
        assert children_of(doc, claimant, primary_famc_only=True) == []

    def test_children_primary_famc_filter_includes_when_primary(self) -> None:
        doc = _descent_filter_doc()
        primary_father = doc.resolve("@I3@")
        assert sorted(c.xref for c in children_of(doc, primary_father, primary_famc_only=True)) == ["@I5@"]


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

    def test_ancestors_with_generation(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ancestors_of_with_generation(doc, c)
        gens = {s.xref: g for s, g in result}
        assert gens == {"@I3@": 1, "@I4@": 1, "@I1@": 2, "@I2@": 2}

    def test_ancestors_with_generation_shortest_path(self) -> None:
        doc = _cousin_marriage_doc()
        subject = doc.resolve("@I1@")
        result = ancestors_of_with_generation(doc, subject)
        gens = {s.xref: g for s, g in result}
        # @I9@ is reachable at gen 2 via the maternal side (@I4@ → @I9@)
        # and gen 3 via the paternal side (@I3@ → @I5@ → @I9@). BFS first
        # visit wins → 2.
        assert gens["@I9@"] == 2

    def test_ancestors_primary_famc_only(self) -> None:
        doc = _multi_famc_doc()
        subject = doc.resolve("@I1@")
        anc = ancestors_of(doc, subject, primary_famc_only=True)
        assert sorted(a.xref for a in anc) == ["@I2@", "@I3@"]


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

    def test_descendants_with_generation(self) -> None:
        doc = _three_generation_doc()
        gf = doc.resolve("@I1@")
        result = descendants_of_with_generation(doc, gf)
        gens = {s.xref: g for s, g in result}
        assert gens == {"@I3@": 1, "@I5@": 2}

    def test_descendants_primary_famc_filter(self) -> None:
        doc = _descent_filter_doc()
        claimant = doc.resolve("@I1@")
        # Default: @I5@ shows up as a descendant.
        assert sorted(d.xref for d in descendants_of(doc, claimant)) == ["@I5@"]
        # primary_famc_only: empty.
        assert descendants_of(doc, claimant, primary_famc_only=True) == []


class TestAhnentafel:
    def test_subject_is_first_with_sosa_one(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ahnentafel(doc, c)
        assert result[0][0].xref == "@I5@"
        assert result[0][1] == 0
        assert result[0][2] == 1

    def test_father_is_two_mother_is_three(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ahnentafel(doc, c)
        sosa = {s.xref: n for s, _, n in result}
        # @F2@ has HUSB @I3@ + WIFE @I4@ → father=2, mother=3
        assert sosa["@I3@"] == 2
        assert sosa["@I4@"] == 3
        # @F1@ has HUSB @I1@ + WIFE @I2@ → paternal grandfather=4, paternal grandmother=5
        assert sosa["@I1@"] == 4
        assert sosa["@I2@"] == 5

    def test_generation_matches_sosa(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ahnentafel(doc, c)
        for s, gen, sosa in result:
            # Generation = floor(log2(sosa)).
            expected_gen = sosa.bit_length() - 1
            assert gen == expected_gen, f"sosa={sosa}, gen={gen}, expected={expected_gen}"

    def test_depth_limit(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ahnentafel(doc, c, depth=1)
        # Only subject + parents.
        xrefs = sorted(s.xref for s, _, _ in result)
        assert xrefs == ["@I3@", "@I4@", "@I5@"]

    def test_multi_famc_emits_duplicates_per_path(self) -> None:
        doc = _multi_famc_doc()
        subject = doc.resolve("@I1@")
        result = ahnentafel(doc, subject)
        sosas = sorted(n for _, _, n in result)
        # Per the issue: "emit each ancestor once per Sosa-reachable path".
        # Both FAMCs produce (father=sosa 2, mother=sosa 3), so we expect
        # collisions at sosa 2 and 3 with different individuals.
        assert sosas == [1, 2, 2, 3, 3]
        father_xrefs = sorted(s.xref for s, _, n in result if n == 2)
        mother_xrefs = sorted(s.xref for s, _, n in result if n == 3)
        assert father_xrefs == ["@I2@", "@I4@"]
        assert mother_xrefs == ["@I3@", "@I5@"]

    def test_multi_famc_primary_only_collapses(self) -> None:
        doc = _multi_famc_doc()
        subject = doc.resolve("@I1@")
        result = ahnentafel(doc, subject, primary_famc_only=True)
        sosa = {s.xref: n for s, _, n in result}
        # Only @F1@ (primary): @I2@=father=2, @I3@=mother=3
        assert sosa == {"@I1@": 1, "@I2@": 2, "@I3@": 3}

    def test_sorted_by_sosa(self) -> None:
        doc = _three_generation_doc()
        c = doc.resolve("@I5@")
        result = ahnentafel(doc, c)
        sosas = [n for _, _, n in result]
        assert sosas == sorted(sosas)
