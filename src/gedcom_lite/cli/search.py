# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""``gedcom-search`` — search a GEDCOM file by tag, value, path, or relation.

Search modes:

* Generic structure filters (used alone)
    --xref @I1@                 lookup a single record by id
    --tag NAME                  match structures with this tag
    --value Smith               substring match on payload (or --regex)
    --regex                     interpret --value as a regular expression
    --in INDI                   restrict matches to within records of this tag
    --path INDI/BIRT/DATE       tree-path query (path components are tags)

* Person / date / place (combinable; AND together)
    --person "John Smith"       INDI whose NAME contains this string
    --born-between LO HI        INDI with parseable BIRT date in [LO, HI]
    --died-between LO HI        INDI with parseable DEAT date in [LO, HI]
    --born-in PLACE             INDI whose BIRT.PLAC contains this string
    --died-in PLACE             INDI whose DEAT.PLAC contains this string

  LO and HI may be MIN or MAX for an unbounded side (e.g. --died-between MIN 1776).

* Relationship traversal (one at a time; composes with person/date/place as
  a post-filter on the traversal result)
    --children-of @I1@          children via FAMS → CHIL
    --parents-of @I1@           parents via FAMC → HUSB/WIFE
    --ancestors-of @I1@         all ancestors (with --depth N)
    --descendants-of @I1@       all descendants (with --depth N)
    --ahnentafel @I1@           Sosa-numbered ancestor list
    --depth N                   limit ancestor/descendant traversal

* FAMC handling
    --primary-famc-only         follow only the first FAMC of any individual
    --famc-conflicts            list INDIs with more than one FAMC

Output modifiers (one of --json / --facts / --show-record at most):
    --json                      structured matches as JSON
    --facts                     per-INDI canonical JSON shape
    --show-record               include the surrounding record dump
    --count                     emit only the number of matches
    --limit N                   cap the number of matches
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Callable

