"""Impact analysis results belong to the organisation of the user who ran them.

``impact_analysis_results`` has no ``organization_id`` column and its model is
not a ``TenantMixin``, so the automatic tenant predicate never applies to it.
The only ownership link the table carries is ``created_by_id`` -> ``users``.
Every read of the model therefore has to be scoped through that link, and the
scope lives in one place: ``ImpactAnalysisResult.for_organization`` (and
``get_for_organization`` for a read by id).

These tests cover every read of the model in ``app/``:

* ``GET /strategic/api/impact-analysis/history``
* ``GET /enterprise/analysis/impact-analysis`` -- recent list, filtered list,
  total, critical count, high count and the average

plus the writer that records the analysing user, without which a caller's own
history would be empty once reads are scoped.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

HISTORY_URL = "/strategic/api/impact-analysis/history"
ENTERPRISE_URL = "/enterprise/analysis/impact-analysis"

HISTORY_KEYS = {
    "id",
    "analysis_type",
    "trigger_element_type",
    "trigger_element_id",
    "scenario",
    "overall_severity",
    "affected_capabilities_count",
    "affected_applications_count",
    "affected_processes_count",
    "created_at",
}


def _make_user(db_session, org):
    from werkzeug.security import generate_password_hash

    from app.models.user import User

    user = User(
        email=f"impact-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Impact",
        last_name="Tester",
        confirmed=True,
        organization_id=org.id,
        password_hash=generate_password_hash("x"),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _add_result(db_session, created_by_id, **overrides):
    from app.models.traceability import ImpactAnalysisResult

    fields = {
        "analysis_type": "change_impact",
        "trigger_element_type": "MODIFY",
        "trigger_element_id": 1,
        "scenario": "modification",
        "overall_severity": "low",
        "affected_applications_count": 0,
        "affected_capabilities_count": 0,
        "affected_processes_count": 0,
        "created_by_id": created_by_id,
    }
    fields.update(overrides)
    row = ImpactAnalysisResult(**fields)
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def two_orgs(db_session, make_org):
    """Two organisations, one user each."""
    org_a = make_org("impact-a")
    org_b = make_org("impact-b")
    user_a = _make_user(db_session, org_a)
    user_b = _make_user(db_session, org_b)
    return org_a, org_b, user_a, user_b


def _history(client, login_as, user):
    login_as(client, user)
    response = client.get(HISTORY_URL)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


@pytest.fixture
def enterprise_context(app, client, login_as):
    """Render the enterprise impact page and return the template context."""
    from flask import before_render_template

    def _render(user, query_string=None):
        captured = {}

        def _capture(sender, template, context, **extra):
            if template.name == "enterprise/impact_analysis.html":
                captured.update(context)

        login_as(client, user)
        with before_render_template.connected_to(_capture, app):
            response = client.get(ENTERPRISE_URL, query_string=query_string or {})
        assert response.status_code == 200, response.get_data(as_text=True)[:500]
        assert captured, "the impact analysis template was not rendered"
        return captured

    return _render


# --------------------------------------------------------------------------
# History endpoint
# --------------------------------------------------------------------------


def test_history_returns_only_the_callers_organisation(
    db_session, client, login_as, two_orgs
):
    """One organisation's analyses never appear in another's history."""
    _, _, user_a, user_b = two_orgs
    a_row = _add_result(
        db_session,
        user_a.id,
        trigger_element_id=424242,
        overall_severity="critical",
        affected_applications_count=7,
    )
    b_row = _add_result(db_session, user_b.id, trigger_element_id=515151)

    seen_by_b = _history(client, login_as, user_b)
    seen_by_a = _history(client, login_as, user_a)

    assert [r["id"] for r in seen_by_b] == [b_row.id]
    assert all(r["trigger_element_id"] != 424242 for r in seen_by_b)
    assert [r["id"] for r in seen_by_a] == [a_row.id]
    assert seen_by_a[0]["trigger_element_id"] == 424242
    assert seen_by_a[0]["overall_severity"] == "critical"
    assert seen_by_a[0]["affected_applications_count"] == 7


def test_history_is_empty_when_only_another_organisation_has_rows(
    db_session, client, login_as, two_orgs
):
    _, _, user_a, user_b = two_orgs
    _add_result(db_session, user_a.id, trigger_element_id=424242)

    assert _history(client, login_as, user_b) == []


def test_history_keeps_fields_ordering_and_limit_for_the_callers_own_rows(
    db_session, client, login_as, two_orgs
):
    """Scoping does not change what an in-organisation user sees."""
    _, _, user_a, user_b = two_orgs
    base = datetime(2026, 1, 1, 12, 0, 0)
    own = [
        _add_result(
            db_session,
            user_a.id,
            trigger_element_id=1000 + n,
            created_at=base + timedelta(minutes=n),
        )
        for n in range(12)
    ]
    # Newer rows from the other organisation sit between and after the
    # caller's own; they must neither displace nor reorder them.
    for n in range(5):
        _add_result(
            db_session,
            user_b.id,
            trigger_element_id=9000 + n,
            created_at=base + timedelta(minutes=6, seconds=30 + n),
        )
    _add_result(
        db_session, user_b.id, trigger_element_id=9999,
        created_at=base + timedelta(hours=1),
    )

    seen = _history(client, login_as, user_a)

    expected = list(reversed(own))[:10]
    assert len(seen) == 10
    assert [r["id"] for r in seen] == [r.id for r in expected]
    assert seen == [r.to_dict() for r in expected]
    assert set(seen[0]) == HISTORY_KEYS
    created = [r["created_at"] for r in seen]
    assert created == sorted(created, reverse=True)


def test_history_returns_nothing_for_rows_without_a_provable_owner(
    db_session, client, login_as, two_orgs
):
    """A row with no creator belongs to nobody the caller can prove."""
    _, _, user_a, user_b = two_orgs
    _add_result(db_session, None, trigger_element_id=777001)

    assert _history(client, login_as, user_a) == []
    assert _history(client, login_as, user_b) == []


def test_history_returns_nothing_for_a_creator_without_an_organisation(
    db_session, client, login_as, two_orgs, make_org
):
    """A creator that belongs to no organisation is not a match for anyone."""
    from sqlalchemy import text

    org_a, _, user_a, user_b = two_orgs
    orphan_creator = _make_user(db_session, org_a)
    _add_result(db_session, orphan_creator.id, trigger_element_id=777002)
    # users.organization_id is NOT NULL on a current schema; relax it inside
    # this transaction (rolled back with the test) to model an older database
    # that allowed a user without an organisation.
    db_session.execute(
        text("ALTER TABLE users ALTER COLUMN organization_id DROP NOT NULL")
    )
    db_session.execute(
        text("UPDATE users SET organization_id = NULL WHERE id = :uid"),
        {"uid": orphan_creator.id},
    )

    assert _history(client, login_as, user_a) == []
    assert _history(client, login_as, user_b) == []


def test_scope_helper_returns_nothing_for_a_caller_without_an_organisation(
    db_session, two_orgs
):
    """``organization_id = NULL`` must never be read as "creators with no
    organisation": no organisation for the caller means no rows at all."""
    from sqlalchemy import text

    from app.models.traceability import ImpactAnalysisResult

    org_a, _, user_a, _ = two_orgs
    orphan_creator = _make_user(db_session, org_a)
    _add_result(db_session, orphan_creator.id, trigger_element_id=777003)
    _add_result(db_session, None, trigger_element_id=777004)
    _add_result(db_session, user_a.id, trigger_element_id=777005)
    db_session.execute(
        text("ALTER TABLE users ALTER COLUMN organization_id DROP NOT NULL")
    )
    db_session.execute(
        text("UPDATE users SET organization_id = NULL WHERE id = :uid"),
        {"uid": orphan_creator.id},
    )

    assert ImpactAnalysisResult.for_organization(None).all() == []
    assert ImpactAnalysisResult.for_organization(None).count() == 0
    assert ImpactAnalysisResult.get_for_organization(1, None) is None


