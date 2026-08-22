"""Transformation schema reconciliation for fresh and long-lived databases."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Column, Integer, String, Table, create_engine, inspect, text

from app import db
from app.commands.reconcile_schema import _reconcile


@pytest.fixture
def pre_feature_transformation_schema(app):
    """Real pre-Task-1 tables in an isolated PostgreSQL schema.

    Unlike the old synthetic-column test, these are the actual table names and
    legacy columns/FKs.  A dedicated search_path lets the production reconciler
    operate unchanged without touching the shared public test schema.
    """
    schema = f"test_transformation_pre_{uuid.uuid4().hex[:12]}"
    with app.app_context():
        public_engine = db.engine
        with public_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(
                text(
                    f"""
                    CREATE TABLE "{schema}".organizations (
                        id INTEGER PRIMARY KEY
                    );
                    CREATE TABLE "{schema}".users (
                        id INTEGER PRIMARY KEY,
                        organization_id INTEGER NOT NULL
                    );
                    CREATE TABLE "{schema}".strategic_initiatives (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(256) NOT NULL,
                        organization_id INTEGER NOT NULL
                    );
                    CREATE TABLE "{schema}".enterprise_initiatives (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        organization_id INTEGER
                    );
                    CREATE TABLE "{schema}".work_packages (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        organization_id INTEGER NOT NULL
                    );
                    CREATE TABLE "{schema}".strategic_roadmap_items (
                        id INTEGER PRIMARY KEY,
                        initiative_id INTEGER REFERENCES "{schema}".strategic_initiatives(id),
                        title VARCHAR(256) NOT NULL
                    );
                    CREATE TABLE "{schema}".benefits (
                        id INTEGER PRIMARY KEY,
                        initiative_id INTEGER,
                        name VARCHAR(255) NOT NULL,
                        CONSTRAINT benefits_initiative_id_fkey
                          FOREIGN KEY (initiative_id)
                          REFERENCES "{schema}".enterprise_initiatives(id)
                          ON DELETE CASCADE
                    );
                    CREATE TABLE "{schema}".solutions (
                        id INTEGER PRIMARY KEY,
                        initiative_id INTEGER REFERENCES "{schema}".strategic_initiatives(id),
                        name VARCHAR(255) NOT NULL,
                        organization_id INTEGER NOT NULL
                    );
                    INSERT INTO "{schema}".organizations (id) VALUES (1), (2);
                    INSERT INTO "{schema}".users (id, organization_id) VALUES (1, 1), (2, 2);
                    INSERT INTO "{schema}".strategic_initiatives
                        (id, name, organization_id)
                        VALUES (10, 'Programme A', 1), (20, 'Programme B', 2);
                    INSERT INTO "{schema}".enterprise_initiatives
                        (id, name, organization_id)
                        VALUES (30, 'Legacy A', 1);
                    INSERT INTO "{schema}".strategic_roadmap_items
                        (id, initiative_id, title)
                        VALUES (100, 10, 'Existing roadmap row');
                    INSERT INTO "{schema}".benefits (id, initiative_id, name)
                        VALUES (200, 30, 'Existing benefit');
                    INSERT INTO "{schema}".solutions
                        (id, initiative_id, name, organization_id)
                        VALUES (300, 10, 'Existing solution', 1);
                    """
                )
            )

        isolated_engine = create_engine(
            public_engine.url,
            connect_args={"options": f"-csearch_path={schema},public"},
        )
        original_engine = db.engines[None]
        db.session.remove()
        db.engines[None] = isolated_engine
        try:
            yield schema, isolated_engine
        finally:
            db.session.remove()
            db.engines[None] = original_engine
            isolated_engine.dispose()
            with public_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_fresh_schema_contains_transformation_tables(app, _schema):
    expected = {
        "programme_workstreams",
        "programme_role_assignments",
        "programme_outcome_commitments",
        "measure_definitions",
    }
    with app.app_context():
        assert expected <= set(inspect(db.engine).get_table_names())


def test_existing_schema_reconciles_additive_columns_idempotently(app, _schema):
    table_name = f"test_reconcile_{uuid.uuid4().hex[:12]}"
    model_table = Table(
        table_name,
        db.metadata,
        Column("id", Integer, primary_key=True),
        Column("additive_value", String(40), nullable=True),
    )
    try:
        with app.app_context(), db.engine.begin() as connection:
            connection.execute(text(f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY)'))

        with app.app_context():
            dry_added, dry_failed, _missing, _blocking = _reconcile(dry_run=True)
            assert dry_failed == []
            assert any(
                item.startswith(f"{table_name}.additive_value ::") for item in dry_added
            )
            assert "additive_value" not in {
                column["name"] for column in inspect(db.engine).get_columns(table_name)
            }

            first_added, first_failed, _missing, _blocking = _reconcile(dry_run=False)
            assert first_failed == []
            assert any(
                item.startswith(f"{table_name}.additive_value ::") for item in first_added
            )
            second_added, second_failed, _missing, _blocking = _reconcile(dry_run=False)
            assert second_failed == []
            assert not any(item.startswith(f"{table_name}.") for item in second_added)
    finally:
        with app.app_context(), db.engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        db.metadata.remove(model_table)


def test_genuine_pre_feature_schema_backfills_roadmap_and_repairs_delivery_fks(
    app, pre_feature_transformation_schema
):
    _schema_name, isolated_engine = pre_feature_transformation_schema
    with app.app_context():
        dry_added, dry_failed, _missing, _blocking = _reconcile(dry_run=True)
        assert dry_failed == []
        assert any(
            item.startswith("strategic_roadmap_items.organization_id ::")
            for item in dry_added
        )
        with isolated_engine.connect() as connection:
            assert "organization_id" not in {
                column["name"]
                for column in inspect(connection).get_columns("strategic_roadmap_items")
            }

        first_added, first_failed, _missing, _blocking = _reconcile(dry_run=False)
        assert first_failed == []
        assert (
            "backfill.strategic_roadmap_items.organization_id "
            ":: before=1, updated=1, unresolved=0, conflicts=0"
        ) in first_added

        with isolated_engine.connect() as connection:
            roadmap_org = connection.scalar(
                text("SELECT organization_id FROM strategic_roadmap_items WHERE id = 100")
            )
            assert roadmap_org == 1
            benefit_fk = connection.execute(
                text(
                    """
                    SELECT rc.delete_rule
                    FROM information_schema.referential_constraints rc
                    WHERE rc.constraint_name = 'fk_benefits_legacy_enterprise_initiative'
                      AND rc.constraint_schema = current_schema()
                    """
                )
            ).scalar_one()
            assert benefit_fk == "SET NULL"
            solution_fk = connection.execute(
                text(
                    """
                    SELECT rc.delete_rule
                    FROM information_schema.referential_constraints rc
                    WHERE rc.constraint_name = 'fk_solutions_strategic_initiative'
                      AND rc.constraint_schema = current_schema()
                    """
                )
            ).scalar_one()
            assert solution_fk == "RESTRICT"

        second_added, second_failed, _missing, _blocking = _reconcile(dry_run=False)
        assert second_failed == []
        assert not any(item.startswith("backfill.strategic_roadmap_items") for item in second_added)


def test_pre_feature_roadmap_without_tenant_provenance_is_reported_not_guessed(
    app, pre_feature_transformation_schema
):
    _schema_name, isolated_engine = pre_feature_transformation_schema
    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []
        with isolated_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO strategic_roadmap_items
                        (id, initiative_id, title, organization_id)
                    VALUES (101, NULL, 'Unowned legacy roadmap row', NULL)
                    """
                )
            )

        added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert any(
            item == (
                "backfill.strategic_roadmap_items.organization_id "
                ":: before=1, updated=0, unresolved=1, conflicts=0"
            )
            for item in added
        )
        assert any("1 unresolved row(s)" in item for item in failed)
        with isolated_engine.connect() as connection:
            assert connection.scalar(
                text("SELECT organization_id FROM strategic_roadmap_items WHERE id = 101")
            ) is None


