"""Schema and database guards for canonical typed ARB decisions."""

import pytest

from app.models.mixins import TenantMixin


def test_decision_event_and_condition_schema_contract():
    from app.models.arb_decision_event import ARBCondition, ARBDecisionEvent

    assert issubclass(ARBDecisionEvent, TenantMixin)
    assert issubclass(ARBCondition, TenantMixin)
    event_columns = ARBDecisionEvent.__table__.columns
    assert {
        "review_cycle_id", "review_item_id", "outcome", "from_state", "to_state",
        "rationale", "conditions_json", "subject_type", "subject_id",
        "decision_brief_id", "solution_id", "architecture_model_id", "adr_id",
        "decision_brief_version_id", "solution_evidence_snapshot_id",
        "subject_evidence_snapshot_id", "actor_id", "command_receipt_id",
        "command_generation", "created_at",
    } <= set(event_columns.keys())
    assert event_columns["review_cycle_id"].unique
    assert event_columns["review_item_id"].unique
    condition_columns = ARBCondition.__table__.columns
    assert {
        "decision_event_id", "review_cycle_id", "review_item_id",
        "condition_number", "description", "category", "due_date",
        "blocks_execution", "status", "fulfilled_at", "fulfilled_by_id",
        "fulfilment_evidence_id", "waived_at", "waived_by_id", "waiver_reason",
        "waiver_expires_at", "compensating_control",
    } <= set(condition_columns.keys())
    checks = " ".join(
        str(item.sqltext)
        for model in (ARBDecisionEvent, ARBCondition)
        for item in model.__table__.constraints
        if item.__class__.__name__ == "CheckConstraint"
    )
    assert all(value in checks for value in (
        "decision_brief", "solution", "architecture_model", "adr",
        "blocks_execution", "pending", "length(btrim(description)) > 0",
    ))


def test_decision_schema_is_registered_for_additive_reconciliation():
    from app.commands.reconcile_schema import _TRANSFORMATION_TABLES

    assert "arb_decision_events" in _TRANSFORMATION_TABLES
    assert "arb_canonical_conditions" in _TRANSFORMATION_TABLES


def test_decision_guard_sql_binds_terminal_projection_and_command_envelopes():
    from app.models.arb_decision_event import _decision_membership_sql

    sql = _decision_membership_sql('"public"')
    assert "review.decided_by_id = NEW.actor_id" in sql
    assert "review.submitter_id <> NEW.actor_id" in sql
    assert "cycle.terminal_outcome = NEW.outcome" in sql
    assert "review.decision = NEW.outcome" in sql
    assert "'arb-decision:' || NEW.organization_id::text || ':'" in sql
    assert "receipt.status = 'succeeded'" in sql
    assert "operation_results" in sql
    assert "command_materialisations" in sql
    assert "result.object_ids::jsonb" in sql


def test_condition_guard_sql_binds_canonical_decision_membership():
    from app.models.arb_decision_event import _condition_membership_sql

    sql = _condition_membership_sql('"public"')
    assert "decision.outcome = 'approved_with_conditions'" in sql
    assert "decision.review_cycle_id = NEW.review_cycle_id" in sql
    assert "decision.review_item_id = NEW.review_item_id" in sql
    assert "decision.organization_id = NEW.organization_id" in sql


def test_reconcile_installs_decision_tables_and_enabled_guards(app, _schema):
    from app import db
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, missing, blocking = _reconcile(dry_run=False)
        assert failed == []
        assert not {"arb_decision_events", "arb_canonical_conditions"} & set(missing)
        assert not [item for item in blocking if "arb_decision" in item]
        rows = db.session.execute(db.text(
            "SELECT tgname FROM pg_trigger WHERE tgrelid IN "
            "('arb_decision_events'::regclass, 'arb_canonical_conditions'::regclass) "
            "AND NOT tgisinternal AND tgenabled = 'O'"
        )).scalars().all()
        assert set(rows) >= {
            "trg_arb_decision_event_membership", "trg_arb_decision_event_immutable",
            "trg_arb_condition_membership", "trg_arb_condition_immutable",
        }


def test_direct_sql_rejects_nonblocking_or_blank_condition(app, _schema):
    from app import db
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _reconcile(dry_run=False)
        with db.engine.begin() as connection:
            with pytest.raises(Exception, match="arb_condition"):
                connection.exec_driver_sql(
                    "INSERT INTO arb_canonical_conditions (organization_id, decision_event_id, "
                    "review_cycle_id, review_item_id, condition_number, description, "
                    "blocks_execution, status) VALUES (1, 1, 1, 1, ' ', ' ', false, 'pending')"
                )
