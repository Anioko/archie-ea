"""DELETE /api/apqc/process-mappings/<id> deletes a ProcessApplicationMapping
or CapabilityProcessMapping row by id alone, with no ownership check at all.
Neither model carries an organization_id of its own -- ownership is only
reachable via application_id / capability_id -- so a caller from any
organisation could delete another organisation's mapping row. Reproduced
before fixing: organisation A deleted organisation B's rows (200, rows gone).
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


def test_delete_refuses_a_foreign_organisations_application_mapping(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-fence-a1")
    org_b = make_org("apqc-fence-b1")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id)
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "u1")
    pam_id, uid = pam_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.delete(f"/api/apqc/process-mappings/{pam_id}?type=application")

    assert r.status_code == 404
    assert db_session.get(ProcessApplicationMapping, pam_id) is not None


def test_delete_refuses_a_foreign_organisations_capability_mapping(app, db_session, make_org, client, login_as):
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("apqc-fence-a2")
    org_b = make_org("apqc-fence-b2")
    process = _process(db_session)
    cap_b = BusinessCapability(name="CapB", organization_id=org_b.id)
    db_session.add(cap_b)
    db_session.flush()
    cpm_b = CapabilityProcessMapping(capability_id=cap_b.id, apqc_process_id=process.id)
    db_session.add(cpm_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "u2")
    cpm_id, uid = cpm_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.delete(f"/api/apqc/process-mappings/{cpm_id}?type=capability")

    assert r.status_code == 404
    assert db_session.get(CapabilityProcessMapping, cpm_id) is not None


def test_delete_still_works_for_the_owning_organisations_mappings(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.business_capabilities import BusinessCapability
    from app.models.apqc_process import ProcessApplicationMapping, CapabilityProcessMapping
    from app.models.user import User

    org_a = make_org("apqc-fence-a3")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    cap_a = BusinessCapability(name="CapA", organization_id=org_a.id)
    db_session.add_all([app_a, cap_a])
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id)
    cpm_a = CapabilityProcessMapping(capability_id=cap_a.id, apqc_process_id=process.id)
    db_session.add_all([pam_a, cpm_a])
    db_session.flush()
    user_a = _user(db_session, org_a, "u3")
    pam_id, cpm_id, uid = pam_a.id, cpm_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r1 = client.delete(f"/api/apqc/process-mappings/{pam_id}?type=application")
    r2 = client.delete(f"/api/apqc/process-mappings/{cpm_id}?type=capability")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert db_session.get(ProcessApplicationMapping, pam_id) is None
    assert db_session.get(CapabilityProcessMapping, cpm_id) is None
