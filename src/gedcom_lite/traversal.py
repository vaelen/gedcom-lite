# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Ancestry / descendancy traversal helpers."""

from __future__ import annotations

from .core import GedcomDocument, Structure


def parents_of(doc: GedcomDocument, indi: Structure) -> list[Structure]:
    """Return the INDI records that are parents of ``indi`` via FAMC."""
    out: list[Structure] = []
    for famc in indi.find_all_children("FAMC"):
        fam = doc.resolve(famc.payload or "")
        if fam is None:
            continue
        for role in ("HUSB", "WIFE"):
            for slot in fam.find_all_children(role):
                p = doc.resolve(slot.payload or "")
                if p is not None and p not in out:
                    out.append(p)
    return out


def children_of(doc: GedcomDocument, indi: Structure) -> list[Structure]:
    """Return the INDI records that are children of ``indi`` via FAMS → CHIL."""
    out: list[Structure] = []
    for fams in indi.find_all_children("FAMS"):
        fam = doc.resolve(fams.payload or "")
        if fam is None:
            continue
        for chil in fam.find_all_children("CHIL"):
            c = doc.resolve(chil.payload or "")
            if c is not None and c not in out:
                out.append(c)
    return out


def ancestors_of(doc: GedcomDocument, indi: Structure, depth: int = 99) -> list[Structure]:
    """All ancestors of ``indi`` up to ``depth`` generations."""
    seen: set[str] = set()
    frontier: list[tuple[Structure, int]] = [(indi, 0)]
    out: list[Structure] = []
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for p in parents_of(doc, node):
            if p.xref and p.xref not in seen:
                seen.add(p.xref)
                out.append(p)
                frontier.append((p, d + 1))
    return out


def descendants_of(doc: GedcomDocument, indi: Structure, depth: int = 99) -> list[Structure]:
    """All descendants of ``indi`` down to ``depth`` generations."""
    seen: set[str] = set()
    frontier: list[tuple[Structure, int]] = [(indi, 0)]
    out: list[Structure] = []
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for c in children_of(doc, node):
            if c.xref and c.xref not in seen:
                seen.add(c.xref)
                out.append(c)
                frontier.append((c, d + 1))
    return out
