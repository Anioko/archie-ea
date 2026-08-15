"""Bad user input must get a 4xx with a message, never a 500.

Pins the fixes from the 13 Aug 2026 validation audit: four write-handlers did
bare ``int()``/``float()`` on request data with no try/except anywhere in the
function, so ordinary fat-fingered input (``{"influence_level": "high"}``)
crashed into the generic 500 handler instead of telling the user which field
was wrong.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; app is session-scoped).
"""

import uuid

import pytest


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


@pytest.fixture
def admin_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("validation")
    user = User(
        email=f"validation-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Val",
        last_name="Idator",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


def test_stakeholder_create_bad_int_is_400(admin_client):
    resp = admin_client.post(
        "/api/stakeholders/",
        json={"name": "X", "influence_level": "high"},
    )
    assert resp.status_code == 400
    assert "influence_level" in resp.get_json()["error"]


def test_stakeholder_create_bad_solution_id_is_400(admin_client):
    resp = admin_client.post(
        "/api/stakeholders/",
        json={"name": "X", "solution_id": "not-a-number"},
    )
    assert resp.status_code == 400


def test_stakeholder_update_bad_int_is_400(admin_client):
    created = admin_client.post("/api/stakeholders/", json={"name": "Patch Target"})
    assert created.status_code == 201
    sid = created.get_json()["id"]

    resp = admin_client.patch(
        f"/api/stakeholders/{sid}", json={"influence_level": "very"}
    )
    assert resp.status_code == 400


def test_bulk_process_link_bad_threshold_is_400(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("application_api.api_bulk_process_link")
    resp = admin_client.post(
        url, json={"application_ids": [], "confidence_threshold": "abc"}
    )
    assert resp.status_code == 400

    resp = admin_client.post(
        url, json={"application_ids": [], "confidence_threshold": 7}
    )
    assert resp.status_code == 400


def test_template_search_bad_limit_is_400(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("application_mgmt.search_templates_advanced")
    resp = admin_client.post(url, json={"query": "x", "limit": "abc"})
    assert resp.status_code == 400


def test_billing_upgrade_bad_seats_is_not_500(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("billing.billing_upgrade")
    resp = admin_client.post(url, data={"plan": "pro", "seats": "many"})
    # A plain HTML form: the fix redirects back with a flash, never a 500.
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Second half of the 15 Aug 2026 sweep (handoff TASK 4a) — one test per newly
# fixed route family. `org_and_client` mirrors `admin_client` but also hands
# back the org/user so tests that need a pre-existing tenant-scoped row
# (Solution, SolutionRequirement, SolutionMetric, ...) can create it with
# `tenant_ctx` before exercising the endpoint.
# ---------------------------------------------------------------------------


@pytest.fixture
def org_and_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("validation2")
    user = User(
        email=f"validation2-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Val",
        last_name="Idator2",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return org, client, user


def test_roadmap_elements_bad_implementation_weeks_is_400(admin_client):
    resp = admin_client.post(
        "/api/architecture-assistant/roadmap-elements",
        json={"solution_option": {"implementation_weeks": "many"}},
    )
    assert resp.status_code == 400
    assert "implementation_weeks" in resp.get_json()["error"]


def test_enrich_requirement_bad_driver_id_is_400(org_and_client, tenant_ctx):
    org, client, _user = org_and_client
    from app import db
    from app.models.solution_architect_models import SolutionRequirement

    with tenant_ctx(org.id):
        req = SolutionRequirement(name="Req X", description="d")
        db.session.add(req)
        db.session.commit()
        req_id = req.id

    resp = client.patch(
        f"/api/enterprise/requirements/{req_id}/enrich",
        json={"driver_id": "not-a-number"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "driver_id" in body["error"]


def test_abacus_auto_suggest_bad_threshold_is_400(admin_client):
    resp = admin_client.post(
        "/capability-map/api/capabilities/abacus-auto-suggest",
        json={"application_ids": [1], "threshold": "high"},
    )
    assert resp.status_code == 400
    assert "threshold" in resp.get_json()["error"]


def test_infer_component_specs_bad_batch_size_is_400(org_and_client, tenant_ctx):
    org, client, _user = org_and_client
    from app import db
    from app.models.solution_models import Solution

    with tenant_ctx(org.id):
        sol = Solution(name="Journey Sol", created_by_id=_user.id)
        db.session.add(sol)
        db.session.commit()
        sol_id = sol.id

    # Solution is audit-logged (app/middleware/audit_middleware.py): its
    # after_insert hook reads current_user inside the tenant_ctx's own
    # unauthenticated test_request_context, which flask-login caches onto
    # `g`. A later Werkzeug context can reuse that same `g` bucket (see
    # CLAUDE.md's flask_login g._login_user note), so re-establish the
    # session here or the next request reads back as anonymous.
    _login(client, _user.id)

    resp = client.post(
        f"/architecture-journey/{sol_id}/infer-component-specs",
        json={"batch_size": "lots"},
    )
    assert resp.status_code == 400


def test_roadmap_builder_create_work_package_bad_start_date_is_400(admin_client):
    resp = admin_client.post(
        "/api/roadmap-builder/work-packages",
        json={"name": "WP1", "start_date": "not-a-date"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "start_date" in body["error"]


def test_runtime_health_report_bad_latency_is_400(app, db_session, tenant_ctx, make_org, monkeypatch):
    from app import db
    from app.models.solution_models import Solution
    from app.models.published_api_spec import PublishedAPISpec

    org = make_org("validation3")
    with tenant_ctx(org.id):
        sol = Solution(name="RT Sol")
        db.session.add(sol)
        db.session.flush()
        spec = PublishedAPISpec(
            solution_id=sol.id,
            spec_type="openapi",
            spec_version="1.0.0",
            spec_content={},
            status="published",
        )
        db.session.add(spec)
        db.session.commit()
        sol_id = sol.id

    monkeypatch.setitem(app.config, "RUNTIME_REPORT_TOKEN", "test-token-123")
    client = app.test_client()
    resp = client.post(
        "/solutions/api/runtime/health-report",
        json={"solution_id": sol_id, "avg_latency_ms": "slow"},
        headers={"X-Runtime-Report-Token": "test-token-123"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["received"] is False


def test_sync_capabilities_bad_ids_is_400(org_and_client, tenant_ctx):
    org, client, _user = org_and_client
    from app import db
    from app.models.solution_models import Solution

    with tenant_ctx(org.id):
        sol = Solution(name="Link Sol")
        db.session.add(sol)
        db.session.commit()
        sol_id = sol.id

    # Re-establish the session — see the comment in
    # test_infer_component_specs_bad_batch_size_is_400 (Solution's audit
    # hook reads current_user inside tenant_ctx's own request context).
    _login(client, _user.id)

    resp = client.post(
        f"/solutions/{sol_id}/sync-capabilities",
        json={"ids": ["abc"]},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "ids" in body["error"]


def test_update_solution_metric_bad_measurement_date_is_400(org_and_client, tenant_ctx):
    org, client, _user = org_and_client
    from app import db
    from app.models.solution_models import Solution
    from app.models.solution_lifecycle_models import SolutionMetric

    with tenant_ctx(org.id):
        sol = Solution(name="Metric Sol")
        db.session.add(sol)
        db.session.flush()
        metric = SolutionMetric(solution_id=sol.id, name="Metric X")
        db.session.add(metric)
        db.session.commit()
        sol_id = sol.id
        metric_id = metric.id

    # Re-establish the session — see the comment in
    # test_infer_component_specs_bad_batch_size_is_400 (Solution's audit
    # hook reads current_user inside tenant_ctx's own request context).
    _login(client, _user.id)

    resp = client.put(
        f"/solutions/{sol_id}/metrics/{metric_id}",
        json={"measurement_date": "not-a-date"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "measurement_date" in body["error"]


def test_sap_import_bad_solution_id_is_400(admin_client):
    resp = admin_client.post(
        "/api/sap/import",
        json={"solution_id": "not-a-number", "mock": True},
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
    assert "solution_id" in resp.get_json()["error"]


# NOTE: codegen_routes.py's generate_code/generate_stream quality-gate fixes
# (min_quality_score / min_chain_completeness / max_lint_violations) are not
# covered by an HTTP-level test here. Reaching that code path means driving
# the full generation pipeline (UML synthesis, optional LLM enrichment,
# runtime smoke checks) to completion first, which is disproportionate setup
# for pinning a try/except around a float()/int() call. The fix follows the
# exact pattern proven by every other test in this file and was verified by
# the compile gate and a manual read of the diff.
