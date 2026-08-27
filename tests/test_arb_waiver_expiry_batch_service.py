"""Contracts for automatic, tenant-explicit ARB waiver expiry processing."""

from __future__ import annotations

from contextlib import contextmanager
import importlib
import json
from types import SimpleNamespace

import pytest
from flask import Flask

from app.modules.transformation_room.domain import NotAuthorised


def _module():
    try:
        return importlib.import_module(
            "app.modules.transformation_room.arb_waiver_expiry_batch_service"
        )
    except ModuleNotFoundError:
        pytest.fail("automatic ARB waiver expiry requires a batch service")


@pytest.fixture
def expiry_app():
    app = Flask("arb-waiver-expiry-test")
    app.config["ARB_CONDITION_EXPIRY_CAPABILITY"] = "batch-secret"
    with app.app_context():
        yield app


def test_batch_uses_deterministic_revisioned_commands_and_isolates_failures(
    expiry_app, monkeypatch
):
    module = _module()
    service = module.ARBWaiverExpiryBatchService
    candidates = (
        module.WaiverExpiryCandidate(organization_id=41, condition_id=601, revision=4),
        module.WaiverExpiryCandidate(organization_id=42, condition_id=602, revision=7),
        module.WaiverExpiryCandidate(organization_id=41, condition_id=603, revision=2),
    )
    calls = []

    @contextmanager
    def lock():
        yield True

    def expire(**kwargs):
        calls.append(kwargs)
        if kwargs["condition_id"] == 602:
            raise RuntimeError("isolated failure")
        return SimpleNamespace(created=True, idempotent=False)

    monkeypatch.setattr(service, "_advisory_lock", staticmethod(lock))
    monkeypatch.setattr(
        service,
        "_select_due",
        classmethod(lambda cls, organization_ids, batch_size: candidates),
    )
    monkeypatch.setattr(module.TypedARBConditionLifecycleService, "expire_waivers", expire)

    result = service.run(organization_ids=[42, 41, 42], batch_size=3)

    assert result.as_dict() == {
        "lock_acquired": True,
        "organization_ids": [41, 42],
        "batch_size": 3,
        "selected_count": 3,
        "expired_count": 2,
        "replayed_count": 0,
        "failed_count": 1,
        "errors": [
            {
                "organization_id": 42,
                "condition_id": 602,
                "condition_revision": 7,
                "error_type": "RuntimeError",
                "reason": "isolated failure",
            }
        ],
    }
    assert calls == [
        {
            "capability": "batch-secret",
            "command_key": "arb-waiver-expiry:41:601:5",
            "condition_id": 601,
            "organization_id": 41,
        },
        {
            "capability": "batch-secret",
            "command_key": "arb-waiver-expiry:42:602:8",
            "condition_id": 602,
            "organization_id": 42,
        },
        {
            "capability": "batch-secret",
            "command_key": "arb-waiver-expiry:41:603:3",
            "condition_id": 603,
            "organization_id": 41,
        },
    ]


def test_batch_reports_replay_and_duplicate_scheduler_without_inventing_work(
    expiry_app, monkeypatch
):
    module = _module()
    service = module.ARBWaiverExpiryBatchService

    @contextmanager
    def held_lock():
        yield False

    monkeypatch.setattr(service, "_advisory_lock", staticmethod(held_lock))
    result = service.run(organization_ids=[41], batch_size=10)
    assert result.as_dict() == {
        "lock_acquired": False,
        "organization_ids": [41],
        "batch_size": 10,
        "selected_count": 0,
        "expired_count": 0,
        "replayed_count": 0,
        "failed_count": 0,
        "errors": [],
    }

    @contextmanager
    def acquired_lock():
        yield True

    monkeypatch.setattr(service, "_advisory_lock", staticmethod(acquired_lock))
    monkeypatch.setattr(
        service,
        "_select_due",
        classmethod(
            lambda cls, organization_ids, batch_size: (
                module.WaiverExpiryCandidate(41, 601, 4),
            )
        ),
    )
    monkeypatch.setattr(
        module.TypedARBConditionLifecycleService,
        "expire_waivers",
        lambda **kwargs: SimpleNamespace(created=False, idempotent=True),
    )
    replay = service.run(organization_ids=[41], batch_size=10)
    assert replay.expired_count == 0
    assert replay.replayed_count == 1
    assert replay.failed_count == 0