def test_transformation_fk_checks_and_membership_triggers_are_installed(app, _schema):
    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []
        constraints = db.session.execute(
            text(
                """
                SELECT c.conname, c.contype, c.confdeltype, t.relname AS table_name
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname IN (
                    'programme_workstreams', 'programme_role_assignments',
                    'programme_outcome_commitments', 'measure_definitions',
                    'work_packages', 'strategic_roadmap_items', 'benefits', 'solutions'
                )
                """
            )
        ).mappings().all()
        names = {row["conname"] for row in constraints}
        assert "ck_programme_workstream_type" in names
        assert "ck_programme_outcome_direction" in names
        assert "ck_measure_definition_aggregation" in names

        benefit_legacy_fk = next(
            row
            for row in constraints
            if row["table_name"] == "benefits"
            and row["contype"] == "f"
            and row["conname"] == "fk_benefits_legacy_enterprise_initiative"
        )
        assert benefit_legacy_fk["confdeltype"] == "n"  # SET NULL

        trigger_tables = set(
            db.session.scalars(
                text(
                    """
                    SELECT event_object_table
                    FROM information_schema.triggers
                    WHERE trigger_name = 'trg_transformation_membership'
                    """
                )
            )
        )
        assert {
            "programme_workstreams",
            "programme_role_assignments",
            "programme_outcome_commitments",
            "measure_definitions",
            "work_packages",
            "strategic_roadmap_items",
            "benefits",
            "solutions",
        } <= trigger_tables


