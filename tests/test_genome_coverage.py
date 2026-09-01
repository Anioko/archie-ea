"""First-ever codegen/genome test: the deterministic Capability->Application
coverage slice + emitter.

Asserts the three properties the reference slice must prove (01_blueprint.md s4):
  (a) real capability and application names from the tenant render;
  (b) every populated cell resolves to real, non-null ArchiMate element ids;
  (c) DETERMINISM — building the slice twice yields byte-identical output
      (same spec_hash) and the emitted HTML is byte-identical.

Uses the SHARED fixtures in tests/conftest.py (db_session, make_org, tenant_ctx).
Seeds a small org with 2 capabilities, 2 applications, their ArchiMate elements,
and 2 mappings.
"""
from __future__ import annotations

import pytest

from app.modules.genome.emit.coverage_matrix import emit_coverage_matrix_html
from app.modules.genome.services.coverage_slice import (
    SliceProvenanceError,
    build_coverage_slice,
)


def _seed(db_session, org_id):
    """Seed 2 caps, 2 apps, their elements, and 2 mappings. Returns names."""
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability

    # ArchiMate elements (the provenance anchors).
    cap_elem_1 = ArchiMateElement(name="Customer Management", type="Capability", layer="business", organization_id=org_id)
    cap_elem_2 = ArchiMateElement(name="Order Fulfilment", type="Capability", layer="business", organization_id=org_id)
    app_elem_1 = ArchiMateElement(name="Salesforce CRM", type="ApplicationComponent", layer="application", organization_id=org_id)
    app_elem_2 = ArchiMateElement(name="SAP ERP", type="ApplicationComponent", layer="application", organization_id=org_id)
    db_session.add_all([cap_elem_1, cap_elem_2, app_elem_1, app_elem_2])
    db_session.flush()

    cap1 = BusinessCapability(
        name="Customer Management", code=f"CAP-{org_id}-1", level=1,
        organization_id=org_id, archimate_element_id=cap_elem_1.id,
    )
    cap2 = BusinessCapability(
        name="Order Fulfilment", code=f"CAP-{org_id}-2", level=1,
        organization_id=org_id, archimate_element_id=cap_elem_2.id,
    )
    app1 = ApplicationComponent(
        name="Salesforce CRM", organization_id=org_id, archimate_element_id=app_elem_1.id,
    )
    app2 = ApplicationComponent(
        name="SAP ERP", organization_id=org_id, archimate_element_id=app_elem_2.id,
    )
    db_session.add_all([cap1, cap2, app1, app2])
    db_session.flush()

    m1 = ApplicationCapabilityMapping(
        organization_id=org_id, application_component_id=app1.id,
        business_capability_id=cap1.id, support_level="full", coverage_percentage=90,
        relationship_type="enables",
    )
    m2 = ApplicationCapabilityMapping(
        organization_id=org_id, application_component_id=app2.id,
        business_capability_id=cap2.id, support_level="partial", coverage_percentage=50,
        relationship_type="supports",
    )
    db_session.add_all([m1, m2])
    db_session.flush()

    return {
        "cap_names": {"Customer Management", "Order Fulfilment"},
        "app_names": {"Salesforce CRM", "SAP ERP"},
        "element_ids": {cap_elem_1.id, cap_elem_2.id, app_elem_1.id, app_elem_2.id},
    }


def test_coverage_slice_real_names_and_provenance(db_session, make_org, tenant_ctx):
    org = make_org("genome")
    seed = _seed(db_session, org.id)

    with tenant_ctx(org.id):
        s = build_coverage_slice(org.id)

    # (a) real names render into the slice.
    cap_names = {c["name"] for c in s["capabilities"]}
    app_names = {a["name"] for a in s["applications"]}
    assert seed["cap_names"] <= cap_names
    assert seed["app_names"] <= app_names

    # Single named capability store (ADR 0008).
    assert s["capability_source"] == "business_capability"

    # 2 mappings -> 2 populated cells.
    assert len(s["cells"]) == 2

    # (b) every populated cell resolves to real, non-null element ids.
    for cell in s["cells"]:
        prov = cell["provenance"]
        cap_eid = prov["capability_archimate_element_id"]
        app_eid = prov["application_archimate_element_id"]
        assert cap_eid is not None and app_eid is not None
        assert cap_eid in seed["element_ids"]
        assert app_eid in seed["element_ids"]


