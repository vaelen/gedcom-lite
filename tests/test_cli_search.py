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
