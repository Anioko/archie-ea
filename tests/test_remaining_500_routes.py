"""Regression tests for the last five 500-ing GET routes from the design-review sweep.

WHAT WAS BROKEN
----------------
- ``/api/ea/workflow-adm-lifecycle``: ``ADMPhaseGateService._count_phase_outputs``
  / ``_has_type_in_phase`` filtered ``ea_workflow_instances.architecture_id``, a
  column that has never existed on that table — the architecture an instance
  runs against is only ever recorded in its JSON ``context`` field (see
  ``EAWorkflowEngine.start_workflow``). Every call raised
  ``psycopg2.errors.UndefinedColumn``. A sibling bug in the same route
  (``routes_ea_workflows.py``) joined on ``EAWorkflowInstance.definition_id``,
  which also does not exist (the real column is ``workflow_definition_id``);
  that one was swallowed by a local try/except and only zeroed out instance
  counts, but is fixed alongside the crash for the same reason.
- ``/api/v1/capabilities/manufacturing``: queried ``ManufacturingCapability``
  but read ``name``/``description``/``domain``/``level``/``business_owner``/
  ``status`` off it — those fields live on the ``UnifiedCapability`` row it
  specializes (``cap.unified_capability``), not on ``ManufacturingCapability``
  itself, which only carries manufacturing KPIs (OEE, FPY, etc.). Every row hit
  an ``AttributeError``.
- ``/integration/api/instances``: read ``EAWorkflowInstance.workflow_code`` and
  ``.current_step`` directly; neither is a column on that model.
  ``workflow_code`` lives on the related ``EAWorkflowDefinition``
  (``instance.definition.workflow_code``); the step field is
  ``current_step_id``.
- ``/strategic/api/investment-analysis`` and ``/strategic/investment-matrix``
  (same underlying service): ``InvestmentPrioritizationService._calculate_risk_score``
  compared ``m.technical_debt_score > 70`` without a None guard;
  ``technical_debt_score`` is nullable and unset on real data, raising
  ``TypeError: '>' not supported between instances of 'NoneType' and 'int'``.

Follows the pattern in ``tests/test_adm_phase_viewpoints.py`` (Task 2 of this
wave): shared fixtures from ``tests/conftest.py`` so nothing survives the test.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    """Standard Flask-Login test-client pattern; see
    tests/test_ba_tenant_and_authz.py::_login for why the g-cache clear below
    is required in this test harness (pytest-flask reuses one request context
    across client calls, and Flask-Login caches the resolved user on it)."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_logged_in_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("remaining-500")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"remaining-500-{suffix}@example.com",
        first_name="Sweep",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


ENDPOINTS = [
    "/api/ea/workflow-adm-lifecycle",
    "/api/v1/capabilities/manufacturing",
    "/integration/api/instances",
    "/strategic/api/investment-analysis",
    "/strategic/investment-matrix",
]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_route_does_not_500(app, db_session, make_org, path):
    client = _make_logged_in_client(app, db_session, make_org)
    resp = client.get(path)
    assert resp.status_code < 500, (
        f"{path} returned {resp.status_code}: {resp.get_data(as_text=True)[:2000]}"
    )
