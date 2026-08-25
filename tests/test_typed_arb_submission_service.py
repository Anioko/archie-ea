"""Database contracts for typed ARB subjects and immutable review cycles."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
import uuid

import pytest
import psycopg2
from sqlalchemy.orm import configure_mappers

from app.models.architecture_review_board import ARBReviewItem
from app.models.mixins import TenantMixin


SUBJECT_TYPES = {
    "decision_brief",
    "solution",
    "architecture_model",
    "adr",
}


def _typed_models():
    arb_models = importlib.import_module("app.models.architecture_review_board")
    decision_models = importlib.import_module("app.models.transformation_decision")
    assert hasattr(arb_models, "ARBReviewCycle"), "ARBReviewCycle is not implemented"
    assert hasattr(
        decision_models, "ARBSubjectEvidenceSnapshot"
    ), "ARBSubjectEvidenceSnapshot is not implemented"
    return arb_models.ARBReviewCycle, decision_models.ARBSubjectEvidenceSnapshot


def _check_sql(model) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    )


def test_typed_cycle_schema_has_real_subject_and_adapter_evidence_foreign_keys():
    """Removing a real FK would let a polymorphic integer lose its subject."""
    cycle, snapshot = _typed_models()

    assert {
        "organization_id",
        "subject_type",
        "subject_id",
        "decision_brief_id",
        "solution_id",
        "architecture_model_id",
        "adr_id",
        "decision_brief_version_id",
        "solution_evidence_snapshot_id",
        "subject_evidence_snapshot_id",
        "review_number",
        "cycle_number",
        "predecessor_cycle_id",
        "status",
        "migration_gap_reason",
        "legacy_source_type",
        "legacy_source_id",
        "opened_at",
        "closed_at",
        "terminal_outcome",
    } <= set(cycle.__table__.columns.keys())
    assert {
        "organization_id",
        "subject_type",
        "subject_id",
        "architecture_model_id",
        "adr_id",
        "schema_version",
        "policy_version",
        "captured_by_id",
        "captured_at",
        "payload",
        "citations",
        "content_hash",
    } <= set(snapshot.__table__.columns.keys())

    expected_targets = {
        "decision_brief_id": "decision_briefs.id",
        "solution_id": "solutions.id",
        "architecture_model_id": "architecture_models.id",
        "adr_id": "architecture_decision_records.id",
        "decision_brief_version_id": "decision_brief_versions.id",
        "solution_evidence_snapshot_id": "arb_submission_evidence_snapshots.id",
        "subject_evidence_snapshot_id": "arb_subject_evidence_snapshots.id",
    }
    for column_name, target in expected_targets.items():
        foreign_keys = cycle.__table__.columns[column_name].foreign_keys
        assert {foreign_key.target_fullname for foreign_key in foreign_keys} == {target}


def test_cycle_shape_history_chain_and_open_uniqueness_are_database_constraints():
    """Shape, historical gaps, monotonic chains, and open-cycle races need DB guards."""
    cycle, snapshot = _typed_models()
    cycle_checks = _check_sql(cycle)
    snapshot_checks = _check_sql(snapshot)

    assert SUBJECT_TYPES <= {
        subject_type for subject_type in SUBJECT_TYPES if subject_type in cycle_checks
    }
    assert "historical_unverified" in cycle_checks
    assert "migration_gap_reason IS NOT NULL" in cycle_checks
    assert "legacy_source_type IS NOT NULL" in cycle_checks
    assert "legacy_source_id IS NOT NULL" in cycle_checks
    assert "cycle_number = 1" in cycle_checks
    assert "predecessor_cycle_id IS NULL" in cycle_checks
    assert {"architecture_model", "adr"} <= {
        subject_type for subject_type in SUBJECT_TYPES if subject_type in snapshot_checks
    }

    indexes = {index.name: index for index in cycle.__table__.indexes}
    open_index = indexes["uq_arb_review_cycle_open_subject"]
    assert open_index.unique is True
    assert tuple(column.name for column in open_index.columns) == (
        "organization_id",
        "subject_type",
        "subject_id",
    )
    assert open_index.dialect_options["postgresql"]["where"] is not None

    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and tuple(column.name for column in constraint.columns)
        == ("organization_id", "subject_type", "subject_id", "cycle_number")
        for constraint in cycle.__table__.constraints
    )


def test_review_item_is_a_nullable_additive_one_to_one_cycle_projection():
    """Existing Solution reviews remain valid while typed reviews have one owner."""
    _cycle, _snapshot = _typed_models()
    columns = ARBReviewItem.__table__.columns

    assert {
        "subject_type",
        "subject_id",
        "decision_brief_id",
        "decision_brief_version_id",
        "solution_evidence_snapshot_id",
        "subject_evidence_snapshot_id",
        "review_cycle_id",
    } <= set(columns.keys())
    assert all(
        columns[name].nullable
        for name in (
            "subject_type",
            "subject_id",
            "decision_brief_id",
            "decision_brief_version_id",
            "solution_evidence_snapshot_id",
            "subject_evidence_snapshot_id",
            "review_cycle_id",
        )
    )
    assert columns["review_cycle_id"].unique is True
    review_checks = _check_sql(ARBReviewItem)
    assert all(subject_type in review_checks for subject_type in SUBJECT_TYPES)
    assert "review_cycle_id IS NULL" in review_checks


def test_typed_arb_models_are_tenant_scoped_in_the_full_mapper_registry():
    """A new ARB table without TenantMixin would silently bypass tenant filtering."""
    cycle, snapshot = _typed_models()
    from app.models.archimate_core import ArchitectureModel as exported_model
    from app.models.models import ArchitectureModel as canonical_model

    configure_mappers()
    assert exported_model is canonical_model
    assert issubclass(canonical_model, TenantMixin)
    assert issubclass(cycle, TenantMixin)
    assert issubclass(snapshot, TenantMixin)


def test_subject_snapshot_hash_covers_typed_membership_and_evidence():
    """Changing either evidence or typed identity must change the content hash."""
    _cycle, snapshot_type = _typed_models()
    snapshot = snapshot_type(
        organization_id=41,
        subject_type="architecture_model",
        subject_id=73,
        architecture_model_id=73,
        schema_version=1,
        policy_version="architecture-model-arb-r1",
        captured_at=datetime.now(timezone.utc),
        payload={"name": "Governed model", "version": "1.0"},
        citations=[],
    )
    snapshot.content_hash = snapshot.recompute_content_hash()
    original_hash = snapshot.content_hash

    snapshot.payload = {"name": "tampered", "version": "1.0"}
    assert snapshot.recompute_content_hash() != original_hash

    snapshot.payload = {"name": "Governed model", "version": "1.0"}
    snapshot.subject_id = 74
    snapshot.architecture_model_id = 74
    assert snapshot.recompute_content_hash() != original_hash


def _install_typed_schema(app):
    from app import db
    from app.commands.reconcile_schema import _reconcile

    with app.app_context():
        _added, failed, missing, blocking = _reconcile(dry_run=False)
        assert failed == []
        assert "arb_review_cycles" not in missing
        assert "arb_subject_evidence_snapshots" not in missing
        assert not [item for item in blocking if item.startswith("arb_")]
        return db.engine.raw_connection()


def _seed_org_user_model(cursor, label):
    suffix = uuid.uuid4().hex[:12]
    cursor.execute(
        "INSERT INTO organizations (name, slug) VALUES (%s, %s) RETURNING id",
        (f"Typed ARB {label} {suffix}", f"typed-arb-{label}-{suffix}"),
    )
    organization_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO users (organization_id, email, enterprise_role) "
        "VALUES (%s, %s, 'enterprise_architect') RETURNING id",
        (organization_id, f"typed-arb-{label}-{suffix}@example.test"),
    )
    user_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO architecture_models (organization_id, name, version) "
        "VALUES (%s, %s, '1.0') RETURNING id",
        (organization_id, f"Typed model {suffix}"),
    )
    model_id = cursor.fetchone()[0]
    return organization_id, user_id, model_id


def _insert_model_snapshot(cursor, organization_id, model_id):
    cursor.execute(
        """
        INSERT INTO arb_subject_evidence_snapshots (
            organization_id, subject_type, subject_id, architecture_model_id,
            schema_version, policy_version, captured_at, payload, citations,
            content_hash
        ) VALUES (
            %s, 'architecture_model', %s, %s, 1,
            'architecture-model-arb-r1', clock_timestamp(), '{}'::json,
            '[]'::json, %s
        ) RETURNING id
        """,
        (organization_id, model_id, model_id, "a" * 64),
    )
    return cursor.fetchone()[0]


def _insert_model_cycle(
    cursor,
    *,
    organization_id,
    model_id,
    snapshot_id,
    cycle_number=1,
    predecessor_cycle_id=None,
    closed=False,
):
    cursor.execute(
        """
        INSERT INTO arb_review_cycles (
            organization_id, subject_type, subject_id, architecture_model_id,
            subject_evidence_snapshot_id, review_number, cycle_number,
            predecessor_cycle_id, status, opened_at, closed_at, terminal_outcome
        ) VALUES (
            %s, 'architecture_model', %s, %s, %s, %s, %s, %s,
            %s, clock_timestamp(),
            CASE WHEN %s THEN clock_timestamp() ELSE NULL END,
            CASE WHEN %s THEN 'returned_for_evidence' ELSE NULL END
        ) RETURNING id
        """,
        (
            organization_id,
            model_id,
            model_id,
            snapshot_id,
            f"CYCLE-{uuid.uuid4().hex[:20]}",
            cycle_number,
            predecessor_cycle_id,
            "returned_for_evidence" if closed else "submitted",
            closed,
            closed,
        ),
    )
    return cursor.fetchone()[0]


def _insert_model_review(
    cursor,
    *,
    organization_id,
    user_id,
    model_id,
    snapshot_id,
    cycle_id,
    status="submitted",
):
    cursor.execute(
        """
        INSERT INTO arb_review_items (
            organization_id, review_number, title, review_type, submitter_id,
            subject_type, subject_id, architecture_model_id,
            subject_evidence_snapshot_id, review_cycle_id, status
        ) VALUES (
            %s, %s, 'Typed architecture review', 'architecture_change', %s,
            'architecture_model', %s, %s, %s, %s, %s
        ) RETURNING id
        """,
        (
            organization_id,
            f"REV-{uuid.uuid4().hex[:20]}",
            user_id,
            model_id,
            model_id,
            snapshot_id,
            cycle_id,
            status,
        ),
    )
    return cursor.fetchone()[0]


def test_reconcile_installs_typed_arb_constraints_idempotently(app, _schema):
    """Existing databases receive tables, checks, indexes and enabled triggers."""
    arb_models = importlib.import_module("app.models.architecture_review_board")
    assert hasattr(arb_models, "ensure_arb_cycle_constraints")
    assert hasattr(arb_models, "inspect_arb_cycle_constraints")

    raw = _install_typed_schema(app)
    raw.close()
    raw = _install_typed_schema(app)
    raw.close()
    from app import db

    with app.app_context(), db.engine.connect() as connection:
        assert arb_models.inspect_arb_cycle_constraints(connection) == []


def test_direct_snapshot_commit_rejects_cross_tenant_subject(app, _schema):
    """A forged FK from another tenant must fail at the database commit boundary."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_a, _user_a, _model_a = _seed_org_user_model(cursor, "snapshot-a")
        _org_b, _user_b, model_b = _seed_org_user_model(cursor, "snapshot-b")
        _insert_model_snapshot(cursor, org_a, model_b)
        with pytest.raises(psycopg2.Error, match="snapshot subject is outside its tenant"):
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_direct_cycle_commit_requires_adapter_snapshot_membership_and_review(app, _schema):
    """A cycle cannot pin another subject's evidence even with valid foreign keys."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_a = _seed_org_user_model(cursor, "cycle-membership")
        cursor.execute(
            "INSERT INTO architecture_models (organization_id, name) "
            "VALUES (%s, 'Other governed model') RETURNING id",
            (org_id,),
        )
        model_b = cursor.fetchone()[0]
        snapshot_b = _insert_model_snapshot(cursor, org_id, model_b)
        cycle_id = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_a,
            snapshot_id=snapshot_b,
        )
        _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_a,
            snapshot_id=snapshot_b,
            cycle_id=cycle_id,
        )
        with pytest.raises(psycopg2.Error, match="cycle snapshot does not belong"):
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_direct_cycle_commit_requires_exactly_one_review_projection(app, _schema):
    """A cycle without its sole canonical ARBReviewItem cannot commit."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, _user_id, model_id = _seed_org_user_model(cursor, "cycle-review")
        snapshot_id = _insert_model_snapshot(cursor, org_id, model_id)
        _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
        )
        with pytest.raises(psycopg2.Error, match="cycle review projection is missing"):
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_direct_cycle_commit_requires_review_status_projection(app, _schema):
    """The cycle cannot become a parallel workflow-status authority."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_id = _seed_org_user_model(cursor, "cycle-status")
        snapshot_id = _insert_model_snapshot(cursor, org_id, model_id)
        cycle_id = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
        )
        review_id = _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_id=cycle_id,
        )
        cursor.execute(
            "UPDATE arb_review_items SET status = 'in_review' WHERE id = %s",
            (review_id,),
        )
        with pytest.raises(psycopg2.Error, match="cycle review projection"):
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_direct_cycle_commit_rejects_non_monotonic_predecessor(app, _schema):
    """A successor must be the next cycle for the same closed typed subject."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_id = _seed_org_user_model(cursor, "cycle-chain")
        snapshot_id = _insert_model_snapshot(cursor, org_id, model_id)
        first_cycle = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            closed=True,
        )
        _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_id=first_cycle,
            status="returned_for_evidence",
        )
        third_cycle = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_number=3,
            predecessor_cycle_id=first_cycle,
        )
        _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_id=third_cycle,
        )
        with pytest.raises(psycopg2.Error, match="cycle predecessor is not monotonic"):
            raw.commit()
    finally:
        raw.rollback()
        raw.close()


