"""Grounded verification: a schema-valid patch that contradicts the existing
model is rejected before it reaches the approval queue."""
import pytest
from app.modules.genome.patch.grounding import ground_genome_patch
from app.models.archimate_core import ArchiMateElement


def _patch(org_id, *, a_type="Capability", layer="strategy", name="New Thing",
           op="add", anchor="Capability"):
    return {
        "target": {"organization_id": org_id, "domain": "business"},
        "operation": op,
        "element": {"archimate_type": a_type, "layer": layer, "name": name},
        "provenance": {"proposed_by": "1", "rationale": "because", "archimate_anchor": anchor},
    }


def _seed(session, org_id, name, a_type, layer):
    e = ArchiMateElement(name=name, type=a_type, layer=layer, organization_id=org_id)
    session.add(e)
    session.flush()
    return e


def test_type_layer_mismatch_is_rejected(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        # a Capability is a strategy element; declaring it in the business layer is untrue
        r = ground_genome_patch(_patch(org.id, a_type="Capability", layer="business"), session=db_session)
        assert not r.ok and any("layer" in e for e in r.errors)


def test_dangling_anchor_warns_not_blocks(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        r = ground_genome_patch(_patch(org.id, anchor="A Thing That Does Not Exist"), session=db_session)
        # advisory, not a hard block: ok, but the approver is warned
        assert r.ok
        assert any("anchor" in w for w in r.warnings)


def test_anchor_to_known_type_is_allowed(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        r = ground_genome_patch(_patch(org.id, name="Fresh Capability", anchor="Requirement"), session=db_session)
        assert r.ok, r.errors


def test_anchor_to_existing_element_is_allowed(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        _seed(db_session, org.id, "Order Management", "Capability", "strategy")
        r = ground_genome_patch(_patch(org.id, name="Fresh Capability", anchor="order management"), session=db_session)
        assert r.ok, r.errors  # case-insensitive name match


def test_duplicate_add_is_rejected(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        _seed(db_session, org.id, "Billing", "Capability", "strategy")
        r = ground_genome_patch(_patch(org.id, a_type="Capability", name="billing"), session=db_session)
        assert not r.ok and any("already exists" in e for e in r.errors)


def test_duplicate_check_is_org_scoped(db_session, make_org, tenant_ctx):
    org_a = make_org()
    org_b = make_org()
    with tenant_ctx(org_a.id):
        _seed(db_session, org_a.id, "Billing", "Capability", "strategy")
    with tenant_ctx(org_b.id):
        # same name in a different org is NOT a duplicate for org_b
        r = ground_genome_patch(_patch(org_b.id, a_type="Capability", name="Billing"), session=db_session)
        assert r.ok, r.errors


def test_valid_grounded_patch_passes(db_session, make_org, tenant_ctx):
    org = make_org()
    with tenant_ctx(org.id):
        r = ground_genome_patch(_patch(org.id, name="Wholly New Capability", anchor="Capability"), session=db_session)
        assert r.ok, r.errors
