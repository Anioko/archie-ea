"""Wave 4 Phase A Task 2: backfill-arb-ea-tenancy derives each row's
organization from its already-scoped FK parent — never guessed, because a
wrong assignment here hands one tenant's governance record to another.

Scenario: ARBReviewItem submitted in org A, an EAWorkflowInstance started in
org B, a child comment/step under each, and an orphan row (no derivable FK
org) — all seeded with organization_id NULL, as they would be on an existing
database before this command has ever run.

Three of the 14 models are GLOBAL_REFERENCE — shared catalog/config data
(globally-unique code, seeded from DEFAULT_* constants, never queried scoped
to an org): arb_governance_standards, arb_workflow_stages,
ea_workflow_definitions. Their NULL rows are the correct, permanent state,
not an unresolved backfill — this file asserts they are reported separately
("global", not "orphan"), never derived/written, never touched by --org-id,
and never trip the exit-nonzero gate. That gate is reserved for genuinely
per-tenant rows (e.g. an EAWorkflowInstance with no started_by_id, now that
its workflow_definition_id fallback is permanently NULL) so a deploy runbook
can gate Phase B on it without an operator being forced to stamp a bogus org
onto a shared catalog just to make the command exit 0.
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


def _workflow_definition(db_session):
    """A GLOBAL_REFERENCE definition — organization_id stays NULL forever."""
    from app.models.workflow_models import EAWorkflowDefinition

    defn = EAWorkflowDefinition(
        workflow_code=f"WF-{uuid.uuid4().hex[:8]}",
        workflow_name="Test workflow",
        workflow_category="architecture",
        steps=[{"id": "step1"}],
        organization_id=None,
    )
    db_session.add(defn)
    db_session.flush()
    return defn


def _run(dry_run=False, org_id=None):
    from app.commands.backfill_arb_ea_tenancy import run_backfill

    return {s["table"]: s for s in run_backfill(dry_run=dry_run, org_id=org_id)}


def _clear_preexisting_genuine_orphans(db_session):
    """Delete any NULL-org rows in the 11 per-tenant tables before a test that
    asserts an exact exit code against the *whole* table (not just the row(s)
    this test adds).

    The shared TEST_DATABASE_URL is long-lived and `db_session`'s
    rollback-on-teardown isolation does not appear to hold across every prior
    run of this suite in this environment (organizations alone number in the
    thousands) — a pre-existing test-infrastructure characteristic, not
    something this command introduces. This command scans whole tables, not a
    single org, so an "exit 0" assertion needs the per-tenant tables free of
    leftover genuine orphans first. Scoped to TEST_DATABASE_URL only; never
    runs against production.
    """
    from sqlalchemy import text

    from app.commands.backfill_arb_ea_tenancy import GLOBAL_REFERENCE, MODEL_SPECS

    for table, _subquery in MODEL_SPECS:
        if table in GLOBAL_REFERENCE:
            continue
        db_session.execute(text(f'DELETE FROM "{table}" WHERE organization_id IS NULL'))
    db_session.commit()


@pytest.fixture(autouse=True)
def _clean_baseline(db_session):
    """Every test in this module asserts exact per-model counts (``orphan ==
    0``, an exit code against the whole table). This command scans whole
    tables, not a single org, so those assertions need a clean starting
    point regardless of what earlier test runs against this shared,
    long-lived TEST_DATABASE_URL left behind — see
    `_clear_preexisting_genuine_orphans`'s docstring."""
    _clear_preexisting_genuine_orphans(db_session)


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
    from app.models.workflow_models import EAWorkflowInstance

    _org_a, org_b = two_orgs
    user_b = _user(db_session, org_b, "starter")
    defn = _workflow_definition(db_session)

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
    db_session.refresh(defn)

    assert instance.organization_id == org_b.id
    assert stats["ea_workflow_instances"]["orphan"] == 0
    # The definition is GLOBAL_REFERENCE: the instance's org came from
    # started_by_id, not from the (permanently NULL) definition.
    assert defn.organization_id is None


def test_step_execution_derives_org_from_parent_instance(db_session, two_orgs):
    from app.models.workflow_models import EAWorkflowInstance, EAWorkflowStepExecution

    _org_a, org_b = two_orgs
    user_b = _user(db_session, org_b, "starter")
    defn = _workflow_definition(db_session)

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


