"""Canonical immutable typed ARB decisions and execution-blocking conditions."""

from sqlalchemy import event, inspect

from app import db
from app.models.mixins import TenantMixin


_TYPED_SHAPE = (
    "((subject_type = 'decision_brief' AND subject_id = decision_brief_id "
    "AND decision_brief_id IS NOT NULL AND decision_brief_version_id IS NOT NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL AND subject_evidence_snapshot_id IS NULL) OR "
    "(subject_type = 'solution' AND subject_id = solution_id AND solution_id IS NOT NULL "
    "AND solution_evidence_snapshot_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NULL AND decision_brief_version_id IS NULL "
    "AND subject_evidence_snapshot_id IS NULL) OR "
    "(subject_type = 'architecture_model' AND subject_id = architecture_model_id "
    "AND architecture_model_id IS NOT NULL AND subject_evidence_snapshot_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND solution_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL AND solution_evidence_snapshot_id IS NULL) OR "
    "(subject_type = 'adr' AND subject_id = adr_id AND adr_id IS NOT NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL "
    "AND decision_brief_version_id IS NULL AND solution_evidence_snapshot_id IS NULL))"
)


class ARBDecisionEvent(TenantMixin, db.Model):
    __tablename__ = "arb_decision_events"

    id = db.Column(db.Integer, primary_key=True)
    review_cycle_id = db.Column(db.Integer, db.ForeignKey("arb_review_cycles.id", ondelete="RESTRICT"), nullable=False, unique=True)
    review_item_id = db.Column(db.Integer, db.ForeignKey("arb_review_items.id", ondelete="RESTRICT"), nullable=False, unique=True)
    outcome = db.Column(db.String(40), nullable=False)
    from_state = db.Column(db.String(40), nullable=False)
    to_state = db.Column(db.String(40), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    conditions_json = db.Column(db.JSON, nullable=False, default=list, server_default=db.text("'[]'::json"))
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    decision_brief_id = db.Column(db.Integer, db.ForeignKey("decision_briefs.id", ondelete="RESTRICT"))
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id", ondelete="RESTRICT"))
    architecture_model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id", ondelete="RESTRICT"))
    adr_id = db.Column(db.Integer, db.ForeignKey("architecture_decision_records.id", ondelete="RESTRICT"))
    decision_brief_version_id = db.Column(db.Integer, db.ForeignKey("decision_brief_versions.id", ondelete="RESTRICT"))
    solution_evidence_snapshot_id = db.Column(db.Integer, db.ForeignKey("arb_submission_evidence_snapshots.id", ondelete="RESTRICT"))
    subject_evidence_snapshot_id = db.Column(db.Integer, db.ForeignKey("arb_subject_evidence_snapshots.id", ondelete="RESTRICT"))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    command_receipt_id = db.Column(db.Integer, db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"), nullable=False, unique=True)
    command_generation = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.CheckConstraint(_TYPED_SHAPE, name="ck_arb_decision_event_typed_shape"),
        db.CheckConstraint("outcome IN ('approved','approved_with_conditions','rejected','deferred','returned_for_evidence','returned_for_options','withdrawn') AND to_state = outcome", name="ck_arb_decision_event_outcome"),
        db.CheckConstraint("length(btrim(rationale)) > 0 AND command_generation > 0", name="ck_arb_decision_event_required"),
        db.CheckConstraint("json_typeof(conditions_json) = 'array' AND ((outcome = 'approved_with_conditions' AND json_array_length(conditions_json) > 0) OR (outcome <> 'approved_with_conditions' AND json_array_length(conditions_json) = 0))", name="ck_arb_decision_event_conditions"),
    )


class ARBCondition(TenantMixin, db.Model):
    __tablename__ = "arb_canonical_conditions"

    id = db.Column(db.Integer, primary_key=True)
    decision_event_id = db.Column(db.Integer, db.ForeignKey("arb_decision_events.id", ondelete="RESTRICT"), nullable=False)
    review_cycle_id = db.Column(db.Integer, db.ForeignKey("arb_review_cycles.id", ondelete="RESTRICT"), nullable=False)
    review_item_id = db.Column(db.Integer, db.ForeignKey("arb_review_items.id", ondelete="RESTRICT"), nullable=False)
    condition_number = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80))
    due_date = db.Column(db.Date)
    blocks_execution = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    status = db.Column(db.String(30), nullable=False, default="pending", server_default="pending")
    fulfilled_at = db.Column(db.DateTime(timezone=True))
    fulfilled_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    fulfilment_evidence_id = db.Column(db.Integer, db.ForeignKey("evidence_records.id", ondelete="RESTRICT"))
    waived_at = db.Column(db.DateTime(timezone=True))
    waived_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"))
    waiver_reason = db.Column(db.Text)
    waiver_expires_at = db.Column(db.DateTime(timezone=True))
    compensating_control = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("organization_id", "review_cycle_id", "condition_number", name="uq_arb_condition_number"),
        db.CheckConstraint("length(btrim(condition_number)) > 0 AND length(btrim(description)) > 0", name="ck_arb_condition_terms"),
        db.CheckConstraint("blocks_execution IS TRUE", name="ck_arb_condition_blocks_execution"),
        db.CheckConstraint("status IN ('pending','fulfilled','waived')", name="ck_arb_condition_status"),
    )


