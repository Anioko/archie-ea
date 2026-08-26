"""
flask reconcile-schema — bring an existing database's columns in line with the
ORM models.

`db.create_all()` (run by `flask init-db`) creates missing *tables* but never
adds *columns* to tables that already exist. When a model gains a column in a
later release, a long-lived database drifts: the ORM SELECTs a column Postgres
doesn't have, the request 500s, and one bad column can blank a whole page.

This command diffs every mapped model's columns against the live table and runs
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for each missing one. It is:
  - SAFE: adds columns only — never drops, retypes, or reorders. Added columns
    are always nullable, so an existing row can never violate them.
  - IDEMPOTENT: `IF NOT EXISTS` means re-running is a no-op.

A column that declares a `server_default` keeps it, so existing rows are
populated as the column is added rather than left NULL. This matters for any
column the ORM must read back — an optimistic-lock version, a status the code
treats as non-optional — where an all-NULL backfill is not a neutral starting
state but a broken one. On PostgreSQL 11+ `ADD COLUMN ... DEFAULT` is a
metadata-only operation, so this stays cheap on a large table.

It also creates the four canonical Transformation Programme tables when they are
absent. Other missing tables remain the responsibility of `flask init-db`
(`create_all`). Run them together:  flask init-db && flask reconcile-schema

Usage:
    flask --app manage reconcile-schema            # apply
    flask --app manage reconcile-schema --dry-run  # report drift, change nothing
"""
import click
from flask.cli import with_appcontext

from app import db


_TRANSFORMATION_TABLES = (
    "programme_workstreams",
    "programme_role_assignments",
    "programme_outcome_commitments",
    "measure_definitions",
    "command_idempotency_records",
    "command_materialisations",
    "operation_results",
    "transformation_outbox_events",
    "transformation_candidates",
    "candidate_overlap_dispositions",
    "candidate_signals",
    "evidence_records",
    "evidence_claim_heads",
    "evidence_head_events",
    "evidence_requests",
    "transformation_options",
    "transformation_option_versions",
    "decision_briefs",
    "decision_brief_versions",
    "decision_brief_option_citations",
    "decision_brief_evidence_citations",
    "decision_events",
    "arb_subject_evidence_snapshots",
    # arb_review_cycles carries a RESTRICT FK to this table, so it must exist
    # first. Without it reconcile-schema can never converge on a database that
    # predates the submission-evidence feature: arb_review_cycles fails with
    # UndefinedTable on every pass.
    "arb_submission_evidence_snapshots",
    "arb_review_cycles",
)

