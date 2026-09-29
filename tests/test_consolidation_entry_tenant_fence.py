"""Regression tests: ConsolidationListEntry has no organization_id of its
own (ownership is via application_id) and several routes fetched it with a
bare query.get(...) with no tenant fence at all -- letting any logged-in
user read, update, or delete another organisation's consolidation entry
(financial figures, risk assessment, savings estimates)."""
import uuid

import pytest


def _make_entry_for_org(db_session, org):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.consolidation_list import ConsolidationListEntry

    app = ApplicationComponent(name=f"App {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db_session.add(app)
    db_session.flush()
    entry = ConsolidationListEntry(
        application_id=app.id,
        estimated_savings=999999,
        risk_assessment="SECRET-RISK",
        source_type="manual",
    )
    db_session.add(entry)
    db_session.flush()
    return entry


def _make_user(db_session, org, prefix):
    from app.models.user import User

    user = User(
        email=f"{prefix}-{uuid.uuid4().hex[:6]}@example.test",
        first_name="P",
        last_name="Q",
        organization_id=org.id,
        confirmed=True,
    )
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.commit()
    return user


def test_entry_detail_refuses_a_foreign_organisations_entry(app, db_session, make_org, client, login_as):
    from app.models.user import User

    org_a = make_org("cle-fence-a1")
    org_b = make_org("cle-fence-b1")
    entry_b = _make_entry_for_org(db_session, org_b)
    user_a = _make_user(db_session, org_a, "u1")
    entry_b_id, uid = entry_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/consolidation-list/api/entry/{entry_b_id}/detail")
    body = r.get_data(as_text=True)
    assert r.status_code == 404
    assert "999999" not in body
    assert "SECRET-RISK" not in body


def test_entry_detail_still_works_for_the_owning_organisation(app, db_session, make_org, client, login_as):
    from app.models.user import User

    org_a = make_org("cle-fence-a2")
    entry_a = _make_entry_for_org(db_session, org_a)
    user_a = _make_user(db_session, org_a, "u2")
    entry_a_id, uid = entry_a.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.get(f"/consolidation-list/api/entry/{entry_a_id}/detail")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "999999" in body


def test_update_entry_refuses_to_modify_a_foreign_organisations_entry(app, db_session, make_org, client, login_as):
    from app.models.consolidation_list import ConsolidationListEntry
    from app.models.user import User

    org_a = make_org("cle-fence-a3")
    org_b = make_org("cle-fence-b3")
    entry_b = _make_entry_for_org(db_session, org_b)
    user_a = _make_user(db_session, org_a, "u3")
    entry_b_id, uid = entry_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.put(
        f"/consolidation-list/api/entry/{entry_b_id}",
        json={"risk_assessment": "TAMPERED"},
    )
    assert r.status_code == 404

    still = db_session.get(ConsolidationListEntry, entry_b_id)
    assert still.risk_assessment == "SECRET-RISK"


def test_remove_entry_refuses_to_delete_a_foreign_organisations_entry(app, db_session, make_org, client, login_as):
    from app.models.consolidation_list import ConsolidationListEntry
    from app.models.user import User

    org_a = make_org("cle-fence-a4")
    org_b = make_org("cle-fence-b4")
    entry_b = _make_entry_for_org(db_session, org_b)
    user_a = _make_user(db_session, org_a, "u4")
    entry_b_id, uid = entry_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.delete(f"/consolidation-list/api/entry/{entry_b_id}")
    assert r.status_code == 404

    assert db_session.get(ConsolidationListEntry, entry_b_id) is not None


def test_bulk_action_skips_a_foreign_organisations_entry_id(app, db_session, make_org, client, login_as):
    from app.models.consolidation_list import ConsolidationListEntry
    from app.models.user import User

    org_a = make_org("cle-fence-a5")
    org_b = make_org("cle-fence-b5")
    entry_b = _make_entry_for_org(db_session, org_b)
    user_a = _make_user(db_session, org_a, "u5")
    entry_b_id, uid = entry_b.id, user_a.id
    db_session.expunge_all()

    login_as(client, db_session.get(User, uid))
    r = client.post(
        "/consolidation-list/api/bulk-action",
        json={"entry_ids": [entry_b_id], "action": "decommission"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["updated_count"] == 0
    assert any(str(entry_b_id) in e for e in body["errors"])

    still = db_session.get(ConsolidationListEntry, entry_b_id)
    assert still.recommended_action != "decommission"
