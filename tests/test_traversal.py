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
    cousins_of_with_degree,
    descendants_of,
    descendants_of_with_generation,
    parents_of,
    siblings_of,
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


def _sibling_doc() -> GedcomDocument:
    """Subject with one full and one half sibling.

        @F1@: @I2@ (HUSB) + @I3@ (WIFE) → @I1@ (subject), @I6@ (full sibling)
        @F2@: @I2@ (HUSB) + @I8@ (WIFE) → @I7@ (half sibling via shared @I2@)
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Subject //\n1 FAMC @F1@\n"
        b"0 @I2@ INDI\n1 NAME SharedParent //\n1 SEX M\n1 FAMS @F1@\n1 FAMS @F2@\n"
        b"0 @I3@ INDI\n1 NAME OtherParent //\n1 SEX F\n1 FAMS @F1@\n"
        b"0 @I6@ INDI\n1 NAME FullSibling //\n1 FAMC @F1@\n"
        b"0 @I7@ INDI\n1 NAME HalfSibling //\n1 FAMC @F2@\n"
        b"0 @I8@ INDI\n1 NAME StepParent //\n1 SEX F\n1 FAMS @F2@\n"
        b"0 @F1@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I1@\n1 CHIL @I6@\n"
        b"0 @F2@ FAM\n1 HUSB @I2@\n1 WIFE @I8@\n1 CHIL @I7@\n"
        b"0 TRLR\n"
    )
    return GedcomDocument.parse(src)


def _sibling_multi_famc_doc() -> GedcomDocument:
    """Subject with two FAMCs, each with a different sibling.

        @F1@ (primary): @I2@ + @I3@ → @I1@, @I6@
        @F2@ (secondary): @I4@ + @I5@ → @I1@, @I7@

    With ``primary_famc_only=True``, only @I6@ should appear; without it,
    both @I6@ and @I7@.
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Subject //\n1 FAMC @F1@\n1 FAMC @F2@\n"
        b"0 @I2@ INDI\n1 NAME PrimaryFather //\n1 SEX M\n1 FAMS @F1@\n"
        b"0 @I3@ INDI\n1 NAME PrimaryMother //\n1 SEX F\n1 FAMS @F1@\n"
        b"0 @I4@ INDI\n1 NAME SecondaryFather //\n1 SEX M\n1 FAMS @F2@\n"
        b"0 @I5@ INDI\n1 NAME SecondaryMother //\n1 SEX F\n1 FAMS @F2@\n"
        b"0 @I6@ INDI\n1 NAME PrimarySibling //\n1 FAMC @F1@\n"
        b"0 @I7@ INDI\n1 NAME SecondarySibling //\n1 FAMC @F2@\n"
        b"0 @F1@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I1@\n1 CHIL @I6@\n"
        b"0 @F2@ FAM\n1 HUSB @I4@\n1 WIFE @I5@\n1 CHIL @I1@\n1 CHIL @I7@\n"
        b"0 TRLR\n"
    )
    return GedcomDocument.parse(src)


