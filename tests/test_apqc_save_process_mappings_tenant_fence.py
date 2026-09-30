"""Review defects D1/D4 on the PR fencing the process-mapping bulk-update
route (reviews/pr303-review-v1.md): POST /api/apqc/process-mappings
(save_process_mappings, Format 1) updated an existing ProcessApplicationMapping
by a caller-supplied mapping_id, and created a new one pointing at a
caller-supplied application_id, with no ownership check on either path.
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


def test_update_via_mapping_id_refuses_a_foreign_organisations_mapping(app, db_session, make_org, client, login_as):
    """D1: the exploit shape is a caller-owned application_id (so the
    ownership check on app_id alone would pass) paired with a mapping_id
    that actually belongs to a foreign organisation's row for a different
    application -- the fence must catch the mismatch, not just check app_id
    in isolation."""
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-save-a1")
    org_b = make_org("apqc-save-b1")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()
    pam_b = ProcessApplicationMapping(application_id=app_b.id, apqc_process_id=process.id,
                                       support_level="partial")
    db_session.add(pam_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "s1")
    pam_id, app_a_id, process_id, uid = pam_b.id, app_a.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "process_id": process_id,
        "applications": [{
            "application_id": str(app_a_id),
            "mapping_id": pam_id,
            "mapping": {"support_level": "full"},
        }],
    })

    assert r.status_code == 200
    still = db_session.get(ProcessApplicationMapping, pam_id)
    assert still.support_level == "partial", "org B's mapping must be untouched"


def test_create_path_refuses_to_link_a_foreign_organisations_application(app, db_session, make_org, client, login_as):
    """D4"""
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-save-a2")
    org_b = make_org("apqc-save-b2")
    process = _process(db_session)
    app_b = ApplicationComponent(name="AppB", organization_id=org_b.id)
    db_session.add(app_b)
    db_session.flush()
    user_a = _user(db_session, org_a, "s2")
    app_b_id, process_id, uid = app_b.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "process_id": process_id,
        "applications": [{"application_id": str(app_b_id), "mapping": {"support_level": "full"}}],
    })

    assert r.status_code == 200
    body = r.get_json()
    assert body.get("created", 0) == 0
    assert ProcessApplicationMapping.query.filter_by(
        application_id=app_b_id, apqc_process_id=process_id
    ).first() is None


def test_create_and_update_still_work_for_the_owning_organisation(app, db_session, make_org, client, login_as):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.apqc_process import ProcessApplicationMapping
    from app.models.user import User

    org_a = make_org("apqc-save-a3")
    process = _process(db_session)
    app_a = ApplicationComponent(name="AppA", organization_id=org_a.id)
    db_session.add(app_a)
    db_session.flush()
    user_a = _user(db_session, org_a, "s3")
    app_a_id, process_id, uid = app_a.id, process.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post("/api/apqc/process-mappings", json={
        "process_id": process_id,
        "applications": [{"application_id": str(app_a_id), "mapping": {"support_level": "full"}}],
    })

    assert r.status_code == 200
    body = r.get_json()
    assert body.get("created", 0) == 1
    created = ProcessApplicationMapping.query.filter_by(
        application_id=app_a_id, apqc_process_id=process_id
    ).first()
    assert created is not None
    assert created.support_level == "full"
