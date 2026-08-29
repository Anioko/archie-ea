"""The ArchiMate backbone must be provable, not assumed.

AGENTS.md states the rule plainly: "ArchiMate is the backbone, not a view. Every
backend CREATE for a motivation entity must call _sync_archimate_element() so a
matching ArchiMateElement row exists. A plain textarea is not an acceptable
substitute -- the field IS the element."

Everything a user would judge this platform on reads from that backbone:
traceability, impact analysis, line of sight, the capability lenses, the Chief
Architect workbench. If elements can be missing without anyone knowing, every one
of those features is quietly incomplete and none of them can say so.

Today the rule is enforced by a function that:

  * ends in `except Exception: return None`, and
  * is called by nine sites, none of which check the return value, and
  * has no tests at all.

So a Driver, Goal, Constraint, Requirement, Risk or Metric can commit while its
element silently does not. These tests pin the properties that make the backbone
verifiable rather than hoped-for.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def solution_owner(db_session, make_org):
    from app.models.user import User

    org = make_org("backbone")
    user = User(
        email=f"backbone-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Bea",
        last_name="Bone",
        confirmed=True,
        organization_id=org.id,
        enterprise_role="solution_architect",
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def problem(db_session, solution_owner, solution):
    """The chain a motivation row actually needs: session -> problem definition.

    SolutionDriver.problem_id is NOT NULL and points at
    solution_problem_definitions, which points at solution_analysis_sessions. The
    test builds the real chain rather than inventing a shortcut, because a fixture
    that bypasses a NOT NULL constraint proves nothing about production.
    """
    from app.models.solution_architect_models import (
        SolutionAnalysisSession,
        SolutionProblemDefinition,
    )

    # organization_id set explicitly. SolutionAnalysisSession carries TenantMixin,
    # whose organization_id is NOT NULL and is normally filled by the tenant
    # middleware's before_flush hook -- which only runs inside a request. This
    # fixture runs outside one, so it must supply it. That is the same defect this
    # module exists to fix, met here in the fixture itself.
    session = SolutionAnalysisSession(
        created_by_id=solution_owner.id,
        organization_id=solution_owner.organization_id,
        name=f"Backbone session {uuid.uuid4().hex[:6]}",
    )
    db_session.add(session)
    db_session.flush()

    definition = SolutionProblemDefinition(
        session_id=session.id,
        organization_id=solution_owner.organization_id,
        problem_description="Backbone audit fixture",
    )
    db_session.add(definition)
    db_session.flush()
    return definition


@pytest.fixture
def solution(db_session, solution_owner):
    from app.models.solution_models import Solution

    row = Solution(
        name=f"Backbone solution {uuid.uuid4().hex[:6]}",
        organization_id=solution_owner.organization_id,
        created_by_id=solution_owner.id,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ── the sync itself ──────────────────────────────────────────────────────────


def test_sync_creates_the_element_and_both_junctions(db_session, solution):
    """One call must leave the element and both junction rows consistent.

    Two junctions exist because different readers use different ones --
    SolutionArchiMateElement is what scoring queries, SolutionElement is what the
    layer views walk. A sync that writes one and not the other produces an element
    that is visible on one screen and absent from another, which is worse than one
    that is simply missing.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_element import SolutionElement
    from app.models.solution_models import SolutionArchiMateElement
    from app.modules.solutions_strategic.v2.routes.solution_phase_routes import (
        _sync_archimate_element,
    )

    element = _sync_archimate_element(
        solution.id,
        ae_type="Driver",
        ae_layer="Motivation",
        name="Regulatory pressure",
        description="SM-CR deadline",
    )
    db_session.flush()

    assert element is not None, "the sync returned None -- the backbone row was not created"
    assert element.type == "Driver"
    assert (element.layer or "").lower() == "motivation"

    assert (
        db_session.query(SolutionElement)
        .filter_by(solution_id=solution.id, archimate_element_id=element.id)
        .count()
        == 1
    ), "SolutionElement junction missing; layer views would not show this element"

    assert (
        db_session.query(SolutionArchiMateElement)
        .filter_by(solution_id=solution.id, element_id=element.id)
        .count()
        == 1
    ), "SolutionArchiMateElement junction missing; scoring queries would not see it"

    assert db_session.query(ArchiMateElement).filter_by(id=element.id).count() == 1


def test_sync_is_idempotent_on_name_and_type(db_session, solution):
    """A repeated CREATE must not fork the backbone into duplicate elements."""
    from app.modules.solutions_strategic.v2.routes.solution_phase_routes import (
        _sync_archimate_element,
    )

    first = _sync_archimate_element(
        solution.id, ae_type="Goal", ae_layer="Motivation", name="Reduce cycle time"
    )
    db_session.flush()
    second = _sync_archimate_element(
        solution.id, ae_type="Goal", ae_layer="Motivation", name="Reduce cycle time"
    )
    db_session.flush()

    assert first is not None and second is not None
    assert first.id == second.id, "a second sync created a duplicate element"


