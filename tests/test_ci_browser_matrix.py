"""The release workflow must produce real, retained cross-browser evidence."""

from pathlib import Path


CI = Path(".github/workflows/ci.yml")


def _workflow():
    return CI.read_text(encoding="utf-8")


def test_ci_runs_critical_journeys_in_firefox_and_webkit():
    workflow = _workflow()

    assert "browser-compatibility:" in workflow
    assert "browser: [firefox, webkit]" in workflow
    assert "SMOKE_BROWSER: ${{ matrix.browser }}" in workflow
    assert "playwright install --with-deps ${{ matrix.browser }}" in workflow
    for suite in (
        "test_accessibility_audit.py",
        "test_archetype_journeys.py",
        "test_authorisation_matrix.py",
        "test_roadmap_crud_journey.py",
        "test_transformation_room_journeys.py",
    ):
        assert suite in workflow


def test_ci_fails_when_required_browser_is_missing_and_retains_evidence():
    workflow = _workflow()

    assert workflow.count('SMOKE_REQUIRE_BROWSER: "1"') >= 2
    assert "if: always()" in workflow
    assert "--junitxml=" in workflow
    assert "retention-days: 30" in workflow
    assert "${{ github.sha }}" in workflow