_TRANSFORMATION_FOREIGN_KEYS = (
    (
        "fk_evidence_requests_submitted_evidence",
        "evidence_requests",
        "submitted_evidence_id",
        "evidence_records",
        "id",
        "RESTRICT",
    ),
    (
        "fk_evidence_requests_accepted_evidence",
        "evidence_requests",
        "accepted_evidence_id",
        "evidence_records",
        "id",
        "RESTRICT",
    ),
    (
        "fk_work_packages_strategic_initiative",
        "work_packages",
        "strategic_initiative_id",
        "strategic_initiatives",
        "id",
        "RESTRICT",
    ),
    (
        "fk_work_packages_programme_workstream",
        "work_packages",
        "programme_workstream_id",
        "programme_workstreams",
        "id",
        "RESTRICT",
    ),
    (
        "fk_work_packages_decision_brief_version",
        "work_packages",
        "decision_brief_version_id",
        "decision_brief_versions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_strategic_roadmap_items_initiative",
        "strategic_roadmap_items",
        "initiative_id",
        "strategic_initiatives",
        "id",
        "RESTRICT",
    ),
    (
        "fk_strategic_roadmap_items_organization",
        "strategic_roadmap_items",
        "organization_id",
        "organizations",
        "id",
        "RESTRICT",
    ),
    (
        "fk_strategic_roadmap_items_programme_workstream",
        "strategic_roadmap_items",
        "programme_workstream_id",
        "programme_workstreams",
        "id",
        "RESTRICT",
    ),
    (
        "fk_strategic_roadmap_items_work_package",
        "strategic_roadmap_items",
        "work_package_id",
        "work_packages",
        "id",
        "RESTRICT",
    ),
    (
        "fk_strategic_roadmap_items_decision_brief_version",
        "strategic_roadmap_items",
        "decision_brief_version_id",
        "decision_brief_versions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_benefits_strategic_initiative",
        "benefits",
        "strategic_initiative_id",
        "strategic_initiatives",
        "id",
        "RESTRICT",
    ),
    (
        "fk_benefits_programme_workstream",
        "benefits",
        "programme_workstream_id",
        "programme_workstreams",
        "id",
        "RESTRICT",
    ),
    (
        "fk_benefits_outcome_commitment",
        "benefits",
        "outcome_commitment_id",
        "programme_outcome_commitments",
        "id",
        "RESTRICT",
    ),
    (
        "fk_benefits_decision_brief_version",
        "benefits",
        "decision_brief_version_id",
        "decision_brief_versions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_solutions_strategic_initiative",
        "solutions",
        "initiative_id",
        "strategic_initiatives",
        "id",
        "RESTRICT",
    ),
    (
        "fk_solutions_programme_workstream",
        "solutions",
        "workstream_id",
        "programme_workstreams",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_subject_snapshot_architecture_model",
        "arb_subject_evidence_snapshots",
        "architecture_model_id",
        "architecture_models",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_subject_snapshot_adr",
        "arb_subject_evidence_snapshots",
        "adr_id",
        "architecture_decision_records",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_subject_snapshot_captured_by",
        "arb_subject_evidence_snapshots",
        "captured_by_id",
        "users",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_decision_brief",
        "arb_review_cycles",
        "decision_brief_id",
        "decision_briefs",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_solution",
        "arb_review_cycles",
        "solution_id",
        "solutions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_architecture_model",
        "arb_review_cycles",
        "architecture_model_id",
        "architecture_models",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_adr",
        "arb_review_cycles",
        "adr_id",
        "architecture_decision_records",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_decision_brief_version",
        "arb_review_cycles",
        "decision_brief_version_id",
        "decision_brief_versions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_solution_snapshot",
        "arb_review_cycles",
        "solution_evidence_snapshot_id",
        "arb_submission_evidence_snapshots",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_subject_snapshot",
        "arb_review_cycles",
        "subject_evidence_snapshot_id",
        "arb_subject_evidence_snapshots",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_cycle_predecessor",
        "arb_review_cycles",
        "predecessor_cycle_id",
        "arb_review_cycles",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_item_decision_brief",
        "arb_review_items",
        "decision_brief_id",
        "decision_briefs",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_item_decision_brief_version",
        "arb_review_items",
        "decision_brief_version_id",
        "decision_brief_versions",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_item_solution_snapshot",
        "arb_review_items",
        "solution_evidence_snapshot_id",
        "arb_submission_evidence_snapshots",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_item_subject_snapshot",
        "arb_review_items",
        "subject_evidence_snapshot_id",
        "arb_subject_evidence_snapshots",
        "id",
        "RESTRICT",
    ),
    (
        "fk_arb_review_item_cycle",
        "arb_review_items",
        "review_cycle_id",
        "arb_review_cycles",
        "id",
        "RESTRICT",
    ),
)

_MATERIALISATION_INDEXES = (
    ("uq_work_package_materialisation", "work_packages"),
    ("uq_roadmap_item_materialisation", "strategic_roadmap_items"),
    ("uq_benefit_materialisation", "benefits"),
    ("uq_decision_brief_workstream_scope", "decision_briefs"),
    ("uq_decision_brief_candidate_scope", "decision_briefs"),
)

_DECISION_BRIEF_SCOPE_INDEXES = {
    "uq_decision_brief_workstream_scope": (
        "organization_id, workstream_id",
        "candidate_id IS NULL",
    ),
    "uq_decision_brief_candidate_scope": (
        "organization_id, workstream_id, candidate_id",
        "candidate_id IS NOT NULL",
    ),
}

_MEMBERSHIP_TABLES = (
    "programme_workstreams",
    "programme_role_assignments",
    "programme_outcome_commitments",
    "measure_definitions",
    "work_packages",
    "strategic_roadmap_items",
    "benefits",
    "solutions",
)

