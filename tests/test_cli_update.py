# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ``gedcom-update`` CLI."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gedcom_lite.cli.update import main


def _run(args: list[str], capsysbinary: pytest.CaptureFixture[bytes]) -> tuple[int, bytes, bytes]:
    rc = main(args)
    out = capsysbinary.readouterr()
    return rc, out.out, out.err


@pytest.fixture
def tmp_minimal70(tmp_path: Path, examples_root: Path) -> Path:
    target = tmp_path / "minimal70.ged"
    shutil.copy(examples_root / "gedcom70" / "minimal70.ged", target)
    return target


@pytest.fixture
def tmp_maximal70(tmp_path: Path, examples_root: Path) -> Path:
    target = tmp_path / "maximal70.ged"
    shutil.copy(examples_root / "gedcom70" / "maximal70.ged", target)
    return target


@pytest.fixture
def tmp_remarriage1(tmp_path: Path, examples_root: Path) -> Path:
    target = tmp_path / "remarriage1.ged"
    shutil.copy(examples_root / "gedcom70" / "remarriage1.ged", target)
    return target


class TestSetPayload:
    def test_changes_only_target_line(
        self,
        tmp_maximal70: Path,
        tmp_path: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        out_path = tmp_path / "out.ged"
        rc, _, _ = _run(
            [str(tmp_maximal70), "-o", str(out_path),
             "set-payload", "@I1@", "NAME", "Test /Mutated/"],
            capsysbinary,
        )
        assert rc == 0
        original = tmp_maximal70.read_bytes().decode("utf-8-sig").splitlines()
        modified = out_path.read_bytes().decode("utf-8-sig").splitlines()
        assert len(original) == len(modified)
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(original, modified)) if a != b]
        assert len(diffs) == 1
        assert "Test /Mutated/" in diffs[0][2]


class TestAddSubstructure:
    def test_appends_under_record(
        self,
        tmp_minimal70: Path,
        tmp_path: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        # First add an INDI record (also exercises add-record).
        out1 = tmp_path / "step1.ged"
        rc, _, _ = _run([str(tmp_minimal70), "-o", str(out1), "add-record", "INDI"], capsysbinary)
        assert rc == 0
        # Then add a NAME under @I1@.
        out2 = tmp_path / "step2.ged"
        rc, _, _ = _run(
            [str(out1), "-o", str(out2),
             "add-substructure", "@I1@", "", "NAME", "Jane /Doe/"],
            capsysbinary,
        )
        assert rc == 0
        text = out2.read_text(encoding="utf-8")
        assert "0 @I1@ INDI" in text
        assert "1 NAME Jane /Doe/" in text


class TestRemove:
    def test_removes_named_path(
        self,
        tmp_path: Path,
        examples_root: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        # Build a small fixture with a NAME we can remove.
        src = tmp_path / "src.ged"
        src.write_bytes(
            b"0 HEAD\n1 GEDC\n2 VERS 7.0\n0 @I1@ INDI\n1 NAME Jane\n1 SEX F\n0 TRLR\n"
        )
        out = tmp_path / "out.ged"
        rc, _, _ = _run(
            [str(src), "-o", str(out), "remove", "@I1@", "NAME"],
            capsysbinary,
        )
        assert rc == 0
        assert b"NAME" not in out.read_bytes()
        assert b"SEX" in out.read_bytes()


class TestDeleteRecord:
    def test_blocks_when_pointers_exist(
        self,
        tmp_maximal70: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = tmp_path / "out.ged"
        with pytest.raises(SystemExit) as exc:
            main([str(tmp_maximal70), "-o", str(out), "delete-record", "@I1@"])
        # SystemExit message goes to stderr via the raise.
        assert "refusing" in str(exc.value).lower() or "@I1@" in str(exc.value)

    def test_void_strategy_succeeds(
        self,
        tmp_remarriage1: Path,
        tmp_path: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        out = tmp_path / "out.ged"
        rc, _, _ = _run(
            [str(tmp_remarriage1), "-o", str(out),
             "delete-record", "@I1@", "--orphan-pointers", "void"],
            capsysbinary,
        )
        assert rc == 0
        assert b"@VOID@" in out.read_bytes()


class TestSafetyContract:
    def test_default_does_not_modify_input(
        self,
        tmp_minimal70: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        original = tmp_minimal70.read_bytes()
        rc, stdout, _ = _run(
            [str(tmp_minimal70), "add-record", "INDI"],
            capsysbinary,
        )
        assert rc == 0
        assert tmp_minimal70.read_bytes() == original
        # The new content goes to stdout instead.
        assert b"0 @I1@ INDI" in stdout

    def test_in_place_overwrites(
        self,
        tmp_minimal70: Path,
        capsysbinary: pytest.CaptureFixture[bytes],
    ) -> None:
        original = tmp_minimal70.read_bytes()
        rc, _, _ = _run(
            [str(tmp_minimal70), "--in-place", "add-record", "INDI"],
            capsysbinary,
        )
        assert rc == 0
        new = tmp_minimal70.read_bytes()
        assert new != original
        assert b"0 @I1@ INDI" in new

    def test_in_place_and_o_mutually_exclusive(
        self,
        tmp_minimal70: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = main([str(tmp_minimal70),
                   "--in-place", "-o", str(tmp_path / "out.ged"),
                   "add-record", "INDI"])
        assert rc == 2
