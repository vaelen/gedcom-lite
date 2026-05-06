# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ``gedcom-search`` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gedcom_lite.cli.search import main


def _run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(args)
    out = capsys.readouterr()
    return rc, out.out, out.err


@pytest.fixture
def maximal70(examples_root: Path) -> Path:
    return examples_root / "gedcom70" / "maximal70.ged"


@pytest.fixture
def family_tree(tmp_path: Path) -> Path:
    """A small synthetic two-generation tree, with @I6@ having two FAMC."""
    src = (
        "0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        "0 @I1@ INDI\n1 NAME Subject //\n1 BIRT\n2 DATE 1 JAN 2000\n2 PLAC Boston\n1 FAMC @F1@\n"
        "0 @I2@ INDI\n1 NAME Father //\n1 SEX M\n1 FAMS @F1@\n1 FAMC @F2@\n"
        "0 @I3@ INDI\n1 NAME Mother //\n1 SEX F\n1 FAMS @F1@\n"
        "0 @I4@ INDI\n1 NAME Grandpa //\n1 SEX M\n1 FAMS @F2@\n"
        "0 @I5@ INDI\n1 NAME Grandma //\n1 SEX F\n1 FAMS @F2@\n"
        "0 @I6@ INDI\n1 NAME Disputed //\n1 FAMC @F1@\n1 FAMC @F2@\n"
        "0 @F1@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I1@\n1 CHIL @I6@\n"
        "0 @F2@ FAM\n1 HUSB @I4@\n1 WIFE @I5@\n1 CHIL @I2@\n1 CHIL @I6@\n"
        "0 TRLR\n"
    )
    path = tmp_path / "family.ged"
    path.write_text(src, encoding="utf-8")
    return path


