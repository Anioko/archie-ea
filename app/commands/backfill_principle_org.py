"""
flask backfill-principle-org — give the ArchiMate Principle rows a tenant.

`Principle` (app/models/models.py) shipped without an organization_id. The tenant
filter in app/middleware/tenant_isolation.py attaches
``organization_id == g.current_org_id`` to every SELECT on a TenantMixin model, so
a model without that column is not merely unfiltered — it is structurally
impossible to filter. Any authenticated user of any tenant could read every other
tenant's architecture principles.

Principle now uses TenantMixin. This command completes the change on an existing
database:

  `flask reconcile-schema` adds a missing column as plain nullable, with no FK and
  no index. Rows predating the change therefore hold NULL, and because the filter
  compares with `=`, NULL matches NOTHING — every existing principle silently
  vanishes from the governance dashboard, the ARB screens and the AI chat tools
  for every user. This command assigns them an owner.

Unlike backfill-value-stream-tenancy, this does NOT set the column NOT NULL: the
model deliberately declares organization_id as nullable so the column can land via
reconcile-schema without a maintenance window (see the comment on Principle).
Tightening to NOT NULL is a follow-up once every install is known to be backfilled;
doing it here would put the database out of step with the ORM and trip the
schema-drift gate.

Idempotent; safe to re-run. Run AFTER reconcile-schema:

    flask --app manage backfill-principle-org --dry-run
    flask --app manage backfill-principle-org
    flask --app manage backfill-principle-org --org-id 3
"""

import click
from flask.cli import with_appcontext

from app import db

TABLE = "principles"


def _resolve_org_id(conn, explicit):
    from sqlalchemy import text

    if explicit is not None:
        row = conn.execute(
            text("SELECT id FROM organizations WHERE id = :i"), {"i": explicit}
        ).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit
    rows = conn.execute(text("SELECT id, name FROM organizations ORDER BY id")).fetchall()
    if not rows:
        raise click.ClickException("No organizations exist; create one before backfilling.")
    if len(rows) == 1:
        click.echo(
            f"  single organization found: id={rows[0][0]} ({rows[0][1]}) — assigning orphans to it"
        )
        return rows[0][0]
    # Refuse to guess. Picking wrongly hands one tenant's governance record to
    # another, which is the exact failure this command exists to prevent.
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which one "
        "owns the pre-existing principles."
    )


@click.command("backfill-principle-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_principle_org(dry_run, org_id):
    """Backfill organization_id on the principles table."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if TABLE not in set(insp.get_table_names()):
        click.echo(f"  - {TABLE}: table absent, nothing to do")
        return

    conn = db.session.connection()

    cols = {c["name"] for c in insp.get_columns(TABLE)}
    if "organization_id" not in cols:
        if dry_run:
            click.echo(f"  - {TABLE}: would ADD COLUMN organization_id")
            click.echo("dry-run: no changes committed.")
            db.session.rollback()
            return
        conn.execute(
            text(f'ALTER TABLE "{TABLE}" ADD COLUMN IF NOT EXISTS organization_id INTEGER')
        )
        click.echo(f"  + {TABLE}: added organization_id")

    orphans = conn.execute(
        text(f'SELECT count(*) FROM "{TABLE}" WHERE organization_id IS NULL')
    ).scalar()

    if orphans:
        target = _resolve_org_id(conn, org_id)
        if dry_run:
            click.echo(f"  - {TABLE}: would assign {orphans} orphaned row(s) to org {target}")
        else:
            conn.execute(
                text(f'UPDATE "{TABLE}" SET organization_id = :o WHERE organization_id IS NULL'),
                {"o": target},
            )
            click.echo(f"  + {TABLE}: assigned {orphans} orphaned row(s) to org {target}")
    else:
        click.echo("  no orphaned rows — nothing to assign")

    if dry_run:
        click.echo("dry-run: no changes committed.")
        db.session.rollback()
        return

    # reconcile-schema adds neither an index nor the FK.
    for ddl, label in (
        (
            f'CREATE INDEX IF NOT EXISTS ix_{TABLE}_organization_id ON "{TABLE}" (organization_id)',
            "index",
        ),
        (
            f'ALTER TABLE "{TABLE}" ADD CONSTRAINT fk_{TABLE}_organization '
            'FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE',
            "foreign key",
        ),
    ):
        try:
            conn.execute(text(ddl))
            click.echo(f"  + {TABLE}: {label}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ! {TABLE}: {label} skipped ({str(exc)[:100]})")

    db.session.commit()
    click.echo("backfill-principle-org: done.")


def init_app(app):
    """Register the backfill-principle-org CLI command."""
    app.cli.add_command(backfill_principle_org)