def test_coverage_slice_determinism(db_session, make_org, tenant_ctx):
    org = make_org("genome")
    _seed(db_session, org.id)

    with tenant_ctx(org.id):
        s1 = build_coverage_slice(org.id)
        s2 = build_coverage_slice(org.id)

    # (c) determinism: identical spec_hash and byte-identical emitted HTML.
    assert s1["spec_hash"] == s2["spec_hash"]
    assert s1["spec_hash"].startswith("sha256:")
    html1 = emit_coverage_matrix_html(s1)
    html2 = emit_coverage_matrix_html(s2)
    assert html1 == html2


def test_emitted_html_renders_real_names_and_provenance(db_session, make_org, tenant_ctx):
    org = make_org("genome")
    _seed(db_session, org.id)

    with tenant_ctx(org.id):
        s = build_coverage_slice(org.id)
    html = emit_coverage_matrix_html(s)

    # Real names appear in the rendered heatmap.
    assert "Customer Management" in html
    assert "Salesforce CRM" in html

    # Every populated cell carries both provenance element ids as data-* attrs.
    for cell in s["cells"]:
        prov = cell["provenance"]
        assert f'data-cap-element-id="{prov["capability_archimate_element_id"]}"' in html
        assert f'data-app-element-id="{prov["application_archimate_element_id"]}"' in html


def test_coverage_page_renders_matrix_for_tenant(db_session, make_org, client, login_as):
    """End-to-end: the presenter's click renders the heatmap with real names."""
    import uuid

    from app.models.user import User

    org = make_org("genome")
    _seed(db_session, org.id)
    user = User(
        email=f"genome-{uuid.uuid4().hex[:10]}@example.test",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()

    login_as(client, user)
    resp = client.post("/genome/coverage/generate")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Real tenant names appear, and provenance data attributes are present.
    assert "Customer Management" in body
    assert "Salesforce CRM" in body
    assert "data-cap-element-id=" in body
    assert "data-app-element-id=" in body
    assert 'data-capability-source="business_capability"' in body


def test_missing_provenance_is_a_build_error(db_session, make_org, tenant_ctx):
    """A cell whose capability element id does not resolve must FAIL, not silently gap.

    BusinessCapability auto-anchors to a fresh ArchiMateElement on insert
    (before_insert listener), so a genuinely unanchored capability cannot be
    created through the ORM — which is why the demo tenant is fully traceable.
    To exercise the guard we NULL the anchor with a raw UPDATE (bypassing the
    listener, as a legacy pre-listener row would look) and assert the build refuses it.
    """
    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability

    org = make_org("genome")
    app_elem = ArchiMateElement(name="App X", type="ApplicationComponent", layer="application", organization_id=org.id)
    db_session.add(app_elem)
    db_session.flush()

    cap = BusinessCapability(
        name="Cap With Dangling Anchor", code=f"CAP-{org.id}-x", level=1,
        organization_id=org.id,
    )
    app = ApplicationComponent(
        name="App X", organization_id=org.id, archimate_element_id=app_elem.id,
    )
    db_session.add_all([cap, app])
    db_session.flush()
    # NULL the capability's provenance anchor via raw UPDATE (bypasses the
    # auto-anchor before_insert listener), then refresh the ORM view of it.
    from app.extensions import db as _db
    _db.session.execute(
        _db.text("UPDATE business_capability SET archimate_element_id = NULL WHERE id = :cid"),
        {"cid": cap.id},
    )
    _db.session.expire(cap)
    db_session.flush()
    db_session.add(ApplicationCapabilityMapping(
        organization_id=org.id, application_component_id=app.id,
        business_capability_id=cap.id, support_level="full", coverage_percentage=100,
    ))
    db_session.flush()

    with tenant_ctx(org.id):
        with pytest.raises(SliceProvenanceError):
            build_coverage_slice(org.id)
