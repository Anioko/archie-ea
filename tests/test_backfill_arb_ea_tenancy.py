"""Wave 4 Phase A Task 2: backfill-arb-ea-tenancy derives each row's
organization from its already-scoped FK parent — never guessed, because a
wrong assignment here hands one tenant's governance record to another.

Scenario: ARBReviewItem submitted in org A, an EAWorkflowInstance started in
org B, a child comment/step under each, and an orphan row (no derivable FK
org) — all seeded with organization_id NULL, as they would be on an existing
database before this command has ever run.
"""

import uuid

import pytest


def _user(db_session, org, label="u"):
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="Test",
        last_name=label,
        organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _review_item(db_session, submitter, arb_session_id=None, solution_id=None):
    from app.models.architecture_review_board import ARBReviewItem

    suffix = uuid.uuid4().hex[:8]
    item = ARBReviewItem(
        review_number=f"REV-TEST-{suffix}",
        title="Test review item",
        review_type="architecture_change",
        submitter_id=submitter.id,
        arb_session_id=arb_session_id,
        solution_id=solution_id,
        organization_id=None,
    )
    db_session.add(item)
    db_session.flush()
    return item


def _run(dry_run=False, org_id=None):
    from app.commands.backfill_arb_ea_tenancy import run_backfill

    return {s["table"]: s for s in run_backfill(dry_run=dry_run, org_id=org_id)}


@pytest.fixture
def two_orgs(db_session, make_org):
    org_a = make_org("wave4-a")
    org_b = make_org("wave4-b")
    return org_a, org_b


def test_review_item_derives_org_from_submitter(db_session, two_orgs):
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "sub")
    item = _review_item(db_session, user_a)
    db_session.commit()

    assert item.organization_id is None  # precondition: NULL before backfill

    stats = _run()
    db_session.refresh(item)

    assert item.organization_id == org_a.id
    assert stats["arb_review_items"]["backfilled"] >= 1
    assert stats["arb_review_items"]["orphan"] == 0


def test_review_comment_derives_org_from_parent_review_item(db_session, two_orgs):
    from app.models.architecture_review_board import ARBReviewComment

    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "sub")
    item = _review_item(db_session, user_a)
    comment = ARBReviewComment(
        review_item_id=item.id,
        user_id=user_a.id,
        content="a comment",
        organization_id=None,
    )
    db_session.add(comment)
    db_session.commit()

    _run()
    db_session.refresh(comment)

    assert comment.organization_id == org_a.id


def test_workflow_instance_derives_org_from_started_by(db_session, two_orgs):
    from app.models.workflow_models import EAWorkflowDefinition, EAWorkflowInstance

    _org_a, org_b = two_orgs
    user_b = _user(db_session, org_b, "starter")

    defn = EAWorkflowDefinition(
        workflow_code=f"WF-{uuid.uuid4().hex[:8]}",
        workflow_name="Test workflow",
        workflow_category="architecture",
        steps=[{"id": "step1"}],
        organization_id=None,
    )
    db_session.add(defn)
    db_session.flush()

    instance = EAWorkflowInstance(
        instance_code=f"INST-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=defn.id,
        started_by_id=user_b.id,
        organization_id=None,
    )
    db_session.add(instance)
    db_session.commit()

    stats = _run()
    db_session.refresh(instance)

    assert instance.organization_id == org_b.id
    assert stats["ea_workflow_instances"]["orphan"] == 0


def test_step_execution_derives_org_from_parent_instance(db_session, two_orgs):
    from app.models.workflow_models import (
        EAWorkflowDefinition,
        EAWorkflowInstance,
        EAWorkflowStepExecution,
    )

    _org_a, org_b = two_orgs
    user_b = _user(db_session, org_b, "starter")

    defn = EAWorkflowDefinition(
        workflow_code=f"WF-{uuid.uuid4().hex[:8]}",
        workflow_name="Test workflow",
        workflow_category="architecture",
        steps=[{"id": "step1"}],
        organization_id=None,
    )
    db_session.add(defn)
    db_session.flush()

    instance = EAWorkflowInstance(
        instance_code=f"INST-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=defn.id,
        started_by_id=user_b.id,
        organization_id=None,
    )
    db_session.add(instance)
    db_session.flush()

    step = EAWorkflowStepExecution(
        instance_id=instance.id,
        step_id="step1",
        organization_id=None,
    )
    db_session.add(step)
    db_session.commit()

    _run()
    db_session.refresh(step)

    assert step.organization_id == org_b.id