def _cousin_doc() -> GedcomDocument:
    """Two-branch tree exercising first and second cousins.

        @I10@ (great-grandparent)
          ├── @I4@ (grandparent of @I1@)
          │     ├── @I2@ (parent of @I1@)
          │     │     └── @I1@ (subject)
          │     └── @I7@ (aunt/uncle)
          │           └── @I8@ (first cousin)
          └── @I12@ (great-aunt/uncle)
                └── @I13@ (parent's first cousin)
                      └── @I14@ (second cousin)
    """
    src = (
        b"0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        b"0 @I1@ INDI\n1 NAME Subject //\n1 FAMC @F1@\n"
        b"0 @I2@ INDI\n1 NAME Parent //\n1 FAMS @F1@\n1 FAMC @F2@\n"
        b"0 @I4@ INDI\n1 NAME Grandparent //\n1 FAMS @F2@\n1 FAMC @F3@\n"
        b"0 @I7@ INDI\n1 NAME AuntUncle //\n1 FAMC @F2@\n1 FAMS @F4@\n"
        b"0 @I8@ INDI\n1 NAME FirstCousin //\n1 FAMC @F4@\n"
        b"0 @I10@ INDI\n1 NAME GreatGrandparent //\n1 FAMS @F3@\n1 FAMS @F5@\n"
        b"0 @I12@ INDI\n1 NAME GreatAuntUncle //\n1 FAMC @F5@\n1 FAMS @F6@\n"
        b"0 @I13@ INDI\n1 NAME FirstCousinOnceRemoved //\n1 FAMC @F6@\n1 FAMS @F7@\n"
        b"0 @I14@ INDI\n1 NAME SecondCousin //\n1 FAMC @F7@\n"
        b"0 @F1@ FAM\n1 HUSB @I2@\n1 CHIL @I1@\n"
        b"0 @F2@ FAM\n1 HUSB @I4@\n1 CHIL @I2@\n1 CHIL @I7@\n"
        b"0 @F3@ FAM\n1 HUSB @I10@\n1 CHIL @I4@\n"
        b"0 @F4@ FAM\n1 HUSB @I7@\n1 CHIL @I8@\n"
        b"0 @F5@ FAM\n1 HUSB @I10@\n1 CHIL @I12@\n"
        b"0 @F6@ FAM\n1 HUSB @I12@\n1 CHIL @I13@\n"
        b"0 @F7@ FAM\n1 HUSB @I13@\n1 CHIL @I14@\n"
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


class TestSiblings:
    def test_full_and_half_siblings(self) -> None:
        doc = _sibling_doc()
        subject = doc.resolve("@I1@")
        sibs = sorted(s.xref for s in siblings_of(doc, subject))
        assert sibs == ["@I6@", "@I7@"]

    def test_excludes_subject(self) -> None:
        doc = _sibling_doc()
        subject = doc.resolve("@I1@")
        sibs = siblings_of(doc, subject)
        assert all(s.xref != "@I1@" for s in sibs)

    def test_no_parents_returns_empty(self) -> None:
        doc = _three_generation_doc()
        root = doc.resolve("@I1@")
        assert siblings_of(doc, root) == []

    def test_primary_famc_only_collapses_to_primary_branch(self) -> None:
        doc = _sibling_multi_famc_doc()
        subject = doc.resolve("@I1@")
        all_sibs = sorted(s.xref for s in siblings_of(doc, subject))
        assert all_sibs == ["@I6@", "@I7@"]
        primary_sibs = sorted(
            s.xref for s in siblings_of(doc, subject, primary_famc_only=True)
        )
        assert primary_sibs == ["@I6@"]


class TestCousins:
    def test_first_cousin_at_depth_1(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        result = cousins_of_with_degree(doc, subject, depth=1)
        by_xref = {s.xref: (deg, rem) for s, deg, rem in result}
        assert by_xref == {"@I7@": (1, 1), "@I8@": (1, 0)}

    def test_excludes_subject_line(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        result = cousins_of_with_degree(doc, subject)
        xrefs = {s.xref for s, _, _ in result}
        assert xrefs.isdisjoint({"@I1@", "@I2@", "@I4@", "@I10@"})

    def test_depth_caps_cumulatively(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        d1 = {s.xref for s, _, _ in cousins_of_with_degree(doc, subject, depth=1)}
        d2 = {s.xref for s, _, _ in cousins_of_with_degree(doc, subject, depth=2)}
        assert d1 == {"@I7@", "@I8@"}
        assert d2 == {"@I7@", "@I8@", "@I12@", "@I13@", "@I14@"}

    def test_second_cousin_degree_and_removed(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        result = cousins_of_with_degree(doc, subject, depth=2)
        by_xref = {s.xref: (deg, rem) for s, deg, rem in result}
        # @I12@: descend_dist=0, gen_n=2 → degree=2, removed=2 (great-aunt/uncle)
        # @I13@: descend_dist=1, gen_n=2 → degree=2, removed=1 (1c1r-like)
        # @I14@: descend_dist=2, gen_n=2 → degree=2, removed=0 (true second cousin)
        assert by_xref["@I12@"] == (2, 2)
        assert by_xref["@I13@"] == (2, 1)
        assert by_xref["@I14@"] == (2, 0)

    def test_sorted_by_degree_then_removed(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        result = cousins_of_with_degree(doc, subject, depth=2)
        keys = [(deg, rem) for _, deg, rem in result]
        assert keys == sorted(keys)

    def test_dedup_via_cousin_marriage(self) -> None:
        # In _cousin_marriage_doc, @I9@ is reachable as both grandparent (gen 2)
        # via the maternal side and great-grandparent (gen 3) via the paternal
        # side. @I7@ (great-grandmother on paternal side) is a non-line
        # individual; she is NOT a cousin (she's an ancestor's spouse, no
        # sibling relation here), so this fixture mainly tests that subject's
        # ancestors are excluded — see test_excludes_subject_line. Use it here
        # to confirm no result entry duplicates an xref.
        doc = _cousin_marriage_doc()
        subject = doc.resolve("@I1@")
        result = cousins_of_with_degree(doc, subject)
        xrefs = [s.xref for s, _, _ in result]
        assert len(xrefs) == len(set(xrefs))

    def test_primary_famc_only(self) -> None:
        doc = _cousin_doc()
        subject = doc.resolve("@I1@")
        # Subject has only one FAMC; primary_famc_only is a no-op for the
        # ancestor walk. The kwarg should still plumb through cleanly.
        plain = {s.xref for s, _, _ in cousins_of_with_degree(doc, subject)}
        primary = {
            s.xref for s, _, _
            in cousins_of_with_degree(doc, subject, primary_famc_only=True)
        }
        assert plain == primary
