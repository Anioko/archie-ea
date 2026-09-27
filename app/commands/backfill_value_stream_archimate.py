"""
flask backfill-value-stream-archimate — mirror existing value streams into ArchiMate.

ArchiMate is the backbone, not a view: a value stream *is* a Strategy-layer
ArchiMate element. Until ValueStream gained an ``archimate_element_id`` column,
the ``after_insert`` listener that creates that element
(app/models/strategy_layer.py::create_archimate_value_stream) raised
AttributeError, so ``create_value_stream`` inserted at Core level to dodge mapper
events entirely. The crash went away; the mirroring never happened.

The visible symptom was the product contradicting itself. The value-stream pages
read the ``value_streams`` table and listed them, while the AI assistant reads
the ArchiMate layer and reported "no value streams modelled" for the very same
tenant.

New value streams are mirrored on insert now. This command repairs rows written
before the fix. Idempotent; only touches rows whose element is missing:

    flask --app manage backfill-value-stream-archimate --dry-run
    flask --app manage backfill-value-stream-archimate
    flask --app manage backfill-value-stream-archimate --org-id 7
"""

import click
from flask.cli import with_appcontext

from app import db


def backfill_value_stream_archimate_elements(org_id=None, dry_run=False):
    """Create the missing ArchiMateElement for every unmirrored ValueStream.

    Returns ``{"linked": int, "scanned": int}``. When ``org_id`` is given the
    work is restricted to that tenant. This runs from the CLI, i.e. outside a
    request context, where the tenant filter is a no-op — so the organisation
    is put in the predicate explicitly rather than trusted to the middleware.
    """
    from app.models.strategy_layer import _link_strategy_archimate
    from app.models.unified_capability import ValueStream

    query = ValueStream.query.filter(ValueStream.archimate_element_id.is_(None))
    if org_id is not None:
        query = query.filter(ValueStream.organization_id == org_id)

    pending = query.all()
    if dry_run or not pending:
        return {"linked": 0, "scanned": len(pending)}

    # Reuse the listener's own helper so a backfilled element is byte-identical
    # to one created on insert — same type, layer, description and org.
    connection = db.session.connection()
    for value_stream in pending:
        _link_strategy_archimate(connection, value_stream, "ValueStream", "Value stream")

    db.session.commit()
    return {"linked": len(pending), "scanned": len(pending)}


@click.command("backfill-value-stream-archimate")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Restrict to a single organization.")
@with_appcontext
def backfill_value_stream_archimate(dry_run, org_id):
    """Create missing ArchiMate elements for pre-existing value streams."""
    from app.models.unified_capability import ValueStream

    if not hasattr(ValueStream, "archimate_element_id"):
        raise click.ClickException(
            "ValueStream has no archimate_element_id attribute — this build predates "
            "the fix. Nothing to back-fill."
        )

    stats = backfill_value_stream_archimate_elements(org_id=org_id, dry_run=dry_run)

    if dry_run:
        click.echo(f"  would link {stats['scanned']} value stream(s) to new ArchiMate elements")
        return
    if stats["linked"] == 0:
        click.echo("  every value stream already has an ArchiMate element. Nothing to do.")
        return
    click.echo(f"  linked {stats['linked']} value stream(s) to new ArchiMate elements")


def init_app(app):
    app.cli.add_command(backfill_value_stream_archimate)
