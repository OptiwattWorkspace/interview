"""Natural-language due dates."""

from __future__ import annotations

from datetime import date

import pytest

from taskbot import dates

# A Saturday, so weekday math is easy to reason about.
TODAY = date(2026, 8, 15)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("today", date(2026, 8, 15)),
        ("tomorrow", date(2026, 8, 16)),
        ("tonight", date(2026, 8, 15)),
    ],
)
def test_relative_words(text, expected):
    assert dates.parse(text, TODAY) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("monday", date(2026, 8, 17)),
        ("mon", date(2026, 8, 17)),
        ("friday", date(2026, 8, 21)),
        ("sunday", date(2026, 8, 16)),
    ],
)
def test_weekdays_resolve_forward(text, expected):
    assert dates.parse(text, TODAY) == expected


def test_same_weekday_means_next_week():
    """Saying 'saturday' on a Saturday means the next one."""
    assert dates.parse("saturday", TODAY) == date(2026, 8, 22)


def test_next_weekday_skips_a_week():
    assert dates.parse("next monday", TODAY) == date(2026, 8, 24)


def test_this_weekday_is_the_upcoming_one():
    assert dates.parse("this monday", TODAY) == date(2026, 8, 17)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("aug 20", date(2026, 8, 20)),
        ("august 20", date(2026, 8, 20)),
        ("aug 20th", date(2026, 8, 20)),
        ("20 aug", date(2026, 8, 20)),
        ("sept 1", date(2026, 9, 1)),
    ],
)
def test_month_names(text, expected):
    assert dates.parse(text, TODAY) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("8/20", date(2026, 8, 20)),
        ("8/20/26", date(2026, 8, 20)),
        ("8/20/2026", date(2026, 8, 20)),
        ("2026-08-20", date(2026, 8, 20)),
    ],
)
def test_numeric_formats(text, expected):
    assert dates.parse(text, TODAY) == expected


def test_past_month_day_rolls_to_next_year():
    """'jan 5' in August means next January, not eight months ago."""
    assert dates.parse("jan 5", TODAY) == date(2027, 1, 5)


def test_leading_preposition_is_stripped():
    assert dates.parse("by friday", TODAY) == date(2026, 8, 21)
    assert dates.parse("on aug 20", TODAY) == date(2026, 8, 20)


def test_in_n_days():
    assert dates.parse("in 3 days", TODAY) == date(2026, 8, 18)
    assert dates.parse("in 2 weeks", TODAY) == date(2026, 8, 29)


@pytest.mark.parametrize(
    "text", ["", "   ", "sale", "the store", "whenever", "13/45", "feb 30"]
)
def test_unparseable_returns_none(text):
    assert dates.parse(text, TODAY) is None


def test_trailing_punctuation_ignored():
    assert dates.parse("friday.", TODAY) == date(2026, 8, 21)
