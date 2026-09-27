"""The release verifier must execute the governance and AI-safety checkers."""

from scripts.verify import build_gates


def test_governance_and_ai_safety_checkers_are_registered():
    baseline = {
        "undefined_names": 0,
        "redefinitions": 0,
        "lint_core": 0,
        "design_tokens": 0,
        "raw_fetch_sites": 0,
        "design_tokens_extended": 0,
        "shell_conformance": 3,
        "nav_coverage": 0,
        "air_gap": 0,
        "raw_sql_tenancy": 0,
        "tenant_scoping": 0,
        "fetch_guards": 0,
        "ui_contract": 0,
        "console_reporting": 0,
        "nav_verified": 0,
        "evidence_contract": 29,
        "role_gate_coverage": 9,
    }
    gates = {gate.name: gate for gate in build_gates(baseline)}

    expected = {
        "evidence-contract": ("ratchet", {"static", "process", "evidence"}),
        "role-gate-coverage": ("ratchet", {"static", "process"}),
        "ai-evidence-rules": ("zero", {"static", "ai", "evidence"}),
        "ai-tool-guard": ("zero", {"static", "ai", "security"}),
        "ai-untrusted-content": ("zero", {"static", "ai", "security"}),
        "ai-approval-honoured": ("zero", {"static", "ai", "security"}),
    }
    for name, (kind, tags) in expected.items():
        assert name in gates
        assert gates[name].kind == kind
        assert tags <= set(gates[name].tags)
