# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Round-trip integration tests.

For every fixture in ``examples/``, parse and re-emit; the resulting bytes must
match the input. This is the gating test for the parser/writer pair.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gedcom_lite import GedcomDocument

from .conftest import ALL_FIXTURES, fixture_id


@pytest.mark.parametrize("path", ALL_FIXTURES, ids=[fixture_id(p) for p in ALL_FIXTURES])
def test_round_trip_byte_identical(path: Path) -> None:
    raw = path.read_bytes()
    doc = GedcomDocument.parse(path)
    assert doc.write() == raw


def test_no_warnings_on_well_formed_fixtures() -> None:
    # The official sample files should parse without warnings.
    for path in ALL_FIXTURES:
        if "handcrafted" in str(path):
            # Handcrafted fixtures may exercise edge cases; allow warnings.
            continue
        doc = GedcomDocument.parse(path)
        assert doc.parse_warnings == [], f"{path.name}: warnings={doc.parse_warnings}"


def test_version_detected(examples_root: Path) -> None:
    assert GedcomDocument.parse(examples_root / "gedcom70" / "minimal70.ged").version == "7.0"
    assert GedcomDocument.parse(examples_root / "gedcom555" / "MINIMAL555.GED").version == "5.5.5"


def test_record_counts_on_maximal70(examples_root: Path) -> None:
    doc = GedcomDocument.parse(examples_root / "gedcom70" / "maximal70.ged")
    counts = doc.record_counts()
    # Spot-check the structure of the official maximal sample.
    assert counts.get("INDI") == 4
    assert counts.get("FAM") == 2
    assert counts.get("SUBM") == 2
    assert counts.get("SOUR") == 2


def test_utf16_le_round_trip(examples_root: Path) -> None:
    path = examples_root / "gedcom555" / "555SAMPLE16LE.GED"
    raw = path.read_bytes()
    doc = GedcomDocument.parse(path)
    assert doc.encoding == "utf-16-le"
    assert doc.write() == raw


def test_utf16_be_round_trip(examples_root: Path) -> None:
    path = examples_root / "gedcom555" / "555SAMPLE16BE.GED"
    raw = path.read_bytes()
    doc = GedcomDocument.parse(path)
    assert doc.encoding == "utf-16-be"
    assert doc.write() == raw


def test_ansel_fixture_round_trip(examples_root: Path) -> None:
    path = examples_root / "handcrafted" / "ansel-sample.ged"
    raw = path.read_bytes()
    doc = GedcomDocument.parse(path)
    assert doc.encoding == "ansel"
    assert doc.declared_char == "ANSEL"
    assert doc.write() == raw
    # Decoded content has the diacritics.
    indi1_name = doc.records[1].find("NAME")
    assert indi1_name is not None and "Müller" in (indi1_name.payload or "")
