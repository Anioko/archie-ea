"""
Schema fix: drop-audit-log-viewpoint-fk (CMP-03).

``archimate_audit_logs.viewpoint_id`` carried a FOREIGN KEY to
``archimate_viewpoints.id``, but the composer stores the COMPOSER diagram id
(``saved_diagrams.id``) there. Every composer audit write (e.g. removing an
element from a saved diagram) therefore violated the constraint, raised a 500,
and surfaced as a "Failed to log audit event" toast — the governance trail was
silently broken.

The model no longer declares the FK (viewpoint_id is a loose reference). This
command drops the matching DB constraint on existing databases. reconcile-schema
adds columns but never drops constraints, so this runs as its own boot step.

Idempotent; safe to re-run.

    flask --app manage drop-audit-log-viewpoint-fk
"""

import click
from flask.cli import with_appcontext

from app import db

TABLE = "archimate_audit_logs"
CONSTRAINT = "archimate_audit_logs_viewpoint_id_fkey"


@click.command("drop-audit-log-viewpoint-fk")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def drop_audit_log_viewpoint_fk(dry_run):
    """Drop the wrong archimate_audit_logs.viewpoint_id -> archimate_viewpoints FK."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if TABLE not in set(insp.get_table_names()):
        click.echo(f"  - {TABLE}: table absent, nothing to do")
        return

    fks = {fk.get("name") for fk in insp.get_foreign_keys(TABLE)}
    if CONSTRAINT not in fks:
        click.echo(f"  - {TABLE}: {CONSTRAINT} already absent — nothing to do")
        return

    if dry_run:
        click.echo(f"  - {TABLE}: would DROP CONSTRAINT {CONSTRAINT}")
        return

    conn = db.session.connection()
    conn.execute(text(f'ALTER TABLE "{TABLE}" DROP CONSTRAINT IF EXISTS "{CONSTRAINT}"'))
    db.session.commit()
    click.echo(f"  + {TABLE}: dropped {CONSTRAINT}")
    click.echo("drop-audit-log-viewpoint-fk: done.")


def init_app(app):
    """Register the drop-audit-log-viewpoint-fk CLI command."""
    app.cli.add_command(drop_audit_log_viewpoint_fk)