_EVIDENCE_WAIVER_CHECK = (
    "waiver_id IS NULL OR (waiver_authority_id IS NOT NULL AND "
    "waiver_reason IS NOT NULL AND waiver_expires_at IS NOT NULL AND "
    "interim_accountable_id IS NOT NULL AND waived_at IS NOT NULL)"
)


def _create_transformation_tables(*, dry_run, existing_tables, added, failed):
    """Create only the new canonical tables when init-db has not run yet."""
    # These modules are not guaranteed to be reached by every CLI bootstrap;
    # import them before consulting metadata so fresh deployments cannot omit
    # the typed ARB tables.
    from app.models.architecture_review_board import ARBReviewCycle  # noqa: F401
    from app.models.arb_submission_evidence import (  # noqa: F401
        ARBSubmissionEvidenceSnapshot,
    )
    from app.models.transformation_decision import (  # noqa: F401
        ARBSubjectEvidenceSnapshot,
    )

    for table_name in _TRANSFORMATION_TABLES:
        if table_name in existing_tables:
            continue
        table = db.metadata.tables.get(table_name)
        if table is None:
            failed.append(f"{table_name}: model is not registered")
            continue
        label = f"table.{table_name}"
        if dry_run:
            added.append(f"{label} :: CREATE TABLE")
            continue
        try:
            # ``existing_tables`` was read from the active/default schema.
            # PostgreSQL's unqualified checkfirst lookup follows search_path
            # and can mistake a same-named public fallback table for this
            # schema's table, silently skipping the required CREATE.
            table.create(bind=db.engine, checkfirst=False)
            existing_tables.add(table_name)
            added.append(f"{label} :: CREATE TABLE")
        except Exception as exc:  # noqa: BLE001 — aggregate every reconciliation failure
            failed.append(f"{label}: {str(exc)[:120]}")


def _ensure_transformation_foreign_keys(*, dry_run, existing_tables, added, failed):
    """Install FKs that ADD COLUMN cannot carry on a long-lived schema."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    for name, table, column, target, target_column, ondelete in _TRANSFORMATION_FOREIGN_KEYS:
        if table not in existing_tables or target not in existing_tables:
            continue
        live_columns = {item["name"] for item in inspector.get_columns(table)}
        if column not in live_columns:
            continue
        existing = inspector.get_foreign_keys(table)
        matching = [
            fk
            for fk in existing
            if fk.get("constrained_columns") == [column]
            and fk.get("referred_table") == target
        ]
        if any(
            fk.get("constrained_columns") == [column]
            and fk.get("referred_table") == target
            and (fk.get("options") or {}).get("ondelete", "").upper() == ondelete
            for fk in matching
        ):
            continue
        label = f"constraint.{name}"
        if dry_run:
            added.append(f"{label} :: FOREIGN KEY")
            continue
        ddl = (
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
            f'FOREIGN KEY ("{column}") REFERENCES "{target}" ("{target_column}") '
            f"ON DELETE {ondelete}"
        )
        try:
            for fk in matching:
                old_name = fk.get("name")
                if old_name:
                    db.session.execute(
                        text(f'ALTER TABLE "{table}" DROP CONSTRAINT "{old_name}"')
                    )
            db.session.execute(text(ddl))
            db.session.commit()
            added.append(f"{label} :: FOREIGN KEY")
            inspector = inspect(db.engine)
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            failed.append(f"{label}: {str(exc)[:120]}")


def _ensure_evidence_waiver_constraint(
    *, dry_run, existing_tables, added, failed
):
    """Install and validate the Task 6 waiver invariant on upgraded databases."""
    from sqlalchemy import inspect, text

    table_name = "evidence_requests"
    constraint_name = "ck_evidence_request_waiver_complete"
    if table_name not in existing_tables:
        return

    required_columns = {
        "waiver_id",
        "waiver_authority_id",
        "waiver_reason",
        "waiver_expires_at",
        "interim_accountable_id",
        "waived_at",
    }
    live_columns = {
        item["name"] for item in inspect(db.engine).get_columns(table_name)
    }
    if not dry_run and not required_columns <= live_columns:
        failed.append(
            f"constraint.{constraint_name}: required waiver columns are missing"
        )
        return

    row = db.session.execute(
        text(
            """
            SELECT c.convalidated
            FROM pg_constraint AS c
            JOIN pg_class AS t ON t.oid = c.conrelid
            JOIN pg_namespace AS n ON n.oid = t.relnamespace
            WHERE n.nspname = current_schema()
              AND t.relname = :table_name
              AND c.conname = :constraint_name
              AND c.contype = 'c'
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    ).mappings().one_or_none()
    if row is not None and row["convalidated"]:
        return

    label = f"constraint.{constraint_name}"
    action = "CHECK NOT VALID THEN VALIDATE"
    if dry_run:
        added.append(f"{label} :: {action}")
        return

    try:
        if row is None:
            db.session.execute(
                text(
                    f'ALTER TABLE "{table_name}" ADD CONSTRAINT '
                    f'"{constraint_name}" CHECK ({_EVIDENCE_WAIVER_CHECK}) NOT VALID'
                )
            )
        db.session.execute(
            text(
                f'ALTER TABLE "{table_name}" VALIDATE CONSTRAINT '
                f'"{constraint_name}"'
            )
        )
        db.session.commit()
        added.append(f"{label} :: {action}")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        failed.append(f"{label}: {str(exc)[:120]}")


