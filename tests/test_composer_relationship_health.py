"""CMP-13: the staleness badge must reflect THIS diagram's relationships.

The relationship-health endpoint used every repository relationship between the
canvas elements, so a diagram with zero drawn relationships still raised "Stale
Relationships Detected" for links that live only on other diagrams. The fix
scopes staleness to the diagram's own SavedDiagramRelationship rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def client(app):
    return app.test_client()


def _user(db_session, org_id):
    from werkzeug.security import generate_password_hash

    from app.models.user import User

    u = User(email=f"cmp13-{uuid.uuid4().hex[:8]}@example.com", first_name="C",
             last_name="13", confirmed=True, organization_id=org_id,
             password_hash=generate_password_hash("x"))
    db_session.add(u)
    db_session.flush()
    return u


def test_zero_drawn_relationships_reports_no_staleness(
        db_session, make_org, tenant_ctx, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import (
        ArchiMateElement, ArchiMateRelationship, SavedDiagram, SavedDiagramElement,
    )
    from app.models.models import ExternalSystem

    org = make_org("a")
    user = _user(db_session, org.id)

    with tenant_ctx(org.id):
        sync_at = datetime.utcnow()
        db_session.add(ExternalSystem(system_type="abacus", last_sync_at=sync_at,
                                      system_name=f"Abacus {uuid.uuid4().hex[:6]}"))
        # A stale app component (synced before the latest Abacus run).
        comp = ApplicationComponent(name="Stale App", abacus_source=True,
                                    last_sync_from_abacus=sync_at - timedelta(days=2),
                                    organization_id=org.id)
        db_session.add(comp)
        db_session.flush()

        e1 = ArchiMateElement(name="A", type="ApplicationComponent", layer="application",
                              application_component_id=comp.id, organization_id=org.id)
        e2 = ArchiMateElement(name="B", type="ApplicationComponent", layer="application",
                              application_component_id=comp.id, organization_id=org.id)
        db_session.add_all([e1, e2])
        db_session.flush()

        # A repository relationship exists between them...
        rel = ArchiMateRelationship(type="serving", source_id=e1.id, target_id=e2.id)
        db_session.add(rel)

        dia = SavedDiagram(name="D", organization_id=org.id)
        db_session.add(dia)
        db_session.flush()
        # ...but the diagram draws BOTH elements and ZERO relationships.
        db_session.add_all([
            SavedDiagramElement(diagram_id=dia.id, element_id=e1.id),
            SavedDiagramElement(diagram_id=dia.id, element_id=e2.id),
        ])
        db_session.flush()
        dia_id = dia.id

    login_as(client, user)
    with tenant_ctx(org.id):
        resp = client.get(f"/archimate/api/saved-viewpoints/{dia_id}/relationship-health")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["stale_relationships"] == [], \
        "a diagram with no drawn relationships must report no stale relationships"