def _decision_membership_sql(schema):
    return f"""
CREATE OR REPLACE FUNCTION {schema}.archie_validate_arb_decision_event() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,{schema} AS $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM arb_review_cycles cycle JOIN arb_review_items review
 ON review.id=NEW.review_item_id AND review.review_cycle_id=cycle.id
 WHERE cycle.id=NEW.review_cycle_id AND cycle.organization_id=NEW.organization_id
 AND review.organization_id=NEW.organization_id AND cycle.status=NEW.outcome
 AND cycle.terminal_outcome = NEW.outcome AND cycle.closed_at IS NOT NULL
 AND review.status=NEW.outcome AND review.decision = NEW.outcome
 AND review.decided_by_id = NEW.actor_id AND review.submitter_id <> NEW.actor_id
 AND review.decision_rationale=NEW.rationale AND cycle.subject_type=NEW.subject_type
 AND cycle.subject_id=NEW.subject_id AND review.subject_type=NEW.subject_type
 AND review.subject_id=NEW.subject_id AND cycle.decision_brief_id IS NOT DISTINCT FROM NEW.decision_brief_id
 AND review.decision_brief_id IS NOT DISTINCT FROM NEW.decision_brief_id
 AND cycle.solution_id IS NOT DISTINCT FROM NEW.solution_id AND review.solution_id IS NOT DISTINCT FROM NEW.solution_id
 AND cycle.architecture_model_id IS NOT DISTINCT FROM NEW.architecture_model_id AND review.architecture_model_id IS NOT DISTINCT FROM NEW.architecture_model_id
 AND cycle.adr_id IS NOT DISTINCT FROM NEW.adr_id AND review.adr_id IS NOT DISTINCT FROM NEW.adr_id
 AND cycle.decision_brief_version_id IS NOT DISTINCT FROM NEW.decision_brief_version_id AND review.decision_brief_version_id IS NOT DISTINCT FROM NEW.decision_brief_version_id
 AND cycle.solution_evidence_snapshot_id IS NOT DISTINCT FROM NEW.solution_evidence_snapshot_id AND review.solution_evidence_snapshot_id IS NOT DISTINCT FROM NEW.solution_evidence_snapshot_id
 AND cycle.subject_evidence_snapshot_id IS NOT DISTINCT FROM NEW.subject_evidence_snapshot_id AND review.subject_evidence_snapshot_id IS NOT DISTINCT FROM NEW.subject_evidence_snapshot_id)
 THEN RAISE EXCEPTION 'ARB decision projection, separation, or typed membership is invalid' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS (SELECT 1 FROM command_idempotency_records receipt
 JOIN operation_results result ON result.id=receipt.operation_result_id AND result.receipt_id=receipt.id
 JOIN command_materialisations materialisation ON materialisation.receipt_id=receipt.id
 WHERE receipt.id=NEW.command_receipt_id AND receipt.organization_id=NEW.organization_id
 AND receipt.actor_id=NEW.actor_id AND receipt.operation='arb.decision'
 AND receipt.natural_key='arb-decision:' || NEW.organization_id::text || ':' || NEW.review_cycle_id::text
 AND receipt.status = 'succeeded' AND receipt.completed_at IS NOT NULL
 AND receipt.lease_generation=NEW.command_generation AND result.organization_id=NEW.organization_id
 AND result.actor_id=NEW.actor_id AND result.operation=receipt.operation
 AND result.natural_key=receipt.natural_key AND result.request_digest=receipt.request_digest
 AND result.receipt_generation=NEW.command_generation
 AND materialisation.organization_id=NEW.organization_id AND materialisation.actor_id=NEW.actor_id
 AND materialisation.operation=receipt.operation AND materialisation.natural_key=receipt.natural_key
 AND materialisation.request_digest=receipt.request_digest AND materialisation.receipt_generation=NEW.command_generation
 AND result.object_ids::jsonb @> jsonb_build_object('review_cycle_id',NEW.review_cycle_id,'review_item_id',NEW.review_item_id,'decision_event_id',NEW.id)
 AND materialisation.object_ids::jsonb @> jsonb_build_object('review_cycle_id',NEW.review_cycle_id,'review_item_id',NEW.review_item_id,'decision_event_id',NEW.id))
 THEN RAISE EXCEPTION 'ARB decision command result/materialisation provenance is invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
"""