def _ensure_benefit_legacy_fk(*, dry_run, existing_tables, added, failed):
    """Replace the historic CASCADE FK without deleting any Benefit rows."""
    from sqlalchemy import inspect, text

    if not {"benefits", "enterprise_initiatives"} <= existing_tables:
        return
    inspector = inspect(db.engine)
    matching = [
        fk
        for fk in inspector.get_foreign_keys("benefits")
        if fk.get("constrained_columns") == ["initiative_id"]
        and fk.get("referred_table") == "enterprise_initiatives"
    ]
    if len(matching) == 1:
        fk = matching[0]
        if (
            fk.get("name") == "fk_benefits_legacy_enterprise_initiative"
            and (fk.get("options") or {}).get("ondelete", "").upper() == "SET NULL"
        ):
            return

    label = "constraint.fk_benefits_legacy_enterprise_initiative"
    if dry_run:
        added.append(f"{label} :: REPLACE WITH ON DELETE SET NULL")
        return
    try:
        for fk in matching:
            name = fk.get("name")
            if name:
                db.session.execute(
                    text(f'ALTER TABLE "benefits" DROP CONSTRAINT "{name}"')
                )
        db.session.execute(
            text(
                """
                ALTER TABLE "benefits"
                ADD CONSTRAINT "fk_benefits_legacy_enterprise_initiative"
                FOREIGN KEY ("initiative_id") REFERENCES "enterprise_initiatives" ("id")
                ON DELETE SET NULL
                """
            )
        )
        db.session.commit()
        added.append(f"{label} :: REPLACE WITH ON DELETE SET NULL")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        failed.append(f"{label}: {str(exc)[:120]}")


def _ensure_materialisation_indexes(*, dry_run, existing_tables, added, failed):
    """Install canonical partial uniqueness on upgraded transformation tables."""
    from sqlalchemy import text

    for index_name, table_name in _MATERIALISATION_INDEXES:
        if table_name not in existing_tables:
            continue
        if db.session.scalar(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = :table_name AND indexname = :index_name"
            ),
            {"table_name": table_name, "index_name": index_name},
        ):
            continue
        table = db.metadata.tables[table_name]
        index = next((item for item in table.indexes if item.name == index_name), None)
        if index is None:
            failed.append(f"index.{index_name}: model index is not registered")
            continue
        label = f"index.{index_name}"
        if dry_run:
            added.append(f"{label} :: CREATE UNIQUE INDEX")
            continue
        try:
            if index_name in _DECISION_BRIEF_SCOPE_INDEXES:
                columns, predicate = _DECISION_BRIEF_SCOPE_INDEXES[index_name]
                schema_name = db.session.scalar(text("SELECT current_schema()"))
                quote = db.engine.dialect.identifier_preparer.quote
                db.session.execute(
                    text(
                        f"CREATE UNIQUE INDEX {quote(index_name)} "
                        f"ON {quote(schema_name)}.{quote(table_name)} ({columns}) "
                        f"WHERE {predicate}"
                    )
                )
                db.session.commit()
            else:
                # The catalog query above already checked the active schema.
                index.create(bind=db.engine, checkfirst=False)
            added.append(f"{label} :: CREATE UNIQUE INDEX")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            failed.append(f"{label}: {str(exc)[:120]}")


