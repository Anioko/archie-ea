"""
flask backfill-data-archimate — mirror existing data entities into ArchiMate.

ArchiMate is the backbone, not a view: every backend CREATE for an
architecturally meaningful entity is supposed to mirror into
``archimate_elements`` (see CLAUDE.md). The data-architecture domain never got
that treatment. ``create_data_entity``
(app/modules/architecture/routes/data_architecture_routes.py) inserted
``DataEntity`` rows directly and never populated the ``archimate_element_id``
column the model has carried since it was added — so the entity catalog page
listed data entities the AI assistant, which reads the ArchiMate layer, could
not see. Same contradiction as the value-stream gap fixed earlier
(app/commands/backfill_value_stream_archimate.py) — this command is that
command's counterpart for the data domain.

ArchiMate 3.2 has no "DataEntity" element type. A DataEntity is a
data-architecture catalogue concept; the closest 3.2 fit is the
Application-layer "DataObject" (see DESIGN.md's domain -> ArchiMate type map,
and app/models/process_data.py::DataEntity.ensure_archimate_element, which
already builds exactly that shape). New DataEntity rows are mirrored on
insert now via the ``after_insert`` listener in
app/models/process_data.py::create_archimate_data_entity. This command
repairs rows written before that fix. Idempotent; only touches rows whose
element is missing:

    flask --app manage backfill-data-archimate --dry-run
    flask --app manage backfill-data-archimate
    flask --app manage backfill-data-archimate --org-id 7

--org-id: DataEntity has NO organization_id column (data entities are not
tenant-scoped rows in their own right — they hang off DataDomain, which is
also global), so --org-id cannot filter *which* rows get backfilled the way
it does for value streams. There is nothing to filter by. Instead it says
which organization owns the ArchiMateElement rows this command is about to
CREATE — ArchiMateElement.organization_id is NOT NULL, and outside a request
context there is no g.current_org_id to default it from. When exactly one
organization exists, that org is used automatically. When several exist, the
command refuses to guess and requires --org-id (the same refusal-to-guess
behaviour as ``_resolve_org_id`` in backfill_value_stream_tenancy.py) —
picking wrongly would hand every backfilled data entity's ArchiMateElement to
the wrong tenant.
"""

import click
from flask.cli import with_appcontext

from app import db


def _resolve_org_id(explicit):
    """Pick the organization new ArchiMateElement rows belong to, or refuse to guess."""
    from sqlalchemy import text

    conn = db.session.connection()

    if explicit is not None:
        row = conn.execute(
            text("SELECT id FROM organizations WHERE id = :i"), {"i": explicit}
        ).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit

    rows = conn.execute(text("SELECT id, name FROM organizations ORDER BY id")).fetchall()
    if len(rows) == 1:
        click.echo(
            f"  single organization found: id={rows[0][0]} ({rows[0][1]}) — "
            "assigning new elements to it"
        )
        return rows[0][0]

    # Refuse to guess. Picking wrongly hands one tenant's data entity to
    # another organization's ArchiMate layer, which is the exact failure this
    # command exists to prevent.
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which "
        "organization owns the ArchiMateElement rows this command creates."
    )


def backfill_data_entity_archimate_elements(org_id=None, dry_run=False):
    """Create the missing ArchiMateElement for every unmirrored DataEntity.

    Returns ``{"linked": int, "scanned": int}``. This runs from the CLI, i.e.
    outside a request context, where ArchiMateElement.organization_id's
    column default has no ``g.current_org_id`` to read — so the organization
    for created elements is resolved explicitly via ``_resolve_org_id``
    rather than left to that default.
    """
    from app.models.process_data import DataEntity, _link_data_entity_archimate

    query = DataEntity.query.filter(DataEntity.archimate_element_id.is_(None))
    pending = query.all()

    if dry_run or not pending:
        return {"linked": 0, "scanned": len(pending)}

    resolved_org_id = _resolve_org_id(org_id)

    # Reuse the listener's own helper so a backfilled element is byte-identical
    # to one created on insert — same type, layer and description.
    connection = db.session.connection()
    for entity in pending:
        _link_data_entity_archimate(connection, entity, organization_id=resolved_org_id)

    db.session.commit()
    return {"linked": len(pending), "scanned": len(pending)}


@click.command("backfill-data-archimate")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option(
    "--org-id",
    type=int,
    default=None,
    help=(
        "Organization to assign newly-created ArchiMateElement rows to. "
        "DataEntity has no organization_id column, so this does not filter which "
        "rows are backfilled — it only applies to elements this command creates. "
        "Required when more than one organization exists."
    ),
)
@with_appcontext
def backfill_data_archimate(dry_run, org_id):
    """Create missing ArchiMate elements for pre-existing data entities."""
    from app.models.process_data import DataEntity

    if not hasattr(DataEntity, "archimate_element_id"):
        raise click.ClickException(
            "DataEntity has no archimate_element_id attribute — this build predates "
            "the fix. Nothing to back-fill."
        )

    if dry_run:
        query = DataEntity.query.filter(DataEntity.archimate_element_id.is_(None))
        scanned = query.count()
        click.echo(f"  would link {scanned} data entit{'y' if scanned == 1 else 'ies'} to new ArchiMate elements")
        return

    stats = backfill_data_entity_archimate_elements(org_id=org_id, dry_run=False)

    if stats["linked"] == 0:
        click.echo("  every data entity already has an ArchiMate element. Nothing to do.")
        return
    click.echo(f"  linked {stats['linked']} data entit{'y' if stats['linked'] == 1 else 'ies'} to new ArchiMate elements")


def init_app(app):
    app.cli.add_command(backfill_data_archimate)
