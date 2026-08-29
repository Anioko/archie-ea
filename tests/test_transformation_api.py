"""HTTP contract for the canonical Transformation Room API.

The route-surface checks pin every Task 10 resource.  The integration checks
drive the real programme service and command envelope; they intentionally use
committed setup because ``CommandService`` opens independent sessions.
"""

from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "74" * 32)


BASE = "/api/v1/transformation-programmes"

ROUTE_CONTRACT = {
    (BASE, "GET"),
    (BASE, "POST"),
    (f"{BASE}/<int:programme_id>", "GET"),
    (f"{BASE}/<int:programme_id>", "DELETE"),
    (f"{BASE}/<int:programme_id>/role-assignments", "POST"),
    (f"{BASE}/<int:programme_id>/workstreams", "GET"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>", "GET"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/objective", "PATCH"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/transitions", "POST"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/discovery-candidates", "GET"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/candidates", "POST"),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/candidates/<int:candidate_id>/evidence-requests",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/candidates/<int:candidate_id>/evidence-observations",
        "POST",
    ),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/evidence", "GET"),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence-requests/<int:evidence_request_id>/attestations",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence-requests/<int:evidence_request_id>/acceptance",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence-requests/<int:evidence_request_id>/decline",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence-requests/<int:evidence_request_id>/expiry",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence-requests/<int:evidence_request_id>/waiver",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/evidence/<int:conflict_evidence_id>/resolution",
        "POST",
    ),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/options", "POST"),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/options/<int:option_id>/versions",
        "POST",
    ),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/option-comparison", "GET"),
    (f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>/decision-briefs", "POST"),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/decision-briefs/<int:brief_id>/readiness",
        "GET",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/decision-briefs/<int:brief_id>/versions",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/decision-briefs/<int:brief_id>/arb-submissions",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/decision-brief-versions/<int:brief_version_id>/execution",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/decision-brief-versions/<int:brief_version_id>/technology-solutions",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/work-packages/<int:work_package_id>/delivery-exports",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/work-packages/<int:work_package_id>/delivery-exports/<int:attempt_id>/retries",
        "POST",
    ),
    (
        f"{BASE}/<int:programme_id>/workstreams/<int:workstream_id>"
        "/benefits/<int:benefit_id>/measurements",
        "POST",
    ),
}


