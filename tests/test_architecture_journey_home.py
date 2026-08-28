"""The Architecture Journey home: purpose, progress, people, evidence, decisions, risks.

`ArchitectureJourney` already existed and was already the right spine -- purpose-led,
independent of a Solution, able to end in an architecture document, a decision, a
roadmap, a programme, or no change at all. What it lacked was edges: two typed
columns (`solution_id`, `programme_id`) and nothing else, while every other record in
the repo is keyed on `solution_id`. A journey whose outcome is `architecture_only`
could not own a participant, a decision, a risk or a document.

These tests pin the edges and the home view built on them. The rule they exist to
enforce, and the one worth restating because it is the easiest to break: a count that
was not computed is `None` and renders as an em dash. It is never `0`. A journey with
no linked decisions and a journey whose decision query failed must not look identical
to a reader who is about to act on the difference.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def journey_owner(db_session, make_org):
    from app.models.user import User

    org = make_org("journey-home")
    user = User(
        email=f"journey-home-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Jo",
        last_name="Owner",
        confirmed=True,
        organization_id=org.id,
        enterprise_role="enterprise_architect",
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


def _make_journey(db_session, owner, **overrides):
    from app.models.architecture_journey import ArchitectureJourney

    journey = ArchitectureJourney(
        owner_id=owner.id,
        organization_id=owner.organization_id,
        title=overrides.pop("title", "Operating model redesign"),
        intent=overrides.pop("intent", "operating_model"),
        selected_layers=overrides.pop("selected_layers", ["motivation", "business"]),
        **overrides,
    )
    db_session.add(journey)
    db_session.flush()
    return journey


# ── the edges ────────────────────────────────────────────────────────────────


def test_journey_links_reference_records_rather_than_copying_them(db_session, journey_owner):
    """A link carries a pointer and a relation, never a copy of the record's fields.

    Copying the title of a decision onto the journey would go stale silently the
    moment someone renamed the decision, and the journey would then display a fact
    that is no longer true anywhere else in the system.
    """
    from app.models.architecture_journey_link import ArchitectureJourneyLink

    journey = _make_journey(db_session, journey_owner)
    link = ArchitectureJourneyLink(
        journey_id=journey.id,
        organization_id=journey_owner.organization_id,
        entity_type="decision",
        entity_id=4242,
        relation="informs",
        created_by_id=journey_owner.id,
    )
    db_session.add(link)
    db_session.flush()

    columns = {column.name for column in ArchitectureJourneyLink.__table__.columns}
    assert {"journey_id", "entity_type", "entity_id", "relation", "organization_id"} <= columns
    # No denormalised copies of the target record.
    assert "title" not in columns
    assert "name" not in columns
    assert "status" not in columns


def test_journey_link_entity_type_is_constrained_to_known_records(db_session, journey_owner):
    """An unconstrained string would let a typo create an edge to nothing."""
    from app.models.architecture_journey_link import JOURNEY_LINK_ENTITY_TYPES

    assert "decision" in JOURNEY_LINK_ENTITY_TYPES
    assert "risk" in JOURNEY_LINK_ENTITY_TYPES
    assert "document" in JOURNEY_LINK_ENTITY_TYPES
    assert "archimate_element" in JOURNEY_LINK_ENTITY_TYPES
    assert "work_package" in JOURNEY_LINK_ENTITY_TYPES
    assert "arb_review" in JOURNEY_LINK_ENTITY_TYPES


def test_journey_members_are_users_not_typed_in_names(db_session, journey_owner):
    """Participants are FKs. A typed-in name is fabricated data the moment it drifts."""
    from app.models.architecture_journey_link import ArchitectureJourneyMember

    journey = _make_journey(db_session, journey_owner)
    member = ArchitectureJourneyMember(
        journey_id=journey.id,
        organization_id=journey_owner.organization_id,
        user_id=journey_owner.id,
        role="business_architect",
    )
    db_session.add(member)
    db_session.flush()

    user_fk = ArchitectureJourneyMember.__table__.c.user_id.foreign_keys
    assert user_fk, "user_id must be a real foreign key to users.id"
    assert next(iter(user_fk)).target_fullname == "users.id"


def test_journey_link_and_member_tables_are_tenant_scoped(db_session):
    """A journey edge that is not tenant-scoped leaks records across organisations."""
    from app.models.architecture_journey_link import (
        ArchitectureJourneyLink,
        ArchitectureJourneyMember,
    )
    from app.models.mixins import TenantMixin

    assert issubclass(ArchitectureJourneyLink, TenantMixin)
    assert issubclass(ArchitectureJourneyMember, TenantMixin)


# ── the read model ───────────────────────────────────────────────────────────


def test_home_view_reports_none_not_zero_for_uncomputed_counts(db_session, journey_owner):
    """The central honesty rule of this screen.

    A journey with nothing linked yet is genuinely empty and reports 0. A journey
    whose counts could not be computed reports None. The two must never collapse
    into the same rendered value, because the reader acts on the difference.
    """
    from app.modules.solutions_strategic.v2.services.journey_home import (
        journey_home_view,
    )

    journey = _make_journey(db_session, journey_owner)
    view = journey_home_view(journey_id=journey.id, actor_user=journey_owner)

    assert view is not None
    # Genuinely empty, and measured as such.
    assert view["counts"]["decisions"] == 0
    assert view["counts"]["risks"] == 0
    assert view["counts"]["participants"] == 1  # the owner


def test_home_view_failure_returns_none_counts_and_never_zero(monkeypatch, db_session, journey_owner):
    """When the link query fails the screen must show em dashes, not a confident zero."""
    from app.modules.solutions_strategic.v2.services import journey_home as module

    journey = _make_journey(db_session, journey_owner)

    def _explode(*args, **kwargs):
        raise RuntimeError("link store unavailable")

    monkeypatch.setattr(module, "_load_links", _explode)

    view = module.journey_home_view(journey_id=journey.id, actor_user=journey_owner)
    assert view["degraded"] is True
    assert view["counts"]["decisions"] is None
    assert view["counts"]["risks"] is None
    assert view["counts"]["documents"] is None


def test_home_view_next_action_is_derived_from_real_state(db_session, journey_owner):
    """The next action must name something the user can actually do now."""
    from app.modules.solutions_strategic.v2.services.journey_home import (
        journey_home_view,
    )

    journey = _make_journey(db_session, journey_owner, current_stage="frame")
    view = journey_home_view(journey_id=journey.id, actor_user=journey_owner)

    next_action = view["next_action"]
    assert next_action["label"]
    assert next_action["reason"], "a next action with no reason is an instruction, not guidance"


def test_home_view_is_tenant_scoped(db_session, make_org, journey_owner):
    """A journey from another organisation must not resolve at all."""
    from app.models.user import User
    from app.modules.solutions_strategic.v2.services.journey_home import (
        journey_home_view,
    )

    other_org = make_org("journey-home-other")
    outsider = User(
        email=f"outsider-{uuid.uuid4().hex[:10]}@example.test",
        confirmed=True,
        organization_id=other_org.id,
        enterprise_role="enterprise_architect",
    )
    outsider.password = "test-password-not-secret"
    db_session.add(outsider)
    db_session.flush()

    journey = _make_journey(db_session, journey_owner)
    assert journey_home_view(journey_id=journey.id, actor_user=outsider) is None


def test_cross_org_admin_cannot_open_another_tenants_journey(
    app, db_session, make_org, journey_owner, login_as
):
    """The admin bypass must be an OWNERSHIP bypass, never a TENANCY bypass.

    ``_require_journey_owner`` waives the owner check for ``is_admin()`` so that an
    administrator can resume a colleague's journey -- which is intended, and pinned
    by test_admin_in_same_tenant_can_resume. The question this test settles is
    whether that waiver also lets an administrator of organisation A open a journey
    belonging to organisation B, since the guard's own query carries no explicit
    organisation predicate.

    It must not. The protection comes from TenantMixin's ORM-event filter rather
    than from anything visible in the guard, which is precisely why it needs a test:
    the invariant is real but invisible at the call site, so a future refactor to a
    raw query or to Session.get() would remove it silently.
    """
    from app.models.user import Role, User

    journey = _make_journey(db_session, journey_owner, title="Tenant A private journey")

    # A real Administrator: is_admin() is a permission check, not a column, so the
    # bypass only engages if the user genuinely holds ADMINISTER.
    Role.insert_roles()
    admin_role = Role.query.filter_by(name="Administrator").first()
    assert admin_role is not None, "Administrator role missing; the test would prove nothing"

    other_org = make_org("journey-admin-other")
    foreign_admin = User(
        email=f"admin-{uuid.uuid4().hex[:10]}@example.test",
        confirmed=True,
        organization_id=other_org.id,
        enterprise_role="chief_architect",
        role=admin_role,
    )
    foreign_admin.password = "test-password-not-secret"
    db_session.add(foreign_admin)
    db_session.flush()
    assert foreign_admin.is_admin(), "the admin bypass must actually be engaged"
    db_session.commit()

    client = app.test_client()
    login_as(client, foreign_admin)

    assert client.get(f"/architecture-journey/work/{journey.id}").status_code == 404, (
        "an administrator of another organisation resolved a foreign journey -- "
        "the admin bypass has become a tenancy bypass"
    )


# ── the rendered screen ──────────────────────────────────────────────────────


def _render_home(app, db_session, owner, login_as, journey):
    db_session.commit()
    client = app.test_client()
    login_as(client, owner)
    response = client.get(f"/architecture-journey/work/{journey.id}")
    assert response.status_code == 200, response.get_data(as_text=True)[:600]
    return response.get_data(as_text=True)


def test_home_has_exactly_one_heading_and_one_breadcrumb(
    app, db_session, journey_owner, login_as
):
    """One feature, one page chrome.

    This surface previously carried three page-level entry points with two
    incompatible breadcrumb ancestries, and a dead landing branch with a second
    competing <h1>. A duplicated breadcrumb is not cosmetic: it tells the reader
    two different stories about where they are in the product.
    """
    journey = _make_journey(db_session, journey_owner)
    html = _render_home(app, db_session, journey_owner, login_as, journey)

    assert html.count("<h1") == 1
    assert html.count('aria-label="Breadcrumb"') == 1


def test_home_shows_participants_decisions_risks_and_governance(
    app, db_session, journey_owner, login_as
):
    """The brief's list, and the reason the link tables exist.

    Before this wave the workspace showed purpose, stage, scope, deliverables and a
    free-text evidence list. Participants, decisions, risks and governance had
    nowhere to come from.
    """
    journey = _make_journey(db_session, journey_owner)
    html = _render_home(app, db_session, journey_owner, login_as, journey)

    for testid in (
        "journey-participants",
        "journey-decisions",
        "journey-risks",
        "journey-governance",
        "journey-next-action",
    ):
        assert f'data-testid="{testid}"' in html, f"{testid} missing from the journey home"


def test_home_renders_a_dash_not_a_zero_when_counts_are_unknown(
    app, monkeypatch, db_session, journey_owner, login_as
):
    """The honesty rule, end to end through the template.

    A journey whose link store cannot be read must not render "0 risks". A reader
    seeing 0 concludes the journey is clean; a reader seeing an em dash knows to go
    and look. The difference is the whole reason this screen exists.
    """
    from app.modules.solutions_strategic.v2.services import journey_home as module

    journey = _make_journey(db_session, journey_owner)

    def _explode(*args, **kwargs):
        raise RuntimeError("link store unavailable")

    monkeypatch.setattr(module, "_load_links", _explode)

    html = _render_home(app, db_session, journey_owner, login_as, journey)

    assert 'data-testid="journey-degraded"' in html, (
        "a degraded journey home must say so; silently showing partial data is the "
        "failure this test exists to prevent"
    )
    assert "—" in html


def test_home_states_when_no_solution_was_assumed(app, db_session, journey_owner, login_as):
    """A journey that ends in architecture only is a first-class outcome."""
    journey = _make_journey(db_session, journey_owner, outcome_type="architecture_only")
    html = _render_home(app, db_session, journey_owner, login_as, journey)

    assert 'data-testid="journey-outcome"' in html
    assert "solution" in html.lower()


def test_home_view_carries_purpose_stage_and_progress(db_session, journey_owner):
    from app.modules.solutions_strategic.v2.services.journey_home import (
        journey_home_view,
    )

    journey = _make_journey(
        db_session, journey_owner, intent="risk_and_compliance", current_stage="shape"
    )
    view = journey_home_view(journey_id=journey.id, actor_user=journey_owner)

    assert view["purpose"]["intent"] == "risk_and_compliance"
    assert view["purpose"]["label"]
    assert view["stage"]["key"] == "shape"
    assert view["stage"]["index"] == 2
    assert view["stage"]["total"] == 5
