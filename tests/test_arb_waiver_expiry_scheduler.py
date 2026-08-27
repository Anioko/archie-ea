"""Scheduler wiring contracts for the optional typed ARB expiry job."""

from __future__ import annotations

from flask import Flask


class _Scheduler:
    def __init__(self):
        self.jobs = []
        self.started = False

    def add_job(self, **kwargs):
        self.jobs.append(kwargs)

    def start(self):
        self.started = True

    def pause(self):
        return None

    def shutdown(self, wait=False):
        return None


def _start(monkeypatch, *, organization_ids="", interval="5"):
    import apscheduler.schedulers.background

    from app._bootstrap.extensions import init_scheduler

    scheduler = _Scheduler()
    monkeypatch.setattr(
        apscheduler.schedulers.background,
        "BackgroundScheduler",
        lambda: scheduler,
    )
    app = Flask("arb-expiry-scheduler-test")
    app.config.update(
        TESTING=False,
        ARB_CONDITION_EXPIRY_ORGANIZATION_IDS=organization_ids,
        ARB_CONDITION_EXPIRY_INTERVAL_MINUTES=interval,
    )
    init_scheduler(app)
    return scheduler


def test_scheduler_disabled_preserves_established_jobs(monkeypatch):
    scheduler = _start(monkeypatch)

    assert scheduler.started is True
    assert {job["id"] for job in scheduler.jobs} == {
        "ea_workflow_scheduler",
        "data_maturity_digest",
        "executive_summary",
        "teams_subscription_renewal",
    }


def test_scheduler_enabled_registers_typed_arb_expiry(monkeypatch):
    scheduler = _start(monkeypatch, organization_ids="41,42", interval="7")

    jobs = {job["id"]: job for job in scheduler.jobs}
    assert scheduler.started is True
    assert "typed_arb_waiver_expiry" in jobs
    assert str(jobs["typed_arb_waiver_expiry"]["trigger"]) == "interval[0:07:00]"


def test_malformed_optional_interval_does_not_disable_established_jobs(monkeypatch):
    scheduler = _start(monkeypatch, organization_ids="41", interval="invalid")

    assert scheduler.started is True
    assert {job["id"] for job in scheduler.jobs} == {
        "ea_workflow_scheduler",
        "data_maturity_digest",
        "executive_summary",
        "teams_subscription_renewal",
    }
