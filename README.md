# gedcom-lite

A lightweight, fidelity-preserving GEDCOM parser, writer, and command-line toolkit for genealogy files. Supports GEDCOM 5.5.1, 5.5.5, and the current FamilySearch GEDCOM 7.0+ standard.

The "lite" in the name is a deliberate scope choice: pure Python, no runtime dependencies, no schema validation, no genealogy domain modelling beyond what the file format itself defines. The library models GEDCOM as a tree of `Structure` records and exposes search and mutation primitives that round-trip every file in the official sample suite **byte-for-byte**.

## Why use it

- **Round-trip fidelity.** Parse a file and write it back unchanged: BOM, line endings, `CONC`/`CONT` choice, sibling order, and unknown extension tags are all preserved.
- **Targeted edits.** Mutation primitives mark only the structures you change as dirty; every other line emits byte-identical to the source. An update that touches a single `NAME` produces a one-line diff.
- **Encoding coverage.** Detects UTF-8 (with or without BOM), UTF-16 LE/BE (with BOM), and ANSEL (legacy 5.5.1) — the ANSEL codec ships in-package.
- **No dependencies.** Pure Python 3.11+ standard library.
- **Three CLI tools.** `gedcom-read`, `gedcom-search`, `gedcom-update` cover the common verbs without scripting.

## Install

```bash
# from PyPI (once published)
pip install gedcom-lite

# from git
pip install "git+https://github.com/vaelen/gedcom-lite@v0.1.0"

# editable, for hacking
git clone https://github.com/vaelen/gedcom-lite
cd gedcom-lite
pip install -e ".[dev]"
```

## Library usage

```python
from gedcom_lite import GedcomDocument

doc = GedcomDocument.parse("tree.ged")

print(doc.version)               # '7.0'
print(doc.encoding)              # 'utf-8-sig'
print(doc.record_counts())       # {'INDI': 142, 'FAM': 47, ...}

indi = doc.resolve("@I1@")
name = indi.find("NAME")
name.set_payload("Jane /Doe/")

doc.write("tree-edited.ged")
```

The full surface is documented in `src/gedcom_lite/__init__.py`. Common helpers:

```python
from gedcom_lite import (
    GedcomDocument, Structure,
    parse_date_value, DateValue,
    parents_of, children_of, ancestors_of, descendants_of,
    document_to_dict, structure_to_dict,
)
```

## CLI usage

Three console scripts are installed:

```bash
gedcom-read   FILE [...]
gedcom-search FILE [filters...]
gedcom-update FILE [-o OUT | --in-place] SUBCOMMAND ...
```

Examples:

```bash
# overview of a file
gedcom-read tree.ged

# list every individual
gedcom-read tree.ged list INDI

# show one record with pointers resolved
gedcom-read tree.ged record @I1@

# JSON dump for piping into jq
gedcom-read tree.ged --json | jq '.records | length'

# find people named Smith
gedcom-search tree.ged --person Smith

# people born between 1900 and 1910
gedcom-search tree.ged --born-between 1900 1910

# children, parents, ancestors, descendants
gedcom-search tree.ged --children-of @I1@
gedcom-search tree.ged --ancestors-of @I1@ --depth 4

# edit a name (default writes to stdout)
gedcom-update tree.ged set-payload @I1@ NAME "Jane /Doe/" > new.ged

# add a NOTE to a record (write to a file)
gedcom-update tree.ged -o new.ged add-substructure @I1@ "" NOTE "Met at reunion"

# delete a record, voiding inbound pointers
gedcom-update tree.ged -o new.ged delete-record @I7@ --orphan-pointers void

# overwrite the source (be sure)
gedcom-update tree.ged --in-place set-payload @I1@ NAME "Jane /Doe/"
```

`gedcom-update` never modifies the input file unless `--in-place` is given.

Run any tool with `--help` for the full flag list.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite covers:

- Tokenizer edge cases (xref slot, missing payload, malformed lines)
- Encoding detection (BOM-first, then `1 CHAR`, then ANSEL)
- ANSEL codec round-trips, including combining-mark ordering
- Date parsing across `ABT`, `BET … AND …`, `FROM … TO …`, calendar escapes
- Round-trip of every fixture in `examples/` (the gating test)
- Mutation primitives, including the "only-touched-lines-change" property
- Ancestry/descendancy traversal
- CLI smoke tests for `gedcom-read`, `gedcom-search`, `gedcom-update`

## Versions in scope

- **GEDCOM 5.5.1** (1999) — the de-facto interchange format used by virtually every genealogy app shipped before 2022.
- **GEDCOM 5.5.5** (2019) — cleanup release of the 5.5.x line.
- **FamilySearch GEDCOM 7.0+** (2021–) — current, actively maintained. UTF-8 only, real extension mechanism, GEDZIP packaging, no `CONC`.

GEDCOM 7 is a breaking change from 5.5.x. `gedcom-lite` reads any of the three; on write it never silently promotes a file to a different version.

## License

MIT — see [LICENSE](LICENSE).

## References

- [GEDCOM 5.5.5 specification](https://www.gedcom.org/)
- [FamilySearch GEDCOM 7 specification](https://gedcom.io/specifications/FamilySearchGEDCOMv7.html)
- [FamilySearch GEDCOM Compatibility Guide](https://gedcom.io/compatibility/)
