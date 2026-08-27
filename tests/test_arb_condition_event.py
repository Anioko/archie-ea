"""C3a canonical ARB condition lifecycle schema contracts."""

from app.models.mixins import TenantMixin


def test_condition_lifecycle_schema_is_additive_and_revisioned():
    from app.models.arb_decision_event import ARBCondition

    columns = ARBCondition.__table__.columns
    assert {
        "revision", "responsible_id", "submitted_evidence_id",
        "evidence_submitted_by_id", "evidence_submitted_at", "verified_by_id",
        "verified_at", "waiver_prior_status", "waiver_scope_json",
    } <= set(columns.keys())
    checks = " ".join(
        str(item.sqltext) for item in ARBCondition.__table__.constraints
        if item.__class__.__name__ == "CheckConstraint"
    )
    assert "evidence_submitted" in checks
    assert "revision > 0" in checks
    assert "waiver_prior_status" in checks
    assert "waiver_scope_json" in checks


def test_condition_event_is_tenant_scoped_typed_and_command_fenced():
    from app.models.arb_condition_event import ARBConditionEvent

    assert issubclass(ARBConditionEvent, TenantMixin)
    assert {
        "condition_id", "review_cycle_id", "review_item_id", "subject_type",
        "subject_id", "from_state", "to_state", "event_type", "condition_revision",
        "submitted_evidence_id", "waiver_scope_json",
        "projection_status", "projection_revision", "actor_id",
        "command_receipt_id", "command_generation", "created_at",
    } <= set(ARBConditionEvent.__table__.columns.keys())


def test_condition_event_guards_prove_source_final_state_and_exact_operation():
    from app.models.arb_condition_event import (
        _condition_event_final_sql,
        _condition_event_source_sql,
    )

    source = _condition_event_source_sql('"public"')
    final = _condition_event_final_sql('"public"')
    assert "condition.status=NEW.from_state" in source
    assert "condition.revision + 1 = NEW.condition_revision" in source
    assert "condition.status=NEW.to_state" in final
    assert "condition.revision=NEW.condition_revision" in final
    assert "WHEN 'submit_evidence' THEN 'arb.condition.evidence.submit'" in final
    assert "WHEN 'verify' THEN 'arb.condition.evidence.verify'" in final
    assert "WHEN 'waive' THEN 'arb.condition.waive'" in final
    assert "WHEN 'waiver_expired' THEN 'arb.condition.waiver.expire'" in final
    assert "receipt.status='succeeded'" in final
    assert "operation_results" in final and "command_materialisations" in final


def test_cycle_and_review_expose_condition_projection_revision():
    from app.models.architecture_review_board import (
        ARBReviewCycle,
        ARBReviewItem,
        _arb_history_function_sql,
    )

    assert "condition_projection_revision" in ARBReviewCycle.__table__.columns
    assert "condition_projection_revision" in ARBReviewItem.__table__.columns
    sql = _arb_history_function_sql('"public"')
    assert "FROM arb_condition_events condition_event" in sql
    assert "condition_event.projection_status = NEW.status" in sql
    assert "condition_event.projection_revision" in sql


def test_arb_cross_table_constraints_install_after_metadata_create():
    from sqlalchemy import event
    from app import db
    from app.models.architecture_review_board import _install_arb_cycle_constraints

    assert event.contains(db.metadata, "after_create", _install_arb_cycle_constraints)


def test_reconcile_registers_condition_event_table():
    from app.commands.reconcile_schema import _TRANSFORMATION_TABLES

    assert "arb_condition_events" in _TRANSFORMATION_TABLES


def test_reconcile_installs_condition_event_guards(app, _schema):
    from app import db
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, missing, _blocking = _reconcile(dry_run=False)
        assert failed == []
        assert "arb_condition_events" not in missing
        names = db.session.execute(db.text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid='arb_condition_events'::regclass "
            "AND NOT tgisinternal AND tgenabled='O'"
        )).scalars().all()
        assert set(names) >= {
            "trg_arb_condition_event_source", "trg_arb_condition_event_final",
            "trg_arb_condition_event_immutable",
        }


