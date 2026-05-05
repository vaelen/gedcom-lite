# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Shared pytest fixtures for the gedcom-lite test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"


@pytest.fixture(scope="session")
def examples_root() -> Path:
    return EXAMPLES


def _all_fixture_paths() -> list[Path]:
    paths: list[Path] = []
    paths += sorted((EXAMPLES / "gedcom555").glob("*.GED"))
    paths += sorted((EXAMPLES / "gedcom70").glob("*.ged"))
    paths += sorted((EXAMPLES / "handcrafted").glob("*.ged"))
    return paths


def _gdz_fixture_paths() -> list[Path]:
    return sorted((EXAMPLES / "gedcom70").glob("*.gdz"))


# Parametrized fixtures used by round-trip and other broad tests. We expose the
# Path objects through indirect parametrization so individual tests can iterate.

ALL_FIXTURES = _all_fixture_paths()
GDZ_FIXTURES = _gdz_fixture_paths()


def fixture_id(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"
