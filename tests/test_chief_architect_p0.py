"""P0 truthfulness contract for the Chief Architect conformance roll-up.

The page must describe exactly the deterministic evidence it has, rather than
turn unavailable controls or a partial ARB queue into a clean portfolio claim.
"""

from datetime import datetime, timedelta, timezone
import re

from app import db
from app.models.organization import Organization
from app.models.user import User
from app.modules.solutions_strategic.v2.services.chief_architect_service import (
    ChiefArchitectService,
)


def _org(db_session, slug):
    org = Organization(name=f"Chief Architect {slug}", slug=f"chief-{slug}")
    db_session.add(org)
    db_session.flush()
    return org


def _solution(db_session, name):
    from app.models.solution_models import Solution

    solution = Solution(name=name)
    db_session.add(solution)
    db_session.flush()
    return solution


def _application_element(db_session, solution_id, name="Application"):
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import SolutionArchiMateElement

    element = ArchiMateElement(name=name, type="ApplicationComponent", layer="application")
    db_session.add(element)
    db_session.flush()
    db_session.add(
        SolutionArchiMateElement(
            solution_id=solution_id,
            element_id=element.id,
            layer_type="application",
            element_table="application_components",
            element_name=name,
        )
    )
    db_session.flush()


def _review_item(db_session, org, number, status, submitted_at, submitter_id, decision=None):
    from app.models.architecture_review_board import ARBReviewItem

    item = ARBReviewItem(
        organization_id=org.id,
        review_number=number,
        title=number,
        review_type="solution",
        status=status,
        submitted_at=submitted_at,
        submitter_id=submitter_id,
        decision=decision,
    )
    db_session.add(item)
    db_session.flush()
    return item


def _user(db_session, org):
    user = User(
        email=f"chief-{org.id}@example.com",
        first_name="Chief",
        last_name="Architect",
        organization_id=org.id,
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    user.password = "TestPass123!"
    db_session.add(user)
    db_session.flush()
    return user


def _visible_text(resp):
    html = resp.get_data(as_text=True)
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html))


def test_unavailable_required_control_withholds_aggregate_and_is_ranked(monkeypatch, db_session, tenant_ctx):
    """A failed review control must not produce a conformance aggregate."""
    from app.modules.solutions_strategic.v2.services.conformance_reviewer import (
        ConformanceReviewer,
    )

    org = _org(db_session, "unavailable")
    with tenant_ctx(org.id):
        solution = _solution(db_session, "Control failure")
        _application_element(db_session, solution.id)

        def unavailable_business_control(_solution_id):
            raise RuntimeError("business catalogue unavailable")

        monkeypatch.setattr(
            ConformanceReviewer,
            "_business_findings",
            staticmethod(unavailable_business_control),
        )

        synthesis = ChiefArchitectService.portfolio_synthesis()

    assert synthesis["solutions_unavailable"] == 1
    assert synthesis["avg_conformance"] is None
    assert synthesis["coverage"]["evaluated"] == 0
    assert synthesis["attention"][0]["status"] == "unavailable"
    assert "business" in synthesis["attention"][0]["reason"].lower()
    assert synthesis["attention"][0]["evidence_url"].endswith("/review-packet")


def test_arb_summary_uses_authoritative_statuses_and_tenant_scope(db_session, tenant_ctx):
    """Open, blocked, decided and SLA age come from visible ARB records only."""
    mine = _org(db_session, "arb-mine")
    other = _org(db_session, "arb-other")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with tenant_ctx(mine.id):
        mine_user = _user(db_session, mine)
        _review_item(db_session, mine, "REV-MINE-OPEN", "submitted", now - timedelta(days=24), mine_user.id)
        _review_item(db_session, mine, "REV-MINE-BLOCKED", "pending_information", now - timedelta(days=7), mine_user.id)
        _review_item(db_session, mine, "REV-MINE-DECIDED", "approved", now - timedelta(days=4), mine_user.id, "approved")
    with tenant_ctx(other.id):
        other_user = _user(db_session, other)
        _review_item(db_session, other, "REV-OTHER-OPEN", "under_review", now - timedelta(days=90), other_user.id)

    with tenant_ctx(mine.id):
        synthesis = ChiefArchitectService.portfolio_synthesis()

    assert synthesis["arb"] == {
        "open": 2,
        "decided": 1,
        "blocked_or_not_ready": 1,
        "oldest_open_age_days": 24,
        "sla_days": 21,
    }


def test_rollup_route_communicates_its_actual_scope(db_session, client, login_as, tenant_ctx):
    """The rendered route must not describe a solution roll-up as enterprise health."""
    org = _org(db_session, "route")
    with tenant_ctx(org.id):
        user = _user(db_session, org)
    login_as(client, user)

    response = client.get("/solutions/architect-synthesis")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "Solution Conformance Roll-up" in text
    assert "As of" in text
    assert "Portfolio-wide architecture health" not in text
    assert "across all reviews" not in text
