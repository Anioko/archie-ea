"""Review findings on PR 306 (reviews/pr306-review-v2.md):

DEFECT-1 (HIGH): POST /api/capabilities/apqc-link's duplicate-mapping check
queried CapabilityProcessMapping by apqc_process_id alone (a shared
reference id) with no organisation fence, returning another organisation's
capability_id in the 409 response body.

DEFECT-4 (MEDIUM): GET /api/apqc/process/<id>/applications counted every
organisation's ProcessApplicationMapping rows in mapped_count, an aggregate
cross-org leak even though the per-application is_mapped flags happened to
stay correct.
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


def test_apqc_link_does_not_reveal_a_foreign_organisations_capability_id(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("apqc-link-a1")
    org_b = make_org("apqc-link-b1")
    process = _process(db_session)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    cap_b = BusinessCapability(name="SECRET-CAP-B-LINK", organization_id=org_b.id)
    db_session.add_all([cap_a, cap_b])
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "link1")
    process_id, cap_a_id, cap_b_id, uid = process.id, cap_a.id, cap_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/capabilities/apqc-link", json={
        "apqc_id": process_id,
        "capability_id": cap_a_id,
    })

    # org A's own capability has no link yet (org B's link is invisible to
    # org A), so the create path should succeed, not 409 with org B's id.
    assert r.status_code != 409
    body = r.get_json()
    assert str(cap_b_id) not in str(body)


def test_apqc_link_still_refuses_a_duplicate_within_the_same_organisation(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("apqc-link-a2")
    process = _process(db_session)
    cap_a1 = BusinessCapability(name="CapA1", organization_id=org_a.id)
    cap_a2 = BusinessCapability(name="CapA2", organization_id=org_a.id)
    db_session.add_all([cap_a1, cap_a2])
    db_session.flush()
    cpm_a1 = CapabilityProcessMapping(capability_id=cap_a1.id, apqc_process_id=process.id)
    db_session.add(cpm_a1)
    db_session.flush()
    user_a = _user(db_session, org_a, "link2")
    process_id, cap_a1_id, cap_a2_id, uid = process.id, cap_a1.id, cap_a2.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/capabilities/apqc-link", json={
        "apqc_id": process_id,
        "capability_id": cap_a2_id,
    })

    assert r.status_code == 409
    body = r.get_json()
    assert body.get("existing_capability_id") == cap_a1_id


def test_process_applications_mapped_count_excludes_a_foreign_organisations_mapping(
    app, db_session, make_org, client, login_as
):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-papps-a1")
    org_b = make_org("apqc-papps-b1")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id)
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add_all([pam_a, pam_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "papps1")
    process_id, app_a_id, uid = process.id, app_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/api/apqc/process/{process_id}/applications")

    assert r.status_code == 200
    body = r.get_json()
    assert body["mapped_count"] == 1
    own_app = next(a for a in body["applications"] if a["id"] == str(app_a_id))
    assert own_app["is_mapped"] is True
