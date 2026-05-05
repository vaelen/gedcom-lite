# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""GEDCOM parser, model, and writer with round-trip fidelity.

Supports GEDCOM 5.5.1, 5.5.5, and FamilySearch GEDCOM 7.0+. Round-trip means a
parse followed by a write produces byte-identical output for unmodified
documents: BOM, line endings, sibling order, ``CONC``/``CONT`` choice, and
unknown extension tags are all preserved.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator

from .ansel import decode_ansel, encode_ansel


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"


@dataclass
class _Decoded:
    text: str
    encoding: str        # 'utf-8', 'utf-8-sig', 'utf-16-le', 'utf-16-be', 'ansel', 'ascii'
    bom: bytes           # the actual BOM bytes that prefixed the file (may be b'')
    declared_char: str | None  # the value of the 1 CHAR header line, if any


def _detect_and_decode(raw: bytes) -> _Decoded:
    """Sniff encoding and decode raw GEDCOM bytes to text.

    Order: BOM → UTF-8 → ``1 CHAR`` header line for 5.5.x → ANSEL fallback.
    The returned text never contains the BOM.
    """
    if raw.startswith(UTF8_BOM):
        return _Decoded(raw[len(UTF8_BOM):].decode("utf-8"), "utf-8-sig", UTF8_BOM, _peek_char(raw[len(UTF8_BOM):], "utf-8"))
    if raw.startswith(UTF16_LE_BOM):
        return _Decoded(raw[len(UTF16_LE_BOM):].decode("utf-16-le"), "utf-16-le", UTF16_LE_BOM, _peek_char(raw[len(UTF16_LE_BOM):], "utf-16-le"))
    if raw.startswith(UTF16_BE_BOM):
        return _Decoded(raw[len(UTF16_BE_BOM):].decode("utf-16-be"), "utf-16-be", UTF16_BE_BOM, _peek_char(raw[len(UTF16_BE_BOM):], "utf-16-be"))

    # No BOM — try UTF-8 first; if that decodes cleanly, look at the header.
    declared: str | None = None
    text: str | None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None

    # UTF-16-LE/BE-encoded ASCII content also passes a UTF-8 decode (each ASCII
    # char becomes ``byte\x00`` which is valid UTF-8 — two codepoints — but the
    # resulting text is full of nulls). Detect that case and re-decode.
    if text is not None and _looks_like_utf16_ascii(text):
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                retext = raw.decode(enc)
                redeclared = _peek_char_text(retext)
                return _Decoded(retext, enc, b"", redeclared)
            except UnicodeDecodeError:
                continue

    if text is not None:
        declared = _peek_char_text(text)

    if text is not None and (declared is None or declared.upper() in ("UTF-8", "UTF8", "ASCII")):
        encoding = "utf-8"
        if declared and declared.upper() == "ASCII":
            encoding = "ascii"
        return _Decoded(text, encoding, b"", declared)

    if text is not None and declared and declared.upper() == "UNICODE":
        # Legacy 5.5.1 convention: UNICODE means UTF-16, typically LE, no BOM.
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                return _Decoded(raw.decode(enc), enc, b"", declared)
            except UnicodeDecodeError:
                continue

    # ANSEL — re-decode with our table. We need the header text first to know
    # CHAR, so peek using ASCII (ANSEL is ASCII-compatible in 0x00-0x7E).
    if text is None:
        ascii_view = raw.decode("ascii", errors="replace")
        declared = _peek_char_text(ascii_view)

    if declared and declared.upper() == "ANSEL":
        return _Decoded(decode_ansel(raw), "ansel", b"", declared)

    # Last resort: ANSEL anyway (common in older 5.5.1 files that omit CHAR).
    return _Decoded(decode_ansel(raw), "ansel", b"", declared)


_CHAR_RE = re.compile(r"^1\s+CHAR\s+(\S+)\s*$", re.MULTILINE)


def _peek_char_text(text: str) -> str | None:
    m = _CHAR_RE.search(text[:4096])
    return m.group(1) if m else None


def _looks_like_utf16_ascii(text: str) -> bool:
    """Heuristic: ASCII content encoded as UTF-16 produces lots of NUL chars
    when interpreted as UTF-8. If more than a quarter of the leading sample is
    NUL, treat it as UTF-16 in disguise.
    """
    sample = text[:512]
    if not sample:
        return False
    return sample.count("\x00") / len(sample) > 0.25


