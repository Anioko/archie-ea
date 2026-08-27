"""Immutable evidence captured specifically for canonical ARB conditions."""

from sqlalchemy import event

from app import db
from app.models.mixins import TenantMixin


_TYPED_SHAPE = (
    "((subject_type='decision_brief' AND subject_id=decision_brief_id "
    "AND decision_brief_id IS NOT NULL AND decision_brief_version_id IS NOT NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND solution_evidence_snapshot_id IS NULL AND subject_evidence_snapshot_id IS NULL) OR "
    "(subject_type='solution' AND subject_id=solution_id AND solution_id IS NOT NULL "
    "AND solution_evidence_snapshot_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND architecture_model_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL AND subject_evidence_snapshot_id IS NULL) OR "
    "(subject_type='architecture_model' AND subject_id=architecture_model_id "
    "AND architecture_model_id IS NOT NULL AND subject_evidence_snapshot_id IS NOT NULL "
    "AND decision_brief_id IS NULL AND solution_id IS NULL AND adr_id IS NULL "
    "AND decision_brief_version_id IS NULL AND solution_evidence_snapshot_id IS NULL) OR "
    "(subject_type='adr' AND subject_id=adr_id AND adr_id IS NOT NULL "
    "AND subject_evidence_snapshot_id IS NOT NULL AND decision_brief_id IS NULL "
    "AND solution_id IS NULL AND architecture_model_id IS NULL "
    "AND decision_brief_version_id IS NULL AND solution_evidence_snapshot_id IS NULL))"
)

IMMUTABLE_CONDITION_EVIDENCE_FIELDS = frozenset(
    {
        "organization_id", "condition_id", "condition_revision", "decision_event_id", "review_cycle_id",
        "review_item_id", "subject_type", "subject_id", "value_json", "content_hash",
        "source_identity", "source_type", "source_version", "source_checksum",
        "observed_at", "collected_at", "freshness_status", "freshness_expires_at",
        "freshness_rule_version", "created_by_id", "command_receipt_id",
        "command_generation", "created_at",
    }
)
CONDITION_EVIDENCE_MEMBERSHIP_IS_EXACT = True


