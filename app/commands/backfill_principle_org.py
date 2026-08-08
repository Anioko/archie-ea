"""
Tenancy backfills: backfill-principle-org, backfill-initiative-org.

Both give a pre-existing table's rows an owning organisation after the model
gained TenantMixin. Same mechanics; `_backfill` holds the logic.

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
    flask --app manage backfill-initiative-org --dry-run
"""

import click
from flask.cli import with_appcontext

from app import db




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


def _backfill(TABLE, dry_run, org_id):
    """Backfill organization_id on one pre-existing tenant table."""
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
    click.echo(f"backfill {TABLE}: done.")


@click.command("backfill-principle-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_principle_org(dry_run, org_id):
    """Backfill organization_id on the principles table."""
    _backfill("principles", dry_run, org_id)


@click.command("backfill-initiative-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_initiative_org(dry_run, org_id):
    """Backfill organization_id on the enterprise_initiatives table.

    EnterpriseInitiative gained TenantMixin. Until this runs, pre-existing
    programmes have a NULL organization_id and are hidden from the portfolio
    views — which is the safe direction to fail, but it is still wrong.
    """
    _backfill("enterprise_initiatives", dry_run, org_id)


def _backfill_from_parent(table, parent_table, fk_column, dry_run):
    """Backfill organization_id by deriving it from an already-scoped parent.

    Exact, not a guess: where the child has a NOT NULL FK to a tenant-scoped
    parent, the parent's organisation *is* the child's. No --org-id, no refusing
    to choose between organisations, and correct even on a multi-tenant install.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    if table not in live or parent_table not in live:
        click.echo(f"  - {table}: table or parent absent, nothing to do")
        return

    conn = db.session.connection()

    cols = {c["name"] for c in insp.get_columns(table)}
    if "organization_id" not in cols:
        if dry_run:
            click.echo(f"  - {table}: would ADD COLUMN organization_id")
            db.session.rollback()
            return
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS organization_id INTEGER'))
        click.echo(f"  + {table}: added organization_id")

    orphans = conn.execute(
        text(f'SELECT count(*) FROM "{table}" WHERE organization_id IS NULL')
    ).scalar()
    if not orphans:
        click.echo("  no orphaned rows — nothing to assign")
    elif dry_run:
        click.echo(f"  - {table}: would derive org for {orphans} row(s) from {parent_table}")
        db.session.rollback()
        return
    else:
        conn.execute(text(
            f'UPDATE "{table}" AS c SET organization_id = p.organization_id '
            f'FROM "{parent_table}" AS p '
            f'WHERE c.{fk_column} = p.id AND c.organization_id IS NULL'
        ))
        remaining = conn.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE organization_id IS NULL')
        ).scalar()
        click.echo(f"  + {table}: derived org for {orphans - remaining} row(s) from {parent_table}")
        if remaining:
            # Only possible if the parent itself is unbackfilled. Say so rather
            # than leaving rows silently invisible.
            click.echo(
                f"  ! {table}: {remaining} row(s) still NULL — their {parent_table} "
                "row has no organization_id yet"
            )

    if dry_run:
        db.session.rollback()
        return

    for ddl, label in (
        (f'CREATE INDEX IF NOT EXISTS ix_{table}_organization_id ON "{table}" (organization_id)', "index"),
        (f'ALTER TABLE "{table}" ADD CONSTRAINT fk_{table}_organization '
         'FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE', "foreign key"),
    ):
        try:
            conn.execute(text(ddl))
            click.echo(f"  + {table}: {label}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ! {table}: {label} skipped ({str(exc)[:100]})")

    db.session.commit()
    click.echo(f"backfill {table}: done.")


@click.command("backfill-kanban-card-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def backfill_kanban_card_org(dry_run):
    """Backfill kanban_cards.organization_id from the owning board.

    KanbanCard gained TenantMixin. board_id is NOT NULL and KanbanBoard is
    already tenant-scoped, so every card's organisation is derivable exactly.
    """
    _backfill_from_parent("kanban_cards", "kanban_boards", "board_id", dry_run)


def init_app(app):
    """Register the tenancy backfill CLI commands."""
    app.cli.add_command(backfill_principle_org)
    app.cli.add_command(backfill_initiative_org)
    app.cli.add_command(backfill_kanban_card_org)
