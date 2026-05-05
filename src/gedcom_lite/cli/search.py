# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""``gedcom-search`` — search a GEDCOM file by tag, value, path, or relation.

Three search modes (one chosen per invocation):

* Generic structure filters
    --xref @I1@                 lookup a single record by id
    --tag NAME                  match structures with this tag
    --value Smith               substring match on payload (or --regex)
    --regex                     interpret --value as a regular expression
    --in INDI                   restrict matches to within records of this tag
    --path INDI/BIRT/DATE       tree-path query (path components are tags)

* Person / date / place
    --person "John Smith"       INDI whose NAME contains this string
    --born-between 1900 1910    INDI with parseable BIRT date in range
    --died-in Boston            INDI with DEAT.PLAC matching

* Relationship traversal
    --children-of @I1@          children via FAMS → CHIL
    --parents-of @I1@           parents via FAMC → HUSB/WIFE
    --ancestors-of @I1@         all ancestors (with --depth N)
    --descendants-of @I1@       all descendants (with --depth N)
    --depth N                   limit ancestor/descendant traversal

Output modifiers:
    --json                      structured matches as JSON
    --show-record               include the surrounding record dump
    --count                     emit only the number of matches
    --limit N                   cap the number of matches
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from gedcom_lite import (
    GedcomDocument,
    Structure,
    ancestors_of,
    children_of,
    descendants_of,
    parents_of,
    parse_date_value,
    structure_to_dict,
)


# ---------------------------------------------------------------------------
# Match shape
# ---------------------------------------------------------------------------

def _record_root(s: Structure) -> Structure:
    node = s
    while node.parent is not None:
        node = node.parent
    return node


def _match_dict(s: Structure) -> dict:
    root = _record_root(s)
    return {
        "xref": root.xref,
        "record_tag": root.tag,
        "tag": s.tag,
        "path": s.path(),
        "payload": s.payload,
        "line": s.source_line_no or None,
    }


def _format_match_line(s: Structure) -> str:
    root = _record_root(s)
    payload = "" if s.payload is None else f' "{s.payload}"'
    line = f":{s.source_line_no}" if s.source_line_no else ""
    return f"{root.xref or '(no xref)'} {s.path()}{payload}{line}"


# ---------------------------------------------------------------------------
# Structure-level search
# ---------------------------------------------------------------------------

def _structure_filter(
    doc: GedcomDocument,
    *,
    tag: str | None,
    value: str | None,
    regex: bool,
    in_record: str | None,
    path: str | None,
) -> list[Structure]:
    pattern = re.compile(value) if (value is not None and regex) else None
    path_parts = path.split("/") if path else None

    def _matches(s: Structure) -> bool:
        if tag and s.tag != tag:
            return False
        if path_parts is not None:
            structure_path = s.path().split("/")
            if structure_path[-len(path_parts):] != path_parts:
                return False
        if value is not None:
            if pattern is not None:
                if s.payload is None or not pattern.search(s.payload):
                    return False
            else:
                if s.payload is None or value not in s.payload:
                    return False
        return True

    out: list[Structure] = []
    for record in (doc.header, *doc.records):
        if in_record and record.tag != in_record:
            continue
        for s in record.walk():
            if _matches(s):
                out.append(s)
    return out


# ---------------------------------------------------------------------------
# Person-shaped queries
# ---------------------------------------------------------------------------

def _individuals(doc: GedcomDocument) -> list[Structure]:
    return doc.find_records("INDI")


def _person_name_match(doc: GedcomDocument, query: str, regex: bool) -> list[Structure]:
    pattern = re.compile(query, re.IGNORECASE) if regex else None
    needle = query.lower()
    out: list[Structure] = []
    for indi in _individuals(doc):
        for n in indi.find_all_children("NAME"):
            payload = n.payload or ""
            if pattern is not None:
                if pattern.search(payload):
                    out.append(indi)
                    break
            else:
                if needle in payload.lower():
                    out.append(indi)
                    break
    return out


