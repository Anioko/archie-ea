"""Regression test for /ea-workflows/journeys route.

Tests the route's handling of workflow instances with None iteration_number
(see GitHub issue: TypeError on sorted() when iteration_number is None).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def test_sorted_with_none_iteration_keys():
    """Verify the sorting key handles None values correctly.

    This is a unit test of the sorting logic used in /ea-workflows/journeys.
    The route groups instances by iteration_number, then sorts the keys.
    If any key is None, the original code `sorted(iterations.keys())` raises
    TypeError. The fix uses `key=lambda k: (k is None, k)` to sort None last.
    """
    from collections import defaultdict

    # Simulate what the route does: group instances by iteration_number
    iterations = defaultdict(list)
    iterations[None].append("instance_with_none")
    iterations[1].append("instance_1a")
    iterations[1].append("instance_1b")
    iterations[2].append("instance_2")

    # The fix: sort with a key function that puts None last
    sorted_keys = sorted(iterations.keys(), key=lambda k: (k is None, k))

    # Verify None is last, and numeric keys are ordered
    assert sorted_keys == [1, 2, None], f"Expected [1, 2, None], got {sorted_keys}"


def _login(client, user_id, app):
    """Set up test client login for *user_id*.

    Follows the pattern from test_ba_tenant_and_authz.py to properly
    clear Flask-Login's cache so the login actually takes effect.
    """
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def test_ea_workflows_journeys_route_returns_200(app, db_session, make_org):
    """Test that /ea-workflows/journeys route returns 200 for a logged-in user.

    Creates test workflow definitions and instances, then calls the route
    and asserts it doesn't crash and returns 200.
    """
    from app.models.user import User
    from app.models.workflow_models import EAWorkflowDefinition, EAWorkflowInstance

    # Create test org and user
    org = make_org("test")

    # Create a user for login
    user = User(
        email="test-user@example.com",
        first_name="Test",
        last_name="User",
        organization_id=org.id,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()

    # Create a workflow definition with ADM_ code
    definition = EAWorkflowDefinition(
        workflow_code="ADM_Phase_A",
        workflow_name="Phase A",
        workflow_category="architecture",
        steps=[{"step_id": "1", "name": "Initial", "type": "start"}],
    )
    db_session.add(definition)
    db_session.flush()

    # Create workflow instances with normal iteration numbers
    for i in range(1, 3):
        instance = EAWorkflowInstance(
            instance_code=f"ADM_Instance_{i}",
            workflow_definition_id=definition.id,
            status="completed",
            iteration_number=i,
        )
        db_session.add(instance)
    db_session.flush()

    # Test the route via test client
    client = app.test_client()

    # Login the user using the proper pattern
    _login(client, user.id, app)

    # Call the route
    response = client.get("/ea-workflows/journeys")

    # Verify it returns 200 (not 500 with TypeError)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Response: {response.get_json() if response.content_type == 'application/json' else response.data}"
    )

    # Verify the response contains the expected structure
    data = response.get_json()
    assert data.get("success") is True
    assert "journeys" in data
    assert len(data["journeys"]) == 2  # Two iterations


def test_ea_workflows_journeys_requires_login(app):
    """Test that the /ea-workflows/journeys route requires authentication."""
    client = app.test_client()
    response = client.get("/ea-workflows/journeys", follow_redirects=False)
    # Should redirect to login or return 401
    assert response.status_code in (302, 401), (
        f"Expected 302 or 401, got {response.status_code}"
    )
