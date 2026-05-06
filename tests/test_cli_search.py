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

    def test_combining_modes(self, maximal70: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _, stderr = _run([str(maximal70), "--tag", "NAME", "--person", "Smith"], capsys)
        assert rc == 2
        assert "single mode" in stderr

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