def test_genuine_orphan_reported_and_left_null_without_org_id(db_session):
    """An EAWorkflowInstance with no started_by_id (scheduled/API-triggered)
    and only a GLOBAL_REFERENCE definition to fall back on has no derivable
    organization — a genuine per-tenant orphan. It must be reported as
    'orphan' (not 'global') and left NULL, not guessed."""
    from app.models.workflow_models import EAWorkflowInstance

    defn = _workflow_definition(db_session)
    instance = EAWorkflowInstance(
        instance_code=f"INST-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=defn.id,
        started_by_id=None,
        triggered_by="scheduled",
        organization_id=None,
    )
    db_session.add(instance)
    db_session.commit()

    stats = _run()
    db_session.refresh(instance)

    assert instance.organization_id is None, "a genuine orphan must never be guessed an org"
    assert stats["ea_workflow_instances"]["orphan"] >= 1
    assert stats["ea_workflow_instances"]["backfilled"] == 0


def _stage(db_session):
    from app.models.architecture_review_board import ARBWorkflowStage

    return ARBWorkflowStage(
        code=f"stage-{uuid.uuid4().hex[:8]}", name="Test Stage", organization_id=None
    )


def _standard(db_session):
    from app.models.architecture_review_board import ARBGovernanceStandard

    return ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:8]}",
        name="Shared standard",
        owner_id=None,
        organization_id=None,
    )


@pytest.mark.parametrize(
    "table,build",
    [
        ("arb_workflow_stages", _stage),
        ("arb_governance_standards", _standard),
    ],
)
def test_global_reference_rows_reported_as_global_not_orphan(db_session, table, build):
    """GLOBAL_REFERENCE tables' NULL rows are the correct, permanent state:
    reported under 'global', never 'orphan', and never written to."""
    row = build(db_session)
    db_session.add(row)
    db_session.commit()

    stats = _run()
    db_session.refresh(row)

    assert row.organization_id is None
    assert stats[table]["global"] >= 1
    assert stats[table]["orphan"] == 0, "a global-reference row must never count as an orphan"
    assert stats[table]["backfilled"] == 0


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


def test_genuine_orphans_assigned_with_org_id_flag(db_session, two_orgs):
    from app.models.workflow_models import EAWorkflowInstance

    org_a, _org_b = two_orgs
    defn = _workflow_definition(db_session)
    instance = EAWorkflowInstance(
        instance_code=f"INST-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=defn.id,
        started_by_id=None,
        triggered_by="scheduled",
        organization_id=None,
    )
    db_session.add(instance)
    db_session.commit()

    stats = _run(org_id=org_a.id)
    db_session.refresh(instance)

    assert instance.organization_id == org_a.id
    assert stats["ea_workflow_instances"]["assigned_orphans"] >= 1
    assert stats["ea_workflow_instances"]["orphan"] == 0


def test_global_reference_never_assigned_by_org_id(db_session, two_orgs):
    """--org-id is for genuine orphans only. A GLOBAL_REFERENCE row must stay
    NULL even when --org-id is given — stamping an org onto a shared catalog
    would be exactly the wrong-tenant assignment this command guards against."""
    from app.models.architecture_review_board import ARBGovernanceStandard

    org_a, _org_b = two_orgs
    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:8]}",
        name="Shared standard",
        owner_id=None,
        organization_id=None,
    )
    db_session.add(standard)
    db_session.commit()

    stats = _run(org_id=org_a.id)
    db_session.refresh(standard)

    assert standard.organization_id is None, "--org-id must never touch a GLOBAL_REFERENCE row"
    assert stats["arb_governance_standards"]["assigned_orphans"] == 0
    assert stats["arb_governance_standards"]["global"] >= 1


def test_cli_exits_nonzero_when_genuine_orphans_remain_without_org_id(db_session, app):
    """The deploy runbook gates Phase B on 0 genuine orphans — the CLI must
    fail loudly when a per-tenant row failed to derive."""
    from app.models.workflow_models import EAWorkflowInstance

    defn = _workflow_definition(db_session)
    instance = EAWorkflowInstance(
        instance_code=f"INST-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=defn.id,
        started_by_id=None,
        triggered_by="scheduled",
        organization_id=None,
    )
    db_session.add(instance)
    db_session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["backfill-arb-ea-tenancy"])

    assert result.exit_code != 0, "must exit non-zero when a genuine orphan remains and --org-id is absent"


def test_cli_does_not_exit_nonzero_for_global_reference_rows_alone(db_session, app):
    """A GLOBAL_REFERENCE row with no org is expected and permanent — it must
    NOT force a deploy operator to pass --org-id (which would stamp a bogus
    org onto the shared catalog just to make the command exit 0)."""
    from app.models.architecture_review_board import ARBWorkflowStage

    stage = ARBWorkflowStage(
        code=f"stage-{uuid.uuid4().hex[:8]}", name="Test Stage", organization_id=None
    )
    db_session.add(stage)
    db_session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["backfill-arb-ea-tenancy"])

    assert result.exit_code == 0, (
        f"a global-reference-only NULL must not trip the exit-nonzero gate: {result.output}"
    )
