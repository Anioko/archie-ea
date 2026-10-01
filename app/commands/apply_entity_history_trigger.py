"""
Schema fix: apply-entity-history-trigger.

``reconcile-schema`` is ADD-COLUMN-only and can never create a trigger, so
the generic trigger every change to ``archimate_elements`` and
``archimate_relationships`` must go through (one ``entity_history`` version
per INSERT/UPDATE, non-overlapping recorded intervals) needs its own deploy
step, the same convention
``apply_unified_capability_provenance_migration.py`` already uses for
"a DDL object reconcile-schema cannot create".

One PL/pgSQL function, ``entity_history_record_version()``, shared by both
tables' triggers:

- On INSERT: writes one open (``valid_to IS NULL``) version.
- On UPDATE: closes the row's current open version (``valid_to``,
  ``superseded_at`` both set to the same timestamp) and opens a new one —
  never two writes that could observe different "now()" values, since both
  happen in the same trigger invocation with one captured timestamp.
- A ``DELETE`` is intentionally not covered here (PR 1 scope is INSERT/UPDATE
  per the brief); a deleted element's last version simply stays open, which
  is correct for "the model as of a date" answered from a date before the
  delete.

Idempotent: ``CREATE OR REPLACE FUNCTION`` and ``DROP TRIGGER IF
EXISTS``/``CREATE TRIGGER`` are both safe to re-run; safe to re-run on every
deploy, matching ``apply-unified-capability-provenance-migration``'s own
convention of re-applying rather than checking a version marker.

    flask --app manage apply-entity-history-trigger
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app import db

TABLES = ("archimate_elements", "archimate_relationships")

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION entity_history_record_version()
RETURNS TRIGGER AS $$
DECLARE
    -- statement_timestamp(), not NOW()/transaction_timestamp(): NOW() is
    -- stable for the whole transaction, so two updates on the same row in
    -- one transaction (no intervening COMMIT) would both capture the same
    -- value, closing the first version at the exact instant it opened --
    -- a zero-length interval (pr311-v1 review, DEFECT D1).
    now_ts TIMESTAMP := statement_timestamp();
    row_org_id INTEGER;
    row_snapshot JSON;
BEGIN
    row_org_id := NEW.organization_id;
    row_snapshot := row_to_json(NEW);

    IF TG_OP = 'UPDATE' THEN
        UPDATE entity_history
        SET valid_to = now_ts, superseded_at = now_ts
        WHERE table_name = TG_TABLE_NAME
          AND record_id = NEW.id
          AND valid_to IS NULL;
    END IF;

    INSERT INTO entity_history
        (organization_id, table_name, record_id, snapshot,
         valid_from, valid_to, recorded_at, source)
    VALUES
        (row_org_id, TG_TABLE_NAME, NEW.id, row_snapshot,
         now_ts, NULL, now_ts, 'trigger');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


@click.command("apply-entity-history-trigger")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def apply_entity_history_trigger(dry_run):
    """Create/replace the entity_history trigger on archimate_elements and
    archimate_relationships. Idempotent."""
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names())

    if "entity_history" not in existing_tables:
        click.echo(
            "  - entity_history table absent (init-db/reconcile-schema runs "
            "before this step) — nothing to do this run"
        )
        return

    if dry_run:
        click.echo("  - would CREATE OR REPLACE FUNCTION entity_history_record_version()")
        for table in TABLES:
            click.echo(f"  - would ensure trigger entity_history_trg on {table}")
        return

    conn = db.session.connection()
    conn.execute(text(FUNCTION_SQL))

    for table in TABLES:
        if table not in existing_tables:
            click.echo(f"  - {table}: table absent, skipping its trigger")
            continue
        conn.execute(text(f'DROP TRIGGER IF EXISTS entity_history_trg ON "{table}"'))
        conn.execute(text(f"""
            CREATE TRIGGER entity_history_trg
            AFTER INSERT OR UPDATE ON "{table}"
            FOR EACH ROW
            EXECUTE FUNCTION entity_history_record_version()
        """))
        click.echo(f"  + {table}: entity_history_trg ensured")

    db.session.commit()
    click.echo("apply-entity-history-trigger: done.")


def init_app(app):
    """Register the apply-entity-history-trigger CLI command."""
    app.cli.add_command(apply_entity_history_trigger)
