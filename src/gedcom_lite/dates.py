# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""GEDCOM date payload parsing.

Best-effort, year-resolution parsing of `DateValue` payloads. Recognises:

- Exact dates (`1 JAN 2000`, `JAN 2000`, `2000`)
- Approximate (`ABT 1850`, `EST 1850`, `CAL 1850`)
- Bounded (`BEF 1900`, `AFT 1900`)
- Ranges (`BET 1900 AND 1910`)
- Periods (`FROM 1900 TO 1910`, `FROM 1900`, `TO 1910`)
- Calendar escapes (`@#DJULIAN@`, `@#DHEBREW@`, `@#DFRENCH R@`)

Free-text "phrase" payloads (`(around the war)` in 5.5.x or PHRASE-style in 7.0)
are returned as `kind="phrase"` with no resolved year.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DateValue:
    kind: str        # 'exact' | 'range' | 'period' | 'approximate' | 'phrase' | 'unknown'
    start_year: int | None = None
    end_year: int | None = None
    calendar: str | None = None
    raw: str = ""


_YEAR_RE = re.compile(r"\b(\d{1,4})\b")


def _year_of(s: str) -> int | None:
    """Best-effort year extraction. GEDCOM dates put the year last (`1 JAN 2000`)
    so we prefer the last 4-digit token, falling back to the last numeric token.
    """
    matches = _YEAR_RE.findall(s)
    if not matches:
        return None
    four_digit = [m for m in matches if len(m) == 4]
    if four_digit:
        return int(four_digit[-1])
    return int(matches[-1])


def parse_date_value(payload: str | None) -> DateValue:
    """Best-effort parse of a GEDCOM DateValue payload."""
    if not payload:
        return DateValue(kind="unknown")
    p = payload.strip()
    raw = p

    cal: str | None = None
    cm = re.match(r"@#D([^@]+)@\s*", p)
    if cm:
        cal = cm.group(1).strip()
        p = p[cm.end():]

    up = p.upper()
    if up.startswith("BET ") and " AND " in up:
        a, _, b = p.partition(" AND ")
        return DateValue(kind="range",
                         start_year=_year_of(a[4:]),
                         end_year=_year_of(b),
                         calendar=cal, raw=raw)
    if up.startswith("FROM "):
        rest = p[5:]
        if " TO " in rest.upper():
            i = rest.upper().index(" TO ")
            return DateValue(kind="period",
                             start_year=_year_of(rest[:i]),
                             end_year=_year_of(rest[i + 4:]),
                             calendar=cal, raw=raw)
        return DateValue(kind="period", start_year=_year_of(rest), calendar=cal, raw=raw)
    if up.startswith("TO "):
        return DateValue(kind="period", end_year=_year_of(p[3:]), calendar=cal, raw=raw)
    if up.startswith("BEF "):
        return DateValue(kind="range", end_year=_year_of(p[4:]), calendar=cal, raw=raw)
    if up.startswith("AFT "):
        return DateValue(kind="range", start_year=_year_of(p[4:]), calendar=cal, raw=raw)
    if up.startswith(("ABT ", "EST ", "CAL ")):
        y = _year_of(p[4:])
        return DateValue(kind="approximate", start_year=y, end_year=y, calendar=cal, raw=raw)
    y = _year_of(p)
    if y is not None:
        return DateValue(kind="exact", start_year=y, end_year=y, calendar=cal, raw=raw)
    return DateValue(kind="phrase", calendar=cal, raw=raw)