def test_database_rejects_two_open_cycles_for_one_typed_subject(app, _schema):
    """The partial unique index closes the concurrent-open race."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_id = _seed_org_user_model(cursor, "cycle-open")
        snapshot_id = _insert_model_snapshot(cursor, org_id, model_id)
        first_cycle = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
        )
        _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_id=first_cycle,
        )
        with pytest.raises(psycopg2.Error):
            _insert_model_cycle(
                cursor,
                organization_id=org_id,
                model_id=model_id,
                snapshot_id=snapshot_id,
                cycle_number=2,
                predecessor_cycle_id=first_cycle,
            )
    finally:
        raw.rollback()
        raw.close()


def test_historical_unverified_cycle_validates_without_fabricated_snapshot(app, _schema):
    """Legacy model/ADR/Solution history records its evidence gap, never fake evidence."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_id = _seed_org_user_model(cursor, "historical-gap")
        cursor.execute(
            """
            INSERT INTO arb_review_cycles (
                organization_id, subject_type, subject_id, architecture_model_id,
                review_number, cycle_number, status, migration_gap_reason,
                legacy_source_type, legacy_source_id, opened_at, closed_at,
                terminal_outcome
            ) VALUES (
                %s, 'architecture_model', %s, %s, %s, 1,
                'historical_unverified', 'legacy review has no provable snapshot',
                'arb_review_item', 9127, clock_timestamp(), clock_timestamp(),
                'historical_unverified'
            ) RETURNING id
            """,
            (org_id, model_id, model_id, f"HIST-{uuid.uuid4().hex[:20]}"),
        )
        cycle_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO arb_review_items (
                organization_id, review_number, title, review_type, submitter_id,
                subject_type, subject_id, architecture_model_id, review_cycle_id,
                status
            ) VALUES (
                %s, %s, 'Historical architecture review', 'architecture_change',
                %s, 'architecture_model', %s, %s, %s,
                'historical_unverified'
            )
            """,
            (
                org_id,
                f"REV-HIST-{uuid.uuid4().hex[:16]}",
                user_id,
                model_id,
                model_id,
                cycle_id,
            ),
        )
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    finally:
        raw.rollback()
        raw.close()


def test_historical_solution_cycle_also_validates_without_fabricated_snapshot(app, _schema):
    """The legacy Solution adapter receives the same honest gap treatment."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, _model_id = _seed_org_user_model(cursor, "historical-solution")
        cursor.execute(
            "INSERT INTO solutions (organization_id, name) VALUES (%s, %s) RETURNING id",
            (org_id, f"Historical solution {uuid.uuid4().hex[:10]}"),
        )
        solution_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO arb_review_cycles (
                organization_id, subject_type, subject_id, solution_id,
                review_number, cycle_number, status, migration_gap_reason,
                legacy_source_type, legacy_source_id, opened_at, closed_at,
                terminal_outcome
            ) VALUES (
                %s, 'solution', %s, %s, %s, 1, 'historical_unverified',
                'legacy review has no provable snapshot', 'arb_review_item',
                9128, clock_timestamp(), clock_timestamp(),
                'historical_unverified'
            ) RETURNING id
            """,
            (org_id, solution_id, solution_id, f"HIST-{uuid.uuid4().hex[:20]}"),
        )
        cycle_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO arb_review_items (
                organization_id, review_number, title, review_type, submitter_id,
                subject_type, subject_id, solution_id, review_cycle_id, status
            ) VALUES (
                %s, %s, 'Historical Solution review', 'solution_design', %s,
                'solution', %s, %s, %s, 'historical_unverified'
            )
            """,
            (
                org_id,
                f"REV-HIST-{uuid.uuid4().hex[:16]}",
                user_id,
                solution_id,
                solution_id,
                cycle_id,
            ),
        )
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    finally:
        raw.rollback()
        raw.close()


