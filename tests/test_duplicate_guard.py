"""Named entities must not be silently duplicated on create (ARCH-030).

The August 2026 QA sweep POSTed the same application name three times and got
``201 Created`` every time (ids 71, 72, 73). At the same moment the repository
held 25 duplicate-name groups covering 67 of its 145 ArchiMate elements, and
four solutions three of which shared a byte-identical name. There was no
duplicate check anywhere on the write path, and the AI agent creates entities
autonomously, so the duplication accrued at machine speed.

These tests pin the guard: second create is a 409 naming the first, and the
explicit ``allow_duplicate`` opt-in still works.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; app is session-scoped).
"""

import uuid

import pytest

from app.utils.duplicate_guard import normalize_name


def _clear_login_cache():
    """Drop flask_login's per-``g`` user cache.

    The shared ``db_session`` fixture holds one app context open for the whole
    test, so ``g`` is reused across test-client requests and flask_login's
    ``g._login_user`` survives from one to the next. Without this, a second
    client's request executes as the *first* client's user — which is how four
    cross-org tests once reported a tenant leak that does not exist (see the
    note in tests/test_ba_tenant_and_authz.py::_login). Call it immediately
    before each request that must run as a different user.
    """
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    _clear_login_cache()


@pytest.fixture
def admin_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("dupguard")
    user = User(
        email=f"dupguard-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Dup",
        last_name="Guard",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


@pytest.fixture
def unique_name():
    return f"QA-DUP Probe {uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# The normaliser                                                              #
# --------------------------------------------------------------------------- #


def test_normalize_name_is_case_and_whitespace_insensitive():
    assert normalize_name("  HxGN   EAM ") == normalize_name("hxgn eam")
    assert normalize_name(None) == ""
    assert normalize_name("   ") == ""


def test_normalize_name_keeps_genuinely_different_names_apart():
    assert normalize_name("Order Processing") != normalize_name("Order Processing v2")


# --------------------------------------------------------------------------- #
# POST /applications/create — the path the QA engineer reproduced             #
# --------------------------------------------------------------------------- #


def test_second_application_with_same_name_is_409(admin_client, unique_name):
    first = admin_client.post("/applications/create", json={"name": unique_name})
    assert first.status_code == 201, first.get_data(as_text=True)
    first_id = first.get_json()["id"]

    second = admin_client.post("/applications/create", json={"name": unique_name})
    assert second.status_code == 409, second.get_data(as_text=True)

    body = second.get_json()
    assert body["success"] is False
    assert unique_name in body["error"]
    # Actionable: the caller is told exactly what it collided with.
    assert body["duplicate_of"]["id"] == first_id
    assert body["duplicate_of"]["name"] == unique_name


def test_application_duplicate_check_ignores_case_and_whitespace(
    admin_client, unique_name
):
    assert (
        admin_client.post("/applications/create", json={"name": unique_name}).status_code
        == 201
    )

    resp = admin_client.post(
        "/applications/create", json={"name": f"  {unique_name.upper()}  "}
    )
    assert resp.status_code == 409


def test_allow_duplicate_flag_permits_the_duplicate(admin_client, unique_name):
    assert (
        admin_client.post("/applications/create", json={"name": unique_name}).status_code
        == 201
    )

    body_flag = admin_client.post(
        "/applications/create", json={"name": unique_name, "allow_duplicate": True}
    )
    assert body_flag.status_code == 201, body_flag.get_data(as_text=True)

    query_flag = admin_client.post(
        "/applications/create?allow_duplicate=true", json={"name": unique_name}
    )
    assert query_flag.status_code == 201

    header_flag = admin_client.post(
        "/applications/create",
        json={"name": unique_name},
        headers={"X-Allow-Duplicate": "true"},
    )
    assert header_flag.status_code == 201


def test_different_names_still_create(admin_client, unique_name):
    assert (
        admin_client.post("/applications/create", json={"name": unique_name}).status_code
        == 201
    )
    assert (
        admin_client.post(
            "/applications/create", json={"name": f"{unique_name} Reporting"}
        ).status_code
        == 201
    )


# --------------------------------------------------------------------------- #
# Tenancy — the guard must not leak names between organisations               #
# --------------------------------------------------------------------------- #


def test_duplicate_check_is_scoped_to_the_organisation(
    app, db_session, make_org, unique_name
):
    """Two organisations may each hold an application of the same name.

    ApplicationComponent inherits TenantMixin, so the guard relies on the
    injected organisation predicate rather than writing its own. If that
    injection ever stopped applying, org B would get a spurious 409 here.
    """
    from app.models.user import User

    clients = []
    for label in ("dupa", "dupb"):
        org = make_org(label)
        user = User(
            email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
            first_name=label,
            last_name="Tester",
            organization_id=org.id,
            confirmed=True,
            enterprise_role="platform_admin",
        )
        db_session.add(user)
        db_session.flush()
        client = app.test_client()
        _login(client, user.id)
        clients.append(client)

    _clear_login_cache()
    assert (
        clients[0].post("/applications/create", json={"name": unique_name}).status_code
        == 201
    )
    # Different tenant, same name — legitimate, must not collide.
    _clear_login_cache()
    second = clients[1].post("/applications/create", json={"name": unique_name})
    assert second.status_code == 201, second.get_data(as_text=True)


# --------------------------------------------------------------------------- #
# The AI agent's tools — duplication at machine speed                         #
# --------------------------------------------------------------------------- #


def test_agent_create_solution_refuses_a_duplicate(app, db_session, make_org):
    """Three of the four HxGN EAM solutions came in through a path like this."""
    from app.models.user import User
    from app.modules.ai_chat.tools.executor import ToolExecutor

    org = make_org("dupagent")
    user = User(
        email=f"dupagent-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Agent",
        last_name="Runner",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    name = f"QA-DUP Solution {uuid.uuid4().hex[:8]}"
    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        executor = ToolExecutor(user.id)

        first = executor._tool_create_solution({"name": name, "description": "x"})
        assert first["success"] is True
        first_id = first["result"]["id"]

        second = executor._tool_create_solution({"name": name, "description": "x"})
        assert second["success"] is False
        assert second["code"] == "DUPLICATE_NAME"
        assert second["duplicate_of"]["id"] == first_id
        # The agent is told how to proceed deliberately, not just refused.
        assert "allow_duplicate" in second["error"]

        forced = executor._tool_create_solution(
            {"name": name, "description": "x", "allow_duplicate": True}
        )
        assert forced["success"] is True
        assert forced["result"]["id"] != first_id
