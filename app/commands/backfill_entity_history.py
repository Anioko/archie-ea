"""
Tenancy/history backfill: backfill-entity-history.

``apply-entity-history-trigger`` only records versions for a row inserted or
updated AFTER the trigger exists. Every element and relationship that
already existed needs one seeded ("open", ``valid_to IS NULL``) version so
"the model as of a date" (PR 2) has something to answer from for dates
before this brief shipped, instead of silently returning nothing for every
pre-existing row.

``recorded_at`` is backfilled from the audit log's earliest matching entry
for that row where one exists (``soc2_audit_log`` filtered by
``table_name``/``record_id``); left ``NULL`` ("unknown") where none does,
per CLAUDE.md's null-display convention — never guessed at as "now" or as
the row's own ``created_at``, which is not evidence of when history started
being tracked.

Idempotent: a row already carrying an open ``entity_history`` version is
skipped. Runs one organisation at a time with raw SQL carrying an explicit
``organization_id`` predicate (the ORM tenant listener does not apply
outside a request context — see CLAUDE.md's multi-tenancy section).

    flask --app manage backfill-entity-history --dry-run
    flask --app manage backfill-entity-history
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app import db

TABLES = ("archimate_elements", "archimate_relationships")


def _organization_ids(conn):
    return [r[0] for r in conn.execute(text("SELECT id FROM organizations ORDER BY id")).fetchall()]


def _backfill_table(conn, table, org_id, dry_run):
    # Rows for this org that have no entity_history row at all yet (neither
    # open nor closed) -- a row the trigger already versioned (e.g. created
    # after this command's own deploy but before this run) is left alone.
    pending = conn.execute(text(f"""
        SELECT t.id FROM "{table}" t
        WHERE t.organization_id = :org_id
          AND NOT EXISTS (
              SELECT 1 FROM entity_history eh
              WHERE eh.table_name = :table_name AND eh.record_id = t.id
          )
    """), {"org_id": org_id, "table_name": table}).fetchall()

    if not pending:
        return 0

    if dry_run:
        return len(pending)

    for (record_id,) in pending:
        recorded_at = conn.execute(text("""
            SELECT MIN(created_at) FROM soc2_audit_log
            WHERE table_name = :table_name AND record_id = :record_id
        """), {"table_name": table, "record_id": record_id}).scalar()

        conn.execute(text(f"""
            INSERT INTO entity_history
                (organization_id, table_name, record_id, snapshot,
                 valid_from, valid_to, recorded_at, source)
            SELECT :org_id, :table_name, :record_id, row_to_json(t.*),
                   COALESCE(:recorded_at, NOW()), NULL, :recorded_at, 'backfill'
            FROM "{table}" t WHERE t.id = :record_id
        """), {
            "org_id": org_id, "table_name": table, "record_id": record_id,
            "recorded_at": recorded_at,
        })

    return len(pending)


@click.command("backfill-entity-history")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def backfill_entity_history(dry_run):
    """Seed one open entity_history version per pre-existing element/relationship."""
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names())
    if "entity_history" not in existing_tables:
        click.echo("  - entity_history table absent — nothing to do this run")
        return

    org_ids = _organization_ids(db.session.connection())
    total = 0
    for org_id in org_ids:
        # A fresh connection each iteration: db.session.remove() below
        # invalidates the previous one, and reusing it here would break.
        conn = db.session.connection()
        for table in TABLES:
            if table not in existing_tables:
                continue
            count = _backfill_table(conn, table, org_id, dry_run)
            total += count
            if count:
                verb = "would seed" if dry_run else "seeded"
                click.echo(f"  {'~' if dry_run else '+'} org {org_id}, {table}: {verb} {count} version(s)")
        if not dry_run:
            db.session.commit()
        db.session.remove()

    click.echo(f"backfill-entity-history: {'would seed' if dry_run else 'seeded'} {total} version(s) total.")


def init_app(app):
    """Register the backfill-entity-history CLI command."""
    app.cli.add_command(backfill_entity_history)
