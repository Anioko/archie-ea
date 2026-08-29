"""The nav-verified gate must not report a count it did not measure.

The gate counts sidebar-reachable routes that no test has exercised, using
``route_verification.json`` -- a file written by running the suite with
``-p scripts.route_verification_audit``.

That file is **untracked and exists in exactly one working copy**. Consequences,
all measured on the same commit:

    repo root (file present, dated 21 Aug)   [18 > 0]   "exercised by a test 2224"
    any fresh worktree (file absent)         [57 > 0]   "exercised by a test  n/a"

So the same commit measures differently in two checkouts, and **no clean clone or
worktree can ever pass this gate**. Worse, the second number is not a measurement:
57 is the entire navigation set, reported as though 57 routes had been found
wanting. A reader sees a count and reasonably concludes it was counted.

That is the same error the platform forbids everywhere else -- a `0` that means
"not computed" is indistinguishable from a measured zero, and a `57` that means
"no data" is indistinguishable from a measured 57. A gate is held to the rule it
enforces.

The fix is not to make it pass. Absent evidence must still fail, because a skip
that reads as a pass is how a red gate reached production this week. It must fail
*saying it has no evidence*, with the command that produces some.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "route_verification_audit.py"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def test_count_reports_unmeasured_rather_than_a_number(tmp_path):
    """With no audit data, --count must not emit a plausible integer."""
    result = _run("--count", "--results", str(tmp_path / "absent.json"))
    out = result.stdout.strip()

    assert out, "the audit printed nothing at all"
    assert not out.splitlines()[-1].strip().isdigit(), (
        "with no audit data the script printed a bare integer, which the gate and "
        "any reader will take as a measured count of unverified routes"
    )
    assert "unmeasured" in out.lower() or "no audit data" in out.lower(), (
        "the script must say it has no data, not merely decline to print a number"
    )


def test_report_names_the_command_that_produces_data(tmp_path):
    result = _run("--results", str(tmp_path / "absent.json"))
    assert "route_verification_audit" in result.stdout, (
        "the report must name the command that generates the missing data"
    )


def test_a_real_count_is_still_printed_when_data_exists(tmp_path):
    """The honest path must keep working, or the fix is a regression."""
    results = tmp_path / "present.json"
    results.write_text(
        json.dumps({"exercised": ["main.index", "arb.dashboard"]}), encoding="utf-8"
    )

    result = _run("--count", "--results", str(results))
    last = result.stdout.strip().splitlines()[-1].strip()
    assert last.isdigit(), (
        f"with audit data present the script must print a real count, got {last!r}"
    )


def test_gate_distinguishes_unmeasured_from_a_bad_score():
    """The gate's own failure text must say which of the two it is."""
    import inspect

    sys.path.insert(0, str(ROOT / "scripts"))
    import verify  # noqa: E402

    source = inspect.getsource(verify.gate_nav_verified)
    assert "unmeasured" in source.lower() or "no audit data" in source.lower(), (
        "gate_nav_verified cannot tell 'no evidence' apart from 'routes are "
        "unverified'; both currently render as a count"
    )