MUTATION_PATHS = (
    ("POST", BASE),
    ("DELETE", f"{BASE}/999999"),
    ("POST", f"{BASE}/999999/role-assignments"),
    ("PATCH", f"{BASE}/999999/workstreams/999999/objective"),
    ("POST", f"{BASE}/999999/workstreams/999999/transitions"),
    ("POST", f"{BASE}/999999/workstreams/999999/candidates"),
    ("POST", f"{BASE}/999999/workstreams/999999/candidates/999999/evidence-requests"),
    ("POST", f"{BASE}/999999/workstreams/999999/candidates/999999/evidence-observations"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence-requests/999999/attestations"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence-requests/999999/acceptance"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence-requests/999999/decline"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence-requests/999999/expiry"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence-requests/999999/waiver"),
    ("POST", f"{BASE}/999999/workstreams/999999/evidence/999999/resolution"),
    ("POST", f"{BASE}/999999/workstreams/999999/options"),
    ("POST", f"{BASE}/999999/workstreams/999999/options/999999/versions"),
    ("POST", f"{BASE}/999999/workstreams/999999/decision-briefs"),
    ("POST", f"{BASE}/999999/workstreams/999999/decision-briefs/999999/versions"),
    ("POST", f"{BASE}/999999/workstreams/999999/decision-briefs/999999/arb-submissions"),
    ("POST", f"{BASE}/999999/workstreams/999999/decision-brief-versions/999999/execution"),
    (
        "POST",
        f"{BASE}/999999/workstreams/999999/decision-brief-versions/999999/technology-solutions",
    ),
    ("POST", f"{BASE}/999999/workstreams/999999/work-packages/999999/delivery-exports"),
    (
        "POST",
        f"{BASE}/999999/workstreams/999999/work-packages/999999/delivery-exports/999999/retries",
    ),
    ("POST", f"{BASE}/999999/workstreams/999999/benefits/999999/measurements"),
)


_CLEANUP_TABLES = (
    "archie_command_claim_challenges",
    "transformation_outbox_events",
    "operation_results",
    "command_materialisations",
    "command_idempotency_records",
    "measure_definitions",
    "programme_outcome_commitments",
    "programme_role_assignments",
    "programme_workstreams",
    "strategic_initiatives",
    "users",
)


@pytest.fixture(scope="module", autouse=True)
def transformation_api_schema(app, _schema):
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []


@pytest.fixture
def committed_session(app, _schema):
    """Committed setup visible to the command service's isolated sessions."""
    from app import db

    with app.app_context():
        db.session.remove()
        cleanup_org_ids: set[int] = set()
        try:
            yield db.session, cleanup_org_ids
        finally:
            db.session.remove()
            if cleanup_org_ids:
                raw = db.engine.raw_connection()
                try:
                    with raw.cursor() as cursor:
                        cursor.execute("SHOW session_replication_role")
                        original_role = cursor.fetchone()[0]
                        cursor.execute("SET session_replication_role = replica")
                        try:
                            for table in _CLEANUP_TABLES:
                                cursor.execute(
                                    f'DELETE FROM "{table}" WHERE organization_id = ANY(%s)',
                                    (list(cleanup_org_ids),),
                                )
                            cursor.execute(
                                "DELETE FROM organizations WHERE id = ANY(%s)",
                                (list(cleanup_org_ids),),
                            )
                        finally:
                            cursor.execute(f"SET session_replication_role = {original_role}")
                            raw.commit()
                finally:
                    raw.close()


def _make_org(session, cleanup_org_ids, label):
    from app.models.organization import Organization

    suffix = uuid.uuid4().hex[:10]
    org = Organization(name=f"API {label} {suffix}", slug=f"api-{label}-{suffix}")
    session.add(org)
    session.flush()
    cleanup_org_ids.add(org.id)
    return org


def _make_user(session, org, *, role="enterprise_architect"):
    from app.models.user import User

    user = User(
        organization_id=org.id,
        email=f"transformation-api-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Transformation",
        last_name="Architect",
        enterprise_role=role,
        confirmed=True,
    )
    session.add(user)
    session.flush()
    return user


def _ensure_guards(session):
    from app.models.transformation_db_guards import ensure_transformation_db_guards

    ensure_transformation_db_guards(session.connection(), capability_secrets=("74" * 32,))


def _intake(owner_id):
    return {
        "name": "Simplify the application estate",
        "objective": "Reduce duplicated capability cost without service loss",
        "owner_id": owner_id,
        "target_date": "2027-06-30",
        "target_date_unavailable_reason": None,
        "workstream_type": "application_rationalisation",
        "scope_expression": {"business_units": ["Retail"]},
        "outcome": {
            "statement": "Reduce annual run cost",
            "owner_id": owner_id,
            "direction": "decrease",
            "measure": {
                "metric_name": "Annual run cost",
                "unit": "GBP",
                "currency": "GBP",
                "aggregation": "sum",
                "baseline_value": None,
                "unavailable_reason": "Finance baseline requested",
                "target_value": "900000.00",
            },
        },
    }


def _assert_envelope(body, *, error_code=None):
    assert set(body) == {"data", "meta", "errors", "request_id"}
    assert isinstance(body["request_id"], str) and body["request_id"]
    if error_code is None:
        assert body["errors"] == []
        assert body["data"] is not None
    else:
        assert body["data"] is None
        assert body["errors"][0]["code"] == error_code


def test_transformation_api_registers_the_complete_single_versioned_surface(app):
    observed = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
        if rule.rule.startswith(BASE) and method not in {"HEAD", "OPTIONS"}
    }
    assert observed == ROUTE_CONTRACT


def test_transformation_api_anonymous_requests_use_uniform_401(client):
    response = client.get(BASE, headers={"X-Request-ID": "anonymous-api-probe"})
    assert response.status_code == 401
    body = response.get_json()
    _assert_envelope(body, error_code="not_authenticated")
    assert body["request_id"] == "anonymous-api-probe"


@pytest.mark.parametrize(("method", "path"), MUTATION_PATHS)
def test_transformation_api_every_mutation_requires_idempotency_key(
    method, path, client, committed_session, login_as
):
    session, cleanup_org_ids = committed_session
    org = _make_org(session, cleanup_org_ids, "headers")
    user = _make_user(session, org)
    session.commit()
    login_as(client, user)

    response = client.open(path, method=method, json={})

    assert response.status_code == 400
    body = response.get_json()
    _assert_envelope(body, error_code="validation_failed")
    assert body["errors"][0]["field"] == "Idempotency-Key"


