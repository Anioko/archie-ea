"""POST /api/process-gaps/mappings/bulk updates a ProcessApplicationMapping
by mapping_id (taken from the request body) with no ownership check at all.
ProcessApplicationMapping carries no organization_id of its own -- ownership
is only reachable via application_id -- so a caller from any organisation
could mutate another organisation's mapping by supplying its id. Reproduced
before fixing: organisation A updated organisation B's mapping row.
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


def test_bulk_update_refuses_a_foreign_organisations_mapping(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pam-fence-a1")
    org_b = make_org("pam-fence-b1")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id,
                                       support_level="partial", assessment_notes="original")
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "u1")
    pam_id, app_b_id, process_id, uid = pam_b.id, app_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/process-gaps/mappings/bulk", json={
        "mappings": [{
            "mapping_id": pam_id,
            "application_id": app_b_id,
            "apqc_process_id": process_id,
            "support_level": "full",
            "notes": "TAMPERED",
        }]
    })

    assert r.status_code == 200
    body = r.get_json()
    assert body.get("updated", 0) == 0
    still = db_session.get(ProcessApplicationMapping, pam_id)
    assert still.support_level == "partial"
    assert still.assessment_notes == "original"


def test_bulk_update_still_works_for_the_owning_organisations_mapping(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("pam-fence-a2")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    db_session.add(app_a)
    db_session.flush()
    pam_a = ProcessApplicationMapping(application_id=app_a.id, apqc_process_id=process.id,
                                       support_level="partial")
    db_session.add(pam_a)
    db_session.flush()
    user_a = _user(db_session, org_a, "u2")
    pam_id, app_a_id, process_id, uid = pam_a.id, app_a.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/capability-map/api/process-gaps/mappings/bulk", json={
        "mappings": [{
            "mapping_id": pam_id,
            "application_id": app_a_id,
            "apqc_process_id": process_id,
            "support_level": "full",
            "notes": "updated by owner",
        }]
    })

    assert r.status_code == 200
    body = r.get_json()
    assert body.get("updated", 0) == 1
    still = db_session.get(ProcessApplicationMapping, pam_id)
    assert still.support_level == "full"
    assert still.assessment_notes == "updated by owner"