def _peek_char(raw: bytes, encoding: str) -> str | None:
    try:
        return _peek_char_text(raw[:8192].decode(encoding, errors="replace"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Line splitting
# ---------------------------------------------------------------------------

def _split_lines(text: str) -> tuple[list[str], list[str]]:
    """Split text into (lines, terminators). Each line excludes its terminator.

    Recognised terminators: ``CRLF``, ``LF``, ``CR``. Trailing data with no
    terminator is returned as a final line with terminator ``''``. Empty lines
    are dropped (a blank line is not legal GEDCOM and tools commonly tolerate
    stray ones).
    """
    lines: list[str] = []
    terms: list[str] = []
    i = 0
    n = len(text)
    buf_start = 0
    while i < n:
        ch = text[i]
        if ch == "\r":
            line = text[buf_start:i]
            term = "\r\n" if i + 1 < n and text[i + 1] == "\n" else "\r"
            if line:
                lines.append(line)
                terms.append(term)
            i += len(term)
            buf_start = i
        elif ch == "\n":
            line = text[buf_start:i]
            term = "\n"
            if line:
                lines.append(line)
                terms.append(term)
            i += 1
            buf_start = i
        else:
            i += 1
    if buf_start < n:
        line = text[buf_start:]
        if line:
            lines.append(line)
            terms.append("")
    return lines, terms


def _predominant_terminator(terms: list[str]) -> str:
    counts = {"\r\n": 0, "\n": 0, "\r": 0}
    for t in terms:
        if t in counts:
            counts[t] += 1
    best, n = max(counts.items(), key=lambda kv: kv[1])
    return best if n > 0 else "\n"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass
class _Token:
    level: int
    xref: str | None
    tag: str
    payload: str | None
    raw: str


_LEVEL_RE = re.compile(r"^(\d+)\s")


def _tokenize(line: str) -> _Token:
    """Parse one GEDCOM line into its parts.

    Format: ``Level [Space Xref] Space Tag [Space Payload]``.
    Raises ``ValueError`` on malformed input.
    """
    m = _LEVEL_RE.match(line)
    if not m:
        raise ValueError(f"line does not start with a level: {line!r}")
    level = int(m.group(1))
    rest = line[m.end():]

    xref = None
    if rest.startswith("@"):
        end = rest.find("@", 1)
        if end == -1:
            raise ValueError(f"unterminated xref in line: {line!r}")
        xref = rest[: end + 1]
        rest = rest[end + 1:]
        if not rest.startswith(" "):
            raise ValueError(f"missing space after xref in line: {line!r}")
        rest = rest[1:]

    space = rest.find(" ")
    if space == -1:
        tag = rest
        payload = None
    else:
        tag = rest[:space]
        payload = rest[space + 1:]
    if not tag:
        raise ValueError(f"empty tag in line: {line!r}")
    return _Token(level=level, xref=xref, tag=tag, payload=payload, raw=line)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class Structure:
    """One GEDCOM structure (record or substructure).

    A record is a Structure with ``level == 0``. Substructures hang off
    ``children`` of a parent. Round-trip fidelity is preserved by retaining
    ``original_line`` (and its terminator) and only regenerating output when
    ``_dirty`` is set by a mutation.
    """
    level: int
    tag: str
    payload: str | None = None
    xref: str | None = None
    children: list["Structure"] = field(default_factory=list)
    parent: "Structure | None" = field(default=None, repr=False)
    original_line: str | None = field(default=None, repr=False)
    original_terminator: str = field(default="", repr=False)
    source_line_no: int = field(default=0, repr=False)
    _dirty: bool = field(default=False, repr=False)

    # ---------------- mutation ----------------

    def set_payload(self, value: str | None) -> None:
        self.payload = value
        self._dirty = True

    def set_tag(self, tag: str) -> None:
        self.tag = tag
        self._dirty = True

    def add_child(self, tag: str, payload: str | None = None) -> "Structure":
        child = Structure(level=self.level + 1, tag=tag, payload=payload, parent=self)
        child._dirty = True
        self.children.append(child)
        return child

    def remove(self) -> None:
        if self.parent is None:
            raise ValueError(
                "cannot remove a top-level structure via remove(); "
                "use GedcomDocument.remove_record"
            )
        self.parent.children.remove(self)

    # ---------------- traversal & query ----------------

    def walk(self) -> Iterator["Structure"]:
        yield self
        for ch in self.children:
            yield from ch.walk()

    def find(self, tag: str) -> "Structure | None":
        for ch in self.children:
            if ch.tag == tag:
                return ch
        return None

    def find_all_children(self, tag: str) -> list["Structure"]:
        return [ch for ch in self.children if ch.tag == tag]

    def text(self) -> str:
        """Reassemble multi-line payload using ``CONT``/``CONC`` children."""
        out = self.payload or ""
        for ch in self.children:
            if ch.tag == "CONT":
                out += "\n" + (ch.payload or "")
            elif ch.tag == "CONC":
                out += ch.payload or ""
            else:
                break
        return out

    def path(self) -> str:
        """Slash-delimited tag path from the nearest record root, e.g. ``INDI/BIRT/DATE``."""
        parts: list[str] = []
        node: Structure | None = self
        while node is not None and node.level > 0:
            parts.append(node.tag)
            node = node.parent
        if node is not None:
            parts.append(node.tag)
        return "/".join(reversed(parts))

    # ---------------- serialization helpers ----------------

    def render_line(self) -> str:
        parts: list[str] = [str(self.level)]
        if self.xref:
            parts.append(self.xref)
        parts.append(self.tag)
        if self.payload is not None and self.payload != "":
            parts.append(self.payload)
        return " ".join(parts)


@dataclass
class GedcomDocument:
    """A parsed GEDCOM file."""
    header: Structure
    records: list[Structure]
    trailer: Structure
    encoding: str = "utf-8"
    bom: bytes = b""
    line_terminator: str = "\n"
    declared_char: str | None = None
    xrefs: dict[str, Structure] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)

    # ---------------- I/O ----------------

    @classmethod
    def parse(cls, source: str | bytes | os.PathLike[str] | IO[bytes]) -> "GedcomDocument":
        raw = _read_bytes(source)
        decoded = _detect_and_decode(raw)
        lines, terms = _split_lines(decoded.text)
        terminator = _predominant_terminator(terms)

        warnings: list[str] = []
        tokens: list[_Token] = []
        for ln, line in enumerate(lines, start=1):
            try:
                tokens.append(_tokenize(line))
            except ValueError as e:
                warnings.append(f"line {ln}: {e}")

        # Build tree.
        root_children: list[Structure] = []
        stack: list[Structure] = []
        for ln, (tok, term) in enumerate(zip(tokens, terms), start=1):
            s = Structure(
                level=tok.level,
                tag=tok.tag,
                payload=tok.payload,
                xref=tok.xref,
                original_line=tok.raw,
                original_terminator=term,
                source_line_no=ln,
            )
            if tok.level == 0:
                stack = [s]
                root_children.append(s)
                continue
            while stack and stack[-1].level >= tok.level:
                stack.pop()
            if not stack:
                warnings.append(f"line {ln}: orphan substructure (no parent at lower level)")
                stack = [s]
                root_children.append(s)
                continue
            parent = stack[-1]
            s.parent = parent
            parent.children.append(s)
            if len(stack) == tok.level:
                stack.append(s)
            else:
                stack = stack[: tok.level]
                stack.append(s)

        if not root_children:
            raise ValueError("empty GEDCOM file")
        header = None
        trailer = None
        records: list[Structure] = []
        for r in root_children:
            if r.tag == "HEAD" and header is None:
                header = r
            elif r.tag == "TRLR":
                trailer = r
            else:
                records.append(r)
        if header is None:
            raise ValueError("missing HEAD record")
        if trailer is None:
            warnings.append("missing TRLR record")
            trailer = Structure(level=0, tag="TRLR", original_terminator=terminator)
            trailer._dirty = True

        xrefs: dict[str, Structure] = {}
        for r in records:
            if r.xref:
                if r.xref in xrefs:
                    warnings.append(f"duplicate xref {r.xref}")
                xrefs[r.xref] = r

        return cls(
            header=header,
            records=records,
            trailer=trailer,
            encoding=decoded.encoding,
            bom=decoded.bom,
            line_terminator=terminator,
            declared_char=decoded.declared_char,
            xrefs=xrefs,
            parse_warnings=warnings,
        )

    def write(self, sink: os.PathLike[str] | str | IO[bytes] | None = None) -> bytes:
        """Serialize the document. Returns the raw bytes; writes to ``sink`` if given."""
        chunks: list[str] = []
        for top in (self.header, *self.records, self.trailer):
            self._write_structure(top, chunks)
        text = "".join(chunks)
        encoded = self._encode(text)
        if sink is not None:
            _write_bytes(sink, encoded)
        return encoded

    # ---------------- internals ----------------

    def _write_structure(self, s: Structure, out: list[str]) -> None:
        if s.original_line is not None and not s._dirty:
            out.append(s.original_line)
            out.append(s.original_terminator or self.line_terminator)
        else:
            out.append(s.render_line())
            out.append(self.line_terminator)
        for ch in s.children:
            self._write_structure(ch, out)

    def _encode(self, text: str) -> bytes:
        enc = self.encoding
        if enc == "utf-8-sig":
            return UTF8_BOM + text.encode("utf-8")
        if enc == "utf-16-le":
            return self.bom + text.encode("utf-16-le")
        if enc == "utf-16-be":
            return self.bom + text.encode("utf-16-be")
        if enc == "ansel":
            return encode_ansel(text)
        if enc == "ascii":
            return text.encode("ascii")
        return text.encode("utf-8")

    # ---------------- queries ----------------

    @property
    def version(self) -> str | None:
        gedc = self.header.find("GEDC")
        if gedc is None:
            return None
        vers = gedc.find("VERS")
        return vers.payload if vers else None

    @property
    def is_v7(self) -> bool:
        v = self.version or ""
        return v.startswith("7.")

    @property
    def is_v5(self) -> bool:
        v = self.version or ""
        return v.startswith("5.")

    def all_structures(self) -> Iterator[Structure]:
        for top in (self.header, *self.records, self.trailer):
            yield from top.walk()

    def find_records(self, tag: str) -> list[Structure]:
        return [r for r in self.records if r.tag == tag]

    def record_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.tag] = counts.get(r.tag, 0) + 1
        return counts

    def resolve(self, xref: str) -> Structure | None:
        return self.xrefs.get(xref)

    # ---------------- record-level mutation ----------------

    def add_record(self, tag: str, xref: str | None = None) -> Structure:
        if xref is not None:
            if xref in self.xrefs:
                raise ValueError(f"xref {xref} already exists")
        else:
            xref = self._fresh_xref(tag)
        s = Structure(level=0, tag=tag, xref=xref)
        s._dirty = True
        self.records.append(s)
        self.xrefs[xref] = s
        return s

    def remove_record(self, xref: str) -> None:
        rec = self.xrefs.pop(xref, None)
        if rec is None:
            raise KeyError(xref)
        self.records.remove(rec)

    def inbound_pointers(self, xref: str) -> list[Structure]:
        """Find every structure whose payload is a pointer to ``xref``."""
        return [s for s in self.all_structures() if s.payload == xref]

    def _fresh_xref(self, tag: str) -> str:
        prefix = {"INDI": "I", "FAM": "F", "SUBM": "U", "SOUR": "S",
                  "REPO": "R", "OBJE": "M", "NOTE": "N", "SNOTE": "N"}.get(tag, "X")
        i = 1
        while True:
            candidate = f"@{prefix}{i}@"
            if candidate not in self.xrefs:
                return candidate
            i += 1