@pytest.mark.parametrize(
    "statement",
    (
        "UPDATE arb_subject_evidence_snapshots SET payload = '{}'::json WHERE id = %s",
        "DELETE FROM arb_subject_evidence_snapshots WHERE id = %s",
        "UPDATE arb_review_cycles SET subject_id = subject_id + 1 WHERE id = %s",
        "DELETE FROM arb_review_cycles WHERE id = %s",
        "UPDATE arb_review_items SET subject_id = subject_id + 1 WHERE id = %s",
        "DELETE FROM arb_review_items WHERE id = %s",
    ),
)
def test_direct_sql_cannot_rewrite_typed_snapshot_or_history(app, _schema, statement):
    """Snapshot and typed identity/history are append-only outside the ORM too."""
    raw = _install_typed_schema(app)
    try:
        cursor = raw.cursor()
        org_id, user_id, model_id = _seed_org_user_model(cursor, "cycle-history")
        snapshot_id = _insert_model_snapshot(cursor, org_id, model_id)
        cycle_id = _insert_model_cycle(
            cursor,
            organization_id=org_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
        )
        review_id = _insert_model_review(
            cursor,
            organization_id=org_id,
            user_id=user_id,
            model_id=model_id,
            snapshot_id=snapshot_id,
            cycle_id=cycle_id,
        )
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        target_id = (
            snapshot_id
            if "arb_subject_evidence_snapshots" in statement
            else cycle_id
            if "arb_review_cycles" in statement
            else review_id
        )
        with pytest.raises(psycopg2.Error, match="append-only|immutable"):
            cursor.execute(statement, (target_id,))
    finally:
        raw.rollback()
        raw.close()
