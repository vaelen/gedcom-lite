# Changelog

All notable changes to `gedcom-lite` are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

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
