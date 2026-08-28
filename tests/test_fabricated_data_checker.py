"""The fabricated-data checker must catch the shapes that actually reach users.

This checker enforces the platform's cardinal rule: Archie is a system of record,
and a screen that invents a plausible value when the real one is missing is worse
than one showing nothing, because the reader cannot tell the difference and acts
on it.

Two holes in that enforcement, both found by auditing live code rather than by
reading the checker:

1. **Every rule is JS/HTML-shaped.** `catch-returns-fake` matches a JavaScript
   `catch` assigning an array-of-objects. The equivalent Python -- an `except`
   returning a dict of zeroed scalars -- is invisible, and that is precisely the
   shape the ARB legacy dashboard uses to render "Pending 0" after a database
   failure. A reader seeing 0 concludes the queue is clear.

2. **An unrecognised escape-hatch spelling suppresses nothing while looking like
   a filed exception.** `ALLOW` matches `fabricated-ok:`. The string
   `fabricated-values-ok` does not contain it, so 152 sites across `app/` carry a
   marker that has never suppressed anything -- and whoever wrote them believed
   they had recorded a reviewable decision. A silent non-exception is worse than
   no exception: it stops the next reader from looking.

These tests pin both. They drive the checker over fixture files rather than the
live tree, so they assert its behaviour rather than today's debt count.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_fabricated_data.py"


def _run_on(tmp_path, filename, source):
    """Run the checker against a throwaway tree containing one file."""
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    target = app_dir / filename
    target.write_text(source, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


PYTHON_ZERO_FILL = '''
def dashboard_metrics():
    try:
        return real_metrics()
    except Exception:
        # Renders as four confident stat cards after a database failure.
        return {
            "total_items": 0,
            "pending_items": 0,
            "approved_items": 0,
            "approval_rate": 0,
        }
'''

PYTHON_SEVERITY_DEFAULT = '''
def risk_view(raw):
    try:
        return compute(raw)
    except Exception:
        return {"risk_level": "LOW", "total_score": 0}
'''

PYTHON_HONEST_NONE = '''
def dashboard_metrics():
    try:
        return real_metrics()
    except Exception:
        # None renders as an em dash: the screen says it does not know.
        return {
            "total_items": None,
            "pending_items": None,
            "approval_rate": None,
        }
'''


def test_python_except_returning_zeroed_dict_is_flagged(tmp_path):
    """The shape that renders "Pending 0" after a database failure."""
    output = _run_on(tmp_path, "zero_fill_routes.py", PYTHON_ZERO_FILL)
    assert "zero_fill_routes.py" in output, (
        "an except block returning a dict of zeroed scalars reached the checker "
        "unflagged; this is the shape that renders a confident 0 for a value that "
        "was never computed"
    )


def test_python_except_returning_a_severity_word_is_flagged(tmp_path):
    """"LOW" is a claim about risk, not an absence of one."""
    output = _run_on(tmp_path, "risk_routes.py", PYTHON_SEVERITY_DEFAULT)
    assert "risk_routes.py" in output, (
        "an except block defaulting a severity label was not flagged; an "
        "unassessed risk presented as LOW is indistinguishable from an assessed one"
    )


def test_python_except_returning_none_is_not_flagged(tmp_path):
    """The correct shape must stay quiet, or the rule trains people to ignore it."""
    output = _run_on(tmp_path, "honest_routes.py", PYTHON_HONEST_NONE)
    assert "honest_routes.py" not in output, (
        "returning None from an except was flagged; that is the prescribed fix "
        "and flagging it would make the gate impossible to satisfy honestly"
    )


def test_documented_escape_hatch_still_suppresses(tmp_path):
    source = PYTHON_ZERO_FILL.replace(
        "return {",
        "return {  # fabricated-ok: demo fixture, not a rendered metric",
    )
    output = _run_on(tmp_path, "excused_routes.py", source)
    assert "excused_routes.py" not in output


def test_an_unrecognised_marker_spelling_is_itself_a_finding(tmp_path):
    """The 152-site hole.

    `fabricated-values-ok` does not contain `fabricated-ok`, so it never
    suppressed anything -- while reading, to every subsequent author, exactly like
    a filed exception. The checker must say so rather than stay silent, because
    silence is what made 152 of them accumulate.
    """
    source = PYTHON_ZERO_FILL.replace(
        "return {",
        "return {  # fabricated-values-ok: best-effort enrichment",
    )
    output = _run_on(tmp_path, "misspelled_routes.py", source)
    assert "misspelled_routes.py" in output
    assert "marker" in output.lower() or "fabricated-values-ok" in output, (
        "the checker must name the unrecognised marker; reporting only the "
        "underlying fabrication leaves the author believing their exception was "
        "read and rejected on its merits"
    )


def test_checker_accepts_a_root_argument():
    """Needed so these tests can drive it over a fixture tree, not the live one."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--help"],
        capture_output=True,
        text=True,
    )
    assert "--root" in result.stdout, "the checker needs a --root to be testable"