class ARBConditionEvidenceRecord(TenantMixin, db.Model):
    __tablename__ = "arb_condition_evidence_records"

    id = db.Column(db.Integer, primary_key=True)
    condition_id = db.Column(db.Integer, db.ForeignKey("arb_canonical_conditions.id", ondelete="RESTRICT"), nullable=False, index=True)
    condition_revision = db.Column(db.Integer, nullable=False)
    decision_event_id = db.Column(db.Integer, db.ForeignKey("arb_decision_events.id", ondelete="RESTRICT"), nullable=False)
    review_cycle_id = db.Column(db.Integer, db.ForeignKey("arb_review_cycles.id", ondelete="RESTRICT"), nullable=False)
    review_item_id = db.Column(db.Integer, db.ForeignKey("arb_review_items.id", ondelete="RESTRICT"), nullable=False)
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    decision_brief_id = db.Column(db.Integer, db.ForeignKey("decision_briefs.id", ondelete="RESTRICT"))
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id", ondelete="RESTRICT"))
    architecture_model_id = db.Column(db.Integer, db.ForeignKey("architecture_models.id", ondelete="RESTRICT"))
    adr_id = db.Column(db.Integer, db.ForeignKey("architecture_decision_records.id", ondelete="RESTRICT"))
    decision_brief_version_id = db.Column(db.Integer, db.ForeignKey("decision_brief_versions.id", ondelete="RESTRICT"))
    solution_evidence_snapshot_id = db.Column(db.Integer, db.ForeignKey("arb_submission_evidence_snapshots.id", ondelete="RESTRICT"))
    subject_evidence_snapshot_id = db.Column(db.Integer, db.ForeignKey("arb_subject_evidence_snapshots.id", ondelete="RESTRICT"))
    value_json = db.Column(db.JSON, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    source_identity = db.Column(db.String(1024), nullable=False)
    source_type = db.Column(db.String(80), nullable=False)
    source_version = db.Column(db.String(512), nullable=False)
    source_checksum = db.Column(db.String(64), nullable=False)
    observed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    collected_at = db.Column(db.DateTime(timezone=True), nullable=False)
    freshness_status = db.Column(db.String(30), nullable=False)
    freshness_expires_at = db.Column(db.DateTime(timezone=True))
    freshness_rule_version = db.Column(db.String(160), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    command_receipt_id = db.Column(db.Integer, db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"), nullable=False, unique=True)
    command_generation = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.CheckConstraint(_TYPED_SHAPE, name="ck_arb_condition_evidence_typed_shape"),
        db.CheckConstraint("length(content_hash) = 64", name="ck_arb_condition_evidence_hash"),
        db.CheckConstraint("length(source_checksum) = 64", name="ck_arb_condition_evidence_source_hash"),
        db.CheckConstraint("freshness_status IN ('fresh','stale','unknown','not_applicable')", name="ck_arb_condition_evidence_freshness"),
        db.CheckConstraint("command_generation > 0", name="ck_arb_condition_evidence_generation"),
        db.CheckConstraint("condition_revision > 0", name="ck_arb_condition_evidence_revision"),
        db.UniqueConstraint("organization_id", "condition_id", "content_hash", name="uq_arb_condition_evidence_content"),
    )


def _membership_sql(schema):
    return f"""
CREATE OR REPLACE FUNCTION {schema}.archie_validate_arb_condition_evidence() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,{schema} AS $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM arb_canonical_conditions condition
 JOIN arb_decision_events decision ON decision.id=condition.decision_event_id
 JOIN arb_review_cycles cycle ON cycle.id=condition.review_cycle_id
 JOIN arb_review_items review ON review.id=condition.review_item_id
 WHERE condition.id=NEW.condition_id AND condition.organization_id=NEW.organization_id
 AND decision.id=NEW.decision_event_id AND decision.organization_id=NEW.organization_id
 AND cycle.id=NEW.review_cycle_id AND cycle.organization_id=NEW.organization_id
 AND review.id=NEW.review_item_id AND review.organization_id=NEW.organization_id
 AND decision.review_cycle_id=cycle.id AND decision.review_item_id=review.id
 AND decision.subject_type=NEW.subject_type AND decision.subject_id=NEW.subject_id
 AND decision.decision_brief_id IS NOT DISTINCT FROM NEW.decision_brief_id
 AND decision.solution_id IS NOT DISTINCT FROM NEW.solution_id
 AND decision.architecture_model_id IS NOT DISTINCT FROM NEW.architecture_model_id
 AND decision.adr_id IS NOT DISTINCT FROM NEW.adr_id
 AND decision.decision_brief_version_id IS NOT DISTINCT FROM NEW.decision_brief_version_id
 AND decision.solution_evidence_snapshot_id IS NOT DISTINCT FROM NEW.solution_evidence_snapshot_id
 AND decision.subject_evidence_snapshot_id IS NOT DISTINCT FROM NEW.subject_evidence_snapshot_id)
 THEN RAISE EXCEPTION 'ARB condition evidence membership is invalid' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS (SELECT 1 FROM users actor WHERE actor.id=NEW.created_by_id AND actor.organization_id=NEW.organization_id)
 THEN RAISE EXCEPTION 'ARB condition evidence actor is outside tenant' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
"""


def ensure_arb_condition_evidence_guards(connection):
    if connection.dialect.name != "postgresql":
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    q = connection.dialect.identifier_preparer.quote(schema)
    connection.exec_driver_sql(_membership_sql(q))
    connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {q}.archie_reject_arb_condition_evidence_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN RAISE EXCEPTION 'ARB condition evidence is append-only' USING ERRCODE='55000'; END $$;
DROP TRIGGER IF EXISTS trg_arb_condition_evidence_membership ON {q}.arb_condition_evidence_records; CREATE CONSTRAINT TRIGGER trg_arb_condition_evidence_membership AFTER INSERT OR UPDATE ON {q}.arb_condition_evidence_records DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {q}.archie_validate_arb_condition_evidence();
DROP TRIGGER IF EXISTS trg_arb_condition_evidence_immutable ON {q}.arb_condition_evidence_records; CREATE TRIGGER trg_arb_condition_evidence_immutable BEFORE UPDATE OR DELETE ON {q}.arb_condition_evidence_records FOR EACH ROW EXECUTE FUNCTION {q}.archie_reject_arb_condition_evidence_mutation();""")


@event.listens_for(ARBConditionEvidenceRecord.__table__, "after_create")
def _install(_target, connection, **_kwargs):
    ensure_arb_condition_evidence_guards(connection)


def _reject(_mapper, _connection, _target):
    raise ValueError("ARB condition evidence is append-only")


event.listen(ARBConditionEvidenceRecord, "before_update", _reject)
event.listen(ARBConditionEvidenceRecord, "before_delete", _reject)

__all__ = [
    "ARBConditionEvidenceRecord", "CONDITION_EVIDENCE_MEMBERSHIP_IS_EXACT",
    "IMMUTABLE_CONDITION_EVIDENCE_FIELDS", "ensure_arb_condition_evidence_guards",
]
