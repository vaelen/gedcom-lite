# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Ancestry / descendancy traversal helpers."""

from __future__ import annotations

from .core import GedcomDocument, Structure


def _primary_famc_xref(indi: Structure) -> str | None:
    famc = indi.find("FAMC")
    return famc.payload if famc and famc.payload else None


def parents_of(
    doc: GedcomDocument,
    indi: Structure,
    *,
    primary_famc_only: bool = False,
) -> list[Structure]:
    """Return the INDI records that are parents of ``indi`` via FAMC.

    With ``primary_famc_only=True``, only the first FAMC is followed.
    """
    famc_list = indi.find_all_children("FAMC")
    if primary_famc_only:
        famc_list = famc_list[:1]
    out: list[Structure] = []
    for famc in famc_list:
        fam = doc.resolve(famc.payload or "")
        if fam is None:
            continue
        for role in ("HUSB", "WIFE"):
            for slot in fam.find_all_children(role):
                p = doc.resolve(slot.payload or "")
                if p is not None and p not in out:
                    out.append(p)
    return out


def children_of(
    doc: GedcomDocument,
    indi: Structure,
    *,
    primary_famc_only: bool = False,
) -> list[Structure]:
    """Return the INDI records that are children of ``indi`` via FAMS → CHIL.

    With ``primary_famc_only=True``, a candidate child is only included if its
    own primary FAMC points back to the family currently being expanded — i.e.,
    we count as a parent only when we are the child's primary parental link.
    """
    out: list[Structure] = []
    for fams in indi.find_all_children("FAMS"):
        fam = doc.resolve(fams.payload or "")
        if fam is None:
            continue
        for chil in fam.find_all_children("CHIL"):
            c = doc.resolve(chil.payload or "")
            if c is None or c in out:
                continue
            if primary_famc_only and _primary_famc_xref(c) != fam.xref:
                continue
            out.append(c)
    return out


def ancestors_of_with_generation(
    doc: GedcomDocument,
    indi: Structure,
    depth: int = 99,
    *,
    primary_famc_only: bool = False,
) -> list[tuple[Structure, int]]:
    """All ancestors of ``indi``, paired with their generation number.

    Generation is the BFS depth: parents = 1, grandparents = 2, etc. For
    individuals reachable through multiple paths the shortest path wins
    (BFS first-visit-wins).
    """
    seen: set[str] = set()
    frontier: list[tuple[Structure, int]] = [(indi, 0)]
    out: list[tuple[Structure, int]] = []
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for p in parents_of(doc, node, primary_famc_only=primary_famc_only):
            if p.xref and p.xref not in seen:
                seen.add(p.xref)
                out.append((p, d + 1))
                frontier.append((p, d + 1))
    return out


def descendants_of_with_generation(
    doc: GedcomDocument,
    indi: Structure,
    depth: int = 99,
    *,
    primary_famc_only: bool = False,
) -> list[tuple[Structure, int]]:
    """All descendants of ``indi``, paired with their generation number."""
    seen: set[str] = set()
    frontier: list[tuple[Structure, int]] = [(indi, 0)]
    out: list[tuple[Structure, int]] = []
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for c in children_of(doc, node, primary_famc_only=primary_famc_only):
            if c.xref and c.xref not in seen:
                seen.add(c.xref)
                out.append((c, d + 1))
                frontier.append((c, d + 1))
    return out


def ancestors_of(
    doc: GedcomDocument,
    indi: Structure,
    depth: int = 99,
    *,
    primary_famc_only: bool = False,
) -> list[Structure]:
    """All ancestors of ``indi`` up to ``depth`` generations."""
    return [s for s, _ in ancestors_of_with_generation(
        doc, indi, depth, primary_famc_only=primary_famc_only
    )]


def descendants_of(
    doc: GedcomDocument,
    indi: Structure,
    depth: int = 99,
    *,
    primary_famc_only: bool = False,
) -> list[Structure]:
    """All descendants of ``indi`` down to ``depth`` generations."""
    return [s for s, _ in descendants_of_with_generation(
        doc, indi, depth, primary_famc_only=primary_famc_only
    )]


def ahnentafel(
    doc: GedcomDocument,
    indi: Structure,
    depth: int = 99,
    *,
    primary_famc_only: bool = False,
) -> list[tuple[Structure, int, int]]:
    """Sosa-Stradonitz numbered ancestor list rooted at ``indi``.

    Returns a list of ``(structure, generation, sosa)`` tuples, ordered by
    Sosa number. The subject is included as ``(indi, 0, 1)``. The father
    (HUSB) of person N gets Sosa ``2 * N``; the mother (WIFE) gets ``2 * N + 1``.

    With ``primary_famc_only=True`` the FAMC fan-out collapses so each
    ancestor has one Sosa number. Without it, an ancestor reachable through
    multiple FAMC paths is emitted once per Sosa-reachable path.
    """
    out: list[tuple[Structure, int, int]] = [(indi, 0, 1)]
    frontier: list[tuple[Structure, int, int]] = [(indi, 0, 1)]
    while frontier:
        node, gen, sosa = frontier.pop(0)
        if gen >= depth:
            continue
        famc_list = node.find_all_children("FAMC")
        if primary_famc_only:
            famc_list = famc_list[:1]
        for famc in famc_list:
            fam = doc.resolve(famc.payload or "")
            if fam is None:
                continue
            husb = fam.find("HUSB")
            wife = fam.find("WIFE")
            father = doc.resolve(husb.payload or "") if husb and husb.payload else None
            mother = doc.resolve(wife.payload or "") if wife and wife.payload else None
            if father is not None:
                entry = (father, gen + 1, 2 * sosa)
                out.append(entry)
                frontier.append(entry)
            if mother is not None:
                entry = (mother, gen + 1, 2 * sosa + 1)
                out.append(entry)
                frontier.append(entry)
    out.sort(key=lambda t: t[2])
    return out
