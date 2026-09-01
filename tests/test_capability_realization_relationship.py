"""App→capability mapping must also be an ArchiMate realization relationship.

Mapping an application to a capability was stored only as junction rows, so
line-of-sight and impact analysis were blind to it — the fact existed as data but
not as architecture. `_mirror_mapping` now also writes an ArchiMate 3.2
`realization` relationship (ApplicationComponent → Capability). These tests pin
that it is created, idempotent, and removed on unmap.
"""

import pytest

from app.models.application_portfolio import ApplicationComponent
from app.models.archimate_core import ArchiMateRelationship
from app.models.business_capabilities import BusinessCapability
from app.modules.capabilities.routes.mapping_routes import _mirror_mapping


def _rel(db_session, src, tgt):
    return ArchiMateRelationship.query.filter_by(
        source_id=src, target_id=tgt, type="realization"
    ).first()


@pytest.mark.usefixtures("db_session")
def test_mapping_creates_realization_relationship(db_session, make_org, tenant_ctx):
    org = make_org("real")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Order Mgmt", organization_id=org.id, level=1)
        app = ApplicationComponent(name="OMS", organization_id=org.id,
                                   lifecycle_status="operational")
        db_session.add_all([cap, app])
        db_session.commit()  # listeners create both ArchiMate elements

        _mirror_mapping(cap.id, app.id, "full")
        db_session.commit()
        rel = _rel(db_session, app.archimate_element_id, cap.archimate_element_id)
        assert rel is not None, "app→capability mapping must create a realization"
        assert rel.derived_from == "capability_mapping"

        # idempotent — mapping again does not duplicate
        _mirror_mapping(cap.id, app.id, "partial")
        db_session.commit()
        count = ArchiMateRelationship.query.filter_by(
            source_id=app.archimate_element_id,
            target_id=cap.archimate_element_id, type="realization",
        ).count()
        assert count == 1


@pytest.mark.usefixtures("db_session")
def test_unmapping_removes_relationship(db_session, make_org, tenant_ctx):
    org = make_org("real")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Billing", organization_id=org.id, level=1)
        app = ApplicationComponent(name="Biller", organization_id=org.id,
                                   lifecycle_status="operational")
        db_session.add_all([cap, app])
        db_session.commit()
        _mirror_mapping(cap.id, app.id, "full")
        db_session.commit()
        assert _rel(db_session, app.archimate_element_id, cap.archimate_element_id)

        _mirror_mapping(cap.id, app.id, "full", delete=True)
        db_session.commit()
        assert _rel(db_session, app.archimate_element_id, cap.archimate_element_id) is None
