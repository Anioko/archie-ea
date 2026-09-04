"""The exhaustive product audit must remain runnable for every product role."""

import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/whole-product-audit.yml"


def _valid_roles():
    tree = ast.parse((ROOT / "app/models/user.py").read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants[target.id] = node.value.value
        elif target.id == "VALID_ROLES" and isinstance(node.value, ast.List):
            return [
                constants[element.id] if isinstance(element, ast.Name) else element.value
                for element in node.value.elts
            ]
    raise AssertionError("VALID_ROLES not found")


def test_whole_product_audit_runs_every_role_and_retains_failure_evidence():
    assert WORKFLOW.exists(), "whole-product audit workflow is missing"
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    job = workflow["jobs"]["audit"]

    assert set(job["strategy"]["matrix"]["persona"]) == set(_valid_roles())
    assert "workflow_dispatch" in raw
    assert "postgres:16" in raw
    assert "scripts/production_readiness_audit.py" in raw
    assert "--persona ${{ matrix.persona }}" in raw
    assert "if: always()" in raw
    assert "audit-${{ matrix.persona }}-${{ github.sha }}" in raw
    assert "retention-days: 30" in raw


def test_whole_product_audit_exercises_both_desktop_and_mobile():
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "--desktop-only" not in raw
    assert "--level" not in raw, "the active audit must run all defined levels"


def test_audit_report_inventories_every_visible_control_per_page():
    from scripts import production_readiness_audit as audit

    source = (ROOT / "scripts/production_readiness_audit.py").read_text(encoding="utf-8")
    assert "out.controls =" in audit.PAGE_PROBE
    assert "getBoundingClientRect" in audit.PAGE_PROBE
    assert '[contenteditable="true"]' in audit.PAGE_PROBE
    assert '[tabindex]:not([tabindex="-1"])' in audit.PAGE_PROBE
    assert "@click(?:\\.[\\w-]+)*" in audit.PAGE_PROBE
    assert '"control_inventory": control_inventory' in source
    assert '"controls": probe.get("controls") or []' in source


def test_information_only_observations_do_not_fail_the_audit():
    from scripts import production_readiness_audit as audit

    observations = [
        {"severity": "info", "kind": "expected-forbidden"},
        {"severity": "medium", "kind": "broken-control"},
    ]

    assert audit.blocking_findings(observations) == [observations[1]]


def test_authorization_distinguishes_expected_and_unexpected_admin_access():
    from scripts import production_readiness_audit as audit

    base = {"route": "/admin/users", "endpoint": "admin.users", "viewport": "desktop"}
    expected_denial = audit.evaluate_findings({1, 8}, {**base, "persona": "cto"}, {}, 403, [], [])
    admin_denial = audit.evaluate_findings(
        {1, 8}, {**base, "persona": "platform_admin"}, {}, 403, [], []
    )
    unexpected_access = audit.evaluate_findings(
        {8}, {**base, "persona": "cto"}, {}, 200, [], []
    )

    assert any(f["kind"] == "expected-forbidden" and f["severity"] == "info"
               for f in expected_denial)
    assert any(f["kind"] == "unexpected-forbidden" for f in admin_denial)
    assert any(f["kind"] == "unauthorized-access" for f in unexpected_access)


def test_control_inventory_never_serializes_editable_values():
    from playwright.sync_api import sync_playwright
    from scripts import production_readiness_audit as audit

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content("""
            <label for="email">Email address</label>
            <input id="email" value="private@example.com">
            <label for="notes">Notes</label>
            <textarea id="notes">private field contents</textarea>
            <div contenteditable="true" aria-label="Comment">another secret</div>
        """)
        probe = page.evaluate(audit.PAGE_PROBE)
        browser.close()

    serialized = str(probe["controls"])
    assert "private@example.com" not in serialized
    assert "private field contents" not in serialized
    assert "another secret" not in serialized
    assert {control["label"] for control in probe["controls"]} == {
        "Email address", "Notes", "Comment"
    }


def test_button_name_probe_resolves_label_references_in_chromium():
    from playwright.sync_api import sync_playwright
    from scripts import production_readiness_audit as audit

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content('''
                <span id="preference">Weekly digest</span>
                <button role="switch" aria-labelledby="preference"></button>
                <button class="broken-reference" aria-labelledby="missing"></button>
            ''')
            probe = page.evaluate(audit.PAGE_PROBE)
            assert probe["unnamedButtons"] == ["broken-reference"]
        finally:
            browser.close()
