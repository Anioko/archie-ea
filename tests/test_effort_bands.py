"""Task 04: effort_band -- a pure display-time band derived from
WorkPackage.estimated_effort_hours (docs/adr/0011-derived-display-bands.md).

No db_session fixture needed: this function takes no db access, no flask.g,
no request context, per ADR 0011 rule 2.
"""

from __future__ import annotations

import pytest

from app.modules.interface_register.services.size_bands import effort_band


@pytest.mark.parametrize(
    "hours,expected",
    [
        (0, "S"),
        (40, "S"),
        (41, "M"),
        (160, "M"),
        (161, "L"),
        (400, "L"),
        (401, "XL"),
        (1000, "XL"),
    ],
)
def test_effort_band_boundary_values(hours, expected):
    assert effort_band(hours) == expected


def test_effort_band_none_is_none_never_a_default_band():
    """NULL effort must never be mistaken for a measured 'S' -- the
    fabricated-data / null-display rule (root CLAUDE.md, ADR 0011 rule 3)."""
    assert effort_band(None) is None


def test_effort_band_negative_is_none_not_a_default_band():
    assert effort_band(-5) is None


def test_effort_band_non_numeric_is_none():
    assert effort_band("not-a-number") is None
    assert effort_band(object()) is None
