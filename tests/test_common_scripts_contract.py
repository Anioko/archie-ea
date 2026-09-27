"""Contracts for JavaScript shared by every rendered page."""

from pathlib import Path


COMMON_SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "templates"
    / "partials"
    / "_scripts_common.html"
)


def test_lucide_invalid_attribute_fallback_is_explicitly_reviewed():
    """The global setAttribute fallback must never become an accidental swallow."""
    source = COMMON_SCRIPTS.read_text(encoding="utf-8")

    assert (
        "swallow-ok: lucide invalid attributes are skipped so remaining icons render"
        in source
    )
