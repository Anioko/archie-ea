"""App→capability mapping must produce exactly ONE ArchiMate relationship, not two.

A prior pass this session added a hand-rolled ArchiMateRelationship(type=
"realization") mirror to _mirror_mapping, without checking whether one already
existed. It did: app/models/archimate_relationship_sync.py's Listener 10 already
mirrors every ApplicationCapabilityMapping insert/delete into a real
ArchiMateRelationship(type="serving") — a mapper event that fires regardless of
which code path inserts the row. The hand-rolled mirror was a second, duplicate
authority for the same fact (ADR-0008) and has been removed; these tests pin the
correct behaviour — exactly one relationship, of the canonical "serving" type,
created by the existing listener alone.
"""

import pytest

from app.models.application_portfolio import ApplicationComponent
from app.models.archimate_core import ArchiMateRelationship
from app.models.business_capabilities import BusinessCapability
from app.modules.capabilities.routes.mapping_routes import _mirror_mapping


def _rels(db_session, src, tgt):
    return ArchiMateRelationship.query.filter_by(source_id=src, target_id=tgt).all()


@pytest.mark.usefixtures("db_session")
def test_mapping_creates_exactly_one_relationship_not_two(db_session, make_org, tenant_ctx):
    org = make_org("real")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Order Mgmt", organization_id=org.id, level=1)
        app = ApplicationComponent(name="OMS", organization_id=org.id,
                                   lifecycle_status="operational")
        db_session.add_all([cap, app])
        db_session.commit()  # listeners create both ArchiMate elements

        _mirror_mapping(cap.id, app.id, "full")
        db_session.commit()

        rels = _rels(db_session, app.archimate_element_id, cap.archimate_element_id)
        assert len(rels) == 1, f"expected exactly one relationship, got {len(rels)}: {[r.type for r in rels]}"
        assert rels[0].type == "serving"

        # idempotent — mapping again does not duplicate
        _mirror_mapping(cap.id, app.id, "partial")
        db_session.commit()
        rels_again = _rels(db_session, app.archimate_element_id, cap.archimate_element_id)
        assert len(rels_again) == 1


@pytest.mark.usefixtures("db_session")
def test_unmapping_removes_the_relationship(db_session, make_org, tenant_ctx):
    org = make_org("real")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Billing", organization_id=org.id, level=1)
        app = ApplicationComponent(name="Biller", organization_id=org.id,
                                   lifecycle_status="operational")
        db_session.add_all([cap, app])
        db_session.commit()
        _mirror_mapping(cap.id, app.id, "full")
        db_session.commit()
        assert len(_rels(db_session, app.archimate_element_id, cap.archimate_element_id)) == 1

        _mirror_mapping(cap.id, app.id, "full", delete=True)
        db_session.commit()
        assert _rels(db_session, app.archimate_element_id, cap.archimate_element_id) == []
