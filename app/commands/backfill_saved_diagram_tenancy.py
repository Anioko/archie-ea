"""
Tenancy backfill: backfill-saved-diagram-tenancy.

CMP-01 (composer QA, 18 Aug 2026). ``SavedDiagram`` gained ``TenantMixin`` so a
composer diagram lists and loads only for the org that owns it. The desync it
fixes: ``element_count`` counted (un-scoped) ``saved_diagram_elements`` rows
while the load endpoint's element SELECT is tenant-scoped, so a cross-org viewer
saw "36 elements" in the picker but a blank canvas.

On an existing database ``reconcile-schema`` adds ``saved_diagrams.organization_id``
as a plain nullable column. Because the tenant filter compares with ``=``, a NULL
matches NOTHING — every pre-existing diagram would vanish from every org's picker
until this runs. This command assigns each diagram the org it actually belongs to.

Derivation is EXACT, not a guess: a diagram's org is the org of the elements it
contains (``saved_diagram_elements`` -> ``archimate_elements.organization_id``).
Where a diagram's elements unanimously share one org, that org is written. A
diagram with no resolvable elements (empty, or all elements deleted) has no
intrinsic owner; those fall back to ``--org-id`` / the sole organization, and are
reported rather than silently assigned when the choice is ambiguous.

Idempotent; safe to re-run. Run AFTER reconcile-schema:

    flask --app manage backfill-saved-diagram-tenancy --dry-run
    flask --app manage backfill-saved-diagram-tenancy
    flask --app manage backfill-saved-diagram-tenancy --org-id 3
"""

import click
from flask.cli import with_appcontext

from app import db

TABLE = "saved_diagrams"
ELEMENTS = "saved_diagram_elements"
ARCHIMATE = "archimate_elements"


def _resolve_fallback_org(conn, explicit):
    """Pick the org for diagrams with no resolvable element-derived owner."""
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
        return rows[0][0]
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Some diagrams have no elements to "
        "derive an org from — re-run with --org-id to say which org owns those."
    )


@click.command("backfill-saved-diagram-tenancy")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None,
              help="Org to assign diagrams whose owner can't be derived from elements.")