def test_condition_reconcile_sql_converges_revision_check_and_evidence_fks():
    from app.models.arb_decision_event import _condition_reconcile_sql

    sql = _condition_reconcile_sql('"public"')
    assert "UPDATE \"public\".arb_canonical_conditions SET revision = 1" in sql
    assert "ALTER COLUMN revision SET DEFAULT 1" in sql
    assert "ALTER COLUMN revision SET NOT NULL" in sql
    assert "ck_arb_condition_lifecycle" in sql and "VALIDATE CONSTRAINT" in sql
    assert "fk_arb_condition_submitted_evidence" in sql
    assert "fk_arb_condition_fulfilment_evidence" in sql


def test_final_guard_binds_typed_evidence_projection_and_actor_semantics():
    from app.models.arb_condition_event import _condition_event_final_sql

    sql = _condition_event_final_sql('"public"')
    assert "decision.subject_type=NEW.subject_type" in sql
    assert "cycle.status=NEW.projection_status" in sql
    assert "review.status=NEW.projection_status" in sql
    assert "cycle.condition_projection_revision=NEW.projection_revision" in sql
    assert "review.condition_projection_revision=NEW.projection_revision" in sql
    assert "evidence.condition_id=NEW.condition_id" in sql
    assert "submission_event.event_type='submit_evidence'" in sql
    assert "submission_event.condition_revision=evidence.condition_revision + 1" in sql
    assert "submission_event.condition_revision<NEW.condition_revision" in sql
    assert "submission_event.submitted_evidence_id=evidence.id" in sql
    assert "condition.evidence_submitted_by_id=NEW.actor_id" in sql
    assert "condition.verified_by_id=NEW.actor_id" in sql
    assert "condition.waived_by_id=NEW.actor_id" in sql
    assert "evidence.organization_id=NEW.organization_id" in sql
    assert "evidence.decision_brief_id IS NOT DISTINCT FROM decision.decision_brief_id" in sql
    assert "evidence.solution_id IS NOT DISTINCT FROM decision.solution_id" in sql
    assert "condition.fulfilment_evidence_id=evidence.id" in sql
    assert "condition.submitted_evidence_id=evidence.id" in sql
    assert "condition.evidence_submitted_by_id<>NEW.actor_id" in sql
    assert "review.submitter_id<>NEW.actor_id" in sql


def test_verify_guard_rejects_cross_scope_substitution_and_same_actor():
    from app.models.arb_condition_event import _condition_event_final_sql

    sql = _condition_event_final_sql('"public"')
    required = (
        "evidence.condition_id=NEW.condition_id",
        "evidence.decision_event_id=NEW.decision_event_id",
        "evidence.review_cycle_id=NEW.review_cycle_id",
        "evidence.review_item_id=NEW.review_item_id",
        "submission_event.condition_revision=evidence.condition_revision + 1",
        "submission_event.condition_revision<NEW.condition_revision",
        "submission_event.submitted_evidence_id=evidence.id",
        "condition.submitted_evidence_id=NEW.submitted_evidence_id",
        "condition.fulfilment_evidence_id=NEW.submitted_evidence_id",
        "condition.evidence_submitted_by_id<>NEW.actor_id",
    )
    assert all(predicate in sql for predicate in required)


def test_verify_uses_prior_submission_event_not_adjacent_evidence_revision():
    """Waive/expiry revisions may intervene without changing immutable evidence."""
    from app.models.arb_condition_event import _condition_event_final_sql

    sql = _condition_event_final_sql('"public"')
    assert "submission_event.condition_revision=evidence.condition_revision + 1" in sql
    assert "submission_event.condition_revision<NEW.condition_revision" in sql


def test_expiry_uses_immutable_waiver_event_and_cleared_final_projection():
    from app.models.arb_condition_event import _condition_event_final_sql

    sql = _condition_event_final_sql('"public"')
    assert "waiver_event.event_type='waive'" in sql
    assert "waiver_event.waiver_scope_json::jsonb ->> 'prior_status'=NEW.to_state" in sql
    assert "condition.waiver_prior_status IS NULL" in sql
    assert "condition.waiver_scope_json IS NULL" in sql
