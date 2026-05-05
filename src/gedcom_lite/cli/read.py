# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""``gedcom-read`` — summarize, list, or show records from a GEDCOM file.

Subcommands:
  summary  (default)    one-paragraph overview + per-record-type counts
  list TAG              enumerate every record of TAG (INDI, FAM, SOUR, …)
  record XREF           show one record as a level-indented outline with
                        pointers resolved inline

Use ``--json`` with any subcommand to emit JSON instead of human-readable text.
"""

from __future__ import annotations

import argparse
import json
import sys

from gedcom_lite import (
    GedcomDocument,
    Structure,
    document_to_dict,
    structure_to_dict,
)


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------

def _name_of(rec: Structure) -> str:
    name = rec.find("NAME")
    if name and name.payload:
        return name.payload
    return rec.xref or "(unknown)"


def _date_of(rec: Structure, event_tag: str) -> str | None:
    ev = rec.find(event_tag)
    if ev is None:
        return None
    d = ev.find("DATE")
    return d.payload if d and d.payload else None


def _summary_line(rec: Structure) -> str:
    if rec.tag == "INDI":
        birth = _date_of(rec, "BIRT")
        death = _date_of(rec, "DEAT")
        dates = ""
        if birth or death:
            dates = f"  ({birth or '?'} – {death or '?'})"
        return f"{rec.xref}  {_name_of(rec)}{dates}"
    if rec.tag == "FAM":
        partners = []
        for slot in ("HUSB", "WIFE"):
            for s in rec.find_all_children(slot):
                if s.payload:
                    partners.append(s.payload)
        chil = rec.find_all_children("CHIL")
        return f"{rec.xref}  {' × '.join(partners) or '(no spouses)'}  [{len(chil)} child{'ren' if len(chil) != 1 else ''}]"
    if rec.tag == "SOUR":
        title = rec.find("TITL")
        return f"{rec.xref}  {title.payload if title and title.payload else '(no title)'}"
    if rec.tag == "REPO":
        nm = rec.find("NAME")
        return f"{rec.xref}  {nm.payload if nm and nm.payload else '(no name)'}"
    if rec.tag == "OBJE":
        f = rec.find("FILE")
        return f"{rec.xref}  {f.payload if f and f.payload else '(no file)'}"
    if rec.tag in ("NOTE", "SNOTE"):
        snippet = (rec.payload or "")[:60]
        return f"{rec.xref}  {snippet!r}"
    if rec.tag == "SUBM":
        nm = rec.find("NAME")
        return f"{rec.xref}  {nm.payload if nm and nm.payload else '(no name)'}"
    return f"{rec.xref}  ({rec.tag})"


def _term_label(t: str) -> str:
    return {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}.get(t, repr(t))


def render_summary(doc: GedcomDocument) -> str:
    lines: list[str] = []
    lines.append(f"GEDCOM version: {doc.version or 'unknown'}")
    bom = "with BOM" if doc.bom else "no BOM"
    lines.append(f"Encoding: {doc.encoding} ({bom})")
    lines.append(f"Line ending: {_term_label(doc.line_terminator)}")
    sour = doc.header.find("SOUR")
    if sour:
        prod = sour.payload or "(unknown)"
        ver = sour.find("VERS")
        nm = sour.find("NAME")
        bits = [prod]
        if nm and nm.payload:
            bits.append(nm.payload)
        if ver and ver.payload:
            bits.append(f"v{ver.payload}")
        lines.append(f"Originating software: {' / '.join(bits)}")
    lang = doc.header.find("LANG")
    if lang and lang.payload:
        lines.append(f"Default language: {lang.payload}")
    schema = doc.header.find("SCHMA")
    if schema:
        tags = [t.payload.split(maxsplit=1) for t in schema.find_all_children("TAG") if t.payload]
        if tags:
            lines.append("Declared extension tags:")
            for parts in tags:
                if len(parts) == 2:
                    lines.append(f"  {parts[0]}  →  {parts[1]}")
                else:
                    lines.append(f"  {parts[0]}")
    counts = doc.record_counts()
    if counts:
        lines.append("Records:")
        for tag, n in sorted(counts.items()):
            lines.append(f"  {tag:6s} {n}")
    else:
        lines.append("Records: (none)")
    if doc.parse_warnings:
        lines.append("Warnings:")
        for w in doc.parse_warnings:
            lines.append(f"  {w}")
    return "\n".join(lines) + "\n"


def render_list(doc: GedcomDocument, tag: str) -> str:
    matches = doc.find_records(tag)
    if not matches:
        return f"(no {tag} records)\n"
    return "\n".join(_summary_line(r) for r in matches) + "\n"


def render_record(doc: GedcomDocument, xref: str, max_depth: int = 99) -> str:
    rec = doc.resolve(xref)
    if rec is None:
        raise SystemExit(f"no record with xref {xref}")
    return _render_structure(rec, doc, depth=0, max_depth=max_depth)


def _render_structure(s: Structure, doc: GedcomDocument, depth: int, max_depth: int) -> str:
    indent = "  " * depth
    head_parts = []
    if s.xref:
        head_parts.append(s.xref)
    head_parts.append(s.tag)
    if s.payload is not None and s.payload != "":
        head_parts.append(s.payload)
    line = indent + " ".join(head_parts)
    if s.payload and s.payload.startswith("@") and s.payload.endswith("@") and s.payload != "@VOID@":
        target = doc.resolve(s.payload)
        if target is not None:
            line += f"   → {_summary_line(target)}"
    out = [line]
    if depth < max_depth:
        for ch in s.children:
            out.append(_render_structure(ch, doc, depth + 1, max_depth))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gedcom-read",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("file", help="path to a .ged file (or - for stdin)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("summary", help="(default) file-level summary")
    pl = sub.add_parser("list", help="list records of a given type")
    pl.add_argument("tag", help="record tag to enumerate (INDI, FAM, SOUR, REPO, OBJE, SUBM, NOTE, SNOTE, …)")
    pr = sub.add_parser("record", help="show one record")
    pr.add_argument("xref", help="cross-reference id, e.g. @I1@")
    pr.add_argument("--depth", type=int, default=99, help="max nesting depth to render (default: unlimited)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.file == "-":
        doc = GedcomDocument.parse(sys.stdin.buffer.read())
    else:
        doc = GedcomDocument.parse(args.file)

    if args.command in (None, "summary"):
        if args.json:
            sys.stdout.write(json.dumps(document_to_dict(doc), indent=2, ensure_ascii=False))
            sys.stdout.write("\n")
        else:
            sys.stdout.write(render_summary(doc))
        return 0

    if args.command == "list":
        if args.json:
            recs = [structure_to_dict(r) for r in doc.find_records(args.tag)]
            sys.stdout.write(json.dumps(recs, indent=2, ensure_ascii=False))
            sys.stdout.write("\n")
        else:
            sys.stdout.write(render_list(doc, args.tag))
        return 0

    if args.command == "record":
        rec = doc.resolve(args.xref)
        if rec is None:
            print(f"no record with xref {args.xref}", file=sys.stderr)
            return 1
        if args.json:
            sys.stdout.write(json.dumps(structure_to_dict(rec), indent=2, ensure_ascii=False))
            sys.stdout.write("\n")
        else:
            sys.stdout.write(render_record(doc, args.xref, args.depth) + "\n")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
