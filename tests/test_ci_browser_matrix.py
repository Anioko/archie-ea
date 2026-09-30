"""The release workflow must produce real, retained cross-browser evidence."""

from pathlib import Path

import yaml


CI = Path(".github/workflows/ci.yml")


def _workflow():
    return CI.read_text(encoding="utf-8")


def _parsed():
    return yaml.safe_load(_workflow())["jobs"]


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


# ── Shard runner choice and parallelism ────────────────────────────────────


def test_shard_runs_on_falls_back_to_self_hosted_when_variable_unset():
    """The shard job's runs-on references vars.CI_SHARD_RUNNER and falls back
    to self-hosted + ibm-vsi when the variable is unset; a forked PR must
    never leave ubuntu-latest."""
    jobs = _parsed()
    runs_on = jobs["tests-shard"]["runs-on"]

    assert "vars.CI_SHARD_RUNNER" in runs_on
    assert "self-hosted" in runs_on
    assert "ibm-vsi" in runs_on
    assert "ubuntu-latest" in runs_on
    assert "github.event.pull_request.head.repo.full_name == github.repository" in runs_on


def test_shard_max_parallel_reads_variable_with_default_6():
    """max-parallel reads vars.CI_SHARD_MAX_PARALLEL and defaults to 6 when
    the variable is unset; forked PRs keep 8."""
    jobs = _parsed()
    max_parallel = jobs["tests-shard"]["strategy"]["max-parallel"]

    assert "vars.CI_SHARD_MAX_PARALLEL" in max_parallel
    assert "6" in max_parallel
    assert "8" in max_parallel


def test_ci_fast_runner_takes_precedence_over_shard_runner():
    """When vars.CI_FAST_RUNNER is set and the PR carries the ci-fast label,
    the shard job uses that runner. The variable and label check must both
    appear in the runs-on expression, and CI_FAST_RUNNER must be evaluated
    before CI_SHARD_RUNNER so it takes precedence."""
    jobs = _parsed()
    runs_on = jobs["tests-shard"]["runs-on"]

    assert "vars.CI_FAST_RUNNER" in runs_on
    assert "ci-fast" in runs_on
    fast_pos = runs_on.index("vars.CI_FAST_RUNNER")
    shard_pos = runs_on.index("vars.CI_SHARD_RUNNER")
    assert fast_pos < shard_pos, (
        "vars.CI_FAST_RUNNER must appear before vars.CI_SHARD_RUNNER "
        "so it takes precedence"
    )


def test_ci_fast_runner_guarded_by_pull_request_event():
    """vars.CI_FAST_RUNNER and the ci-fast label check must only apply to
    pull_request events, so a push to main never evaluates the label check
    against a missing pull_request context."""
    jobs = _parsed()
    runs_on = jobs["tests-shard"]["runs-on"]

    assert "github.event_name == 'pull_request'" in runs_on


def test_labeled_event_triggers_workflow_for_ci_fast():
    """Adding a label must trigger a fresh workflow run so the ci-fast label
    takes effect without requiring a new push."""
    workflow = _workflow()
    assert "labeled" in workflow


def test_ci_fast_max_parallel_is_8_bypassing_shard_cap():
    """On the ci-fast lane (CI_FAST_RUNNER set and ci-fast label present)
    max-parallel must be 8, bypassing CI_SHARD_MAX_PARALLEL.  The expression
    must reference CI_FAST_RUNNER and ci-fast, and the literal 8 for the
    ci-fast lane must appear before the CI_SHARD_MAX_PARALLEL fallback so it
    takes precedence."""
    jobs = _parsed()
    max_parallel = jobs["tests-shard"]["strategy"]["max-parallel"]

    assert "vars.CI_FAST_RUNNER" in max_parallel
    assert "ci-fast" in max_parallel
    # The ci-fast 8 must appear before the CI_SHARD_MAX_PARALLEL reference
    # so the ci-fast lane's value takes precedence.
    fast_eight_pos = max_parallel.index("&& 8 || vars.CI_SHARD_MAX_PARALLEL")
    shard_var_pos = max_parallel.index("vars.CI_SHARD_MAX_PARALLEL")
    assert fast_eight_pos < shard_var_pos, (
        "ci-fast lane's 8 must appear before vars.CI_SHARD_MAX_PARALLEL "
        "so it takes precedence over the shard cap"
    )


def test_jobs_skip_on_non_ci_fast_labeled_events():
    """Every job (except release-image, which already gates on event_name)
    must carry an if: condition that skips the job when the trigger is a
    labeled pull_request event that does not carry the ci-fast label.  This
    prevents a full CI re-run when any unrelated label is added to a PR."""
    jobs = _parsed()
    gating_jobs = {
        "secret-scan", "static-gates", "boot-health", "tests-shard",
        "tests", "db-gates", "security-sast", "smoke",
        "browser-compatibility", "walkthrough", "dependency-audit",
    }
    for job_id in gating_jobs:
        job = jobs[job_id]
        if_expr = job.get("if", "")
        assert "labeled" in if_expr, (
            f"{job_id} must guard against non-ci-fast labeled events"
        )
        assert "ci-fast" in if_expr, (
            f"{job_id} must allow ci-fast labeled events through"
        )
        assert "github.event.action" in if_expr or "labeled" in if_expr, (
            f"{job_id} must check the event action for labeled"
        )
