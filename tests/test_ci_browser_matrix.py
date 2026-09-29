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


def _jobs_running_non_smoke_pytest():
    """Every CI job with a step that runs the non-smoke pytest suite, as
    (job id, steps, index of that step)."""
    import yaml

    jobs = yaml.safe_load(_workflow())["jobs"]
    found = []
    for job_id, job in jobs.items():
        steps = job.get("steps", [])
        for index, step in enumerate(steps):
            run = step.get("run", "")
            if "pytest" in run and "--ignore=tests/smoke" in run:
                found.append((job_id, steps, index))
                break
    return found


def test_non_smoke_job_installs_chromium_for_collected_csp_browser_tests():
    """tests/csp/test_csp_evaluator.py is collected by the non-smoke run, so
    every job that runs it — each backend-test shard, since which shard it
    lands in is decided at collection time — must install Chromium first."""
    runners = _jobs_running_non_smoke_pytest()

    assert "tests-shard" in {job_id for job_id, _, _ in runners}
    for job_id, steps, pytest_index in runners:
        installs = [
            i for i, step in enumerate(steps)
            if "playwright install --with-deps" in step.get("run", "")
            and "chromium" in step["run"].split("playwright install --with-deps", 1)[1].split("\n", 1)[0]
        ]
        assert installs and installs[0] < pytest_index, (
            f"{job_id} runs the non-smoke pytest suite without installing Chromium first"
        )