@with_appcontext
def backfill_saved_diagram_tenancy(dry_run, org_id):
    """Backfill saved_diagrams.organization_id, derived from member elements."""
    from sqlalchemy import inspect, text

    click.echo("backfill-saved-diagram-tenancy" + (" (dry-run)" if dry_run else "") + ":")

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    if TABLE not in live:
        click.echo(f"  - {TABLE}: table absent, nothing to do")
        return

    conn = db.session.connection()

    cols = {c["name"] for c in insp.get_columns(TABLE)}
    if "organization_id" not in cols:
        if dry_run:
            click.echo(f"  - {TABLE}: would ADD COLUMN organization_id")
            db.session.rollback()
            return
        conn.execute(
            text(f'ALTER TABLE "{TABLE}" ADD COLUMN IF NOT EXISTS organization_id INTEGER')
        )
        click.echo(f"  + {TABLE}: added organization_id")

    orphans = conn.execute(
        text(f'SELECT count(*) FROM "{TABLE}" WHERE organization_id IS NULL')  # nosec B608 -- table identifier is a module literal
    ).scalar()
    if not orphans:
        click.echo("  no orphaned rows — nothing to assign")
        if not dry_run:
            _add_index_and_fk(conn, dry_run)
            db.session.commit()
        else:
            db.session.rollback()
        return

    # Derive org from elements, but ONLY where the diagram's elements agree on a
    # single org — a mixed-org diagram must not be silently handed to one tenant.
    derivable = ELEMENTS in live and ARCHIMATE in live
    derived = 0
    if derivable:
        derive_sql = text(
            f'UPDATE "{TABLE}" AS d SET organization_id = agg.org '  # nosec B608 -- table identifiers are module literals
            f'FROM ( '
            f'  SELECT sde.diagram_id AS did, '
            f'         MIN(ae.organization_id) AS org, '
            f'         COUNT(DISTINCT ae.organization_id) AS n_orgs '
            f'  FROM "{ELEMENTS}" sde '
            f'  JOIN "{ARCHIMATE}" ae ON ae.id = sde.element_id '
            f'  GROUP BY sde.diagram_id '
            f') AS agg '
            f'WHERE d.id = agg.did AND d.organization_id IS NULL AND agg.n_orgs = 1'
        )
        if dry_run:
            preview = conn.execute(text(
                f'SELECT count(*) FROM "{TABLE}" d WHERE d.organization_id IS NULL AND EXISTS ('  # nosec B608 -- table identifiers are module literals
                f'  SELECT 1 FROM "{ELEMENTS}" sde JOIN "{ARCHIMATE}" ae ON ae.id = sde.element_id '
                f'  WHERE sde.diagram_id = d.id '
                f'  GROUP BY sde.diagram_id HAVING COUNT(DISTINCT ae.organization_id) = 1)'
            )).scalar()
            click.echo(f"  - {TABLE}: would derive org for {preview} diagram(s) from member elements")
        else:
            derived = conn.execute(derive_sql).rowcount or 0
            click.echo(f"  + {TABLE}: derived org for {derived} diagram(s) from member elements")

    remaining = conn.execute(
        text(f'SELECT count(*) FROM "{TABLE}" WHERE organization_id IS NULL')  # nosec B608 -- table identifier is a module literal
    ).scalar()

    if remaining:
        target = _resolve_fallback_org(conn, org_id)
        mixed = 0
        if derivable:
            mixed = conn.execute(text(
                f'SELECT count(*) FROM "{TABLE}" d WHERE d.organization_id IS NULL AND EXISTS ('  # nosec B608 -- table identifiers are module literals
                f'  SELECT 1 FROM "{ELEMENTS}" sde JOIN "{ARCHIMATE}" ae ON ae.id = sde.element_id '
                f'  WHERE sde.diagram_id = d.id '
                f'  GROUP BY sde.diagram_id HAVING COUNT(DISTINCT ae.organization_id) > 1)'
            )).scalar()
        if mixed:
            click.echo(f"  ! {TABLE}: {mixed} diagram(s) span MULTIPLE orgs — assigning to "
                       f"fallback org {target}; review these by hand")
        if dry_run:
            click.echo(f"  - {TABLE}: would assign {remaining} un-derivable diagram(s) to org {target}")
            db.session.rollback()
            return
        conn.execute(
            text(f'UPDATE "{TABLE}" SET organization_id = :o WHERE organization_id IS NULL'),  # nosec B608 -- table identifier is a module literal; org is bound
            {"o": target},
        )
        click.echo(f"  + {TABLE}: assigned {remaining} un-derivable diagram(s) to org {target}")

    if dry_run:
        db.session.rollback()
        return

    _add_index_and_fk(conn, dry_run)
    db.session.commit()
    click.echo(f"backfill {TABLE}: done.")


def _add_index_and_fk(conn, dry_run):
    """reconcile-schema adds neither an index nor the FK for the new column."""
    from sqlalchemy import text

    if dry_run:
        return
    for ddl, label in (
        (f'CREATE INDEX IF NOT EXISTS ix_{TABLE}_organization_id ON "{TABLE}" (organization_id)',
         "index"),
        (f'ALTER TABLE "{TABLE}" ADD CONSTRAINT fk_{TABLE}_organization '
         'FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE',
         "foreign key"),
    ):
        try:
            conn.execute(text(ddl))
            click.echo(f"  + {TABLE}: {label}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  ! {TABLE}: {label} skipped ({str(exc)[:100]})")


def init_app(app):
    """Register the backfill-saved-diagram-tenancy CLI command."""
    app.cli.add_command(backfill_saved_diagram_tenancy)
