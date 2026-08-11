"""
flask backfill-value-stream-tenancy — give the value-stream tables a tenant.

ValueStream, ValueStreamStage and CapabilityValueStreamMapping shipped without
an organization_id. The tenant filter in app/middleware/tenant_isolation.py
works by attaching ``organization_id == g.current_org_id`` to every SELECT on a
TenantMixin model, so a model without that column is not merely unfiltered — it
is structurally impossible to filter. Any authenticated user of any tenant could
read, rename and delete any other tenant's value streams over HTTP.

Those models now use TenantMixin. This command completes the change on an
existing database, because two things stand in the way:

  1. `flask reconcile-schema` adds a missing column as plain nullable with no FK
     and no index (see its ALTER TABLE ... ADD COLUMN IF NOT EXISTS). Rows that
     predate the change therefore hold NULL, and because the filter compares
     with `=`, NULL matches NOTHING — every existing value stream would silently
     vanish from the UI for every user.

  2. ValueStream.code was UNIQUE globally, so two tenants could not both define
     an "OTC" value stream. Uniqueness has to become per-organisation.

Idempotent; safe to re-run. Run AFTER reconcile-schema:

    flask --app manage backfill-value-stream-tenancy --dry-run
    flask --app manage backfill-value-stream-tenancy
    flask --app manage backfill-value-stream-tenancy --org-id 3
"""

import click
from flask.cli import with_appcontext

from app import db

TABLES = ("value_streams", "unified_value_stream_stages", "capability_value_stream_mapping")


def _resolve_org_id(conn, explicit):
    from sqlalchemy import text
    if explicit is not None:
        row = conn.execute(text("SELECT id FROM organizations WHERE id = :i"), {"i": explicit}).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit
    rows = conn.execute(text("SELECT id, name FROM organizations ORDER BY id")).fetchall()
    if len(rows) == 1:
        click.echo(f"  single organization found: id={rows[0][0]} ({rows[0][1]}) — assigning orphans to it")
        return rows[0][0]
    # Refuse to guess. Picking wrongly hands one tenant's data to another, which
    # is the exact failure this command exists to prevent.
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which one "
        "owns the pre-existing value streams."
    )


@click.command("backfill-value-stream-tenancy")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_value_stream_tenancy(dry_run, org_id):
    """Backfill organization_id on the value-stream tables and harden the columns."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    conn = db.session.connection()

    present = [t for t in TABLES if t in live]
    for missing in (t for t in TABLES if t not in live):
        click.echo(f"  - {missing}: table absent, skipping")
    if not present:
        click.echo("No value-stream tables present. Nothing to do.")
        return

    # Every table must have the column before anything can be backfilled.
    for t in present:
        cols = {c["name"] for c in insp.get_columns(t)}
        if "organization_id" not in cols:
            if dry_run:
                click.echo(f"  - {t}: would ADD COLUMN organization_id")
                continue
            conn.execute(text(f'ALTER TABLE "{t}" ADD COLUMN IF NOT EXISTS organization_id INTEGER'))
            click.echo(f"  + {t}: added organization_id")

    orphan_counts = {}
    for t in present:
        cols = {c["name"] for c in insp.get_columns(t)}
        if "organization_id" not in cols and dry_run:
            continue
        n = conn.execute(text(f'SELECT count(*) FROM "{t}" WHERE organization_id IS NULL')).scalar()
        orphan_counts[t] = n

    total_orphans = sum(orphan_counts.values())
    if total_orphans:
        target = _resolve_org_id(conn, org_id)
        for t, n in orphan_counts.items():
            if not n:
                continue
            if dry_run:
                click.echo(f"  - {t}: would assign {n} orphaned row(s) to org {target}")
                continue
            conn.execute(
                text(f'UPDATE "{t}" SET organization_id = :o WHERE organization_id IS NULL'),
                {"o": target},
            )
            click.echo(f"  + {t}: assigned {n} orphaned row(s) to org {target}")
    else:
        click.echo("  no orphaned rows — nothing to assign")

    if dry_run:
        click.echo("dry-run: no changes committed.")
        db.session.rollback()
        return

    # Only now can NOT NULL hold. Index and FK are added here because
    # reconcile-schema adds neither.
    for t in present:
        for ddl, label in (
            (f'CREATE INDEX IF NOT EXISTS ix_{t}_organization_id ON "{t}" (organization_id)', "index"),
            (f'ALTER TABLE "{t}" ALTER COLUMN organization_id SET NOT NULL', "not-null"),
        ):
            try:
                conn.execute(text(ddl))
                click.echo(f"  + {t}: {label}")
            except Exception as exc:  # noqa: BLE001
                click.echo(f"  ! {t}: {label} skipped ({str(exc)[:100]})")

    # value_streams.code was globally unique; make it unique per tenant instead.
    #
    # Both spellings have to go. The column was declared
    # `unique=True, index=True`, which Postgres implements as the unique INDEX
    # ix_value_streams_code, not as a table constraint — so dropping
    # value_streams_code_key alone was a no-op with IF EXISTS, reported success,
    # and left every upgraded database still rejecting a second organisation's
    # "OTC". Measured on a database that had run this command: both
    # ix_value_streams_code and uq_value_streams_org_code were present.
    if "value_streams" in present:
        for ddl, label in (
            ('CREATE UNIQUE INDEX IF NOT EXISTS uq_value_streams_org_code ON "value_streams" (organization_id, code)', "added unique(organization_id, code)"),
            ('ALTER TABLE "value_streams" DROP CONSTRAINT IF EXISTS value_streams_code_key', "dropped global unique(code) constraint"),
            ('DROP INDEX IF EXISTS ix_value_streams_code', "dropped global unique(code) index"),
            ('CREATE INDEX IF NOT EXISTS ix_value_streams_code ON "value_streams" (code)', "restored the plain lookup index on code"),
        ):
            try:
                conn.execute(text(ddl))
                click.echo(f"  + value_streams: {label}")
            except Exception as exc:  # noqa: BLE001
                click.echo(f"  ! value_streams: {label} skipped ({str(exc)[:100]})")

    db.session.commit()
    click.echo("backfill-value-stream-tenancy: done.")


def init_app(app):
    """Register the backfill-value-stream-tenancy CLI command."""
    app.cli.add_command(backfill_value_stream_tenancy)