def _condition_membership_sql(schema):
    return f"""
CREATE OR REPLACE FUNCTION {schema}.archie_validate_arb_condition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,{schema} AS $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM arb_decision_events decision WHERE decision.id=NEW.decision_event_id
 AND decision.outcome = 'approved_with_conditions' AND decision.review_cycle_id = NEW.review_cycle_id
 AND decision.review_item_id = NEW.review_item_id AND decision.organization_id = NEW.organization_id)
 THEN RAISE EXCEPTION 'ARB condition membership is invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
"""


def ensure_arb_decision_guards(connection):
    if connection.dialect.name != "postgresql":
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    q = connection.dialect.identifier_preparer.quote(schema)
    connection.exec_driver_sql(_decision_membership_sql(q))
    connection.exec_driver_sql(_condition_membership_sql(q))
    connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {q}.archie_guard_arb_decision_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'ARB decision history is append-only' USING ERRCODE='55000'; END IF;
 IF TG_TABLE_NAME='arb_decision_events' THEN RAISE EXCEPTION 'ARB decision events are append-only' USING ERRCODE='55000'; END IF;
 IF ROW(OLD.organization_id,OLD.decision_event_id,OLD.review_cycle_id,OLD.review_item_id,OLD.condition_number,OLD.description,OLD.category,OLD.due_date,OLD.blocks_execution,OLD.created_at) IS DISTINCT FROM ROW(NEW.organization_id,NEW.decision_event_id,NEW.review_cycle_id,NEW.review_item_id,NEW.condition_number,NEW.description,NEW.category,NEW.due_date,NEW.blocks_execution,NEW.created_at) THEN RAISE EXCEPTION 'ARB condition identity and terms are immutable' USING ERRCODE='55000'; END IF; RETURN NEW; END $$;
 DROP TRIGGER IF EXISTS trg_arb_decision_event_membership ON {q}.arb_decision_events; CREATE CONSTRAINT TRIGGER trg_arb_decision_event_membership AFTER INSERT OR UPDATE ON {q}.arb_decision_events DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {q}.archie_validate_arb_decision_event();
 DROP TRIGGER IF EXISTS trg_arb_decision_event_immutable ON {q}.arb_decision_events; CREATE TRIGGER trg_arb_decision_event_immutable BEFORE UPDATE OR DELETE ON {q}.arb_decision_events FOR EACH ROW EXECUTE FUNCTION {q}.archie_guard_arb_decision_immutable();
 DROP TRIGGER IF EXISTS trg_arb_condition_membership ON {q}.arb_canonical_conditions; CREATE CONSTRAINT TRIGGER trg_arb_condition_membership AFTER INSERT OR UPDATE ON {q}.arb_canonical_conditions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {q}.archie_validate_arb_condition();
 DROP TRIGGER IF EXISTS trg_arb_condition_immutable ON {q}.arb_canonical_conditions; CREATE TRIGGER trg_arb_condition_immutable BEFORE UPDATE OR DELETE ON {q}.arb_canonical_conditions FOR EACH ROW EXECUTE FUNCTION {q}.archie_guard_arb_decision_immutable();""")


@event.listens_for(ARBCondition.__table__, "after_create")
def _install(_target, connection, **_kwargs):
    if "arb_decision_events" in db.metadata.tables:
        ensure_arb_decision_guards(connection)


def _reject_decision_mutation(_mapper, _connection, _target):
    raise ValueError("ARB decision events are append-only")


def _guard_condition_terms(_mapper, _connection, target):
    immutable = {
        "organization_id", "decision_event_id", "review_cycle_id", "review_item_id",
        "condition_number", "description", "category", "due_date",
        "blocks_execution", "created_at",
    }
    if any(inspect(target).attrs[name].history.has_changes() for name in immutable):
        raise ValueError("ARB condition identity and terms are immutable")


event.listen(ARBDecisionEvent, "before_update", _reject_decision_mutation)
event.listen(ARBDecisionEvent, "before_delete", _reject_decision_mutation)
event.listen(ARBCondition, "before_update", _guard_condition_terms)
event.listen(ARBCondition, "before_delete", _reject_decision_mutation)


__all__ = ["ARBCondition", "ARBDecisionEvent", "ensure_arb_decision_guards"]
