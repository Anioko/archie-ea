"""CMP-03: composer audit-log writes must not fail on the diagram reference.

The audit endpoint stores the composer diagram id (saved_diagrams.id) in
viewpoint_id. That column used to carry a FOREIGN KEY to archimate_viewpoints,
so a perfectly valid saved_diagrams id violated the constraint and every
composer action (notably removing an element) raised "Failed to log audit
event". These tests assert the write succeeds for a saved-diagram id and that a
non-integer entity_id is coerced rather than 500-ing.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(db_session, org_id):
    from app.models.user import User

    from werkzeug.security import generate_password_hash

    u = User(email=f"cmp03-{uuid.uuid4().hex[:8]}@example.com",
             first_name="CMP", last_name="03", confirmed=True,
             organization_id=org_id,
             password_hash=generate_password_hash("x"))
    db_session.add(u)
    db_session.flush()
    return u


def test_viewpoint_id_has_no_archimate_viewpoints_fk():
    """The wrong FK must be gone from the model (loose reference)."""
    from app.models.archimate_viewpoint import ArchimateAuditLog

    col = ArchimateAuditLog.__table__.c.viewpoint_id
    targets = {fk.column.table.name for fk in col.foreign_keys}
    assert "archimate_viewpoints" not in targets, \
        "viewpoint_id must not FK archimate_viewpoints — it holds a saved_diagrams id"


def test_audit_write_succeeds_for_saved_diagram_id(db_session, make_org, tenant_ctx):
    """An audit row referencing a composer diagram id must persist."""
    from app.models.archimate_core import SavedDiagram
    from app.models.archimate_viewpoint import ArchimateAuditLog

    org = make_org("a")
    user = _make_user(db_session, org.id)
    with tenant_ctx(org.id):
        dia = SavedDiagram(name=f"D {uuid.uuid4().hex[:6]}", organization_id=org.id)
        db_session.add(dia)
        db_session.flush()

        entry = ArchimateAuditLog(
            viewpoint_id=dia.id, user_id=user.id,
            action="element_removed", entity_type="element",
            entity_id=123, entity_name="Test El",
        )
        db_session.add(entry)
        db_session.flush()  # would raise IntegrityError under the old FK

    assert entry.id is not None
    assert entry.viewpoint_id == dia.id


def test_endpoint_coerces_noninteger_entity_id(db_session, make_org, tenant_ctx, client, login_as):
    """POSTing a JointJS string cell id must not 500; entity_id stores NULL."""
    from app.models.archimate_viewpoint import ArchimateAuditLog

    org = make_org("a")
    user = _make_user(db_session, org.id)
    login_as(client, user)
    with tenant_ctx(org.id):
        resp = client.post("/archimate/api/audit-log", json={
            "action": "element_removed",
            "entity_type": "element",
            "entity_id": "cell-eu2WgWPngIX_",   # non-integer JointJS id
            "entity_name": "Imported El",
            "viewpoint_id": None,
        })
    assert resp.status_code in (201, 202), resp.get_data(as_text=True)
    if resp.status_code == 201:
        row = ArchimateAuditLog.query.get(resp.get_json()["id"])
        assert row.entity_id is None
