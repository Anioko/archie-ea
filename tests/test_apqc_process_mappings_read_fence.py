"""GET /api/apqc/process-mappings returned every organisation's mappings.
Neither CapabilityProcessMapping nor ProcessApplicationMapping carries an
organization_id of its own -- ownership is only reachable via capability_id /
application_id -- so an unfiltered (or apqc_process_id-only, itself a shared
reference id) query.all() exposed another organisation's capability/
application names, assessor, and other business data via to_dict().
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


def test_capability_mappings_exclude_a_foreign_organisations_rows(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("apqc-read-a1")
    org_b = make_org("apqc-read-b1")
    process = _process(db_session)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    cap_b = BusinessCapability(name="SECRET-CAP-B", organization_id=org_b.id)
    db_session.add_all([cap_a, cap_b])
    db_session.flush()
    cpm_a = CapabilityProcessMapping(capability_id=cap_a.id, apqc_process_id=process.id, assessor="Alice")
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id, assessor="SECRET-BOB")
    db_session.add_all([cpm_a, cpm_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "u1")
    uid = user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/apqc/process-mappings")

    assert r.status_code == 200
    body = r.get_json()
    text = str(body)
    assert "SECRET-CAP-B" not in text
    assert "SECRET-BOB" not in text
    assert any(m.get("capability_name") == "CapA" for m in body["mappings"])


def test_application_mappings_exclude_a_foreign_organisations_rows(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-read-a2")
    org_b = make_org("apqc-read-b2")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="SECRET-APP-B", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id, assessor="Alice")
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id, assessor="SECRET-BOB")
    db_session.add_all([pam_a, pam_b])
    db_session.flush()
    user_a = _user(db_session, org_a, "u2")
    app_a_id, uid = app_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get("/api/apqc/process-mappings", query_string={"type": "application"})

    assert r.status_code == 200
    body = r.get_json()
    text = str(body)
    assert "SECRET-BOB" not in text
    assert any(m.get("application_id") == app_a_id for m in body["mappings"])