_MEMBERSHIP_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION archie_validate_transformation_membership()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'programme_workstreams' THEN
        IF NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.programme_id
              AND p.organization_id = NEW.organization_id
              AND p.record_kind = 'transformation_programme'
        ) THEN
            RAISE EXCEPTION 'workstream programme is outside its tenant or is not a transformation programme'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.lead_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.id = NEW.lead_id AND u.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'workstream lead is outside its tenant' USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'programme_role_assignments' THEN
        IF NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.programme_id AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'role programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.workstream_id AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.programme_id
        ) THEN
            RAISE EXCEPTION 'role workstream does not belong to its programme and tenant'
                USING ERRCODE = '23514';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.id = NEW.user_id AND u.organization_id = NEW.organization_id
        ) OR NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.id = NEW.assigned_by_id AND u.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'role user is outside its tenant' USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'programme_outcome_commitments' THEN
        IF NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.programme_id AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'outcome programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.workstream_id AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.programme_id
        ) THEN
            RAISE EXCEPTION 'outcome workstream does not belong to its programme and tenant'
                USING ERRCODE = '23514';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM users u
            WHERE u.id = NEW.owner_id AND u.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'outcome owner is outside its tenant' USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'measure_definitions' THEN
        IF NOT EXISTS (
            SELECT 1 FROM programme_outcome_commitments o
            WHERE o.id = NEW.outcome_commitment_id
              AND o.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'measure outcome is outside its tenant' USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'work_packages' THEN
        IF NEW.strategic_initiative_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.strategic_initiative_id
              AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'work package programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.programme_workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.programme_workstream_id
              AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.strategic_initiative_id
        ) THEN
            RAISE EXCEPTION 'work package programme and workstream disagree'
                USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'strategic_roadmap_items' THEN
        IF NEW.initiative_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.initiative_id AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'roadmap programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.programme_workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.programme_workstream_id
              AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.initiative_id
        ) THEN
            RAISE EXCEPTION 'roadmap programme and workstream disagree' USING ERRCODE = '23514';
        END IF;
        IF NEW.work_package_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM work_packages wp
            WHERE wp.id = NEW.work_package_id AND wp.organization_id = NEW.organization_id
              AND (NEW.initiative_id IS NULL OR wp.strategic_initiative_id IS NULL
                   OR wp.strategic_initiative_id = NEW.initiative_id)
              AND (NEW.programme_workstream_id IS NULL OR wp.programme_workstream_id IS NULL
                   OR wp.programme_workstream_id = NEW.programme_workstream_id)
        ) THEN
            RAISE EXCEPTION 'roadmap work package is outside its delivery scope'
                USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'benefits' THEN
        IF NEW.initiative_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM enterprise_initiatives p
            WHERE p.id = NEW.initiative_id AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'legacy benefit initiative is outside its tenant'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.strategic_initiative_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.strategic_initiative_id
              AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'benefit programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.programme_workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.programme_workstream_id
              AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.strategic_initiative_id
        ) THEN
            RAISE EXCEPTION 'benefit programme and workstream disagree' USING ERRCODE = '23514';
        END IF;
        IF NEW.outcome_commitment_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_outcome_commitments o
            WHERE o.id = NEW.outcome_commitment_id
              AND o.organization_id = NEW.organization_id
              AND o.programme_id = NEW.strategic_initiative_id
              AND (NEW.programme_workstream_id IS NULL OR o.workstream_id IS NULL
                   OR o.workstream_id = NEW.programme_workstream_id)
        ) THEN
            RAISE EXCEPTION 'benefit outcome is outside its programme scope'
                USING ERRCODE = '23514';
        END IF;

    ELSIF TG_TABLE_NAME = 'solutions' THEN
        IF NEW.initiative_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM strategic_initiatives p
            WHERE p.id = NEW.initiative_id AND p.organization_id = NEW.organization_id
        ) THEN
            RAISE EXCEPTION 'solution programme is outside its tenant' USING ERRCODE = '23514';
        END IF;
        IF NEW.workstream_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM programme_workstreams w
            WHERE w.id = NEW.workstream_id AND w.organization_id = NEW.organization_id
              AND w.programme_id = NEW.initiative_id
        ) THEN
            RAISE EXCEPTION 'solution programme and workstream disagree' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$