def test_transformation_api_real_intake_replays_and_rejects_changed_digest(
    client, committed_session, login_as, monkeypatch
):
    from app import db
    from app.models.strategic import StrategicInitiative

    monkeypatch.setenv("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "74" * 32)
    session, cleanup_org_ids = committed_session
    _ensure_guards(session)
    org = _make_org(session, cleanup_org_ids, "replay")
    owner = _make_user(session, org)
    session.commit()
    login_as(client, owner)
    command_key = f"programme-intake-{uuid.uuid4().hex}"

    first = client.post(BASE, json=_intake(owner.id), headers={"Idempotency-Key": command_key})
    assert first.status_code == 201, first.get_json()
    first_body = first.get_json()
    _assert_envelope(first_body)
    assert first_body["meta"]["idempotent"] is False

    db.session.remove()
    login_as(client, owner)
    replay = client.post(BASE, json=_intake(owner.id), headers={"Idempotency-Key": command_key})
    assert replay.status_code == 200, replay.get_json()
    replay_body = replay.get_json()
    assert replay_body["data"] == first_body["data"]
    assert replay_body["meta"]["idempotent"] is True
    assert replay_body["meta"]["operation_result_id"] == first_body["meta"]["operation_result_id"]

    db.session.remove()
    login_as(client, owner)
    changed = _intake(owner.id)
    changed["objective"] = "A different command body under the same receipt key"
    conflict = client.post(BASE, json=changed, headers={"Idempotency-Key": command_key})
    assert conflict.status_code == 409
    _assert_envelope(conflict.get_json(), error_code="conflict")

    db.session.remove()
    assert (
        db.session.query(StrategicInitiative)
        .filter_by(organization_id=org.id, record_kind="transformation_programme")
        .count()
        == 1
    )


def test_transformation_api_rejects_server_owned_identity_and_status(
    client, committed_session, login_as
):
    session, cleanup_org_ids = committed_session
    org = _make_org(session, cleanup_org_ids, "owned-fields")
    owner = _make_user(session, org)
    session.commit()
    login_as(client, owner)
    payload = _intake(owner.id)
    payload.update(
        {
            "organization_id": org.id,
            "created_by_id": owner.id,
            "status": "approved",
            "roles": ["platform_admin"],
        }
    )

    response = client.post(
        BASE,
        json=payload,
        headers={"Idempotency-Key": f"owned-fields-{uuid.uuid4().hex}"},
    )

    assert response.status_code == 400
    body = response.get_json()
    _assert_envelope(body, error_code="validation_failed")
    assert set(body["errors"][0]["details"]["fields"]) == {
        "created_by_id",
        "organization_id",
        "roles",
        "status",
    }


def test_transformation_api_stale_if_match_is_conflict_and_foreign_id_is_opaque(
    client, committed_session, login_as, monkeypatch
):
    from app import db

    monkeypatch.setenv("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "74" * 32)
    session, cleanup_org_ids = committed_session
    _ensure_guards(session)
    org = _make_org(session, cleanup_org_ids, "tenant-a")
    foreign_org = _make_org(session, cleanup_org_ids, "tenant-b")
    owner = _make_user(session, org)
    foreign_user = _make_user(session, foreign_org)
    session.commit()
    foreign_user_id = foreign_user.id
    login_as(client, owner)
    created = client.post(
        BASE,
        json=_intake(owner.id),
        headers={"Idempotency-Key": f"tenant-boundary-{uuid.uuid4().hex}"},
    ).get_json()["data"]
    programme_id = created["programme_id"]
    workstream_id = created["workstream_id"]

    db.session.remove()
    login_as(client, owner)
    updated = client.patch(
        f"{BASE}/{programme_id}/workstreams/{workstream_id}/objective",
        json={"objective": "A newly governed objective", "scope_expression": {"regions": ["UK"]}},
        headers={"Idempotency-Key": f"objective-{uuid.uuid4().hex}", "If-Match": '"1"'},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["data"]["revision"] == 2

    db.session.remove()
    login_as(client, owner)
    stale = client.patch(
        f"{BASE}/{programme_id}/workstreams/{workstream_id}/objective",
        json={"objective": "A stale objective", "scope_expression": {}},
        headers={"Idempotency-Key": f"stale-{uuid.uuid4().hex}", "If-Match": "1"},
    )
    assert stale.status_code == 409
    _assert_envelope(stale.get_json(), error_code="conflict")

    db.session.remove()
    login_as(client, foreign_user_id)
    foreign = client.get(f"{BASE}/{programme_id}")
    assert foreign.status_code == 404
    foreign_body = foreign.get_json()
    _assert_envelope(foreign_body, error_code="not_found")
    assert str(programme_id) not in foreign_body["errors"][0]["message"]


def test_transformation_api_does_not_accept_a_forged_role_header(
    client, committed_session, login_as, monkeypatch
):
    from app.security.audit import audit_logger

    audited = []
    monkeypatch.setattr(
        audit_logger,
        "log_security_event",
        lambda event_type, severity, details: audited.append(
            (event_type, severity, details)
        ),
    )
    session, cleanup_org_ids = committed_session
    org = _make_org(session, cleanup_org_ids, "forged-role")
    user = _make_user(session, org, role="procurement")
    session.commit()
    login_as(client, user)

    response = client.post(
        BASE,
        json=_intake(user.id),
        headers={
            "Idempotency-Key": f"forged-role-{uuid.uuid4().hex}",
            "X-Enterprise-Role": "platform_admin",
            "X-Roles": "platform_admin,chief_architect",
        },
    )

    assert response.status_code == 403
    _assert_envelope(response.get_json(), error_code="not_authorised")
    assert len(audited) == 1
    details = audited[0][2]
    assert details == {
        "actor_id": user.id,
        "endpoint": "transformation_api.create_programme",
        "reason_code": "programme_create_not_authorised",
        "request_id": response.get_json()["request_id"],
        "tenant_id": org.id,
    }


def test_transformation_api_resolves_current_workstream_assignment_server_side(
    client, committed_session, login_as, monkeypatch
):
    from app import db

    monkeypatch.setenv("TRANSFORMATION_COMMAND_CAPABILITY_SECRET", "74" * 32)
    session, cleanup_org_ids = committed_session
    _ensure_guards(session)
    org = _make_org(session, cleanup_org_ids, "assignment")
    owner = _make_user(session, org)
    assigned_user = _make_user(session, org, role="procurement")
    session.commit()
    owner_id = owner.id
    assigned_user_id = assigned_user.id
    login_as(client, owner_id)
    created = client.post(
        BASE,
        json=_intake(owner_id),
        headers={"Idempotency-Key": f"assignment-programme-{uuid.uuid4().hex}"},
    ).get_json()["data"]

    db.session.remove()
    login_as(client, owner_id)
    assigned = client.post(
        f"{BASE}/{created['programme_id']}/role-assignments",
        json={
            "workstream_id": created["workstream_id"],
            "user_id": assigned_user_id,
            "role": "workstream_lead",
            "effective_from": "2026-08-29",
            "effective_to": None,
        },
        headers={
            "Idempotency-Key": f"assignment-{uuid.uuid4().hex}",
            "If-Match": "1",
        },
    )
    assert assigned.status_code == 201, assigned.get_json()
    assert assigned.get_json()["data"]["revision"] == 2

    db.session.remove()
    login_as(client, assigned_user_id)
    updated = client.patch(
        f"{BASE}/{created['programme_id']}/workstreams/{created['workstream_id']}/objective",
        json={"objective": "Owned by the assigned workstream lead", "scope_expression": {}},
        headers={
            "Idempotency-Key": f"assigned-objective-{uuid.uuid4().hex}",
            "If-Match": "2",
            "X-Roles": "",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["data"]["revision"] == 3


def test_transformation_api_maps_blocked_and_retryable_errors_exactly(
    client, committed_session, login_as, monkeypatch
):
    from app import db
    from app.modules.transformation_room.domain import (
        BlockedByEvidence,
        GateBlocker,
        KnownPreCommitTransient,
    )
    from app.modules.transformation_room.gate_service import TransformationGateService
    from app.modules.transformation_room.programme_service import (
        TransformationProgrammeService,
    )

    session, cleanup_org_ids = committed_session
    _ensure_guards(session)
    org = _make_org(session, cleanup_org_ids, "error-map")
    user = _make_user(session, org)
    session.commit()
    user_id = user.id
    login_as(client, user_id)
    created = client.post(
        BASE,
        json=_intake(user_id),
        headers={"Idempotency-Key": f"error-map-programme-{uuid.uuid4().hex}"},
    ).get_json()["data"]

    db.session.remove()
    login_as(client, user_id)
    monkeypatch.setattr(
        TransformationProgrammeService,
        "list_programmes",
        classmethod(
            lambda cls, **_kwargs: (_ for _ in ()).throw(
                KnownPreCommitTransient("database_busy")
            )
        ),
    )
    retryable = client.get(BASE)
    assert retryable.status_code == 503
    _assert_envelope(retryable.get_json(), error_code="retryable_failure")

    blocker = GateBlocker(
        "missing_evidence",
        "Evidence is required.",
        "workstream",
        1,
        None,
    )
    monkeypatch.setattr(
        TransformationGateService,
        "transition",
        classmethod(
            lambda cls, **_kwargs: (_ for _ in ()).throw(
                BlockedByEvidence("gate_requirements_not_met", blockers=(blocker,))
            )
        ),
    )
    db.session.remove()
    login_as(client, user_id)
    blocked = client.post(
        f"{BASE}/{created['programme_id']}/workstreams/{created['workstream_id']}/transitions",
        json={"target_stage": "discover"},
        headers={
            "Idempotency-Key": f"blocked-map-{uuid.uuid4().hex}",
            "If-Match": "1",
        },
    )
    assert blocked.status_code == 422
    blocked_body = blocked.get_json()
    _assert_envelope(blocked_body, error_code="blocked_by_evidence")
    assert blocked_body["errors"][0]["details"]["blockers"][0]["code"] == "missing_evidence"


def test_transformation_api_maps_persisted_delivery_failure_to_provider_failed(
    client, committed_session, login_as, monkeypatch
):
    from app import db
    from app.modules.transformation_room.domain import CommandResult
    from app.modules.transformation_room.execution_service import (
        TransformationExecutionService,
    )

    session, cleanup_org_ids = committed_session
    _ensure_guards(session)
    org = _make_org(session, cleanup_org_ids, "provider-map")
    user = _make_user(session, org)
    session.commit()
    user_id = user.id
    login_as(client, user_id)
    created = client.post(
        BASE,
        json=_intake(user_id),
        headers={"Idempotency-Key": f"provider-map-programme-{uuid.uuid4().hex}"},
    ).get_json()["data"]
    failed_result = CommandResult(
        created=True,
        idempotent=False,
        operation_result_id=991,
        object_ids={"work_package_id": 771, "delivery_export_attempt_id": 881},
        response={
            "work_package_id": 771,
            "delivery_export_attempt_id": 881,
            "exported": False,
            "status": "failed",
            "external_key": None,
        },
    )
    monkeypatch.setattr(
        TransformationExecutionService,
        "export_work_package",
        classmethod(lambda cls, **_kwargs: failed_result),
    )

    db.session.remove()
    login_as(client, user_id)
    response = client.post(
        f"{BASE}/{created['programme_id']}/workstreams/{created['workstream_id']}"
        "/work-packages/771/delivery-exports",
        json={"provider_key": "jira", "request": {"project": "ARCH"}},
        headers={"Idempotency-Key": f"provider-map-{uuid.uuid4().hex}"},
    )

    assert response.status_code == 502
    body = response.get_json()
    _assert_envelope(body, error_code="provider_failed")
    assert body["meta"]["delivery_export_attempt_id"] == 881


def test_transformation_api_write_surface_remains_csrf_protected(app):
    from app._bootstrap.csrf_coverage import audit

    result = audit(app)
    transformation_writes = [
        entry
        for entry in result["protected"]
        if entry["rule"].startswith(BASE)
    ]
    expected_writes = sum(
        1 for _rule, method in ROUTE_CONTRACT if method in {"POST", "PATCH", "DELETE"}
    )
    assert len(transformation_writes) == expected_writes
    assert not [
        entry
        for entry in result["exempt_allowed"] + result["exempt_unjustified"]
        if entry["rule"].startswith(BASE)
    ]


def test_transformation_api_repeated_foreign_id_probes_use_established_limiter(
    client, committed_session, login_as, monkeypatch
):
    from app.security.audit import audit_logger

    audited = []
    monkeypatch.setattr(
        audit_logger,
        "log_security_event",
        lambda event_type, severity, details: audited.append(
            (event_type, severity, details)
        ),
    )
    session, cleanup_org_ids = committed_session
    org = _make_org(session, cleanup_org_ids, "probe-limit")
    user = _make_user(session, org)
    session.commit()
    login_as(client, user.id)
    monkeypatch.setitem(client.application.config, "RATE_LIMITING_ENABLED", True)
    monkeypatch.setitem(
        client.application.config, "TRANSFORMATION_FOREIGN_ID_PROBE_LIMIT", 1
    )

    first = client.get(f"{BASE}/2147483001")
    second = client.get(f"{BASE}/2147483002")

    assert first.status_code == 404
    assert second.status_code == 429
    body = second.get_json()
    _assert_envelope(body, error_code="retryable_failure")
    assert body["meta"]["retry_after"] >= 1
    assert [event[2]["reason_code"] for event in audited] == [
        "programme_not_found",
        "identifier_probe_rate_limited",
    ]
    assert all(
        set(event[2])
        == {"actor_id", "endpoint", "reason_code", "request_id", "tenant_id"}
        for event in audited
    )
