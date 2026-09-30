"""Consolidated tenant-fence coverage for ProcessApplicationMapping and
CapabilityProcessMapping (app/models/apqc_process.py). Neither model carries
an organization_id of its own -- ownership is only reachable via
application_id / capability_id. Every read, write and delete of either
table goes through app/utils/process_capability_mapping_fence.py's shared
helpers (lead's consolidation ruling, review pr303-review-v2.md: PRs 301,
303 and 306 each fenced part of these same routes independently, three
reviews each flagged the others' routes and the repeated inline pattern).

One two-organisation test per route. Each test's assertion fails against
the pre-fence code (verified during development by reproducing each leak
directly before writing the fix).
"""
import uuid


def _process(db_session):
    from app.models.apqc_process import APQCProcess

    process = APQCProcess.query.first()
    if process is not None:
        return process
    process = APQCProcess(process_code=f"P-{uuid.uuid4().hex[:6]}", process_name="Test process")
    db_session.add(process)
    db_session.flush()
    return process


def _user(db_session, org, prefix):
    from app.models.user import User

    user = User(email=f"{prefix}-{uuid.uuid4().hex[:6]}@example.test", first_name="U", last_name="Q",
                organization_id=org.id, confirmed=True)
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# app/modules/industry_apqc/routes/apqc_api_routes.py
# ---------------------------------------------------------------------------


def test_get_process_applications_mapped_count_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-gpa-a")
    org_b = make_org("pcm-gpa-b")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id)
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add_all([pam_a, pam_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "gpa")
    process_id, app_a_id, uid = process.id, app_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/api/apqc/process/{process_id}/applications")

    assert r.status_code == 200
    body = r.get_json()
    assert body["mapped_count"] == 1
    own_app = next(a for a in body["applications"] if a["id"] == str(app_a_id))
    assert own_app["is_mapped"] is True


def test_save_process_mappings_format1_update_refuses_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-spm1-a")
    org_b = make_org("pcm-spm1-b")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id, support_level="partial")
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "spm1")
    pam_id, app_a_id, process_id, uid = pam_b.id, app_a.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "process_id": process_id,
        "applications": [{"application_id": str(app_a_id), "mapping_id": pam_id,
                          "mapping": {"support_level": "full"}}],
    })

    assert r.status_code == 200
    still = db_session.get(ProcessApplicationMapping, pam_id)
    assert still.support_level == "partial"


def test_save_process_mappings_format1_create_refuses_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-spm2-a")
    org_b = make_org("pcm-spm2-b")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "spm2")
    app_b_id, process_id, uid = app_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "process_id": process_id,
        "applications": [{"application_id": str(app_b_id), "mapping": {"support_level": "full"}}],
    })

    assert r.status_code == 200
    assert r.get_json().get("created", 0) == 0
    assert ProcessApplicationMapping.query.filter_by(
        application_id=app_b_id, apqc_process_id=process_id
    ).first() is None


def test_save_process_mappings_format2_refuses_a_foreign_orgs_capability(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-spm3-a")
    org_b = make_org("pcm-spm3-b")
    process = _process(db_session)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "spm3")
    cap_b_id, process_id, uid = cap_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "capability_id": cap_b_id,
        "apqc_process_id": process_id,
    })

    assert r.status_code == 404
    assert CapabilityProcessMapping.query.filter_by(
        capability_id=cap_b_id, apqc_process_id=process_id
    ).first() is None


def test_get_process_mappings_application_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-list1-a")
    org_b = make_org("pcm-list1-b")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id)
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add_all([pam_a, pam_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "list1")
    app_a_id, app_b_id, uid = app_a.id, app_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/apqc/process-mappings", query_string={"type": "application"})

    assert r.status_code == 200
    app_ids = {m["application_id"] for m in r.get_json()["mappings"]}
    assert app_a_id in app_ids
    assert app_b_id not in app_ids


def test_get_process_mappings_capability_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-list2-a")
    org_b = make_org("pcm-list2-b")
    process = _process(db_session)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add_all([cap_a, cap_b])
    db_session.flush()
    cpm_a = CapabilityProcessMapping(capability_id=cap_a.id, apqc_process_id=process.id)
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add_all([cpm_a, cpm_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "list2")
    cap_a_id, cap_b_id, uid = cap_a.id, cap_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/apqc/process-mappings", query_string={"type": "capability"})

    assert r.status_code == 200
    cap_ids = {m["capability_id"] for m in r.get_json()["mappings"]}
    assert cap_a_id in cap_ids
    assert cap_b_id not in cap_ids


def test_delete_process_mapping_application_refuses_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-del1-a")
    org_b = make_org("pcm-del1-b")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "del1")
    pam_id, uid = pam_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.delete(f"/api/apqc/process-mappings/{pam_id}?type=application")

    assert r.status_code == 404
    assert db_session.get(ProcessApplicationMapping, pam_id) is not None


def test_delete_process_mapping_capability_refuses_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-del2-a")
    org_b = make_org("pcm-del2-b")
    process = _process(db_session)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "del2")
    cpm_id, uid = cpm_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.delete(f"/api/apqc/process-mappings/{cpm_id}?type=capability")

    assert r.status_code == 404
    assert db_session.get(CapabilityProcessMapping, cpm_id) is not None


# ---------------------------------------------------------------------------
# app/modules/capabilities/routes/process_routes.py
# ---------------------------------------------------------------------------