def test_sync_resolves_without_identity_map_shortcuts(db_session, solution):
    """The existing-element lookup must not use Query.get().

    AGENTS.md documents the hazard: Query.get() and Session.get() are tenant-scoped
    only on an identity-map MISS. On a hit they return the cached object with no
    SQL emitted, so do_orm_execute never runs and no tenant predicate is applied.
    In a function that resolves an element by id and hands it back to a caller,
    that is precisely the shape that can return another organisation's row.
    """
    import inspect

    from app.modules.solutions_strategic.v2.routes import solution_phase_routes

    source = inspect.getsource(solution_phase_routes._sync_archimate_element)
    assert ".query.get(" not in source and "session.get(" not in source, (
        "the sync resolves an element with Query.get()/Session.get(); use an "
        "explicit filtered query so the tenant predicate is always applied"
    )


def test_both_sync_definitions_refuse_positional_confusion():
    """Two definitions, two argument orders -- that must not be silently callable.

    solution_phase_routes takes (solution_id, ae_type, ae_layer, name);
    solution_ai_orchestrator takes (solution_id, name, element_type, layer). Calling
    either with the other's convention produces an element whose type and name are
    swapped -- a Driver called "Regulatory pressure" becomes a "Regulatory
    pressure" called "Driver". Nothing fails; the backbone is simply wrong, and
    every downstream view inherits the error.

    Keyword-only parameters make that mistake impossible to express.
    """
    import inspect

    from app.modules.solutions_strategic.v2.routes import solution_phase_routes

    signature = inspect.signature(solution_phase_routes._sync_archimate_element)
    descriptive = [
        name
        for name, param in signature.parameters.items()
        if name not in {"solution_id", "self"}
    ]
    positional = [
        name
        for name in descriptive
        if signature.parameters[name].kind
        is not inspect.Parameter.KEYWORD_ONLY
    ]
    assert not positional, (
        "these parameters can still be passed positionally and so can be "
        f"transposed against the other definition: {positional}"
    )


# ── proving completeness ─────────────────────────────────────────────────────


def test_audit_reports_a_motivation_row_with_no_element(db_session, solution, problem):
    """The audit exists because a silent miss is otherwise undetectable.

    A SolutionDriver committed without its element is a broken record by the
    platform's own rule, and no screen would ever say so. The audit is what turns
    "we assume the backbone is complete" into a number somebody can check.
    """
    from app.models.solution_architect_models import DriverType, SolutionDriver
    from app.services.archimate_backbone_audit import audit_backbone

    orphan = SolutionDriver(
        problem_id=problem.id,
        organization_id=solution.organization_id,
        name=f"Unsynced driver {uuid.uuid4().hex[:6]}",
        driver_type=DriverType.EXTERNAL,
        description="created without calling the sync",
    )
    db_session.add(orphan)
    db_session.flush()

    report = audit_backbone(organization_id=solution.organization_id)

    assert report["missing_total"] >= 1
    names = [item["name"] for item in report["missing"]]
    assert orphan.name in names, (
        "the audit did not report a motivation row that has no ArchiMate element"
    )


def test_audit_is_clean_when_the_sync_was_used(db_session, solution, problem):
    """The honest shape must report zero, or the audit is unusable."""
    from app.models.solution_architect_models import DriverType, SolutionDriver
    from app.modules.solutions_strategic.v2.routes.solution_phase_routes import (
        _sync_archimate_element,
    )
    from app.services.archimate_backbone_audit import audit_backbone

    name = f"Synced driver {uuid.uuid4().hex[:6]}"
    row = SolutionDriver(
        problem_id=problem.id,
        organization_id=solution.organization_id,
        name=name,
        driver_type=DriverType.EXTERNAL,
        description="properly synced",
    )
    db_session.add(row)
    _sync_archimate_element(
        solution.id,
        ae_type="Driver",
        ae_layer="Motivation",
        name=name,
        description="properly synced",
    )
    db_session.flush()

    report = audit_backbone(organization_id=solution.organization_id)
    assert name not in [item["name"] for item in report["missing"]]


def test_audit_is_tenant_scoped(db_session, make_org, solution):
    """An estate-wide completeness figure must not count another tenant's gaps."""
    from app.services.archimate_backbone_audit import audit_backbone

    other = make_org("backbone-other")
    report = audit_backbone(organization_id=other.id)
    assert report["missing_total"] == 0, (
        "the audit counted rows belonging to another organisation"
    )
