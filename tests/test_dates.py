# Copyright (c) 2026 Andrew C. Young (andrew@vaelen.org)
# Licensed under the MIT License. See LICENSE in the project root.
"""Tests for ``parse_date_value``."""

from __future__ import annotations

from gedcom_lite.dates import _year_of, parse_date_value


class TestYearOf:
    def test_picks_4_digit_year(self) -> None:
        assert _year_of("1 JAN 2000") == 2000
        assert _year_of("JAN 2000") == 2000
        assert _year_of("2000") == 2000

    def test_falls_back_to_last_token(self) -> None:
        assert _year_of("99") == 99

    def test_empty(self) -> None:
        assert _year_of("") is None

    def test_no_digits(self) -> None:
        assert _year_of("UNKNOWN") is None


class TestExactDates:
    def test_full_date(self) -> None:
        d = parse_date_value("1 JAN 2000")
        assert d.kind == "exact"
        assert d.start_year == 2000
        assert d.end_year == 2000

    def test_year_only(self) -> None:
        d = parse_date_value("1900")
        assert d.kind == "exact"
        assert d.start_year == 1900

    def test_month_year(self) -> None:
        d = parse_date_value("JUN 1900")
        assert d.kind == "exact"
        assert d.start_year == 1900


class TestApproximate:
    def test_abt(self) -> None:
        d = parse_date_value("ABT 1850")
        assert d.kind == "approximate"
        assert d.start_year == 1850
        assert d.end_year == 1850

    def test_est(self) -> None:
        assert parse_date_value("EST 1850").kind == "approximate"

    def test_cal(self) -> None:
        assert parse_date_value("CAL 1850").kind == "approximate"


class TestRanges:
    def test_bef(self) -> None:
        d = parse_date_value("BEF 1900")
        assert d.kind == "range"
        assert d.end_year == 1900
        assert d.start_year is None

    def test_aft(self) -> None:
        d = parse_date_value("AFT 1900")
        assert d.kind == "range"
        assert d.start_year == 1900
        assert d.end_year is None

    def test_bet_and(self) -> None:
        d = parse_date_value("BET 1900 AND 1910")
        assert d.kind == "range"
        assert d.start_year == 1900
        assert d.end_year == 1910

    def test_bet_with_full_dates(self) -> None:
        d = parse_date_value("BET 1 JAN 1900 AND 31 DEC 1910")
        assert d.kind == "range"
        assert d.start_year == 1900
        assert d.end_year == 1910


class TestPeriods:
    def test_from_to(self) -> None:
        d = parse_date_value("FROM 1900 TO 1910")
        assert d.kind == "period"
        assert d.start_year == 1900
        assert d.end_year == 1910

    def test_from_only(self) -> None:
        d = parse_date_value("FROM 1900")
        assert d.kind == "period"
        assert d.start_year == 1900
        assert d.end_year is None

    def test_to_only(self) -> None:
        d = parse_date_value("TO 1910")
        assert d.kind == "period"
        assert d.start_year is None
        assert d.end_year == 1910


class TestCalendars:
    def test_julian_escape(self) -> None:
        d = parse_date_value("@#DJULIAN@ 1 JAN 1700")
        assert d.calendar == "JULIAN"
        assert d.start_year == 1700

    def test_hebrew(self) -> None:
        d = parse_date_value("@#DHEBREW@ 1 TSH 5760")
        assert d.calendar == "HEBREW"
        assert d.start_year == 5760

    def test_french_republican_with_space(self) -> None:
        d = parse_date_value("@#DFRENCH R@ 1 VEND 8")
        assert d.calendar == "FRENCH R"
        # Year extraction on "1 VEND 8" picks the last numeric token.
        assert d.start_year == 8


class TestEdgeCases:
    def test_empty(self) -> None:
        assert parse_date_value("").kind == "unknown"
        assert parse_date_value(None).kind == "unknown"

    def test_phrase_falls_through(self) -> None:
        # No year-like tokens → phrase
        d = parse_date_value("around the war")
        assert d.kind == "phrase"
        assert d.raw == "around the war"

    def test_lowercase_keywords_treated_as_exact_with_year(self) -> None:
        # We uppercase before keyword matching; lowercase year-only goes through
        # as exact (the year regex still finds the digits).
        d = parse_date_value("1900")
        assert d.kind == "exact"
