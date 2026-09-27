"""R1-B17 PR 1: every scheduled job runs outside the web process, inside its
organisation's tenant context, once a dedicated jobs worker is configured.

Two things are exercised here:

1. ``JOBS_RUN_IN_WORKER`` / ``RUNNING_AS_JOBS_WORKER`` gate whether
   ``init_scheduler`` starts anything in THIS process -- the acceptance
   criterion "no job runs in the web process when the worker is configured".
2. The Teams subscription renewal job, which previously called
   ``TeamsMeetingService.renew_if_needed()`` with no tenant context at all
   (so the tenant-scoped ``APISettings`` query it makes resolved whichever
   organisation's row Postgres returned first), now visits every active
   organisation separately through ``tenant_scope``.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clean_jobs_worker_env(monkeypatch):
    """Every test in this module starts from neither env var set."""
    monkeypatch.delenv("JOBS_RUN_IN_WORKER", raising=False)
    monkeypatch.delenv("RUNNING_AS_JOBS_WORKER", raising=False)


def _shutdown_and_pop(app):
    """Mirror the teardown in test_capability_projection_job.py::test_ac7b --
    a real BackgroundScheduler leaking out of a test would keep firing jobs
    against the shared test database for the rest of the pytest session.
    """
    leaked = app.extensions.pop("ea_workflow_scheduler", None)
    if leaked is not None:
        try:
            leaked.shutdown(wait=False)
        except Exception:
            pass


def test_scheduler_not_started_in_web_process_when_worker_configured(
    app, monkeypatch
):
    """Acceptance: no job runs in the web process when the worker is configured."""
    from app._bootstrap.extensions import init_scheduler

    monkeypatch.setenv("JOBS_RUN_IN_WORKER", "1")

    original_testing = app.testing
    app.testing = False
    try:
        init_scheduler(app)
        assert app.extensions.get("ea_workflow_scheduler") is None, (
            "init_scheduler() started a scheduler in the web process even "
            "though JOBS_RUN_IN_WORKER=1 and RUNNING_AS_JOBS_WORKER is unset"
        )
    finally:
        _shutdown_and_pop(app)
        app.testing = original_testing


def test_scheduler_still_starts_when_no_worker_is_configured(app, monkeypatch):
    """Backward compatibility: today's single-process deployments and every
    pre-existing test (e.g. test_capability_projection_job.py::test_ac7b)
    depend on init_scheduler() registering jobs when neither env var is set.
    """
    from app._bootstrap.extensions import init_scheduler

    original_testing = app.testing
    app.testing = False
    try:
        init_scheduler(app)
        assert app.extensions.get("ea_workflow_scheduler") is not None
    finally:
        _shutdown_and_pop(app)
        app.testing = original_testing


def test_scheduler_starts_in_the_jobs_worker_process_itself(app, monkeypatch):
    """The jobs worker (app/jobs/worker.py) sets RUNNING_AS_JOBS_WORKER before
    calling create_app(); that must start the scheduler even when
    JOBS_RUN_IN_WORKER=1 is also set on the same process's config -- the
    worker IS the process JOBS_RUN_IN_WORKER is asking for.
    """
    from app._bootstrap.extensions import init_scheduler

    monkeypatch.setenv("JOBS_RUN_IN_WORKER", "1")
    monkeypatch.setenv("RUNNING_AS_JOBS_WORKER", "1")

    original_testing = app.testing
    app.testing = False
    try:
        init_scheduler(app)
        assert app.extensions.get("ea_workflow_scheduler") is not None
    finally:
        _shutdown_and_pop(app)
        app.testing = original_testing


class _CapturingScheduler:
    """Stand-in for APScheduler's BackgroundScheduler that records every
    job's callable instead of actually scheduling it, so a test can invoke
    one job function directly and deterministically -- same technique as
    tests/test_arb_waiver_expiry_scheduler.py.
    """

    def __init__(self):
        self.jobs = {}
        self.started = False

    def add_job(self, **kwargs):
        self.jobs[kwargs["id"]] = kwargs["func"]

    def start(self):
        self.started = True

    def pause(self):
        pass

    def shutdown(self, wait=False):
        pass


def _capture_scheduler(monkeypatch):
    import apscheduler.schedulers.background

    scheduler = _CapturingScheduler()
    monkeypatch.setattr(
        apscheduler.schedulers.background, "BackgroundScheduler", lambda: scheduler
    )
    return scheduler


def test_teams_renewal_visits_every_active_organisation_separately(
    app, db_session, make_org, monkeypatch
):
    from flask import g

    import app.services.teams_meeting_service as teams_mod
    from app._bootstrap.extensions import init_scheduler

    org_a = make_org("teams-a")
    org_b = make_org("teams-b")
    db_session.commit()
    org_a_id, org_b_id = org_a.id, org_b.id

    seen_org_ids = []

    def _fake_renew_if_needed():
        # Read the exact value the isolation listeners key off, to prove
        # this call ran inside a real tenant_scope() and not with g unset.
        seen_org_ids.append(g.current_org_id)
        return {"status": "skipped", "reason": "no subscription on record"}

    monkeypatch.setattr(
        teams_mod.TeamsMeetingService,
        "renew_if_needed",
        staticmethod(_fake_renew_if_needed),
    )

    scheduler = _capture_scheduler(monkeypatch)

    original_testing = app.testing
    app.testing = False
    try:
        init_scheduler(app)
        job_func = scheduler.jobs["teams_subscription_renewal"]
        job_func()
    finally:
        app.testing = original_testing

    assert org_a_id in seen_org_ids, (
        f"organisation {org_a_id} was never visited: {seen_org_ids}"
    )
    assert org_b_id in seen_org_ids, (
        f"organisation {org_b_id} was never visited: {seen_org_ids}"
    )
    # Every visit ran with a concrete tenant on g -- never the unscoped call
    # (None) this job made before this fix.
    assert None not in seen_org_ids


def test_teams_renewal_one_tenant_failure_does_not_abort_the_others(
    app, db_session, make_org, monkeypatch
):
    import app.services.teams_meeting_service as teams_mod
    from app._bootstrap.extensions import init_scheduler

    org_fail = make_org("teams-fail")
    org_ok = make_org("teams-ok")
    db_session.commit()
    org_fail_id, org_ok_id = org_fail.id, org_ok.id

    seen_org_ids = []

    def _fake_renew_if_needed():
        from flask import g

        seen_org_ids.append(g.current_org_id)
        if g.current_org_id == org_fail_id:
            raise RuntimeError("Graph API unavailable")
        return {"status": "skipped", "reason": "no subscription on record"}

    monkeypatch.setattr(
        teams_mod.TeamsMeetingService,
        "renew_if_needed",
        staticmethod(_fake_renew_if_needed),
    )

    scheduler = _capture_scheduler(monkeypatch)

    original_testing = app.testing
    app.testing = False
    try:
        init_scheduler(app)
        job_func = scheduler.jobs["teams_subscription_renewal"]
        job_func()  # must not raise -- one tenant's failure is caught and logged
    finally:
        app.testing = original_testing

    assert org_fail_id in seen_org_ids
    assert org_ok_id in seen_org_ids
