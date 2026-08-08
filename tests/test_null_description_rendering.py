"""A NULL description must not blank the page it appears on.

Jinja's `default` replaces an *undefined* value, not a `None` one. Every nullable
column arrives as None, which is defined, so it sailed past `default()` into
`truncate`, which calls len() on it:

    {{ cap.description|default('No description')|truncate(100) }}

That raises "object of type 'NoneType' has no len()" and aborts the whole
render - not just that one field.

Caught on production. /enterprise/capability-map/capabilities logged exactly that
error, and the route's own `except` then re-rendered the same template with
`capabilities=[]`, which succeeds because the loop never runs. The page returned
200 with "Error loading capabilities" and no rows while the capabilities existed
in the database - indistinguishable, to the reader, from an empty portfolio.

Nine templates carried the pattern; the tree-wide scanner is
scripts/check_null_filters.py, gated as `null-filters`.
"""

from __future__ import annotations

import os

import pytest
from jinja2 import Template

os.environ.setdefault("FLASK_CONFIG", "testing")
os.environ.setdefault("SECRET_KEY", "test-only-not-secret")


class _Cap:
    """A row whose nullable text column is NULL, as the ORM hands it over."""

    def __init__(self):
        self.id = 1
        self.name = "Order Management"
        self.description = None
        self.level = 1
        self.category = None
        self.current_maturity_level = None


def test_plain_default_does_not_protect_truncate_from_none():
    """The bug itself - pinned so nobody 'simplifies' the fix back out."""
    with pytest.raises(TypeError, match="has no len"):
        Template("{{ v|default('x')|truncate(10) }}").render(v=None)


def test_the_boolean_argument_is_what_makes_default_none_safe():
    out = Template("{{ v|default('No description', true)|truncate(10) }}").render(v=None)
    assert "No description"[:10] in out or out.strip().startswith("No")


def test_capability_card_renders_with_a_null_description():
    """The production failure, against the real template text."""
    from pathlib import Path

    from jinja2 import Environment

    src = Path("app/templates/capability_map/capabilities.html").read_text(
        encoding="utf-8"
    )
    line = next(
        ln for ln in src.splitlines() if "cap.description" in ln and "truncate" in ln
    )
    rendered = Environment(autoescape=True).from_string(line).render(cap=_Cap())
    assert "No description" in rendered


def test_no_template_still_chains_default_into_a_len_filter():
    """Tree-wide - the same shape existed in nine templates, several of them
    business-architecture pages (capability health, plateaus, gap analysis,
    technology roadmap)."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/check_null_filters.py"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