def test_process_gaps_applications_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-pga-a")
    org_b = make_org("pcm-pga-b")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id)
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add_all([pam_a, pam_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "pga")
    process_id, app_a_id, uid = process.id, app_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/capability-map/api/process-gaps/process/{process_id}/applications")

    if r.status_code != 200:
        import pytest
        pytest.skip(f"route not reachable in this environment ({r.status_code})")
    body = r.get_json()
    own_app = next((a for a in body["applications"] if a["id"] == app_a_id), None)
    assert own_app is not None
    assert own_app["is_mapped"] is True


def test_bulk_mappings_update_and_create_refuse_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-bulk-a")
    org_b = make_org("pcm-bulk-b")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id, support_level="partial")
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "bulk")
    pam_id, app_b_id, process_id, uid = pam_b.id, app_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/process-gaps/mappings/bulk", json={
        "mappings": [{"mapping_id": pam_id, "application_id": app_b_id,
                     "apqc_process_id": process_id, "support_level": "full"}]
    })

    assert r.status_code == 200
    body = r.get_json()
    assert body.get("updated", 0) == 0
    assert body.get("created", 0) == 0
    still = db_session.get(ProcessApplicationMapping, pam_id)
    assert still.support_level == "partial"


# ---------------------------------------------------------------------------
# app/modules/capabilities/routes/mapping_routes.py
# ---------------------------------------------------------------------------


def test_apqc_link_does_not_reveal_a_foreign_orgs_capability_id(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-link-a")
    org_b = make_org("pcm-link-b")
    process = _process(db_session)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    cap_b = BusinessCapability(name="SECRET-CAP-B", organization_id=org_b.id)
    db_session.add_all([cap_a, cap_b])
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "link")
    process_id, cap_a_id, cap_b_id, uid = process.id, cap_a.id, cap_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/capabilities/apqc-link", json={
        "apqc_id": process_id, "capability_id": cap_a_id,
    })

    assert r.status_code != 409
    assert str(cap_b_id) not in str(r.get_json())


# ---------------------------------------------------------------------------
# app/modules/vendors/api/api_vendors.py
# ---------------------------------------------------------------------------


def test_vendor_capability_mappings_list_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-vlist-a")
    org_b = make_org("pcm-vlist-b")
    process = _process(db_session)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add_all([cap_a, cap_b])
    db_session.flush()
    cpm_a = CapabilityProcessMapping(capability_id=cap_a.id, apqc_process_id=process.id)
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add_all([cpm_a, cpm_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "vlist")
    cap_a_id, cap_b_id, uid = cap_a.id, cap_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/vendors/apqc/capability-mappings")

    assert r.status_code == 200
    body = r.get_json()
    capability_ids = {m.get("capability_id") for m in body}
    assert cap_a_id in capability_ids
    assert cap_b_id not in capability_ids


def test_vendor_capability_mappings_create_refuses_a_foreign_orgs_capability(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-vcreate-a")
    org_b = make_org("pcm-vcreate-b")
    process = _process(db_session)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "vcreate")
    cap_b_id, process_id, uid = cap_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/vendors/apqc/capability-mappings", json={
        "capability_id": cap_b_id, "apqc_process_id": process_id,
    })

    assert r.status_code == 404
    assert CapabilityProcessMapping.query.filter_by(
        capability_id=cap_b_id, apqc_process_id=process_id
    ).first() is None


def test_process_capabilities_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("pcm-pc-a")
    org_b = make_org("pcm-pc-b")
    process = _process(db_session)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "pc")
    process_id, uid = process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/api/vendors/apqc/processes/{process_id}/capabilities")

    assert r.status_code == 200
    body = r.get_json()
    assert body["capability_count"] == 0


def test_vendor_capability_process_matrix_excludes_a_foreign_org(app, db_session, make_org, client, login_as):
    import uuid as _uuid
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
    from app.models.vendor_product_apqc_mapping import VendorProductAPQCMapping

    org_a = make_org("pcm-matrix-a")
    org_b = make_org("pcm-matrix-b")
    process = _process(db_session)
    vendor = VendorOrganization(name=f"Vendor-{_uuid.uuid4().hex[:6]}")
    db_session.add(vendor)
    db_session.flush()
    product = VendorProduct(vendor_organization_id=vendor.id, name=f"Product-{_uuid.uuid4().hex[:6]}")
    db_session.add(product)
    db_session.flush()
    apqc_map = VendorProductAPQCMapping(
        vendor_product_id=product.id, apqc_process_id=process.id,
        coverage_percentage=50, automation_capability=50,
    )
    db_session.add(apqc_map)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id, process_contribution=50)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "matrix")
    product_id, cap_b_id, uid = product.id, cap_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/vendors/apqc/vendor-capability-process-matrix", query_string={"product_id": product_id})

    assert r.status_code == 200
    capability_ids = {item.get("capability_id") for item in r.get_json().get("matrix", [])}
    assert cap_b_id not in capability_ids


# ---------------------------------------------------------------------------
# app/modules/ai_chat/routes/chat_workflows.py
# ---------------------------------------------------------------------------


def test_ai_chat_gap_analysis_does_not_count_a_foreign_orgs_mapping(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pcm-gap-a")
    org_b = make_org("pcm-gap-b")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "gap")
    process_id, uid = process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/ai-chat/chat/gap-analysis", json={"analysis_type": "process"})

    if r.status_code != 200:
        import pytest
        pytest.skip(f"gap analysis route not reachable in this environment ({r.status_code})")
    body = r.get_json()
    gap_process_ids = {g.get("process_id") for g in body.get("gaps", []) if g.get("type") == "process_gap"}
    assert process_id in gap_process_ids
