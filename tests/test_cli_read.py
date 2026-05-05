# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ``gedcom-read`` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gedcom_lite.cli.read import main


def _run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(args)
    out = capsys.readouterr()
    return rc, out.out, out.err


class TestSummary:
    def test_minimal70(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "minimal70.ged")], capsys)
        assert rc == 0
        assert "GEDCOM version: 7.0" in stdout
        assert "Records: (none)" in stdout

    def test_maximal70_counts(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "maximal70.ged")], capsys)
        assert rc == 0
        assert "INDI" in stdout
        assert "FAM" in stdout

    def test_explicit_summary_subcommand(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "minimal70.ged"), "summary"], capsys)
        assert rc == 0
        assert "GEDCOM version: 7.0" in stdout


class TestList:
    def test_indi(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "maximal70.ged"), "list", "INDI"], capsys)
        assert rc == 0
        assert "@I1@" in stdout
        assert "@I2@" in stdout

    def test_fam(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "maximal70.ged"), "list", "FAM"], capsys)
        assert rc == 0
        assert "@F1@" in stdout

    def test_unknown_tag_returns_empty(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "minimal70.ged"), "list", "INDI"], capsys)
        assert rc == 0
        assert "(no INDI records)" in stdout


class TestRecord:
    def test_show_existing(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run([str(examples_root / "gedcom70" / "maximal70.ged"), "record", "@I1@"], capsys)
        assert rc == 0
        assert stdout.startswith("@I1@ INDI")

    def test_missing_record(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _, stderr = _run([str(examples_root / "gedcom70" / "minimal70.ged"), "record", "@MISSING@"], capsys)
        assert rc == 1
        assert "no record" in stderr

    def test_depth_limit(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run(
            [str(examples_root / "gedcom70" / "maximal70.ged"), "record", "@I1@", "--depth", "1"],
            capsys,
        )
        assert rc == 0
        # At depth 1 we get the record root + its direct children only.
        # Lines deeper than 2 spaces of indentation should not appear.
        for line in stdout.splitlines():
            indent = len(line) - len(line.lstrip(" "))
            assert indent <= 2


class TestJSON:
    def test_summary_json(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run(
            [str(examples_root / "gedcom70" / "maximal70.ged"), "--json"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert data["version"] == "7.0"
        assert isinstance(data["records"], list)
        assert len(data["records"]) > 0

    def test_list_json(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run(
            [str(examples_root / "gedcom70" / "maximal70.ged"), "--json", "list", "INDI"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert all(d["tag"] == "INDI" for d in data)

    def test_record_json(self, examples_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc, stdout, _ = _run(
            [str(examples_root / "gedcom70" / "maximal70.ged"), "--json", "record", "@I1@"],
            capsys,
        )
        assert rc == 0
        data = json.loads(stdout)
        assert data["xref"] == "@I1@"
        assert data["tag"] == "INDI"
