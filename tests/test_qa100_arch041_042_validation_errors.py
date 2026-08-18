"""ARCH-041/ARCH-042: the New Application modal must render the API's actual
field-level validation errors, not the literal string "Bad Request", and must
mark an invalid field aria-invalid=true with a visible text error next to it.

The root cause was entirely front-end (app/static/js/core/03-fetch.js and
app/static/js/applications/list.js): the JSON API already returns a correct,
specific {"errors": {field: [msg, ...]}} envelope — this test pins that
contract server-side, since crud_routes.py (which emits it) is out of scope
for this wave. The client-side fix (aria-invalid, per-field rendering, no
raw HTTP status phrase) is JS/Jinja and is not exercisable from pytest; it is
covered by reading app/static/js/applications/list.js::applicationCreateForm
and app/templates/applications/list_simple.html directly (see the report).
"""

import uuid

import pytest


@pytest.fixture
def org_client(app, db_session, make_org, login_as):
    from app.models.user import Permission, Role, User

    org = make_org("arch041")
    user = User(
        email=f"arch041-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Arch",
        last_name="Zero41",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()
    role = Role.query.filter(Role.name.in_(("Administrator", "Admin", "admin"))).first()
    if role is None:
        role = Role(name="Administrator", permissions=Permission.ADMINISTER)
        db_session.add(role)
        db_session.flush()
    elif role.permissions is None or (role.permissions & Permission.ADMINISTER) != Permission.ADMINISTER:
        role.permissions = Permission.ADMINISTER
    user.role = role
    db_session.flush()
    client = app.test_client()
    login_as(client, user)
    return org, client, user


def test_invalid_name_returns_structured_field_errors_not_bad_request(org_client):
    """FAIL-FIRST intent: before reading the actual response, the naive
    expectation (matching what the UI showed) is a bare "Bad Request" string.
    This asserts the real envelope the front-end fix now consumes."""
    _, client, _ = org_client
    # Name over the 255-char limit — the exact case from the finding.
    resp = client.post(
        "/applications/create",
        json={"name": "x" * 300},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "errors" in data, "the API must return a field-level errors map"
    assert "name" in data["errors"], "the 'name' field's own error must be present"
    # The literal HTTP status phrase must never be the payload of a field error.
    assert "Bad Request" not in str(data["errors"]["name"])
    joined = " ".join(str(m) for m in data["errors"]["name"])
    assert "255" in joined or "length" in joined.lower(), (
        "the specific validation reason must be present, not a generic phrase"
    )


def test_empty_name_returns_structured_field_error(org_client):
    """ARCH-042's server-side counterpart: an empty required name must also
    come back as a named field error the client can key off of to set
    aria-invalid, not just a bare failure."""
    _, client, _ = org_client
    resp = client.post("/applications/create", json={"name": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "name" in data.get("errors", {})