def test_canonical_programme_and_workstream_fks_use_delete_restrict(app, _schema):
    expected = {
        ("work_packages", "strategic_initiative_id"),
        ("work_packages", "programme_workstream_id"),
        ("strategic_roadmap_items", "initiative_id"),
        ("strategic_roadmap_items", "programme_workstream_id"),
        ("benefits", "strategic_initiative_id"),
        ("benefits", "programme_workstream_id"),
        ("benefits", "outcome_commitment_id"),
        ("solutions", "initiative_id"),
        ("solutions", "workstream_id"),
    }
    with app.app_context():
        _added, failed, _missing, _blocking = _reconcile(dry_run=False)
        assert failed == []
        rows = db.session.execute(
            text(
                """
                SELECT tc.table_name, kcu.column_name, rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                JOIN information_schema.referential_constraints rc
                  ON rc.constraint_schema = tc.constraint_schema
                 AND rc.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND (tc.table_name, kcu.column_name) IN (
                    ('work_packages', 'strategic_initiative_id'),
                    ('work_packages', 'programme_workstream_id'),
                    ('strategic_roadmap_items', 'initiative_id'),
                    ('strategic_roadmap_items', 'programme_workstream_id'),
                    ('benefits', 'strategic_initiative_id'),
                    ('benefits', 'programme_workstream_id'),
                    ('benefits', 'outcome_commitment_id'),
                    ('solutions', 'initiative_id'),
                    ('solutions', 'workstream_id')
                  )
                """
            )
        ).mappings().all()
        assert {(row["table_name"], row["column_name"]) for row in rows} == expected
        assert all(row["delete_rule"] == "RESTRICT" for row in rows)


def test_materialisation_indexes_are_partial_and_unique(app, _schema):
    with app.app_context():
        rows = db.session.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE indexname IN (
                    'uq_work_package_materialisation',
                    'uq_roadmap_item_materialisation',
                    'uq_benefit_materialisation'
                )
                """
            )
        ).mappings().all()
        assert {row["indexname"] for row in rows} == {
            "uq_work_package_materialisation",
            "uq_roadmap_item_materialisation",
            "uq_benefit_materialisation",
        }
        assert all("UNIQUE INDEX" in row["indexdef"] for row in rows)
        assert all("WHERE (materialisation_key IS NOT NULL)" in row["indexdef"] for row in rows)
