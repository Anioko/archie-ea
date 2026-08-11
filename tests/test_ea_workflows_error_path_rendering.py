"""Render-contract regression tests for two ea_workflows error paths.

WHAT WAS BROKEN
----------------
- ``app/templates/ea_workflows/phase_viewpoint.html``: the error branch of
  ``ea_phase_viewpoint`` (app/main/routes_ea_workflows.py) passes
  ``element_count=None`` / ``relationship_count=None``. The template
  interpolated those raw into an Alpine ``<script>`` block
  (``elementCount: {{ element_count }},``), which rendered the bareword
  ``elementCount: None,`` - invalid JavaScript, throwing a ReferenceError and
  killing the whole Alpine component. The same values were also echoed
  unguarded into visible text (``{{ element_count }}``), showing the literal
  string "None" to the user.
- ``app/templates/ea_workflows/dashboard.html``: the error branch of
  ``ea_workflows_dashboard`` passes ``status_counts=None``, but
  ``{{ status_counts.running or 0 }}`` silently rendered ``0`` (Jinja
  attribute access on None is Undefined, and ``Undefined or 0`` is ``0``) -
  a fabricated, confident-looking zero on a page that also shows the
  data-load-error banner saying the figures could not be read.

Both are fixed the same way CLAUDE.md's null-display rule prescribes:
None must render as an em dash ("-"), and JSON embedded in a <script> block
must go through ``|tojson`` rather than raw interpolation.

Follows the login/db setup pattern in tests/test_adm_phase_viewpoints.py and
tests/test_remaining_500_routes.py.
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


def _make_logged_in_client(app, db_session, make_org, label):
    from app.models.user import User

    org = make_org(label)
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="EA",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db_session.add(user)
    # commit (not just flush): the routes under test hit their except branch
    # and call db.session.rollback(), which - under the db_session fixture's
    # SAVEPOINT-per-commit binding - would otherwise roll back an uncommitted
    # flush along with it and orphan the logged-in user mid-request.
    db_session.commit()

    client = app.test_client()
    _login(client, user.id)
    return client


def test_phase_viewpoint_error_path_renders_valid_json_and_no_literal_none(
    app, db_session, make_org, monkeypatch
):
    from app.services.phase_viewpoint_binding_service import PhaseViewpointBindingService

    def _boom(self, *a, **kw):
        raise RuntimeError("forced failure for the error-path test")

    monkeypatch.setattr(PhaseViewpointBindingService, "get_binding", _boom)

    client = _make_logged_in_client(app, db_session, make_org, "phase-viewpoint-err")
    resp = client.get("/ea-workflows/phase/A/viewpoint")
    assert resp.status_code < 500, (
        f"expected the error branch to render, got {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:2000]}"
    )
    body = resp.get_data(as_text=True)

    # The Alpine script block must embed valid JS literals, not the Python
    # bareword "None" (which is not defined in JS and throws).
    assert "elementCount: None" not in body
    assert "relationshipCount: None" not in body
    assert "elementCount: null" in body
    assert "relationshipCount: null" in body

    # The visible summary text must not show the literal word "None".
    assert ">None<" not in body


def test_dashboard_error_path_renders_dash_not_fabricated_zero(
    app, db_session, make_org, monkeypatch
):
    from app.services.ea_workflow_engine import EAWorkflowEngine

    def _boom(self, *a, **kw):
        raise RuntimeError("forced failure for the error-path test")

    monkeypatch.setattr(EAWorkflowEngine, "list_workflow_definitions", _boom)

    client = _make_logged_in_client(app, db_session, make_org, "dashboard-err")
    resp = client.get("/ea-workflows")
    assert resp.status_code < 500, (
        f"expected the error branch to render, got {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:2000]}"
    )
    body = resp.get_data(as_text=True)

    # The data-load-error banner must be present (load_error was set).
    assert "could not be read" in body or "Error:" in body

    # None must render as an em dash for Running / Waiting Approval / Completed,
    # never a fabricated "0" that looks like a measured count.
    assert "&mdash;" in body or "—" in body
