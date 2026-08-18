"""CMP-01: composer saved diagrams must be tenant-scoped.

Regression guard for the "36 elements, blank canvas" bug. A saved diagram and
its member elements belong to one org; a viewer in another org must see neither
the diagram in the picker list nor its element payload — and crucially the
picker's element_count must not advertise a number the loader can't deliver.

Before the fix: SavedDiagram had no organization_id, so it listed for every
org, while ArchiMateElement (TenantMixin) was org-scoped — the count came from
one scope and the elements from another, and they disagreed cross-org.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_element(db_session, org_id, name):
    from app.models.archimate_core import ArchiMateElement

    el = ArchiMateElement(
        name=name, type="ApplicationComponent", layer="application",
        organization_id=org_id,
    )
    db_session.add(el)
    db_session.flush()
    return el


def _make_diagram_with_elements(db_session, org_id, n=3):
    from app.models.archimate_core import SavedDiagram, SavedDiagramElement

    dia = SavedDiagram(name=f"Diagram {uuid.uuid4().hex[:8]}", organization_id=org_id)
    db_session.add(dia)
    db_session.flush()
    for i in range(n):
        el = _make_element(db_session, org_id, f"El {i} {uuid.uuid4().hex[:6]}")
        db_session.add(SavedDiagramElement(
            diagram_id=dia.id, element_id=el.id,
            position_x=10 * i, position_y=10 * i,
        ))
    db_session.flush()
    return dia


def test_saved_diagram_has_organization_column():
    """SavedDiagram must carry organization_id (TenantMixin)."""
    from app.models.archimate_core import SavedDiagram

    assert hasattr(SavedDiagram, "organization_id"), \
        "SavedDiagram must be tenant-scoped to prevent the CMP-01 count/payload desync"


def test_diagram_invisible_to_other_org(db_session, make_org, tenant_ctx):
    """A diagram owned by org A must not be listed for org B."""
    from app.models.archimate_core import SavedDiagram

    org_a = make_org("a")
    org_b = make_org("b")
    dia = _make_diagram_with_elements(db_session, org_a.id, n=5)

    with tenant_ctx(org_a.id):
        owner_ids = {d.id for d in SavedDiagram.query.all()}
    with tenant_ctx(org_b.id):
        other_ids = {d.id for d in SavedDiagram.query.all()}

    assert dia.id in owner_ids, "owner org must see its own diagram"
    assert dia.id not in other_ids, "other org must NOT see org A's diagram (CMP-01 leak)"


def test_count_and_payload_agree_for_owner(db_session, make_org, tenant_ctx):
    """For the owning org, element_count matches the elements the loader resolves."""
    from app.models.archimate_core import ArchiMateElement, SavedDiagram

    org_a = make_org("a")
    dia = _make_diagram_with_elements(db_session, org_a.id, n=4)

    with tenant_ctx(org_a.id):
        vp = SavedDiagram.query.get(dia.id)
        count = vp.to_dict()["element_count"]
        element_ids = [p.element_id for p in vp.positions.all()]
        resolved = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(element_ids)
        ).all()

    assert count == 4
    assert len(resolved) == count, \
        "element_count must equal the number of elements the loader can resolve"


def test_cross_org_loader_cannot_resolve_elements(db_session, make_org, tenant_ctx):
    """Even if org B somehow references the diagram, its elements stay invisible."""
    from app.models.archimate_core import ArchiMateElement, SavedDiagram

    org_a = make_org("a")
    org_b = make_org("b")
    dia = _make_diagram_with_elements(db_session, org_a.id, n=3)
    element_ids = [p.element_id for p in dia.positions.all()]
    dia_id = dia.id

    with tenant_ctx(org_b.id):
        # Expire so the reads below issue real SELECTs (a fresh cross-org request
        # would); Session.get() on an identity-mapped row skips the SELECT the
        # tenant loader-criteria hooks, which is a same-session test artifact, not
        # how a separate request behaves.
        from app import db
        db.session.expire_all()

        resolved = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(element_ids)
        ).all()
        assert resolved == [], "org B must not resolve org A's elements"
        # And the diagram is unreachable under org B's scope. NOTE: assert via a
        # SELECT-emitting query, not Session.get() — get() on an identity-mapped
        # PK returns the cached instance without re-running the statement, so the
        # tenant loader-criteria never applies. The load endpoint must therefore
        # use a filtered query, not a bare get(), to enforce isolation (see the
        # endpoint fix that pairs with this test).
        assert SavedDiagram.query.filter(SavedDiagram.id == dia_id).first() is None