# --------------------------------------------------------------------------
# Read by id
# --------------------------------------------------------------------------


def test_read_by_id_treats_another_organisations_row_as_unknown(
    db_session, two_orgs
):
    """An id from another organisation behaves exactly like an unknown id."""
    from app.models.traceability import ImpactAnalysisResult

    org_a, org_b, user_a, user_b = two_orgs
    a_row = _add_result(db_session, user_a.id, trigger_element_id=424242)
    b_row = _add_result(db_session, user_b.id, trigger_element_id=515151)
    unknown_id = max(a_row.id, b_row.id) + 100000

    get = ImpactAnalysisResult.get_for_organization

    assert get(a_row.id, org_a.id) is a_row
    assert get(b_row.id, org_b.id) is b_row
    # Both directions look the same as an id that does not exist.
    assert get(a_row.id, org_b.id) is None
    assert get(b_row.id, org_a.id) is None
    assert get(unknown_id, org_a.id) is None
    assert get(a_row.id, org_b.id) == get(unknown_id, org_b.id)
    assert get(b_row.id, org_a.id) == get(unknown_id, org_a.id)


def test_read_by_id_returns_nothing_for_rows_without_a_provable_owner(
    db_session, two_orgs
):
    from app.models.traceability import ImpactAnalysisResult

    org_a, org_b, _, _ = two_orgs
    ownerless = _add_result(db_session, None, trigger_element_id=777006)

    assert ImpactAnalysisResult.get_for_organization(ownerless.id, org_a.id) is None
    assert ImpactAnalysisResult.get_for_organization(ownerless.id, org_b.id) is None