def _born_between(doc: GedcomDocument, year_lo: int, year_hi: int) -> list[Structure]:
    if year_lo > year_hi:
        year_lo, year_hi = year_hi, year_lo
    out: list[Structure] = []
    for indi in _individuals(doc):
        birt = indi.find("BIRT")
        if birt is None:
            continue
        date = birt.find("DATE")
        if date is None:
            continue
        dv = parse_date_value(date.payload)
        y = dv.start_year if dv.start_year is not None else dv.end_year
        if y is None:
            continue
        if year_lo <= y <= year_hi:
            out.append(indi)
    return out


def _died_in(doc: GedcomDocument, place: str, regex: bool) -> list[Structure]:
    pattern = re.compile(place, re.IGNORECASE) if regex else None
    needle = place.lower()
    out: list[Structure] = []
    for indi in _individuals(doc):
        deat = indi.find("DEAT")
        if deat is None:
            continue
        plac = deat.find("PLAC")
        if plac is None or plac.payload is None:
            continue
        payload = plac.payload
        if pattern is not None:
            if pattern.search(payload):
                out.append(indi)
        else:
            if needle in payload.lower():
                out.append(indi)
    return out


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

def _person_summary(rec: Structure) -> str:
    name = rec.find("NAME")
    name_str = name.payload if name and name.payload else "(no name)"
    bd = rec.find("BIRT")
    dd = rec.find("DEAT")
    birth = (bd.find("DATE").payload if bd and bd.find("DATE") else None)
    death = (dd.find("DATE").payload if dd and dd.find("DATE") else None)
    if birth or death:
        return f"{rec.xref}  {name_str}  ({birth or '?'} – {death or '?'})"
    return f"{rec.xref}  {name_str}"


def _record_summary_line(rec: Structure) -> str:
    if rec.tag == "INDI":
        return _person_summary(rec)
    if rec.tag == "FAM":
        partners = []
        for slot in ("HUSB", "WIFE"):
            for s in rec.find_all_children(slot):
                if s.payload:
                    partners.append(s.payload)
        chil = rec.find_all_children("CHIL")
        return f"{rec.xref}  {' × '.join(partners) or '(no spouses)'}  [{len(chil)} child{'ren' if len(chil) != 1 else ''}]"
    return f"{rec.xref}  ({rec.tag})"


