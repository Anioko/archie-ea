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


def _scan(tmp_path, source: str, models=None):
    fixture = tmp_path / "fixture_route.py"
    fixture.write_text(source, encoding="utf-8")
    return checker.scan_file(str(fixture), models if models is not None else LEAKY_MODELS)


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


def test_leaky_models_excludes_global_reference_models(tmp_path):
    """Wave-4 Task-2/3: ARBGovernanceStandard, ARBWorkflowStage and
    EAWorkflowDefinition carry organization_id (Phase A, for schema symmetry
    with their 11 per-tenant siblings) but are shared catalogs/templates, not
    per-tenant data. leaky_models() must never surface them, even though a
    naive AST scan (organization_id column + no TenantMixin base) would
    otherwise match them exactly like a genuine leak.

    A future edit that quietly drops the GLOBAL_REFERENCE_MODELS exclusion
    would make this test start flagging ARBGovernanceStandard again — pinning
    that regression is the point.
    """
    models_dir = tmp_path / "app_models"
    models_dir.mkdir()
    (models_dir / "example.py").write_text(
        "class ARBGovernanceStandard(db.Model):\n"
        "    organization_id = db.Column(db.Integer)\n"
        "\n"
        "class ARBWorkflowStage(db.Model):\n"
        "    organization_id = db.Column(db.Integer)\n"
        "\n"
        "class EAWorkflowDefinition(db.Model):\n"
        "    organization_id = db.Column(db.Integer)\n"
        "\n"
        "class TrulyLeaky(db.Model):\n"
        "    organization_id = db.Column(db.Integer)\n",
        encoding="utf-8",
    )
    old = checker.MODELS_DIR
    try:
        checker.MODELS_DIR = str(models_dir)
        found = checker.leaky_models()
    finally:
        checker.MODELS_DIR = old
    assert found & checker.GLOBAL_REFERENCE_MODELS == set(), (
        "global-reference models must never be treated as leaky"
    )
    assert "TrulyLeaky" in found, (
        "a genuinely unmixed model with organization_id must still be flagged as leaky"
    )


def test_global_reference_model_query_is_not_flagged(tmp_path):
    """End-to-end shape of the fix: a bare `.query` over a global-reference
    model produces no finding, while the same shape over a genuine leaky
    model still does — using the real GLOBAL_REFERENCE_MODELS set as the
    checker would see it after leaky_models() has excluded them."""
    src = (
        "def list_standards():\n"
        "    return ARBGovernanceStandard.query.all()\n"
        "\n"
        "def count_leaky():\n"
        "    return LeakyThing.query.count()\n"
    )
    # Simulates the post-exclusion model set leaky_models() would hand to
    # scan_file: without the exclusion, ARBGovernanceStandard would be a
    # "leaky" model just like LeakyThing; the fix removes it before scan_file
    # ever sees it, so the finding must not appear.
    candidate_models = LEAKY_MODELS | {"ARBGovernanceStandard"}
    models = candidate_models - checker.GLOBAL_REFERENCE_MODELS
    findings = _scan(tmp_path, src, models=models)
    assert all(f["model"] != "ARBGovernanceStandard" for f in findings)
    assert any(f["model"] == "LeakyThing" for f in findings)


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
