# Changelog

All notable changes to `gedcom-lite` are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-05-06

### Added
- `gedcom-search`: `--ancestors-of` and `--descendants-of` now attach a `generation` integer to each record (top-level field with `--json`/`--facts`; `(gen N)` suffix in text). Subject = 0; shortest path wins for individuals reachable via multiple FAMC paths.
- `gedcom-search --facts`: new output mode emitting one canonical JSON object per INDI with shape `{xref, name, birth: {date, place}, death: {date, place}, parents, famc}`. Composes with `--xref`, `--person`, `--ancestors-of`, `--descendants-of`, `--ahnentafel`, and `--famc-conflicts`. Mutually exclusive with `--json` and `--show-record`.
- `gedcom-search --primary-famc-only`: when traversing, follow only the first FAMC of any individual. Affects `--parents-of`, `--ancestors-of`, `--descendants-of`, and `--ahnentafel`. For descent, a child counts only when the current family is its primary FAMC.
- `gedcom-search --famc-conflicts`: query mode emitting INDIs with more than one FAMC entry.
- `gedcom-search --ahnentafel @I1@`: Sosa-Stradonitz numbered ancestor list. Subject = 1; father of N = 2N; mother = 2N+1. Emits `sosa` and `generation` in JSON modes; sosa-prefixed text otherwise. Without `--primary-famc-only`, the same individual is emitted once per Sosa-reachable path.
- New public traversal functions: `ancestors_of_with_generation`, `descendants_of_with_generation`, `ahnentafel`. The legacy `ancestors_of` / `descendants_of` wrap them and remain compatible. All four traversal helpers now accept `primary_famc_only=True`.

## [0.1.0] — 2026-05-06

### Added
- Initial release.
- `GedcomDocument` parser/writer with round-trip fidelity for GEDCOM 5.5.1, 5.5.5, and FamilySearch GEDCOM 7.0+.
- Encoding detection: UTF-8 (with/without BOM), UTF-16 LE/BE (with BOM), ANSEL (5.5.1 legacy).
- In-package ANSEL codec including combining-mark ordering.
- Mutation primitives that preserve untouched lines byte-identically: `set_payload`, `add_child`, `remove`, `add_record`, `remove_record`.
- Date parser (`parse_date_value`) covering exact, range (`BET … AND …`), period (`FROM … TO …`), approximate (`ABT`/`EST`/`CAL`), and `BEF`/`AFT` modifiers, with calendar escape recognition.
- Ancestry traversal helpers: `parents_of`, `children_of`, `ancestors_of`, `descendants_of`.
- Three CLI tools installed as console scripts: `gedcom-read`, `gedcom-search`, `gedcom-update`.
- Test suite spanning tokenizer, encoding, ANSEL codec, dates, round-trip, mutation, traversal, and CLI behavior.