def _emit_records(records: list[Structure], args: argparse.Namespace, doc: GedcomDocument) -> None:
    if args.count:
        sys.stdout.write(f"{len(records)}\n")
        return
    if args.json:
        sys.stdout.write(json.dumps([structure_to_dict(r) for r in records], indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return
    for r in records:
        sys.stdout.write(_record_summary_line(r) + "\n")
        if args.show_record:
            sys.stdout.write(_render_record(r) + "\n")


def _emit_structure_matches(matches: list[Structure], args: argparse.Namespace, doc: GedcomDocument) -> None:
    if args.count:
        sys.stdout.write(f"{len(matches)}\n")
        return
    if args.json:
        sys.stdout.write(json.dumps([_match_dict(m) for m in matches], indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return
    seen_records: set[str] = set()
    for m in matches:
        sys.stdout.write(_format_match_line(m) + "\n")
        if args.show_record:
            root = _record_root(m)
            if root.xref and root.xref not in seen_records:
                seen_records.add(root.xref)
                sys.stdout.write(_render_record(root) + "\n")


def _render_record(rec: Structure, depth: int = 0, max_depth: int = 99) -> str:
    indent = "  " * depth
    head = []
    if rec.xref:
        head.append(rec.xref)
    head.append(rec.tag)
    if rec.payload is not None and rec.payload != "":
        head.append(rec.payload)
    out = [indent + " ".join(head)]
    if depth < max_depth:
        for ch in rec.children:
            out.append(_render_record(ch, depth + 1, max_depth))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gedcom-search",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("file", help="path to a .ged file (or - for stdin)")

    g = p.add_argument_group("generic structure filters")
    g.add_argument("--xref", help="lookup a single record by cross-reference id, e.g. @I1@")
    g.add_argument("--tag", help="filter to structures with this tag")
    g.add_argument("--value", help="match payload (substring, or regex with --regex)")
    g.add_argument("--regex", action="store_true", help="interpret --value as a regex")
    g.add_argument("--in", dest="in_record", metavar="TAG",
                   help="restrict matches to within records of this type (INDI, FAM, …)")
    g.add_argument("--path", help="tag-path query, e.g. INDI/BIRT/DATE")

    pe = p.add_argument_group("person / date / place")
    pe.add_argument("--person", metavar="NAME", help="find INDI whose NAME contains this string (case-insensitive)")
    pe.add_argument("--born-between", nargs=2, metavar=("YEAR_LO", "YEAR_HI"), type=int,
                    help="find INDI with parseable BIRT date in [YEAR_LO, YEAR_HI]")
    pe.add_argument("--died-in", metavar="PLACE", help="find INDI whose DEAT.PLAC contains this string")

    rl = p.add_argument_group("relationship traversal")
    rl.add_argument("--children-of", metavar="XREF", help="children of an INDI via FAMS → CHIL")
    rl.add_argument("--parents-of", metavar="XREF", help="parents of an INDI via FAMC → HUSB/WIFE")
    rl.add_argument("--ancestors-of", metavar="XREF", help="all ancestors of an INDI")
    rl.add_argument("--descendants-of", metavar="XREF", help="all descendants of an INDI")
    rl.add_argument("--depth", type=int, default=99, help="cap traversal depth (default: unlimited)")

    o = p.add_argument_group("output")
    o.add_argument("--json", action="store_true", help="emit JSON")
    o.add_argument("--show-record", action="store_true", help="include surrounding record dumps")
    o.add_argument("--count", action="store_true", help="emit only the number of matches")
    o.add_argument("--limit", type=int, help="cap the number of matches emitted")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.file == "-":
        doc = GedcomDocument.parse(sys.stdin.buffer.read())
    else:
        doc = GedcomDocument.parse(args.file)

    person_modes = [args.person is not None, args.born_between is not None, args.died_in is not None]
    rel_modes = [args.children_of, args.parents_of, args.ancestors_of, args.descendants_of]
    rel_active = any(rel_modes)
    generic_filters = any([args.tag, args.value, args.in_record, args.path, args.xref])

    active_modes = sum([generic_filters, any(person_modes), rel_active])
    if active_modes == 0:
        print("error: no search criteria given. See --help for the available filters.", file=sys.stderr)
        return 2
    if active_modes > 1:
        print("error: combine filters within a single mode only (generic / person / relationship).", file=sys.stderr)
        return 2

    if args.xref:
        rec = doc.resolve(args.xref)
        records = [rec] if rec is not None else []
        _emit_records(records[: args.limit] if args.limit else records, args, doc)
        return 0

    if generic_filters:
        matches = _structure_filter(
            doc,
            tag=args.tag, value=args.value, regex=args.regex,
            in_record=args.in_record, path=args.path,
        )
        if args.limit:
            matches = matches[: args.limit]
        _emit_structure_matches(matches, args, doc)
        return 0

    if any(person_modes):
        results: list[Structure] = []
        if args.person is not None:
            results = _person_name_match(doc, args.person, args.regex)
        elif args.born_between is not None:
            results = _born_between(doc, args.born_between[0], args.born_between[1])
        elif args.died_in is not None:
            results = _died_in(doc, args.died_in, args.regex)
        if args.limit:
            results = results[: args.limit]
        _emit_records(results, args, doc)
        return 0

    if rel_active:
        anchor_xref = args.children_of or args.parents_of or args.ancestors_of or args.descendants_of
        anchor = doc.resolve(anchor_xref)
        if anchor is None:
            print(f"error: no INDI with xref {anchor_xref}", file=sys.stderr)
            return 1
        if args.children_of:
            results = children_of(doc, anchor)
        elif args.parents_of:
            results = parents_of(doc, anchor)
        elif args.ancestors_of:
            results = ancestors_of(doc, anchor, depth=args.depth)
        else:
            results = descendants_of(doc, anchor, depth=args.depth)
        if args.limit:
            results = results[: args.limit]
        _emit_records(results, args, doc)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
