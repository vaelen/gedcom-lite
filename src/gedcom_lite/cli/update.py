# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""``gedcom-update`` — modify a GEDCOM file with round-trip fidelity.

Subcommands operate on a record by xref and an optional tag-path within it:

  set-payload XREF PATH VALUE
  add-substructure XREF PATH NEW_TAG [VALUE]
  remove XREF PATH
  add-record TYPE [--xref XREF]      (XREF is auto-generated if omitted)
  delete-record XREF [--orphan-pointers void|strip]

Default output is to stdout. Write to a file with ``-o FILE``, or overwrite the
input with ``--in-place``. The script never modifies the input unless
``--in-place`` is given.

PATH is slash-delimited tags relative to the record root, e.g. ``NAME`` or
``BIRT/DATE``. The first matching child at each level is targeted (consistent
with the GEDCOM convention that the first sibling is preferred). An empty
PATH (``""``) refers to the record itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gedcom_lite import GedcomDocument, Structure


def _navigate(start: Structure, path: str) -> Structure:
    if not path:
        return start
    node = start
    for part in path.split("/"):
        nxt = node.find(part)
        if nxt is None:
            raise SystemExit(f"path component {part!r} not found under {node.tag} (record {start.xref})")
        node = nxt
    return node


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def op_set_payload(doc: GedcomDocument, xref: str, path: str, value: str) -> None:
    rec = doc.resolve(xref)
    if rec is None:
        raise SystemExit(f"no record with xref {xref}")
    target = _navigate(rec, path)
    target.set_payload(value)


def op_add_substructure(doc: GedcomDocument, xref: str, path: str, tag: str, value: str | None) -> None:
    rec = doc.resolve(xref)
    if rec is None:
        raise SystemExit(f"no record with xref {xref}")
    parent = _navigate(rec, path)
    parent.add_child(tag, value)


def op_remove(doc: GedcomDocument, xref: str, path: str) -> None:
    rec = doc.resolve(xref)
    if rec is None:
        raise SystemExit(f"no record with xref {xref}")
    if not path:
        raise SystemExit("`remove` requires a non-empty PATH; use `delete-record` to remove a whole record")
    target = _navigate(rec, path)
    target.remove()


def op_add_record(doc: GedcomDocument, tag: str, xref: str | None) -> str:
    rec = doc.add_record(tag, xref=xref)
    return rec.xref or ""


def op_delete_record(doc: GedcomDocument, xref: str, orphan_strategy: str | None) -> None:
    rec = doc.resolve(xref)
    if rec is None:
        raise SystemExit(f"no record with xref {xref}")
    inbound = doc.inbound_pointers(xref)
    if inbound:
        if orphan_strategy is None:
            details = "\n".join(f"  {p.path()} (record {_record_xref(p)})" for p in inbound[:10])
            extra = "" if len(inbound) <= 10 else f"\n  …and {len(inbound) - 10} more"
            raise SystemExit(
                f"refusing to delete {xref}: {len(inbound)} inbound pointer(s) would dangle.\n"
                f"{details}{extra}\n"
                "Re-run with --orphan-pointers void  (rewrite payloads to @VOID@)\n"
                "         or --orphan-pointers strip (remove the pointing structures)"
            )
        for ptr in inbound:
            if orphan_strategy == "void":
                ptr.set_payload("@VOID@")
            elif orphan_strategy == "strip":
                ptr.remove()
    doc.remove_record(xref)


def _record_xref(s: Structure) -> str | None:
    node = s
    while node.parent is not None:
        node = node.parent
    return node.xref


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gedcom-update",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("file", help="path to the input .ged file (or - for stdin)")
    p.add_argument("-o", "--output", help="write result here (default: stdout)")
    p.add_argument("--in-place", action="store_true",
                   help="overwrite the input file (mutually exclusive with -o and stdin)")

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("set-payload", help="change a structure's payload")
    sp.add_argument("xref")
    sp.add_argument("path")
    sp.add_argument("value")

    sa = sub.add_parser("add-substructure", help="append a new substructure under PATH")
    sa.add_argument("xref")
    sa.add_argument("path")
    sa.add_argument("tag")
    sa.add_argument("value", nargs="?", default=None)

    sr = sub.add_parser("remove", help="delete the structure at PATH within record XREF")
    sr.add_argument("xref")
    sr.add_argument("path")

    ar = sub.add_parser("add-record", help="create a new top-level record")
    ar.add_argument("type", help="record tag, e.g. INDI, FAM, SOUR")
    ar.add_argument("--xref", default=None, help="explicit xref id (auto-generated if omitted)")

    dr = sub.add_parser("delete-record", help="remove a top-level record")
    dr.add_argument("xref")
    dr.add_argument("--orphan-pointers", choices=("void", "strip"), default=None,
                    help="how to handle inbound pointers: void → @VOID@, strip → remove the pointer")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.in_place and args.output:
        print("error: --in-place and -o/--output are mutually exclusive", file=sys.stderr)
        return 2
    if args.in_place and args.file == "-":
        print("error: --in-place requires a file path, not stdin", file=sys.stderr)
        return 2

    if args.file == "-":
        doc = GedcomDocument.parse(sys.stdin.buffer.read())
    else:
        doc = GedcomDocument.parse(args.file)

    new_xref: str | None = None

    if args.command == "set-payload":
        op_set_payload(doc, args.xref, args.path, args.value)
    elif args.command == "add-substructure":
        op_add_substructure(doc, args.xref, args.path, args.tag, args.value)
    elif args.command == "remove":
        op_remove(doc, args.xref, args.path)
    elif args.command == "add-record":
        new_xref = op_add_record(doc, args.type, args.xref)
    elif args.command == "delete-record":
        op_delete_record(doc, args.xref, args.orphan_pointers)

    out_bytes = doc.write()

    if args.in_place:
        Path(args.file).write_bytes(out_bytes)
    elif args.output:
        Path(args.output).write_bytes(out_bytes)
    else:
        sys.stdout.buffer.write(out_bytes)

    if new_xref is not None and (args.in_place or args.output):
        print(new_xref, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