from gedcom_lite import (
    GedcomDocument,
    Structure,
    ahnentafel,
    ancestors_of_with_generation,
    children_of,
    descendants_of_with_generation,
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


IndiPredicate = Callable[[Structure], bool]


def _name_predicate(query: str, regex: bool) -> IndiPredicate:
    pattern = re.compile(query, re.IGNORECASE) if regex else None
    needle = query.lower()

    def pred(indi: Structure) -> bool:
        for n in indi.find_all_children("NAME"):
            payload = n.payload or ""
            if pattern is not None:
                if pattern.search(payload):
                    return True
            else:
                if needle in payload.lower():
                    return True
        return False

    return pred


def _year_range_predicate(event_tag: str, lo: int | None, hi: int | None) -> IndiPredicate:
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo

    def pred(indi: Structure) -> bool:
        ev = indi.find(event_tag)
        if ev is None:
            return False
        date = ev.find("DATE")
        if date is None:
            return False
        dv = parse_date_value(date.payload)
        y = dv.start_year if dv.start_year is not None else dv.end_year
        if y is None:
            return False
        if lo is not None and y < lo:
            return False
        if hi is not None and y > hi:
            return False
        return True

    return pred


def _place_predicate(event_tag: str, place: str, regex: bool) -> IndiPredicate:
    pattern = re.compile(place, re.IGNORECASE) if regex else None
    needle = place.lower()

    def pred(indi: Structure) -> bool:
        ev = indi.find(event_tag)
        if ev is None:
            return False
        plac = ev.find("PLAC")
        if plac is None or plac.payload is None:
            return False
        payload = plac.payload
        if pattern is not None:
            return pattern.search(payload) is not None
        return needle in payload.lower()

    return pred


def _build_indi_predicates(args: argparse.Namespace) -> list[IndiPredicate]:
    preds: list[IndiPredicate] = []
    if args.person is not None:
        preds.append(_name_predicate(args.person, args.regex))
    if args.born_between is not None:
        preds.append(_year_range_predicate("BIRT", args.born_between[0], args.born_between[1]))
    if args.died_between is not None:
        preds.append(_year_range_predicate("DEAT", args.died_between[0], args.died_between[1]))
    if args.born_in is not None:
        preds.append(_place_predicate("BIRT", args.born_in, args.regex))
    if args.died_in is not None:
        preds.append(_place_predicate("DEAT", args.died_in, args.regex))
    return preds


def _apply_predicates(
    records: list[Structure],
    generations: list[int | None] | None,
    sosas: list[int | None] | None,
    preds: list[IndiPredicate],
) -> tuple[list[Structure], list[int | None] | None, list[int | None] | None]:
    if not preds:
        return records, generations, sosas
    keep = [all(p(r) for p in preds) for r in records]
    records = [r for r, k in zip(records, keep) if k]
    if generations is not None:
        generations = [g for g, k in zip(generations, keep) if k]
    if sosas is not None:
        sosas = [s for s, k in zip(sosas, keep) if k]
    return records, generations, sosas


def _famc_conflicts(doc: GedcomDocument) -> list[Structure]:
    return [i for i in _individuals(doc) if len(i.find_all_children("FAMC")) > 1]


# ---------------------------------------------------------------------------
# Per-INDI fact projection (--facts shape)
# ---------------------------------------------------------------------------

def _event_pair(event: Structure | None) -> tuple[str | None, str | None]:
    if event is None:
        return (None, None)
    date = event.find("DATE")
    plac = event.find("PLAC")
    return (
        date.payload if date and date.payload else None,
        plac.payload if plac and plac.payload else None,
    )


def _indi_facts(
    indi: Structure,
    doc: GedcomDocument,
    *,
    generation: int | None = None,
    sosa: int | None = None,
    primary_famc_only: bool = False,
) -> dict:
    name = indi.find("NAME")
    birth_date, birth_place = _event_pair(indi.find("BIRT"))
    death_date, death_place = _event_pair(indi.find("DEAT"))
    parent_xrefs = [
        p.xref for p in parents_of(doc, indi, primary_famc_only=primary_famc_only)
        if p.xref
    ]
    famc_payloads = [
        c.payload for c in indi.find_all_children("FAMC") if c.payload
    ]
    out: dict = {
        "xref": indi.xref,
        "name": name.payload if name and name.payload else None,
        "birth": {"date": birth_date, "place": birth_place},
        "death": {"date": death_date, "place": death_place},
        "parents": parent_xrefs,
        "famc": famc_payloads,
    }
    if generation is not None:
        out["generation"] = generation
    if sosa is not None:
        out["sosa"] = sosa
    return out


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

def _person_summary(rec: Structure, *, generation: int | None = None, sosa: int | None = None) -> str:
    name = rec.find("NAME")
    name_str = name.payload if name and name.payload else "(no name)"
    bd = rec.find("BIRT")
    dd = rec.find("DEAT")
    birth = (bd.find("DATE").payload if bd and bd.find("DATE") else None)
    death = (dd.find("DATE").payload if dd and dd.find("DATE") else None)
    if birth or death:
        line = f"{rec.xref}  {name_str}  ({birth or '?'} – {death or '?'})"
    else:
        line = f"{rec.xref}  {name_str}"
    if sosa is not None:
        line = f"{sosa}  {line}"
    elif generation is not None:
        line = f"{line} (gen {generation})"
    return line


def _record_summary_line(rec: Structure, *, generation: int | None = None, sosa: int | None = None) -> str:
    if rec.tag == "INDI":
        return _person_summary(rec, generation=generation, sosa=sosa)
    if rec.tag == "FAM":
        partners = []
        for slot in ("HUSB", "WIFE"):
            for s in rec.find_all_children(slot):
                if s.payload:
                    partners.append(s.payload)
        chil = rec.find_all_children("CHIL")
        return f"{rec.xref}  {' × '.join(partners) or '(no spouses)'}  [{len(chil)} child{'ren' if len(chil) != 1 else ''}]"
    return f"{rec.xref}  ({rec.tag})"


def _emit_records(
    records: list[Structure],
    args: argparse.Namespace,
    doc: GedcomDocument,
    *,
    generations: list[int | None] | None = None,
    sosas: list[int | None] | None = None,
) -> None:
    if generations is None:
        generations = [None] * len(records)
    if sosas is None:
        sosas = [None] * len(records)

    if args.count:
        sys.stdout.write(f"{len(records)}\n")
        return
    if args.facts:
        items = []
        for r, gen, sosa in zip(records, generations, sosas):
            if r.tag != "INDI":
                continue
            items.append(_indi_facts(
                r, doc,
                generation=gen, sosa=sosa,
                primary_famc_only=args.primary_famc_only,
            ))
        sys.stdout.write(json.dumps(items, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return
    if args.json:
        items = []
        for r, gen, sosa in zip(records, generations, sosas):
            d = structure_to_dict(r)
            if gen is not None:
                d["generation"] = gen
            if sosa is not None:
                d["sosa"] = sosa
            items.append(d)
        sys.stdout.write(json.dumps(items, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return
    for r, gen, sosa in zip(records, generations, sosas):
        sys.stdout.write(_record_summary_line(r, generation=gen, sosa=sosa) + "\n")
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

def _parse_year_bound(value: str) -> int | None:
    if value.upper() in ("MIN", "MAX"):
        return None
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected an integer year or 'MIN'/'MAX', got {value!r}"
        )


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

    pe = p.add_argument_group("person / date / place (combinable; AND together)")
    pe.add_argument("--person", metavar="NAME", help="find INDI whose NAME contains this string (case-insensitive)")
    pe.add_argument("--born-between", nargs=2, metavar=("YEAR_LO", "YEAR_HI"), type=_parse_year_bound,
                    help="find INDI with parseable BIRT date in [YEAR_LO, YEAR_HI] (use MIN/MAX for unbounded)")
    pe.add_argument("--died-between", nargs=2, metavar=("YEAR_LO", "YEAR_HI"), type=_parse_year_bound,
                    help="find INDI with parseable DEAT date in [YEAR_LO, YEAR_HI] (use MIN/MAX for unbounded)")
    pe.add_argument("--born-in", metavar="PLACE", help="find INDI whose BIRT.PLAC contains this string")
    pe.add_argument("--died-in", metavar="PLACE", help="find INDI whose DEAT.PLAC contains this string")

    rl = p.add_argument_group("relationship traversal")
    rl.add_argument("--children-of", metavar="XREF", help="children of an INDI via FAMS → CHIL")
    rl.add_argument("--parents-of", metavar="XREF", help="parents of an INDI via FAMC → HUSB/WIFE")
    rl.add_argument("--ancestors-of", metavar="XREF", help="all ancestors of an INDI")
    rl.add_argument("--descendants-of", metavar="XREF", help="all descendants of an INDI")
    rl.add_argument("--ahnentafel", metavar="XREF", help="Sosa-numbered ancestor list rooted at this INDI")
    rl.add_argument("--depth", type=int, default=99, help="cap traversal depth (default: unlimited)")

    fc = p.add_argument_group("FAMC handling")
    fc.add_argument("--primary-famc-only", action="store_true",
                    help="follow only the first FAMC of any individual during traversal")
    fc.add_argument("--famc-conflicts", action="store_true",
                    help="list INDIs with more than one FAMC entry")

    o = p.add_argument_group("output")
    o.add_argument("--json", action="store_true", help="emit JSON")
    o.add_argument("--facts", action="store_true",
                   help="emit per-INDI canonical JSON facts (xref, name, birth, death, parents, famc)")
    o.add_argument("--show-record", action="store_true", help="include surrounding record dumps")
    o.add_argument("--count", action="store_true", help="emit only the number of matches")
    o.add_argument("--limit", type=int, help="cap the number of matches emitted")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if sum([args.json, args.facts, args.show_record]) > 1:
        print("error: --json, --facts, and --show-record are mutually exclusive.", file=sys.stderr)
        return 2

    if args.file == "-":
        doc = GedcomDocument.parse(sys.stdin.buffer.read())
    else:
        doc = GedcomDocument.parse(args.file)

    indi_filters_active = any([
        args.person is not None,
        args.born_between is not None,
        args.died_between is not None,
        args.born_in is not None,
        args.died_in is not None,
    ])
    rel_modes = [
        args.children_of, args.parents_of, args.ancestors_of,
        args.descendants_of, args.ahnentafel,
    ]
    rel_active = any(rel_modes)
    generic_filters = any([args.tag, args.value, args.in_record, args.path, args.xref])

    if not (generic_filters or indi_filters_active or rel_active or args.famc_conflicts):
        print("error: no search criteria given. See --help for the available filters.", file=sys.stderr)
        return 2
    if generic_filters and (indi_filters_active or rel_active or args.famc_conflicts):
        print(
            "error: generic filters (--xref/--tag/--value/--path/--in) cannot combine "
            "with person/relationship/famc-conflicts modes.",
            file=sys.stderr,
        )
        return 2
    if args.famc_conflicts and (indi_filters_active or rel_active):
        print(
            "error: --famc-conflicts cannot combine with person/relationship filters.",
            file=sys.stderr,
        )
        return 2
    if rel_active and sum(1 for m in rel_modes if m) > 1:
        print(
            "error: pick exactly one of --children-of / --parents-of / --ancestors-of "
            "/ --descendants-of / --ahnentafel.",
            file=sys.stderr,
        )
        return 2

    if args.xref:
        rec = doc.resolve(args.xref)
        records = [rec] if rec is not None else []
        if args.limit:
            records = records[: args.limit]
        _emit_records(records, args, doc)
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

    if args.famc_conflicts:
        results = _famc_conflicts(doc)
        if args.limit:
            results = results[: args.limit]
        _emit_records(results, args, doc)
        return 0

    preds = _build_indi_predicates(args)

    if rel_active:
        anchor_xref = (
            args.children_of or args.parents_of or args.ancestors_of
            or args.descendants_of or args.ahnentafel
        )
        anchor = doc.resolve(anchor_xref)
        if anchor is None:
            print(f"error: no INDI with xref {anchor_xref}", file=sys.stderr)
            return 1
        generations: list[int | None] | None = None
        sosas: list[int | None] | None = None
        if args.children_of:
            results = children_of(doc, anchor, primary_famc_only=args.primary_famc_only)
        elif args.parents_of:
            results = parents_of(doc, anchor, primary_famc_only=args.primary_famc_only)
        elif args.ancestors_of:
            paired = ancestors_of_with_generation(
                doc, anchor, depth=args.depth,
                primary_famc_only=args.primary_famc_only,
            )
            results = [s for s, _ in paired]
            generations = [g for _, g in paired]
        elif args.descendants_of:
            paired = descendants_of_with_generation(
                doc, anchor, depth=args.depth,
                primary_famc_only=args.primary_famc_only,
            )
            results = [s for s, _ in paired]
            generations = [g for _, g in paired]
        else:
            triples = ahnentafel(
                doc, anchor, depth=args.depth,
                primary_famc_only=args.primary_famc_only,
            )
            results = [s for s, _, _ in triples]
            generations = [g for _, g, _ in triples]
            sosas = [n for _, _, n in triples]
        results, generations, sosas = _apply_predicates(results, generations, sosas, preds)
        if args.limit:
            results = results[: args.limit]
            if generations is not None:
                generations = generations[: args.limit]
            if sosas is not None:
                sosas = sosas[: args.limit]
        _emit_records(results, args, doc, generations=generations, sosas=sosas)
        return 0

    if indi_filters_active:
        results = [i for i in _individuals(doc) if all(p(i) for p in preds)]
        if args.limit:
            results = results[: args.limit]
        _emit_records(results, args, doc)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