def test_orphan_row_reported_and_left_null_without_org_id(db_session, two_orgs):
    """ARBGovernanceStandard with no owner has no org-bearing FK to derive
    from — it must be reported as an orphan and left NULL, not guessed."""
    from app.models.architecture_review_board import ARBGovernanceStandard

    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:8]}",
        name="Orphan standard",
        owner_id=None,
        organization_id=None,
    )
    db_session.add(standard)
    db_session.commit()

    stats = _run()
    db_session.refresh(standard)

    assert standard.organization_id is None, "an orphan row must never be guessed an org"
    assert stats["arb_governance_standards"]["orphan"] >= 1
    assert stats["arb_governance_standards"]["backfilled"] == 0


def test_workflow_stage_is_always_orphan(db_session):
    """ARBWorkflowStage has no org-bearing FK at all — it must always be
    reported as an orphan, never silently assigned an org."""
    from app.models.architecture_review_board import ARBWorkflowStage

    stage = ARBWorkflowStage(
        code=f"stage-{uuid.uuid4().hex[:8]}",
        name="Test Stage",
        organization_id=None,
    )
    db_session.add(stage)
    db_session.commit()

    stats = _run()
    db_session.refresh(stage)

    assert stage.organization_id is None
    assert stats["arb_workflow_stages"]["orphan"] >= 1


def test_dry_run_does_not_write(db_session, two_orgs):
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "sub")
    item = _review_item(db_session, user_a)
    db_session.commit()

    stats = _run(dry_run=True)

    db_session.refresh(item)
    assert item.organization_id is None, "dry-run must not write"
    assert stats["arb_review_items"]["derivable"] >= 1


def test_backfill_is_idempotent(db_session, two_orgs):
    """Running twice must not change a row that is already backfilled, and
    must not error re-deriving rows whose org is already set."""
    org_a, _org_b = two_orgs
    user_a = _user(db_session, org_a, "sub")
    item = _review_item(db_session, user_a)
    db_session.commit()

    _run()
    db_session.refresh(item)
    first_org = item.organization_id
    assert first_org == org_a.id

    stats_second = _run()
    db_session.refresh(item)

    assert item.organization_id == first_org, "idempotent re-run must not change an already-set org"
    # Nothing left NULL for this table on the second pass from this row.
    assert stats_second["arb_review_items"]["null"] == 0 or (
        stats_second["arb_review_items"]["null"] > 0
        and stats_second["arb_review_items"]["backfilled"] == 0
    )


def test_orphans_assigned_with_org_id_flag(db_session, two_orgs):
    from app.models.architecture_review_board import ARBGovernanceStandard

    org_a, _org_b = two_orgs
    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:8]}",
        name="Orphan standard",
        owner_id=None,
        organization_id=None,
    )
    db_session.add(standard)
    db_session.commit()

    stats = _run(org_id=org_a.id)
    db_session.refresh(standard)

    assert standard.organization_id == org_a.id
    assert stats["arb_governance_standards"]["assigned_orphans"] >= 1
    assert stats["arb_governance_standards"]["orphan"] == 0


def test_cli_exits_nonzero_when_orphans_remain_without_org_id(db_session, two_orgs, app):
    """The deploy runbook gates Phase B on 0 orphans — the CLI must fail loudly."""
    from app.models.architecture_review_board import ARBGovernanceStandard

    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:8]}",
        name="Orphan standard",
        owner_id=None,
        organization_id=None,
    )
    db_session.add(standard)
    db_session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["backfill-arb-ea-tenancy"])

    assert result.exit_code != 0, "must exit non-zero when orphans remain and --org-id is absent"