class TestErrors:
    def test_no_criteria(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _, stderr = _run([str(maximal70)], capsys)
        assert rc == 2
        assert "no search criteria" in stderr

    def test_combining_generic_with_person_rejected(
        self, maximal70: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run([str(maximal70), "--tag", "NAME", "--person", "Smith"], capsys)
        assert rc == 2
        assert "generic filters" in stderr

    def test_combining_famc_conflicts_with_person_rejected(
        self, maximal70: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(maximal70), "--famc-conflicts", "--person", "Smith"], capsys,
        )
        assert rc == 2
        assert "famc-conflicts" in stderr

    def test_unknown_xref_in_relationship(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _, stderr = _run([str(maximal70), "--children-of", "@MISSING@"], capsys)
        assert rc == 1
        assert "no INDI" in stderr


class TestGenericFilters:
    def test_xref(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--xref", "@I1@"], capsys)
        assert rc == 0
        assert "@I1@" in stdout

    def test_tag(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--tag", "NAME", "--in", "INDI"], capsys)
        assert rc == 0
        assert "@I1@" in stdout

    def test_value_substring(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--value", "Allen", "--in", "INDI"], capsys)
        assert rc == 0
        assert "Allen" in stdout

    def test_path_query(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--path", "INDI/BIRT/DATE"], capsys)
        assert rc == 0
        assert "BIRT/DATE" in stdout

    def test_regex(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--tag", "NAME", "--regex", "--value", r"[Aa]llen"], capsys)
        assert rc == 0
        assert "Allen" in stdout

    def test_count(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--tag", "DATE", "--count"], capsys)
        assert rc == 0
        assert int(stdout.strip()) > 0

    def test_limit(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--tag", "NAME", "--limit", "1"], capsys)
        assert rc == 0
        # Only one match line.
        assert len([ln for ln in stdout.splitlines() if ln.strip()]) == 1


class TestPersonModes:
    def test_person(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--person", "Allen"], capsys)
        assert rc == 0
        assert "@I1@" in stdout

    def test_born_between(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--born-between", "1999", "2001"], capsys)
        assert rc == 0
        assert "@I1@" in stdout

    def test_born_between_no_match(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--born-between", "1700", "1800"], capsys)
        assert rc == 0
        assert stdout.strip() == ""


class TestRelationships:
    def test_children_of(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--children-of", "@I1@"], capsys)
        assert rc == 0
        # Some children expected; just verify non-empty.
        assert stdout.strip() != ""

    def test_parents_of(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--parents-of", "@I4@"], capsys)
        assert rc == 0
        assert "@I1@" in stdout or "@I2@" in stdout


class TestJSONOutput:
    def test_generic_match(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--tag", "NAME", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert all("path" in item and "payload" in item for item in data)

    def test_record_match(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(maximal70), "--person", "Allen", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert data and data[0]["tag"] == "INDI"


class TestGenerationField:
    def test_ancestors_json_includes_generation(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--ancestors-of", "@I1@", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert {d["xref"]: d["generation"] for d in data} == {
            "@I2@": 1, "@I3@": 1, "@I4@": 2, "@I5@": 2,
        }

    def test_descendants_json_includes_generation(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--descendants-of", "@I4@", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        gens = {d["xref"]: d["generation"] for d in data}
        # @I2@ + @I6@ are children of @I4@; @I1@ + @I6@ are grandchildren.
        # @I6@ first visited at gen 1 (BFS).
        assert gens["@I2@"] == 1
        assert gens["@I6@"] == 1
        assert gens["@I1@"] == 2

    def test_ancestors_text_has_gen_suffix(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--ancestors-of", "@I1@"], capsys)
        assert rc == 0
        assert "(gen 1)" in stdout
        assert "(gen 2)" in stdout


class TestFactsOutput:
    def test_xref_facts_shape(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--xref", "@I1@", "--facts"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert len(data) == 1
        rec = data[0]
        assert rec["xref"] == "@I1@"
        assert rec["name"] == "Subject //"
        assert rec["birth"] == {"date": "1 JAN 2000", "place": "Boston"}
        assert rec["death"] == {"date": None, "place": None}
        assert sorted(rec["parents"]) == ["@I2@", "@I3@"]
        assert rec["famc"] == ["@F1@"]
        assert "generation" not in rec
        assert "sosa" not in rec

    def test_facts_with_ancestors_includes_generation(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--ancestors-of", "@I1@", "--facts"], capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert all("generation" in d for d in data)
        assert {d["xref"] for d in data} == {"@I2@", "@I3@", "@I4@", "@I5@"}

    def test_facts_with_person(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--person", "Subject", "--facts"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert len(data) == 1
        assert data[0]["xref"] == "@I1@"

    def test_facts_json_mutex(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(family_tree), "--xref", "@I1@", "--facts", "--json"], capsys,
        )
        assert rc == 2
        assert "mutually exclusive" in stderr

    def test_facts_show_record_mutex(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(family_tree), "--xref", "@I1@", "--facts", "--show-record"], capsys,
        )
        assert rc == 2
        assert "mutually exclusive" in stderr


class TestFamcConflicts:
    def test_lists_only_multi_famc(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--famc-conflicts", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert {d["xref"] for d in data} == {"@I6@"}

    def test_facts_shape_includes_famc(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--famc-conflicts", "--facts"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert len(data) == 1
        assert data[0]["xref"] == "@I6@"
        assert sorted(data[0]["famc"]) == ["@F1@", "@F2@"]


class TestAhnentafelCli:
    def test_text_sosa_ordering(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--ahnentafel", "@I1@"], capsys)
        assert rc == 0
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        # Subject 1, father 2, mother 3, paternal grandfather 4, paternal grandmother 5.
        assert lines[0].startswith("1  @I1@")
        assert lines[1].startswith("2  @I2@")
        assert lines[2].startswith("3  @I3@")
        assert lines[3].startswith("4  @I4@")
        assert lines[4].startswith("5  @I5@")

    def test_json_includes_sosa_and_generation(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--ahnentafel", "@I1@", "--json"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        sosa = {d["xref"]: d["sosa"] for d in data}
        gen = {d["xref"]: d["generation"] for d in data}
        assert sosa["@I1@"] == 1
        assert sosa["@I2@"] == 2
        assert sosa["@I3@"] == 3
        assert gen["@I1@"] == 0
        assert gen["@I2@"] == 1

    def test_facts_includes_sosa(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--ahnentafel", "@I1@", "--facts"], capsys)
        assert rc == 0
        data = json.loads(stdout)
        assert all("sosa" in d and "generation" in d for d in data)

    def test_primary_famc_only_unique(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--ahnentafel", "@I1@", "--primary-famc-only", "--json"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        sosas = [d["sosa"] for d in data]
        assert len(sosas) == len(set(sosas))

    def test_mutex_with_other_relationship_modes(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(family_tree), "--ahnentafel", "@I1@", "--ancestors-of", "@I1@"],
            capsys,
        )
        assert rc == 2
        assert "exactly one" in stderr


class TestPrimaryFamcOnlyFlag:
    def test_ancestors_filtered(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # @I6@ has two FAMC (@F1@, @F2@); primary is @F1@.
        # Default ancestors include both sets; primary-only includes only @F1@.
        rc, stdout, _ = _run(
            [str(family_tree), "--ancestors-of", "@I6@", "--primary-famc-only", "--json"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        xrefs = {d["xref"] for d in data}
        # Primary FAMC @F1@ → parents @I2@, @I3@. @I2@'s FAMC → @I4@, @I5@.
        assert xrefs == {"@I2@", "@I3@", "@I4@", "@I5@"}

    def test_descendants_filter_excludes_secondary_famc_child(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        src = (
            "0 HEAD\n1 GEDC\n2 VERS 7.0\n"
            "0 @I1@ INDI\n1 NAME Claimant //\n1 SEX M\n1 FAMS @F1@\n"
            "0 @I2@ INDI\n1 NAME ClaimantSpouse //\n1 SEX F\n1 FAMS @F1@\n"
            "0 @I3@ INDI\n1 NAME RealFather //\n1 SEX M\n1 FAMS @F2@\n"
            "0 @I4@ INDI\n1 NAME RealMother //\n1 SEX F\n1 FAMS @F2@\n"
            "0 @I5@ INDI\n1 NAME Disputed //\n1 FAMC @F2@\n1 FAMC @F1@\n"
            "0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I5@\n"
            "0 @F2@ FAM\n1 HUSB @I3@\n1 WIFE @I4@\n1 CHIL @I5@\n"
            "0 TRLR\n"
        )
        p = tmp_path / "disputed.ged"
        p.write_text(src, encoding="utf-8")
        rc, stdout, _ = _run(
            [str(p), "--descendants-of", "@I1@", "--primary-famc-only", "--count"],
            capsys,
        )
        assert rc == 0
        assert stdout.strip() == "0"


@pytest.fixture
def dated_tree(tmp_path: Path) -> Path:
    """Three-generation tree with rich BIRT/DEAT date+place coverage."""
    src = (
        "0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        # @I1@ subject — born Boston 1820, died Boston 1880
        "0 @I1@ INDI\n1 NAME John Smith //\n1 SEX M\n"
        "1 BIRT\n2 DATE 1 JAN 1820\n2 PLAC Boston, Massachusetts, USA\n"
        "1 DEAT\n2 DATE 5 JUN 1880\n2 PLAC Boston, Massachusetts, USA\n"
        "1 FAMC @F1@\n"
        # @I2@ father — born London 1790, died Boston 1850
        "0 @I2@ INDI\n1 NAME Henry Smith //\n1 SEX M\n"
        "1 BIRT\n2 DATE 12 MAR 1790\n2 PLAC London, England\n"
        "1 DEAT\n2 DATE 3 OCT 1850\n2 PLAC Boston, Massachusetts, USA\n"
        "1 FAMS @F1@\n"
        # @I3@ mother — born Boston 1795, died Boston 1860
        "0 @I3@ INDI\n1 NAME Mary Smith //\n1 SEX F\n"
        "1 BIRT\n2 DATE 7 SEP 1795\n2 PLAC Boston, Massachusetts, USA\n"
        "1 DEAT\n2 DATE 15 FEB 1860\n2 PLAC Boston, Massachusetts, USA\n"
        "1 FAMS @F1@\n"
        # @I4@ paternal grandfather — born Bristol 1750, died London 1810
        "0 @I4@ INDI\n1 NAME Old Smith //\n1 SEX M\n"
        "1 BIRT\n2 DATE 1750\n2 PLAC Bristol, England\n"
        "1 DEAT\n2 DATE 1810\n2 PLAC London, England\n"
        # @F1@ — Henry × Mary, child @I1@
        "0 @F1@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I1@\n"
        "0 TRLR\n"
    )
    path = tmp_path / "dated.ged"
    path.write_text(src, encoding="utf-8")
    return path


class TestSymmetricFlags:
    def test_died_between(self, dated_tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(dated_tree), "--died-between", "1850", "1860"], capsys)
        assert rc == 0
        # @I2@ died 1850, @I3@ died 1860; @I1@ died 1880, @I4@ died 1810
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert set(xrefs) == {"@I2@", "@I3@"}

    def test_born_in(self, dated_tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(dated_tree), "--born-in", "Boston"], capsys)
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert set(xrefs) == {"@I1@", "@I3@"}

    def test_min_sentinel_lower_bound(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(dated_tree), "--died-between", "MIN", "1820"], capsys)
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        # Only @I4@ died before 1820 (1810).
        assert set(xrefs) == {"@I4@"}

    def test_max_sentinel_upper_bound(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(dated_tree), "--born-between", "1795", "MAX"], capsys)
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        # @I1@ 1820, @I3@ 1795 qualify; @I2@ 1790 and @I4@ 1750 do not.
        assert set(xrefs) == {"@I1@", "@I3@"}

    def test_min_max_case_insensitive(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, _ = _run([str(dated_tree), "--born-between", "min", "max"], capsys)
        assert rc == 0

    def test_invalid_year_bound(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            _run([str(dated_tree), "--born-between", "abc", "1900"], capsys)


class TestCombinedFilters:
    def test_person_and_born_between(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--person", "Smith", "--born-between", "1800", "1850"], capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        # Smiths born 1800-1850: @I1@ (1820). @I2@ 1790, @I3@ 1795, @I4@ 1750 excluded.
        assert set(xrefs) == {"@I1@"}

    def test_three_filters_and(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree),
             "--person", "Smith",
             "--born-between", "1700", "1900",
             "--died-in", "Boston"],
            capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        # Smiths who died in Boston: @I1@, @I2@, @I3@. @I4@ died London — excluded.
        assert set(xrefs) == {"@I1@", "@I2@", "@I3@"}

    def test_born_in_and_died_in(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--born-in", "Boston", "--died-in", "Boston"], capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        # Born and died in Boston: @I1@, @I3@.
        assert set(xrefs) == {"@I1@", "@I3@"}

    def test_died_between_with_min_acceptance(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Acceptance phrasing from issue #2: "died before 1776"-style query.
        rc, stdout, _ = _run(
            [str(dated_tree), "--died-between", "MIN", "1820"], capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert set(xrefs) == {"@I4@"}

    def test_combine_no_match_returns_empty(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--person", "Nobody", "--born-in", "Mars"], capsys,
        )
        assert rc == 0
        assert stdout.strip() == ""


class TestTraversalComposition:
    def test_ancestors_with_person_filter(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # @I1@'s ancestors: @I2@, @I3@. With --person Henry, only @I2@.
        rc, stdout, _ = _run(
            [str(dated_tree), "--ancestors-of", "@I1@", "--person", "Henry"], capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert set(xrefs) == {"@I2@"}

    def test_ancestors_with_born_in_facts(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--ancestors-of", "@I1@", "--born-in", "London", "--facts"], capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        # Only @I2@ (born London) survives the post-filter; generation preserved.
        assert {d["xref"] for d in data} == {"@I2@"}
        assert data[0]["generation"] == 1

    def test_ancestors_with_died_in_filters_subject(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Subject @I1@ died Boston; ancestors @I2@/@I3@ also Boston, @I4@ London.
        # ancestors-of returns ancestors only (excludes subject), so @I4@ filtered out.
        rc, stdout, _ = _run(
            [str(dated_tree), "--ancestors-of", "@I1@", "--died-in", "Boston"], capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert set(xrefs) == {"@I2@", "@I3@"}

    def test_ahnentafel_with_filter_preserves_sosa(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--ahnentafel", "@I1@", "--born-in", "Boston", "--json"], capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        sosa = {d["xref"]: d["sosa"] for d in data}
        # Only @I1@ (sosa 1) and @I3@ (sosa 3) born Boston.
        assert sosa == {"@I1@": 1, "@I3@": 3}

    def test_descendants_with_filter(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # @I2@'s descendants: @I1@. Filtered by --born-in London → empty.
        rc, stdout, _ = _run(
            [str(dated_tree), "--descendants-of", "@I2@", "--born-in", "London"], capsys,
        )
        assert rc == 0
        assert stdout.strip() == ""

    def test_traversal_filter_with_limit(
        self, dated_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(dated_tree), "--ancestors-of", "@I1@", "--died-in", "Boston", "--limit", "1"],
            capsys,
        )
        assert rc == 0
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        assert len(lines) == 1


@pytest.fixture
def cousin_tree(tmp_path: Path) -> Path:
    """Two-branch tree exercising first and second cousins.

    Subject @I1@. First cousin @I8@ via aunt/uncle @I7@ (sibling of parent
    @I2@). Second cousin @I14@ via great-aunt/uncle @I12@ (sibling of
    grandparent @I4@). All males to keep HUSB/WIFE simple.
    """
    src = (
        "0 HEAD\n1 GEDC\n2 VERS 7.0\n"
        "0 @I1@ INDI\n1 NAME Subject //\n1 FAMC @F1@\n"
        "0 @I2@ INDI\n1 NAME Parent //\n1 FAMS @F1@\n1 FAMC @F2@\n"
        "0 @I4@ INDI\n1 NAME Grandparent //\n1 FAMS @F2@\n1 FAMC @F3@\n"
        "0 @I7@ INDI\n1 NAME AuntUncle //\n1 FAMC @F2@\n1 FAMS @F4@\n"
        "0 @I8@ INDI\n1 NAME FirstCousin //\n1 FAMC @F4@\n"
        "0 @I10@ INDI\n1 NAME GreatGrandparent //\n1 FAMS @F3@\n1 FAMS @F5@\n"
        "0 @I12@ INDI\n1 NAME GreatAuntUncle //\n1 FAMC @F5@\n1 FAMS @F6@\n"
        "0 @I13@ INDI\n1 NAME FirstCousinOnceRemoved //\n1 FAMC @F6@\n1 FAMS @F7@\n"
        "0 @I14@ INDI\n1 NAME SecondCousin //\n1 FAMC @F7@\n"
        "0 @F1@ FAM\n1 HUSB @I2@\n1 CHIL @I1@\n"
        "0 @F2@ FAM\n1 HUSB @I4@\n1 CHIL @I2@\n1 CHIL @I7@\n"
        "0 @F3@ FAM\n1 HUSB @I10@\n1 CHIL @I4@\n"
        "0 @F4@ FAM\n1 HUSB @I7@\n1 CHIL @I8@\n"
        "0 @F5@ FAM\n1 HUSB @I10@\n1 CHIL @I12@\n"
        "0 @F6@ FAM\n1 HUSB @I12@\n1 CHIL @I13@\n"
        "0 @F7@ FAM\n1 HUSB @I13@\n1 CHIL @I14@\n"
        "0 TRLR\n"
    )
    p = tmp_path / "cousins.ged"
    p.write_text(src, encoding="utf-8")
    return p


class TestBulkXref:
    def test_multiple_xrefs_facts_in_order(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--xref", "@I1@", "@I2@", "@I3@", "--facts"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert [d["xref"] for d in data] == ["@I1@", "@I2@", "@I3@"]

    def test_missing_xref_warns_continues(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, stderr = _run(
            [str(family_tree), "--xref", "@I1@", "@IBOGUS@", "--facts"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert [d["xref"] for d in data] == ["@I1@"]
        assert "warning: no record with xref @IBOGUS@" in stderr

    def test_all_missing_exits_1(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, stderr = _run(
            [str(family_tree), "--xref", "@IBOGUS@", "@INOPE@", "--facts"],
            capsys,
        )
        assert rc == 1
        data = json.loads(stdout)
        assert data == []
        assert "@IBOGUS@" in stderr
        assert "@INOPE@" in stderr

    def test_single_xref_unchanged_behavior(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--xref", "@I1@"], capsys)
        assert rc == 0
        assert "@I1@" in stdout

    def test_preserves_argument_order(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--xref", "@I3@", "@I1@", "@I2@", "--facts"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert [d["xref"] for d in data] == ["@I3@", "@I1@", "@I2@"]


class TestSiblingsOf:
    def test_siblings_text(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run([str(family_tree), "--siblings-of", "@I1@"], capsys)
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert xrefs == ["@I6@"]

    def test_siblings_facts_no_extra_fields(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--siblings-of", "@I1@", "--facts"], capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert len(data) == 1 and data[0]["xref"] == "@I6@"
        for k in ("generation", "sosa", "degree", "removed"):
            assert k not in data[0]

    def test_siblings_unknown_xref_exit_1(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(family_tree), "--siblings-of", "@MISSING@"], capsys,
        )
        assert rc == 1
        assert "no INDI" in stderr

    def test_siblings_mutex_with_other_rel_modes(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(family_tree), "--siblings-of", "@I1@", "--ancestors-of", "@I1@"],
            capsys,
        )
        assert rc == 2
        assert "exactly one" in stderr

    def test_siblings_with_person_filter(
        self, family_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(family_tree), "--siblings-of", "@I1@", "--person", "Disputed"],
            capsys,
        )
        assert rc == 0
        xrefs = [ln.split()[0] for ln in stdout.splitlines() if ln.strip()]
        assert xrefs == ["@I6@"]


class TestCousinsOf:
    def test_facts_includes_degree_and_removed(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--depth", "1", "--facts"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        by_xref = {d["xref"]: (d["degree"], d["removed"]) for d in data}
        assert by_xref == {"@I7@": (1, 1), "@I8@": (1, 0)}

    def test_text_mode_suffix(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--depth", "1"], capsys,
        )
        assert rc == 0
        assert "(degree 1, removed 0)" in stdout
        assert "(degree 1, removed 1)" in stdout

    def test_json_includes_degree_and_removed(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--depth", "1", "--json"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert all("degree" in d and "removed" in d for d in data)

    def test_depth_caps_cumulatively(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc1, out1, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--depth", "1", "--facts"],
            capsys,
        )
        rc2, out2, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--depth", "2", "--facts"],
            capsys,
        )
        assert rc1 == 0 and rc2 == 0
        d1 = {d["xref"] for d in json.loads(out1)}
        d2 = {d["xref"] for d in json.loads(out2)}
        assert d1 == {"@I7@", "@I8@"}
        assert d2 == {"@I7@", "@I8@", "@I12@", "@I13@", "@I14@"}

    def test_unknown_xref_exit_1(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(cousin_tree), "--cousins-of", "@MISSING@"], capsys,
        )
        assert rc == 1
        assert "no INDI" in stderr

    def test_mutex_with_other_rel_modes(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, _, stderr = _run(
            [str(cousin_tree), "--cousins-of", "@I1@", "--children-of", "@I2@"],
            capsys,
        )
        assert rc == 2
        assert "exactly one" in stderr

    def test_composes_with_person_filter(
        self, cousin_tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc, stdout, _ = _run(
            [str(cousin_tree), "--cousins-of", "@I1@",
             "--person", "FirstCousin", "--facts"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        # Only @I8@ (NAME "FirstCousin //") matches; "FirstCousinOnceRemoved"
        # also contains the substring, so include it. Both should preserve
        # degree/removed metadata.
        xrefs = {d["xref"] for d in data}
        assert "@I8@" in xrefs
        assert all("degree" in d for d in data)
