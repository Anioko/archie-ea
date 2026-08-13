"""Regression tests for the five routes the design-review sweep found 500ing.

Design-review P0 wave, Task 5. Root causes found and fixed:

- /api/ea/workflow-adm-lifecycle: ADMPhaseGateService's raw SQL filtered on
  ea_workflow_instances.architecture_id, a column that does not exist
  (UndefinedColumn on every call). The architecture linkage lives on the
  produced elements — archimate_elements.architecture_id. The route's own
  instance-count query also joined on a nonexistent ``definition_id``
  attribute (real name: workflow_definition_id), silently reporting 0 forever.

- /integration/api/instances: read i.workflow_code (lives on the definition)
  and i.current_step (real name: current_step_id) — AttributeError on the
  first real row; an empty table masked it.

- /api/v1/capabilities/manufacturing: read cap.name / cap.domain.name /
  cap.level / cap.status on ManufacturingCapability, which has none of them
  (they live on the linked UnifiedCapability; its own domain is the
  manufacturing_domain string) — AttributeError on the first real row.

- /strategic/api/investment-analysis and /strategic/investment-matrix share
  InvestmentPrioritizationService, whose risk scorer compared
  technical_debt_score > 70 — TypeError when the column is NULL
  ("not assessed"), which any real mapping row can be.

Uses the shared fixtures in tests/conftest.py (db_session rolls back).
"""

from __future__ import annotations

import uuid

import pytest

ROUTES = [
    "/api/ea/workflow-adm-lifecycle",
    "/api/v1/capabilities/manufacturing",
    "/integration/api/instances",
    "/strategic/api/investment-analysis",
    "/strategic/investment-matrix",
]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_org(db_session, make_org, client):
    """A confirmed user in a fresh org, logged into the test client.

    Clears the flask-login/tenant caches on the shared app context — see
    tests/test_ba_tenant_and_authz.py::_login for why the cookie alone is
    not enough under these fixtures.
    """
    from app.models.user import User

    org = make_org("routes-500")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"routes500-{suffix}@example.com",
        first_name="Routes",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context (the
    tenant flush listener does, on every seed) re-caches an anonymous user
    in `g`; call this right before each test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


def _seed_regression_rows(db_session, org):
    """Rows shaped like the ones that made each route fall over in the
    running app — every one of these 500s was masked by an empty table."""
    from app.models.manufacturing_capability import ManufacturingCapability
    from app.models.unified_application_capability_mapping import (
        UnifiedApplicationCapabilityMapping,
    )
    from app.models.application_portfolio import ApplicationComponent
    from app.models.unified_capability import UnifiedCapability
    from app.models.workflow_models import EAWorkflowDefinition, EAWorkflowInstance

    suffix = uuid.uuid4().hex[:8]

    definition = EAWorkflowDefinition(
        workflow_code=f"TEST_WF_{suffix}",
        workflow_name="Route regression workflow",
        workflow_category="architecture",
        steps=[],
    )
    db_session.add(definition)
    db_session.flush()
    instance = EAWorkflowInstance(
        instance_code=f"TEST_WFI_{suffix}",
        workflow_definition_id=definition.id,
        status="running",
    )

    unified = UnifiedCapability(name=f"Unified Cap {suffix}", level=1)
    db_session.add_all([instance, unified])
    db_session.flush()

    manufacturing = ManufacturingCapability(
        unified_capability_id=unified.id,
        manufacturing_domain="production",
    )
    application = ApplicationComponent(
        name=f"Route App {suffix}",
        organization_id=org.id,
        lifecycle_status="active",
    )
    db_session.add_all([manufacturing, application])
    db_session.flush()

    # technical_debt_score deliberately NULL — "not assessed", the exact
    # shape that crashed the investment risk scorer.
    mapping = UnifiedApplicationCapabilityMapping(
        unified_capability_id=unified.id,
        application_component_id=application.id,
    )
    db_session.add(mapping)
    db_session.flush()


@pytest.mark.parametrize("route", ROUTES)
def test_route_no_server_error_with_real_rows(
    client, logged_in_org, db_session, route
):
    _seed_regression_rows(db_session, logged_in_org)
    _clear_auth_caches()
    response = client.get(route, follow_redirects=True)
    assert response.status_code != 401, f"{route}: login did not take"
    assert response.status_code < 500, (
        f"{route} returned {response.status_code}: "
        f"{response.get_data(as_text=True)[:500]}"
    )


def test_adm_lifecycle_returns_phases(client, logged_in_org):
    _clear_auth_caches()
    response = client.get("/api/ea/workflow-adm-lifecycle")
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    data = response.get_json()
    assert "error" not in data
    assert len(data["phases"]) == 8


def test_integration_instances_serialises_real_rows(
    client, logged_in_org, db_session
):
    _seed_regression_rows(db_session, logged_in_org)
    _clear_auth_caches()
    response = client.get("/integration/api/instances")
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    data = response.get_json()
    assert data["success"] is True
    codes = {i["workflow_code"] for i in data["instances"]}
    assert any(c and c.startswith("TEST_WF_") for c in codes)


def test_risk_score_tolerates_unassessed_debt(db_session, make_org):
    """NULL technical_debt_score is 'not assessed', and must not raise."""
    from app.modules.solutions_strategic.v2.services.investment_prioritization_service import (
        InvestmentPrioritizationService,
    )

    class FakeMapping:
        technical_debt_score = None

    class FakeCapability:
        strategic_importance = "critical"
        compliance_requirements = None

    score = InvestmentPrioritizationService()._calculate_risk_score(
        FakeCapability(), [FakeMapping()]
    )
    assert isinstance(score, int)