# ---------------------------------------------------------------------------
# JSON projection
# ---------------------------------------------------------------------------

def structure_to_dict(s: Structure) -> dict:
    d: dict = {"level": s.level, "tag": s.tag}
    if s.xref is not None:
        d["xref"] = s.xref
    if s.payload is not None:
        d["payload"] = s.payload
    if s.children:
        d["children"] = [structure_to_dict(c) for c in s.children]
    return d


def document_to_dict(doc: GedcomDocument) -> dict:
    return {
        "version": doc.version,
        "encoding": doc.encoding,
        "bom": doc.bom.hex() or None,
        "line_terminator": {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}.get(doc.line_terminator, doc.line_terminator),
        "declared_char": doc.declared_char,
        "header": structure_to_dict(doc.header),
        "records": [structure_to_dict(r) for r in doc.records],
        "trailer": structure_to_dict(doc.trailer),
        "warnings": doc.parse_warnings,
    }


def to_json(doc: GedcomDocument, indent: int | None = 2) -> str:
    return json.dumps(document_to_dict(doc), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Bytes I/O helpers
# ---------------------------------------------------------------------------

def _read_bytes(source: str | bytes | os.PathLike[str] | IO[bytes]) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, (str, os.PathLike)):
        return Path(source).read_bytes()
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            return data.encode("utf-8")
        return data
    raise TypeError(f"unsupported source type: {type(source)!r}")


def _write_bytes(sink: os.PathLike[str] | str | IO[bytes], data: bytes) -> None:
    if isinstance(sink, (str, os.PathLike)):
        Path(sink).write_bytes(data)
        return
    if hasattr(sink, "write"):
        try:
            sink.write(data)
        except TypeError:
            sink.write(data.decode("utf-8"))
        return
    raise TypeError(f"unsupported sink type: {type(sink)!r}")


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def parse(source: str | bytes | os.PathLike[str] | IO[bytes]) -> GedcomDocument:
    """Top-level convenience wrapper for ``GedcomDocument.parse``."""
    return GedcomDocument.parse(source)