# --------------------------------------------------------------------------
# Enterprise impact analysis page: every read on it is scoped
# --------------------------------------------------------------------------


def test_enterprise_page_recent_list_is_scoped(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    a_row = _add_result(db_session, user_a.id, trigger_element_id=424242)
    b_row = _add_result(db_session, user_b.id, trigger_element_id=515151)

    seen_by_b = enterprise_context(user_b)
    seen_by_a = enterprise_context(user_a)

    assert [r.id for r in seen_by_b["recent_analyses"]] == [b_row.id]
    assert [r.id for r in seen_by_a["recent_analyses"]] == [a_row.id]


def test_enterprise_page_recent_list_keeps_ordering_and_limit(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    base = datetime(2026, 2, 1, 9, 0, 0)
    own = [
        _add_result(
            db_session, user_a.id, trigger_element_id=n,
            created_at=base + timedelta(minutes=n),
        )
        for n in range(23)
    ]
    for n in range(4):
        _add_result(
            db_session, user_b.id, trigger_element_id=9000 + n,
            created_at=base + timedelta(hours=1, minutes=n),
        )

    seen = enterprise_context(user_a)["recent_analyses"]

    assert [r.id for r in seen] == [r.id for r in list(reversed(own))[:20]]


def test_enterprise_page_filtered_list_is_scoped(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    a_row = _add_result(
        db_session, user_a.id, trigger_element_type="application",
        trigger_element_id=424242,
    )
    _add_result(
        db_session, user_b.id, trigger_element_type="application",
        trigger_element_id=424242,
    )
    query = {"element_type": "application", "element_id": 424242}

    seen_by_a = enterprise_context(user_a, query)["filtered_analyses"]
    seen_by_b = enterprise_context(user_b, query)["filtered_analyses"]

    assert [r.id for r in seen_by_a] == [a_row.id]
    assert [r.created_by_id for r in seen_by_b] == [user_b.id]
    assert a_row.id not in {r.id for r in seen_by_b}


def test_enterprise_page_filtered_list_hides_another_organisations_rows(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    _add_result(
        db_session, user_a.id, trigger_element_type="application",
        trigger_element_id=424242,
    )
    query = {"element_type": "application", "element_id": 424242}

    assert enterprise_context(user_b, query)["filtered_analyses"] == []


def test_enterprise_page_total_is_scoped(db_session, enterprise_context, two_orgs):
    _, _, user_a, user_b = two_orgs
    for _n in range(3):
        _add_result(db_session, user_a.id)
    for _n in range(5):
        _add_result(db_session, user_b.id)
    _add_result(db_session, None)

    assert enterprise_context(user_a)["total_analyses"] == 3
    assert enterprise_context(user_b)["total_analyses"] == 5


def test_enterprise_page_critical_count_is_scoped(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    _add_result(db_session, user_a.id, overall_severity="critical")
    for _n in range(4):
        _add_result(db_session, user_b.id, overall_severity="critical")
    _add_result(db_session, None, overall_severity="critical")

    assert enterprise_context(user_a)["critical_count"] == 1
    assert enterprise_context(user_b)["critical_count"] == 4


def test_enterprise_page_high_count_is_scoped(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    for _n in range(2):
        _add_result(db_session, user_a.id, overall_severity="high")
    for _n in range(6):
        _add_result(db_session, user_b.id, overall_severity="high")
    _add_result(db_session, None, overall_severity="high")

    assert enterprise_context(user_a)["high_count"] == 2
    assert enterprise_context(user_b)["high_count"] == 6


def test_enterprise_page_average_is_scoped(db_session, enterprise_context, two_orgs):
    _, _, user_a, user_b = two_orgs
    _add_result(db_session, user_a.id, affected_applications_count=2)
    _add_result(db_session, user_a.id, affected_applications_count=4)
    _add_result(db_session, user_b.id, affected_applications_count=40)
    _add_result(db_session, None, affected_applications_count=1000)

    assert enterprise_context(user_a)["avg_affected_applications"] == 3.0
    assert enterprise_context(user_b)["avg_affected_applications"] == 40.0


def test_enterprise_page_is_empty_for_an_organisation_with_no_analyses(
    db_session, enterprise_context, two_orgs
):
    _, _, user_a, user_b = two_orgs
    _add_result(
        db_session, user_a.id, overall_severity="critical",
        affected_applications_count=9,
    )
    context = enterprise_context(user_b)

    assert list(context["recent_analyses"]) == []
    assert context["total_analyses"] == 0
    assert context["critical_count"] == 0
    assert context["high_count"] == 0
    assert context["avg_affected_applications"] == 0


# --------------------------------------------------------------------------
# Writer: an analysis is recorded against the user who ran it
# --------------------------------------------------------------------------


def test_running_an_analysis_records_the_analysing_user(
    db_session, client, login_as, two_orgs
):
    """The analysis endpoint attributes the row to its caller, so the caller's
    own history shows it and no other organisation's does."""
    from app.models.traceability import ImpactAnalysisResult

    _, _, user_a, user_b = two_orgs

    login_as(client, user_a)
    response = client.post(
        "/strategic/api/impact-analysis",
        json={"element_id": 424242, "change_type": "MODIFY"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    analysis_id = response.get_json()["analysis_id"]
    assert analysis_id is not None

    stored = db_session.get(ImpactAnalysisResult, analysis_id)
    assert stored.created_by_id == user_a.id

    assert [r["id"] for r in _history(client, login_as, user_a)] == [analysis_id]
    assert _history(client, login_as, user_b) == []


def test_api_v1_analysis_records_the_analysing_user(
    db_session, client, login_as, two_orgs
):
    """The v1 endpoint runs the same service, so its results are attributed too."""
    from app.models import ArchiMateElement
    from app.models.traceability import ImpactAnalysisResult

    org_a, _, user_a, user_b = two_orgs
    element = ArchiMateElement(
        name=f"Billing {uuid.uuid4().hex[:6]}",
        type="ApplicationComponent",
        layer="application",
        organization_id=org_a.id,
    )
    db_session.add(element)
    db_session.flush()

    login_as(client, user_a)
    response = client.post(
        "/api/v1/impact/analyze",
        json={"element_id": element.id, "scenario": "retirement"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    stored = ImpactAnalysisResult.query.filter_by(
        trigger_element_id=element.id, scenario="retirement"
    ).one()
    assert stored.created_by_id == user_a.id
    assert [r["id"] for r in _history(client, login_as, user_a)] == [stored.id]
    assert _history(client, login_as, user_b) == []


def test_analysis_service_leaves_the_owner_empty_outside_a_request(
    db_session, app
):
    """Background callers have no signed-in user; the row then has no owner
    and is returned to nobody."""
    from app.models.traceability import ImpactAnalysisResult
    from app.modules.solutions_strategic.v2.services.impact_analysis_service import (
        ImpactAnalysisService,
    )

    result = ImpactAnalysisService.analyze_change_impact(element_id=424242)

    stored = db_session.get(ImpactAnalysisResult, result["analysis_id"])
    assert stored.created_by_id is None
