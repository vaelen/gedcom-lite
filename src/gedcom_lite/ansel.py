# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""ANSEL (ANSI Z39.47) ↔ Unicode codec for legacy GEDCOM 5.5.1 files.

ANSEL is an 8-bit MARC-derived encoding used in pre-2010 genealogy software.
This module ships a self-contained translation table so the parser can read and
write ANSEL without an external library. Coverage targets the characters
actually present in real-world 5.5.1 files (Latin diacritics, common
punctuation). Bytes outside the table decode to ``U+FFFD``; on encode,
characters that have no ANSEL spelling fall back to ASCII ``?`` after Unicode
normalisation, which is the documented MARC behaviour.

The ANSEL convention for diacritics is the **opposite** of Unicode: the
combining mark precedes the base letter (e.g. ``0xE2 0x65`` is ``é``). Encoding
walks NFD-normalised text in clusters of ``base + combining-marks`` and emits
the marks first, then the base.
"""

from __future__ import annotations

import unicodedata


# Single-byte ANSEL → Unicode character map. Lower 7 bits are pure ASCII and
# omitted here. Upper-half entries follow ANSI Z39.47 1985.
_ANSEL_TO_UNICODE: dict[int, str] = {
    0x88: "",   # non-sorting beginning marker (rare; treat as no-op)
    0x89: "",   # non-sorting end marker
    0x8D: "‍",  # zero-width joiner (per GEDCOM use)
    0x8E: "‌",  # zero-width non-joiner
    0xA1: "Ł",
    0xA2: "Ø",
    0xA3: "Đ",
    0xA4: "Þ",
    0xA5: "Æ",
    0xA6: "Œ",
    0xA7: "ʹ",
    0xA8: "·",
    0xA9: "♭",
    0xAA: "®",
    0xAB: "±",
    0xAC: "Ơ",
    0xAD: "Ư",
    0xAE: "ʼ",
    0xB0: "ʻ",
    0xB1: "ł",
    0xB2: "ø",
    0xB3: "đ",
    0xB4: "þ",
    0xB5: "æ",
    0xB6: "œ",
    0xB7: "ʺ",
    0xB8: "ı",
    0xB9: "£",
    0xBA: "ð",
    0xBC: "ơ",
    0xBD: "ư",
    0xC0: "°",
    0xC1: "ℓ",
    0xC2: "℗",
    0xC3: "©",
    0xC4: "♯",
    0xC5: "¿",
    0xC6: "¡",
    0xC7: "ß",
    0xC8: "€",
    0xCD: "e",
    0xCE: "o",
    0xCF: "ß",
}


# ANSEL combining diacritics (0xE0-0xFE). Map to the matching Unicode combining
# mark (U+03xx range, mostly). These come BEFORE the base letter in ANSEL.
_ANSEL_COMBINING: dict[int, str] = {
    0xE0: "̉",   # hook above
    0xE1: "̀",   # grave
    0xE2: "́",   # acute
    0xE3: "̂",   # circumflex
    0xE4: "̃",   # tilde
    0xE5: "̄",   # macron
    0xE6: "̆",   # breve
    0xE7: "̇",   # dot above
    0xE8: "̈",   # diaeresis (umlaut)
    0xE9: "̌",   # caron / háček
    0xEA: "̊",   # ring above
    0xEB: "︠",   # ligature, left half
    0xEC: "︡",   # ligature, right half
    0xED: "̕",   # comma above right
    0xEE: "̋",   # double acute
    0xEF: "̐",   # candrabindu
    0xF0: "̧",   # cedilla
    0xF1: "̨",   # ogonek
    0xF2: "̣",   # dot below
    0xF3: "̤",   # diaeresis below
    0xF4: "̥",   # ring below
    0xF5: "̳",   # double underscore
    0xF6: "̲",   # underscore
    0xF7: "̦",   # comma below
    0xF8: "̜",   # left half ring below
    0xF9: "̮",   # breve below
    0xFA: "︢",   # double tilde, left half
    0xFB: "︣",   # double tilde, right half
    0xFE: "̓",   # comma above (high)
}


def decode_ansel(data: bytes) -> str:
    """Decode ANSEL bytes to a Unicode string in NFC form."""
    out: list[str] = []
    pending_marks: list[str] = []
    for b in data:
        if b < 0x80:
            ch = chr(b)
            if pending_marks:
                out.append(ch)
                out.extend(pending_marks)
                pending_marks = []
            else:
                out.append(ch)
            continue
        if b in _ANSEL_COMBINING:
            pending_marks.append(_ANSEL_COMBINING[b])
            continue
        if b in _ANSEL_TO_UNICODE:
            ch = _ANSEL_TO_UNICODE[b]
            if pending_marks:
                out.append(ch)
                out.extend(pending_marks)
                pending_marks = []
            else:
                out.append(ch)
            continue
        # Unknown byte — emit replacement and clear any pending marks so they
        # don't re-bind unexpectedly.
        if pending_marks:
            out.append("�")
            out.extend(pending_marks)
            pending_marks = []
        else:
            out.append("�")
    return unicodedata.normalize("NFC", "".join(out))


# Build reverse maps lazily.
_UNICODE_TO_ANSEL: dict[str, int] | None = None
_UNICODE_TO_ANSEL_COMBINING: dict[str, int] | None = None


def _reverse_maps() -> tuple[dict[str, int], dict[str, int]]:
    global _UNICODE_TO_ANSEL, _UNICODE_TO_ANSEL_COMBINING
    if _UNICODE_TO_ANSEL is None:
        _UNICODE_TO_ANSEL = {v: k for k, v in _ANSEL_TO_UNICODE.items() if v}
    if _UNICODE_TO_ANSEL_COMBINING is None:
        _UNICODE_TO_ANSEL_COMBINING = {v: k for k, v in _ANSEL_COMBINING.items()}
    return _UNICODE_TO_ANSEL, _UNICODE_TO_ANSEL_COMBINING


def encode_ansel(text: str) -> bytes:
    """Encode a Unicode string as ANSEL bytes.

    ANSEL places combining diacritics **before** their base character (the
    opposite of Unicode). We walk NFD-normalised text in clusters of
    ``base + combining-marks`` and emit the marks first, then the base.
    """
    table, combining = _reverse_maps()
    decomposed = unicodedata.normalize("NFD", text)
    out = bytearray()

    i = 0
    n = len(decomposed)
    while i < n:
        base = decomposed[i]
        marks: list[str] = []
        j = i + 1
        while j < n and unicodedata.combining(decomposed[j]):
            marks.append(decomposed[j])
            j += 1

        # Prefer a precomposed mapping if our table has one.
        cluster = unicodedata.normalize("NFC", base + "".join(marks))
        if len(cluster) == 1:
            ch = cluster[0]
            cp = ord(ch)
            if cp < 0x80:
                out.append(cp)
                i = j
                continue
            if ch in table:
                out.append(table[ch])
                i = j
                continue

        # Decomposed form: emit combining marks (in ANSEL order) before base.
        for m in marks:
            if m in combining:
                out.append(combining[m])
            # silently drop unknown marks
        cp = ord(base)
        if cp < 0x80:
            out.append(cp)
        elif base in table:
            out.append(table[base])
        else:
            out.append(ord("?"))
        i = j

    return bytes(out)