@pytest.mark.parametrize(
    ("organization_ids", "batch_size", "message"),
    (
        ([], 10, "organization_ids are required"),
        ([0], 10, "organization_ids must contain positive integers"),
        ([41], 0, "batch_size must be between"),
        ([41], 1001, "batch_size must be between"),
    ),
)
def test_batch_rejects_implicit_tenants_and_unbounded_work(
    expiry_app, organization_ids, batch_size, message
):
    module = _module()
    with pytest.raises(ValueError, match=message):
        module.ARBWaiverExpiryBatchService.run(
            organization_ids=organization_ids, batch_size=batch_size
        )


def test_scheduler_configuration_parses_environment_strings(expiry_app):
    module = _module()
    expiry_app.config["ARB_CONDITION_EXPIRY_ORGANIZATION_IDS"] = "42, 41,42"
    expiry_app.config["ARB_CONDITION_EXPIRY_BATCH_SIZE"] = "25"

    assert module.ARBWaiverExpiryBatchService.configured_organization_ids() == (41, 42)
    assert module.ARBWaiverExpiryBatchService.configured_batch_size() == 25


def test_scheduler_rejects_boolean_tenant_and_principal_ids(expiry_app):
    module = _module()
    lifecycle = module.TypedARBConditionLifecycleService
    expiry_app.config["ARB_CONDITION_EXPIRY_PRINCIPALS"] = {"41": True}

    with pytest.raises(ValueError, match="positive integers"):
        module.ARBWaiverExpiryBatchService.run(
            organization_ids=[True], batch_size=1
        )
    with pytest.raises(NotAuthorised, match="tenant_required"):
        lifecycle._scheduler_actor("batch-secret", organization_id=True)
    with pytest.raises(NotAuthorised, match="principal_invalid"):
        lifecycle._scheduler_actor("batch-secret", organization_id=41)


def test_scheduler_principal_must_be_confirmed_under_lock(expiry_app):
    module = _module()
    lifecycle = module.TypedARBConditionLifecycleService
    expiry_app.config["ARB_CONDITION_EXPIRY_PRINCIPALS"] = {"41": 73}
    actor = lifecycle._scheduler_actor("batch-secret", organization_id=41)

    with pytest.raises(NotAuthorised, match="principal_invalid"):
        lifecycle._authorise_system_principal(
            SimpleNamespace(),
            actor,
            locked_user=SimpleNamespace(
                id=73, organization_id=41, confirmed=False
            ),
        )


def test_cli_requires_explicit_tenants_and_emits_machine_readable_result(app, monkeypatch):
    module = _module()
    expected = module.WaiverExpiryBatchResult(
        lock_acquired=True,
        organization_ids=(41, 42),
        batch_size=25,
        selected_count=2,
        expired_count=2,
        replayed_count=0,
        failed_count=0,
        errors=(),
    )
    monkeypatch.setattr(
        module.ARBWaiverExpiryBatchService,
        "run",
        classmethod(lambda cls, **kwargs: expected),
    )
    runner = app.test_cli_runner()

    missing = runner.invoke(args=["process-arb-waiver-expiries"])
    assert missing.exit_code != 0
    assert "--organization-id" in missing.output

    result = runner.invoke(
        args=[
            "process-arb-waiver-expiries",
            "--organization-id", "41",
            "--organization-id", "42",
            "--batch-size", "25",
        ]
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == expected.as_dict()
