"""CI lifecycle for the navigation-route verification evidence.

``route_verification.json`` is deliberately ignored, local test-run evidence.
The gate is meaningful only when the same CI job first creates a fresh file by
running the non-browser suite with the audit plugin.
"""

from pathlib import Path

from scripts.verify import build_gates, load_baseline


REPO = Path(__file__).resolve().parent.parent


def _tests_job() -> str:
    """Return the CI job that owns the non-browser pytest lifecycle."""
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    return workflow.split("  tests:\n", 1)[1].split("\n  # main grew", 1)[0]


def test_nav_verification_is_not_a_static_gate():
    """Ignored pytest evidence cannot be evaluated by the dependency-only job."""
    gates = {gate.name: gate for gate in build_gates(load_baseline())}

    assert "static" not in gates["nav-verified"].tags, (
        "nav-verified consumes ignored route_verification.json evidence, so it "
        "must run after pytest generates that evidence in the tests job"
    )


def test_tests_job_creates_fresh_nav_evidence_then_enforces_the_gate():
    """A stale local audit file must never satisfy CI's nav-verification gate."""
    lifecycle = _tests_job()

    assert lifecycle, (
        "the tests job has no route-verification lifecycle: it must run pytest "
        "with scripts.route_verification_audit, then enforce nav-verified"
    )

    assert "rm -f route_verification.json" in lifecycle, (
        "the tests job must remove ignored, stale route-verification evidence "
        "before collecting fresh endpoint coverage"
    )
    assert "--ignore=tests/smoke" in lifecycle, (
        "the tests job must collect the full non-smoke suite; browser smoke "
        "tests remain a separate CI job"
    )
    assert "-p scripts.route_verification_audit" in lifecycle, (
        "pytest must load the audit plugin that writes route_verification.json"
    )
    assert "python scripts/verify.py --gate nav-verified" in lifecycle, (
        "the nav-verified gate must run immediately after the same job's pytest "
        "command, while its fresh evidence is available"
    )

    assert lifecycle.index("rm -f route_verification.json") < lifecycle.index(
        "-p scripts.route_verification_audit"
    ) < lifecycle.index("python scripts/verify.py --gate nav-verified")
