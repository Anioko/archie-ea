"""Linking an existing Goal, Driver or Requirement to an application only succeeds when it
belongs to the caller's organisation.

None of ``Goal``, ``Driver`` or ``Requirement`` carry an organisation column: the only reliable
tenant signal is ``archimate_element_id``, set by the standard creation path
(``motivation_layer_service.py``'s "Basecoat pattern": an ``ArchiMateElement`` -- TenantMixin -- is
always created first and linked). The three "link existing X" routes in
``motivation_layer_routes.py`` checked only "is this already linked to a DIFFERENT application",
never whether an unlinked row belongs to another organisation at all: any caller who owns any
application could link any other organisation's unlinked goal, driver or requirement into it,
taking ownership of it. Reproduced for Requirement before the fix: an unlinked requirement created
under organisation B was successfully linked into organisation A's application
(``application_component_id`` changed to A's row).

Also fixed in the same pass: the Requirement branch's flash messages read ``requirement.name``,
which does not exist on the model (it is ``title``) -- every "already linked" message for a
Requirement has always raised ``AttributeError``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text


def _archimate_element(db_session, org):
    from app.models.archimate_core import ArchiMateElement

    element = ArchiMateElement(name=f"El {uuid.uuid4().hex[:6]}", type="Requirement",
                               layer="motivation", organization_id=org.id)
    db_session.add(element)
    db_session.flush()
    return element


def _app_component(db_session, org):
    from app.models.application_portfolio import ApplicationComponent

    app = ApplicationComponent(name=f"App {uuid.uuid4().hex[:6]}", organization_id=org.id)
    db_session.add(app)
    db_session.flush()
    return app


def _user(db_session, org):
    from app.models.user import User

    user = User(email=f"mo-{uuid.uuid4().hex[:6]}@example.test", first_name="M", last_name="O",
                organization_id=org.id, confirmed=True)
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.flush()
    return user


def _requirement(db_session, *, archimate_element_id=None, title="A requirement"):
    from app.models.models import Requirement

    req = Requirement(title=title, description="desc", archimate_element_id=archimate_element_id)
    db_session.add(req)
    db_session.flush()
    return req


def _goal(db_session, *, archimate_element_id=None, name="A goal"):
    from app.models.motivation import Goal

    goal = Goal(name=name, description="desc", archimate_element_id=archimate_element_id)
    db_session.add(goal)
    db_session.flush()
    return goal


def _driver(db_session, *, archimate_element_id=None, name="A driver"):
    from app.models.motivation import Driver

    driver = Driver(name=name, description="desc", archimate_element_id=archimate_element_id)
    db_session.add(driver)
    db_session.flush()
    return driver


def test_a_foreign_organisations_unlinked_requirement_is_refused(app, db_session, make_org, client, login_as):
    org_a, org_b = make_org("mo-req-a"), make_org("mo-req-b")
    app_a = _app_component(db_session, org_a)
    element_b = _archimate_element(db_session, org_b)
    req_b = _requirement(db_session, archimate_element_id=element_b.id, title="SECRET-REQUIREMENT-B")
    user_a = _user(db_session, org_a)
    db_session.commit()
    app_a_id, req_b_id, user_a_id = app_a.id, req_b.id, user_a.id
    db_session.expunge_all()

    from app.models.user import User

    login_as(client, db_session.get(User, user_a_id))
    response = client.post(f"/dashboard/applications/{app_a_id}/requirements/add",
                           data={"element_id": str(req_b_id)}, follow_redirects=True)

    assert response.status_code == 200
    stored = db_session.execute(
        text("select application_component_id from requirements where id = :i"), {"i": req_b_id}
    ).scalar()
    assert stored is None


def test_a_requirement_with_no_archimate_element_is_refused_not_guessed(app, db_session, make_org, client, login_as):
    org_a = make_org("mo-req-nofence")
    app_a = _app_component(db_session, org_a)
    req = _requirement(db_session, archimate_element_id=None, title="Free-floating requirement")
    user_a = _user(db_session, org_a)
    db_session.commit()
    app_a_id, req_id, user_a_id = app_a.id, req.id, user_a.id
    db_session.expunge_all()

    from app.models.user import User

    login_as(client, db_session.get(User, user_a_id))
    client.post(f"/dashboard/applications/{app_a_id}/requirements/add", data={"element_id": str(req_id)})

    stored = db_session.execute(
        text("select application_component_id from requirements where id = :i"), {"i": req_id}
    ).scalar()
    assert stored is None


def test_the_callers_own_requirement_still_links(app, db_session, make_org, client, login_as):
    org_a = make_org("mo-req-own")
    app_a = _app_component(db_session, org_a)
    element_a = _archimate_element(db_session, org_a)
    req_a = _requirement(db_session, archimate_element_id=element_a.id, title="Own requirement")
    user_a = _user(db_session, org_a)
    db_session.commit()
    app_a_id, req_a_id, user_a_id = app_a.id, req_a.id, user_a.id
    db_session.expunge_all()

    from app.models.user import User

    login_as(client, db_session.get(User, user_a_id))
    response = client.post(f"/dashboard/applications/{app_a_id}/requirements/add",
                           data={"element_id": str(req_a_id)}, follow_redirects=True)

    assert response.status_code == 200
    stored = db_session.execute(
        text("select application_component_id from requirements where id = :i"), {"i": req_a_id}
    ).scalar()
    assert stored == app_a_id


def test_a_foreign_organisations_unlinked_goal_and_driver_are_refused(app, db_session, make_org, client, login_as):
    org_a, org_b = make_org("mo-gd-a"), make_org("mo-gd-b")
    app_a = _app_component(db_session, org_a)
    element_b_goal = _archimate_element(db_session, org_b)
    element_b_driver = _archimate_element(db_session, org_b)
    goal_b = _goal(db_session, archimate_element_id=element_b_goal.id, name="SECRET-GOAL-B")
    driver_b = _driver(db_session, archimate_element_id=element_b_driver.id, name="SECRET-DRIVER-B")
    user_a = _user(db_session, org_a)
    db_session.commit()
    app_a_id, goal_b_id, driver_b_id, user_a_id = app_a.id, goal_b.id, driver_b.id, user_a.id
    db_session.expunge_all()

    from app.models.user import User

    login_as(client, db_session.get(User, user_a_id))
    client.post(f"/dashboard/applications/{app_a_id}/goals/add", data={"element_id": str(goal_b_id)})
    client.post(f"/dashboard/applications/{app_a_id}/drivers/add", data={"element_id": str(driver_b_id)})

    goal_linked = db_session.execute(
        text("select application_component_id from goals where id = :i"), {"i": goal_b_id}
    ).scalar()
    driver_linked = db_session.execute(
        text("select application_component_id from drivers where id = :i"), {"i": driver_b_id}
    ).scalar()
    assert goal_linked is None and driver_linked is None
