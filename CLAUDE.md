# CLAUDE.md — Working agreements for gedcom-lite

`gedcom-lite` is a pure-Python, fidelity-preserving GEDCOM toolkit (parser, writer, ANSEL codec, CLI). It is a real Python package — `pip install gedcom-lite` once on PyPI, or `pip install "git+https://github.com/vaelen/gedcom-lite"` from source — consumed by the [`gedcom-skills`](https://github.com/vaelen/gedcom-skills) Claude Code plugin among others.

Read this file before doing any work in the repo.

## Repo shape

```
.
├── pyproject.toml          # hatchling build, console-script entry points
├── LICENSE                 # MIT
├── README.md
├── CHANGELOG.md
├── CLAUDE.md
├── src/
│   └── gedcom_lite/
│       ├── __init__.py     # public API surface (re-exports)
│       ├── core.py         # parser, writer, model (Structure, GedcomDocument)
│       ├── ansel.py        # ANSEL ↔ Unicode codec
│       ├── dates.py        # GEDCOM date parsing
│       ├── traversal.py    # ancestry/descendancy helpers
│       └── cli/            # console-script entry points
│           ├── read.py     # gedcom-read
│           ├── search.py   # gedcom-search
│           └── update.py   # gedcom-update
├── tests/                  # pytest suite (158 tests at v0.1.0)
└── examples/               # GEDCOM fixtures (.ged + .gdz, all versions)
```

## The load-bearing invariant: round-trip fidelity

This is the contract that everything else hinges on. **Parse a file then write it back, and the output bytes must match the input bytes.** That includes:

- BOM (UTF-8, UTF-16 LE, UTF-16 BE)
- Line endings (CRLF, LF, CR)
- Sibling order, including unknown extension tags
- The `CONC` vs `CONT` choice in 5.5.x
- ANSEL byte sequences for 5.5.1 files

The dirty-bit model on `Structure._dirty` is what makes this possible: untouched structures emit verbatim from `original_line`; only mutated structures regenerate from the model fields. If you change anything in `core.py` and the round-trip test fails byte-equivalence on any fixture, **stop and rethink** — fidelity is non-negotiable.

## Module split

Keep these modules focused. Pulling logic across module lines should be deliberate:

- **`core.py`** — encoding sniffing, line splitting, tokenizer, `Structure`, `GedcomDocument`, JSON projection. The biggest module, but everything in it is GEDCOM-shaped.
- **`ansel.py`** — only the ANSEL codec. No GEDCOM knowledge.
- **`dates.py`** — only `DateValue` and `parse_date_value`. No model dependencies.
- **`traversal.py`** — ancestry/descendancy graph helpers. Imports from `core`.
- **`cli/*.py`** — argparse plumbing and human-readable rendering. No business logic that isn't exposed via the library API; CLI scripts should be thin.

If a feature doesn't have an obvious home, prefer creating a new module over bloating `core.py`.

## Testing

The test suite lives under `tests/` and is run with pytest:

```bash
pip install -e ".[dev]"   # one-time
pytest -q
```

Test files are split by area: `test_tokenizer.py`, `test_encoding.py`, `test_ansel.py`, `test_dates.py`, `test_round_trip.py`, `test_mutation.py`, `test_traversal.py`, `test_cli_{read,search,update}.py`.

Discipline:

- **Add a failing test before fixing a bug.** Reproduces the issue, prevents regression.
- **Add a test for any new feature.** No exceptions.
- The CLI tests use `capsys`/`capsysbinary` and call `main(argv=[...])` directly — no subprocess overhead.
- The round-trip test parametrizes over **every fixture in `examples/`**. Adding a new fixture automatically expands coverage.
- Tests must pass on Python 3.11, 3.12, and 3.13 (per `pyproject.toml` classifiers).

## Adding a new feature

1. Read the relevant GEDCOM spec — links in `README.md`. Don't guess at semantics; getting tag context wrong silently corrupts files.
2. If it touches the parser/writer, write a fixture-based round-trip test first.
3. Implement the change, keeping `core.py` focused on shape (not domain semantics).
4. If it's user-visible, update `CHANGELOG.md` under the next version.
5. Bump `version` in `pyproject.toml` **and** `__init__.py` when releasing — semver: bug fixes are patch, new public API is minor, breaking change is major.
6. Every new `.py` file gets the standard MIT header:
   ```python
   # Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
   # Licensed under the MIT License. See LICENSE in the project root.
   ```

## Encoding rules — the easy place to break things

- **GEDCOM 7.0+** is UTF-8 only. Files may have a UTF-8 BOM; preserve it.
- **GEDCOM 5.5.5** can be UTF-8 or UTF-16 (LE/BE), each with BOM.
- **GEDCOM 5.5.1** uses `1 CHAR` to declare encoding: `UTF-8`, `ANSEL`, `ASCII`, or `UNICODE` (= UTF-16 by convention, sometimes BOM-less).
- **Detection order:** BOM → UTF-8 with `1 CHAR` peek → UTF-16-without-BOM heuristic (≥25% NULs in decoded sample) → ANSEL fallback.
- **Never silently re-encode.** A file read as ANSEL must round-trip as ANSEL bytes; a file read as UTF-16-LE must round-trip with the same BOM and byte order.

The ANSEL codec uses a hand-curated table targeting characters seen in real-world 5.5.1 files. The convention for combining diacritics is the **opposite** of Unicode: marks precede the base character. The encoder walks NFD-normalised text in `base + marks` clusters and emits marks first.

## Scope discipline — the "lite" part

This package deliberately does **not** do:

- Schema validation (you can have a structurally valid file that violates the spec semantically).
- 5.5.1 → 7.0 conversion.
- GEDZIP `.gdz` creation/expansion (we treat `.gdz` as opaque zip; bundling/extracting is a separate concern).
- Genealogy domain modelling beyond what GEDCOM itself defines (no `Person.spouse`, `Family.children` convenience API).
- Visualization, GEDCOM-X interop, FamilySearch API integration.

If a feature pushes against this boundary, propose it as a downstream package (`gedcom-validate`, `gedcom-convert-7`, etc.) rather than letting it land here.

## Versioning

Semantic versioning. The current version lives in three places — keep them in sync:

- `pyproject.toml` → `version = "..."`
- `src/gedcom_lite/__init__.py` → `__version__ = "..."`
- `CHANGELOG.md` → newest entry header

Releases are tagged `v0.1.0`, `v0.2.0`, … (with the leading `v`).

## Releasing

PyPI publishing runs from `.github/workflows/release.yml` via OIDC trusted publishing — no API tokens. Steps:

1. Bump the version in all three places above and update `CHANGELOG.md`.
2. Push the changes to the `main` branch (PR or direct push).
3. (Optional, recommended for a first try) Rehearse on TestPyPI: `gh workflow run release.yml`. Verify with `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ gedcom-lite==X.Y.Z` in a throwaway venv.
4. Cut the real release: `gh release create vX.Y.Z --generate-notes`. The workflow builds and uploads to PyPI.
5. Verify with `pip install gedcom-lite==X.Y.Z` in a fresh venv.

CI (`.github/workflows/ci.yml`) runs `pytest` on push and PR across Python 3.11/3.12/3.13. Don't merge a release bump on red CI.

The PyPI / TestPyPI trusted-publisher entries and the `pypi` / `testpypi` GitHub Environments are one-time setup, documented at the top of `release.yml`.

## House style

- Short, declarative, prescriptive where it matters. Match the tone of this file.
- No emojis in code or docs unless the user explicitly asks.
- Default to no comments in code; add one only when the *why* is non-obvious. Module-level docstrings are fine for the *what*.
- Type annotations everywhere. The codebase is `from __future__ import annotations` clean.
- Explicit imports, no wildcards.
