"""The solution issues API names only users of the caller's organisation.

``SolutionIssue.assigned_to_id`` is written from the request body, and ``User`` has no tenant
filter, so an issue could be assigned to a user of ANOTHER organisation and every read then
returned that user's e-mail local part (``assigned_to``). Two fixes: the write refuses an
assignee outside the caller's organisation, and every read resolves the name through
``user_in_org`` so a value already stored still names no one.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text


def _user(db_session, org, first):
    from app.models.user import User

    user = User(
        email=f"{first.lower()}-{uuid.uuid4().hex[:6]}@example.test", first_name=first, last_name="Test",
        organization_id=org.id, confirmed=True,
    )
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.flush()
    return user


def _world(db_session, make_org):
    from app.models.solution_models import Solution

    org_a, org_b = make_org("issues-a"), make_org("issues-b")
    mine = _user(db_session, org_a, "Mia")
    colleague = _user(db_session, org_a, "Cal")
    theirs = _user(db_session, org_b, "Vic")
    solution = Solution(name=f"Issue solution {uuid.uuid4().hex[:8]}")
    solution.organization_id = org_a.id
    db_session.add(solution)
    db_session.flush()
    return org_a, mine, colleague, theirs, solution


def _issue(db_session, org, solution, **fields):
    from app.models.solution_governance import SolutionIssue

    issue = SolutionIssue(
        solution_id=solution.id, title="An issue", description="Something is blocked",
        organization_id=org.id, **fields,
    )
    db_session.add(issue)
    db_session.flush()
    return issue


def _login(db_session, client, login_as, user_id):
    from app.models.user import User

    login_as(client, db_session.get(User, user_id))


def _base(solution):
    return f"/api/solutions/{solution.id}/issues"


def test_reading_an_issue_assigned_to_a_foreign_user_names_no_one(
    app, db_session, make_org, client, login_as
):
    org, mine, _colleague, theirs, solution = _world(db_session, make_org)
    issue = _issue(db_session, org, solution, assigned_to_id=theirs.id, created_by_id=theirs.id)
    db_session.commit()
    mine_id, issue_id, solution_id = mine.id, issue.id, solution.id
    theirs_local = theirs.email.split("@")[0]
    base = f"/api/solutions/{solution_id}/issues"
    db_session.expunge_all()

    _login(db_session, client, login_as, mine_id)
    listed = client.get(base).get_json()
    single = client.get(f"{base}/{issue_id}").get_json()

    assert theirs_local not in str(listed), listed
    assert theirs_local not in str(single), single


def test_reading_an_issue_assigned_to_a_colleague_still_names_them(
    app, db_session, make_org, client, login_as
):
    org, mine, colleague, _theirs, solution = _world(db_session, make_org)
    issue = _issue(db_session, org, solution, assigned_to_id=colleague.id, created_by_id=mine.id)
    db_session.commit()
    mine_id, issue_id, base = mine.id, issue.id, _base(solution)
    colleague_local, mine_local = colleague.email.split("@")[0], mine.email.split("@")[0]
    db_session.expunge_all()

    _login(db_session, client, login_as, mine_id)
    single = client.get(f"{base}/{issue_id}").get_json()

    assert single["assigned_to"] == colleague_local
    assert single["created_by"] == mine_local


def test_assigning_an_issue_to_a_foreign_user_is_refused(
    app, db_session, make_org, client, login_as
):
    org, mine, _colleague, theirs, solution = _world(db_session, make_org)
    issue = _issue(db_session, org, solution, created_by_id=mine.id)
    db_session.commit()
    mine_id, issue_id, theirs_id, base = mine.id, issue.id, theirs.id, _base(solution)
    db_session.expunge_all()

    _login(db_session, client, login_as, mine_id)
    response = client.put(f"{base}/{issue_id}", json={"assigned_to_id": theirs_id})

    assert response.status_code == 400, response.get_data(as_text=True)
    stored = db_session.execute(
        text("select assigned_to_id from solution_issues where id = :i"), {"i": issue_id}
    ).scalar()
    assert stored is None


def test_creating_an_issue_assigned_to_a_foreign_user_is_refused(
    app, db_session, make_org, client, login_as
):
    _org, mine, _colleague, theirs, solution = _world(db_session, make_org)
    db_session.commit()
    mine_id, theirs_id, base = mine.id, theirs.id, _base(solution)
    db_session.expunge_all()

    _login(db_session, client, login_as, mine_id)
    response = client.post(
        base, json={"title": "New", "description": "Blocked", "assigned_to_id": theirs_id},
    )

    assert response.status_code == 400, response.get_data(as_text=True)
