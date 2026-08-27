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
    assert "receipt.operation='arb.condition.transition'" in final
    assert "receipt.status='succeeded'" in final
    assert "operation_results" in final and "command_materialisations" in final


def test_cycle_and_review_expose_condition_projection_revision():
    from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem

    assert "condition_projection_revision" in ARBReviewCycle.__table__.columns
    assert "condition_projection_revision" in ARBReviewItem.__table__.columns


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
