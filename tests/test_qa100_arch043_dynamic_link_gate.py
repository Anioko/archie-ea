"""ARCH-043: scripts/check_dynamic_link_prefixes.py must catch a concatenated
dead link that scripts/check_broken_surfaces.py deliberately skips.

check_broken_surfaces.py's own docstring says it skips any href/fetch target
built by string concatenation ('/x/' + id) — a real, intentional scope
decision, not a bug in that checker. That skip is exactly what let
":href=\"'/dashboard/application/' + targetApplicationId\"" and
":href=\"'/vendors/view/' + targetVendorId\"" ship as dead links (both 404,
correct routes are /applications/<id> and /applications/vendors/<id>) with
no gate catching it.

These tests exercise the new checker's pure logic directly (regex + prefix
matching) rather than re-booting the whole Flask app per test, and confirm it
fails-first on the exact dead pattern from the finding before asserting it is
now silent on the fixed repo.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_dynamic_link_prefixes.py"


def _import_checker():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_dynamic_link_prefixes", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_concat_regex_extracts_literal_prefix():
    mod = _import_checker()
    text = ":href=\"'/dashboard/application/' + targetApplicationId\""
    matches = list(mod._CONCAT_RE.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "/dashboard/application/"


def test_dead_prefix_flagged_against_a_fake_route_table():
    """FAIL-FIRST unit: a literal prefix with no matching live route must be
    reported as dead, regardless of what id gets substituted in."""
    mod = _import_checker()
    live_prefixes = ["/applications/", "/applications/vendors/"]
    assert not mod._prefix_is_live("/dashboard/application/", live_prefixes), (
        "the exact dead prefix from the ARCH-043 finding must be flagged"
    )
    assert not mod._prefix_is_live("/vendors/view/", live_prefixes)


def test_live_prefix_not_flagged_against_a_fake_route_table():
    mod = _import_checker()
    live_prefixes = ["/applications/", "/applications/vendors/"]
    assert mod._prefix_is_live("/applications/", live_prefixes)
    assert mod._prefix_is_live("/applications/vendors/", live_prefixes)


def test_checker_runs_clean_against_the_current_repo():
    """Integration smoke: boots the real app and scans the real templates/JS.
    Regression guard for the two links this wave fixed in
    app/templates/ai_chat/document_upload.html — must not reappear."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--count"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    count = int(proc.stdout.strip().splitlines()[-1])
    assert count == 0, f"expected 0 dead concatenated-link prefixes, found {count}:\n{proc.stdout}"
