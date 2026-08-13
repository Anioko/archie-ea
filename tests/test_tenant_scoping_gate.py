"""Unit tests for scripts/check_tenant_scoping.py.

The gate targets the cross-tenant leak shape: an ORM query/aggregate over a
model that declares an `organization_id` column but does not inherit
TenantMixin, with no organization_id predicate anywhere nearby. These tests
exercise the checker directly against small fixture modules rather than the
real tree, so they stay meaningful regardless of how many real instances the
current tree has.
"""

import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "check_tenant_scoping.py")


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_tenant_scoping", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_tenant_scoping"] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

LEAKY_MODELS = {"LeakyThing"}


def _scan(tmp_path, source: str):
    fixture = tmp_path / "fixture_route.py"
    fixture.write_text(source, encoding="utf-8")
    return checker.scan_file(str(fixture), LEAKY_MODELS)


def test_unfiltered_query_on_leaky_model_is_flagged(tmp_path):
    src = (
        "def count_things():\n"
        "    total = LeakyThing.query.count()\n"
        "    return total\n"
    )
    findings = _scan(tmp_path, src)
    assert len(findings) == 1
    assert findings[0]["model"] == "LeakyThing"
    assert findings[0]["line"] == 2


def test_org_filtered_query_is_not_flagged(tmp_path):
    src = (
        "def count_things():\n"
        "    total = LeakyThing.query.filter_by(organization_id=g.current_org_id).count()\n"
        "    return total\n"
    )
    findings = _scan(tmp_path, src)
    assert findings == []


def test_hatch_marker_suppresses_finding(tmp_path):
    src = (
        "def count_things():\n"
        "    # tenant-scoping-ok: intentionally global across all tenants\n"
        "    total = LeakyThing.query.count()\n"
        "    return total\n"
    )
    findings = _scan(tmp_path, src)
    assert findings == []


def test_tenant_mixin_model_queried_bare_is_not_flagged(tmp_path):
    # TenantMixin models auto-filter via do_orm_execute — they are not in
    # the LEAKY_MODELS set the checker is given, so a bare `.query` on one
    # must never be flagged.
    src = (
        "def count_things():\n"
        "    total = SomeTenantMixinModel.query.count()\n"
        "    return total\n"
    )
    findings = _scan(tmp_path, src)
    assert findings == []


def test_cached_route_without_key_func_is_flagged(tmp_path):
    src = (
        "@app.route('/x')\n"
        "@cached(ttl=300, key_prefix='x')\n"
        "def view():\n"
        "    return 'ok'\n"
    )
    findings = _scan(tmp_path, src)
    assert any(f["model"] == "@cached()" for f in findings)


def test_cached_route_with_key_func_is_not_flagged(tmp_path):
    src = (
        "@app.route('/x')\n"
        "@cached(ttl=300, key_prefix='x', key_func=lambda: g.current_org_id)\n"
        "def view():\n"
        "    return 'ok'\n"
    )
    findings = _scan(tmp_path, src)
    assert findings == []


def test_leaky_models_detected_via_ast(tmp_path):
    models_dir = tmp_path / "app_models"
    models_dir.mkdir()
    (models_dir / "example.py").write_text(
        "from app.models.mixins import TenantMixin\n"
        "\n"
        "class Leaky(db.Model):\n"
        "    organization_id = db.Column(db.Integer)\n"
        "\n"
        "class Mixed(db.Model, TenantMixin):\n"
        "    name = db.Column(db.String)\n",
        encoding="utf-8",
    )
    old = checker.MODELS_DIR
    try:
        checker.MODELS_DIR = str(models_dir)
        found = checker.leaky_models()
    finally:
        checker.MODELS_DIR = old
    assert "Leaky" in found
    assert "Mixed" not in found


def test_real_tree_count_matches_baseline():
    """The gate itself is exercised end-to-end by scripts/verify.py; this just
    confirms --count runs cleanly against the real tree and prints an int."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--count"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    int(proc.stdout.strip())  # raises if not an integer
