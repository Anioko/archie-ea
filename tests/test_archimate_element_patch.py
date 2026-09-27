"""PATCH /archimate/api/elements/<id> must actually persist a rename.

Regression for a defect found by adversarial browser QA (10 Sep 2026): every
rename in the ArchiMate Composer 500'd because the audit-trail write passed
``details=...`` to ``ARBAuditLog``, a field that model does not define (it has
``old_value``/``new_value``/``changed_fields`` instead). The element's name and
description were already updated in the session before the audit insert threw,
so the whole request rolled back and the architect's edit silently vanished —
the single most common Composer action failing on every use.

Uses the shared fixtures (tests/conftest.py) per CLAUDE.md's convention.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id):
    from app.models.user import Role, User

    Role.insert_roles()
    architect_role = Role.query.filter_by(name="Architect").one()
    user = User(
        email=f"patch-test-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test", last_name="Architect",
        organization_id=org_id, confirmed=True,
    )
    user.role = architect_role
    user.password = "TestPass!2026"
    db_session.add(user)
    db_session.flush()
    return user


def test_patch_element_rename_persists(client, db_session, make_org, login_as):
    from app.models.archimate_core import ArchiMateElement

    org = make_org("patch-element")
    user = _make_user(db_session, org.id)

    element = ArchiMateElement(
        name="Original Name", type="ApplicationComponent", layer="application",
        organization_id=org.id,
    )
    db_session.add(element)
    db_session.flush()
    element_id = element.id

    login_as(client, user)

    resp = client.patch(f"/archimate/api/elements/{element_id}", json={"name": "Renamed Element"})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["name"] == "Renamed Element"

    db_session.expire_all()
    reloaded = db_session.get(ArchiMateElement, element_id)
    assert reloaded.name == "Renamed Element", "rename must survive a reload, not just the response body"


def test_patch_element_writes_audit_trail_with_old_and_new_value(client, db_session, make_org, login_as):
    from app.models.archimate_core import ArchiMateElement
    from app.models.architecture_review_board import ARBAuditLog

    org = make_org("patch-element-audit")
    user = _make_user(db_session, org.id)

    element = ArchiMateElement(
        name="Before Rename", type="ApplicationComponent", layer="application",
        organization_id=org.id,
    )
    db_session.add(element)
    db_session.flush()
    element_id = element.id

    login_as(client, user)
    resp = client.patch(f"/archimate/api/elements/{element_id}", json={"name": "After Rename"})
    assert resp.status_code == 200, resp.get_data(as_text=True)

    audit = (
        ARBAuditLog.query
        .filter_by(entity_type="ArchiMateElement", entity_id=element_id, action="element_updated")
        .order_by(ARBAuditLog.id.desc())
        .first()
    )
    assert audit is not None, "rename must leave an audit trail"
    assert audit.old_value["name"] == "Before Rename"
    assert audit.new_value["name"] == "After Rename"