"""


def _ensure_membership_triggers(*, dry_run, existing_tables, added, failed):
    """Install deferrable database membership checks ordinary FKs cannot express."""
    from sqlalchemy import text

    present_tables = [table for table in _MEMBERSHIP_TABLES if table in existing_tables]
    missing_triggers = []
    for table in present_tables:
        # SQLAlchemy does not expose PostgreSQL triggers through Inspector.
        trigger_names = set(
            db.session.scalars(
                text(
                    """
                    SELECT tg.tgname
                    FROM pg_trigger tg
                    JOIN pg_class cls ON cls.oid = tg.tgrelid
                    JOIN pg_namespace namespace ON namespace.oid = cls.relnamespace
                    WHERE cls.relname = :table_name
                      AND namespace.nspname = current_schema()
                      AND NOT tg.tgisinternal
                    """
                ),
                {"table_name": table},
            )
        )
        if "trg_transformation_membership" not in trigger_names:
            missing_triggers.append(table)

    if dry_run:
        added.extend(
            f"trigger.{table}.trg_transformation_membership :: CREATE CONSTRAINT TRIGGER"
            for table in missing_triggers
        )
        return
    try:
        # Function bodies evolve independently of their trigger objects.  Refresh
        # the canonical body on every applying reconciliation and condition only
        # the trigger creation below.
        db.session.execute(text(_MEMBERSHIP_FUNCTION_SQL))
        for table in missing_triggers:
            db.session.execute(
                text(
                    f"""
                    CREATE CONSTRAINT TRIGGER trg_transformation_membership
                    AFTER INSERT OR UPDATE ON "{table}"
                    DEFERRABLE INITIALLY IMMEDIATE
                    FOR EACH ROW EXECUTE FUNCTION archie_validate_transformation_membership()
                    """
                )
            )
            added.append(
                f"trigger.{table}.trg_transformation_membership :: CREATE CONSTRAINT TRIGGER"
            )
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        failed.append(f"transformation_membership_triggers: {str(exc)[:120]}")


def _column_clause(col, dialect):
    """Render `"name" TYPE DEFAULT ...` for one column, or None if it can't be.

    Hand-building the DEFAULT clause would be wrong: SQLAlchemy quotes a plain
    string server_default but emits a text() one raw, and getting that backwards
    produces either a syntax error or a literal that means something else. So
    let SQLAlchemy's own compiler render it.

    NOT NULL is then stripped deliberately. It is the one part of a column
    definition an existing row can fail, and reconcile-schema's contract is that
    it never rewrites or rejects existing data. The ORM still enforces the
    constraint on write; the database simply stays permissive about rows that
    predate the column.
    """
    import re

    from sqlalchemy.schema import CreateColumn

    try:
        rendered = str(CreateColumn(col).compile(dialect=dialect)).strip()
    except Exception:
        return None
    if not rendered:
        return None
    return re.sub(r"\s+NOT\s+NULL\b", "", rendered).strip()


def _backfill_roadmap_organizations(*, dry_run, existing_tables, added, failed):
    """Recover the tenant key for RoadmapItems that predate TenantMixin.

    A roadmap item's canonical programme is the only trustworthy tenant
    provenance available in the old schema.  Rows without that provenance are
    reported and left untouched; guessing would risk assigning another
    organisation's data to the active tenant.
    """
    from sqlalchemy import inspect, text

    required = {"strategic_roadmap_items", "strategic_initiatives"}
    if not required <= existing_tables:
        return
    live_columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("strategic_roadmap_items")
    }
    if "organization_id" not in live_columns:
        return

    before = db.session.scalar(
        text(
            "SELECT count(*) FROM strategic_roadmap_items "
            "WHERE organization_id IS NULL"
        )
    )
    eligible = db.session.scalar(
        text(
            """
            SELECT count(*)
            FROM strategic_roadmap_items r
            JOIN strategic_initiatives p ON p.id = r.initiative_id
            WHERE r.organization_id IS NULL
              AND p.organization_id IS NOT NULL
            """
        )
    )
    conflicts = db.session.scalar(
        text(
            """
            SELECT count(*)
            FROM strategic_roadmap_items r
            JOIN strategic_initiatives p ON p.id = r.initiative_id
            WHERE r.organization_id IS NOT NULL
              AND p.organization_id IS NOT NULL
              AND r.organization_id <> p.organization_id
            """
        )
    )
    unresolved = before - eligible
    updated = eligible
    if not dry_run and eligible:
        result = db.session.execute(
            text(
                """
                UPDATE strategic_roadmap_items AS r
                SET organization_id = p.organization_id
                FROM strategic_initiatives AS p
                WHERE r.initiative_id = p.id
                  AND r.organization_id IS NULL
                  AND p.organization_id IS NOT NULL
                """
            )
        )
        updated = result.rowcount
        db.session.commit()

    if before or conflicts:
        added.append(
            "backfill.strategic_roadmap_items.organization_id "
            f":: before={before}, updated={updated}, "
            f"unresolved={unresolved}, conflicts={conflicts}"
        )
    if unresolved:
        failed.append(
            "backfill.strategic_roadmap_items.organization_id: "
            f"{unresolved} unresolved row(s); no programme tenant provenance"
        )
    if conflicts:
        failed.append(
            "backfill.strategic_roadmap_items.organization_id: "
            f"{conflicts} existing row(s) conflict with their programme tenant"
        )


def _reconcile(dry_run=False):
    """Return (added, failed, missing_tables, blocking) lists of "table.column".

    `blocking` is the REVERSE direction: columns the live database has that the
    models do not declare, restricted to NOT NULL columns with no server default.
    Those are the ones that break writes — the ORM omits the column from its INSERT
    and Postgres rejects the row.

    This direction was previously invisible. `value_streams.organization_id` was
    NOT NULL in production while the ValueStream model did not declare the column
    at all, so every attempt to create a value stream failed with NotNullViolation,
    and this command still reported "0 column(s) would add" because it only ever
    compared model -> database.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    active_schema = db.session.scalar(text("SELECT current_schema()"))
    existing_tables = set(insp.get_table_names(schema=active_schema))
    dialect = db.engine.dialect
    added, failed, missing_tables, blocking = [], [], [], []

    for table in db.metadata.tables.values():
        if table.name not in existing_tables:
            continue
        model_cols = {c.name for c in table.columns}
        for live in insp.get_columns(table.name):
            if live["name"] in model_cols:
                continue
            if live.get("nullable", True):
                continue  # extra but harmless: the ORM simply never writes it
            if live.get("default") is not None or live.get("autoincrement"):
                continue  # the database fills it
            blocking.append(f"{table.name}.{live['name']} :: NOT NULL, no default")

    # .tables.values() (not sorted_tables) so FK-cycle tables are still checked.
    for table in db.metadata.tables.values():
        if table.name not in existing_tables:
            continue
        live_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in live_cols:
                continue
            try:
                coltype = col.type.compile(dialect=dialect)
            except Exception:
                coltype = "TEXT"
            coldef = _column_clause(col, dialect) or f'"{col.name}" {coltype}'
            label = f"{table.name}.{col.name}"
            if dry_run:
                added.append(f"{label} :: {coltype}")
                continue
            ddl = (
                f'ALTER TABLE "{table.name}" '
                f'ADD COLUMN IF NOT EXISTS {coldef}'
            )
            try:
                db.session.execute(text(ddl))
                db.session.commit()
                added.append(f"{label} :: {coltype}")
            except Exception as exc:  # noqa: BLE001 — keep going, report at end
                db.session.rollback()
                failed.append(f"{label}: {str(exc)[:120]}")

    # Upgrade existing transformation tables before creating new ones.  Each
    # guarded table installs the complete transformation guard set in its
    # after_create hook; creating a new table while an older peer still lacks a
    # newly introduced column makes that hook fail and rolls back the upgrade.
    _create_transformation_tables(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    # Table creation changes the catalog; do not keep using a stale inspector.
    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names(schema=active_schema))
    missing_tables.extend(
        table.name
        for table in db.metadata.tables.values()
        if table.name not in existing_tables
    )

    _backfill_roadmap_organizations(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    _ensure_evidence_waiver_constraint(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    _ensure_transformation_foreign_keys(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    _ensure_benefit_legacy_fk(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    _ensure_materialisation_indexes(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )
    _ensure_membership_triggers(
        dry_run=dry_run,
        existing_tables=existing_tables,
        added=added,
        failed=failed,
    )

    if dry_run:
        try:
            from app.models.transformation_db_guards import (
                inspect_transformation_db_guards,
            )

            guard_drift = inspect_transformation_db_guards(db.session.connection())
            failed.extend(
                f"transformation_db_guards:{item}" for item in guard_drift
            )
        except Exception as exc:  # noqa: BLE001 — report inspection failure
            failed.append(f"transformation_db_guards_inspection: {str(exc)[:120]}")
    else:
        try:
            from app.models.transformation_db_guards import (
                ensure_transformation_db_guards,
            )

            ensure_transformation_db_guards(db.session.connection())
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 — report alongside column failures
            db.session.rollback()
            failed.append(f"transformation_db_guards: {str(exc)[:120]}")

    if not dry_run:
        try:
            from app.models.arb_submission_evidence import (
                ensure_evidence_immutability_triggers,
            )

            ensure_evidence_immutability_triggers(db.session.connection())
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 — report alongside column failures
            db.session.rollback()
            failed.append(f"evidence_immutability_triggers: {str(exc)[:120]}")

    if dry_run:
        # When either typed table is absent, dry-run already reports its CREATE
        # action above.  Its functions/triggers cannot exist yet, so describing
        # those dependent objects as failures would turn a repairable pre-feature
        # schema into a false red gate.
        required_arb_tables = {
            "arb_subject_evidence_snapshots",
            "arb_review_cycles",
            "arb_review_items",
        }
        if required_arb_tables <= existing_tables:
            try:
                from app.models.architecture_review_board import (
                    inspect_arb_cycle_constraints,
                )

                arb_drift = inspect_arb_cycle_constraints(db.session.connection())
                failed.extend(f"typed_arb_constraints:{item}" for item in arb_drift)
            except Exception as exc:  # noqa: BLE001 — report inspection failure
                failed.append(
                    f"typed_arb_constraints_inspection: {str(exc)[:120]}"
                )
    else:
        try:
            from app.models.architecture_review_board import (
                ensure_arb_cycle_constraints,
            )
            from app.models.transformation_decision import (
                ensure_arb_subject_snapshot_immutability,
            )

            connection = db.session.connection()
            ensure_arb_subject_snapshot_immutability(connection)
            ensure_arb_cycle_constraints(connection)
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 — report alongside schema failures
            db.session.rollback()
            failed.append(f"typed_arb_constraints: {str(exc)[:120]}")

    return added, failed, missing_tables, blocking


@click.command("reconcile-schema")
@click.option("--dry-run", is_flag=True, help="Report drift without altering anything.")
@with_appcontext
def reconcile_schema(dry_run):
    """Add columns the models declare but existing tables lack (safe, idempotent)."""
    added, failed, missing_tables, blocking = _reconcile(dry_run=dry_run)

    verb = "would add" if dry_run else "added"
    click.echo(f"reconcile-schema: {len(added)} column(s) {verb}.")
    for a in added:
        click.echo(f"  + {a}")
    if missing_tables:
        click.echo(
            f"\n{len(missing_tables)} table(s) absent — run 'flask init-db' to "
            f"create them: {', '.join(sorted(missing_tables)[:10])}"
            + (" ..." if len(missing_tables) > 10 else "")
        )
    if blocking:
        click.echo(
            f"\n{len(blocking)} column(s) present in the DATABASE but absent from the "
            "models, NOT NULL with no default — INSERTs into these tables will fail:"
        )
        for b in blocking:
            click.echo(f"  ! {b}")

    if failed:
        click.echo(f"\n{len(failed)} column(s) FAILED:")
        for f in failed:
            click.echo(f"  ! {f}")
        raise SystemExit(1)
    if not added and not dry_run:
        click.echo("Schema already matches the models. Nothing to do.")


def init_app(app):
    """Register the reconcile-schema CLI command."""
    app.cli.add_command(reconcile_schema)
