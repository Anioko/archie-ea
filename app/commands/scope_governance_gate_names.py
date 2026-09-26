"""
Schema fix: scope-governance-gate-names.

``governance_gates`` is tenant-owned (``TenantMixin``) and each organisation
overrides a system-default gate by name, but the table was created with a
platform-wide ``UNIQUE (gate_name)``. The create route's duplicate check runs
through the tenant filter, so it passed, and the INSERT then hit the global
constraint: once one organisation had configured a gate, every other
organisation got "Failed to create gate" for the same name.

The model now declares ``UNIQUE (organization_id, gate_name)``. This command
brings an existing database into line: it adds the per-organisation constraint
and drops the platform-wide one. ``create_all`` builds a fresh table correctly;
``reconcile-schema`` never touches constraints, so this runs as its own boot
step.

Idempotent; safe to re-run.

    flask --app manage scope-governance-gate-names [--dry-run]
"""

import click
from flask.cli import with_appcontext

from app import db

TABLE = "governance_gates"
OLD_CONSTRAINT = "governance_gates_gate_name_key"
NEW_CONSTRAINT = "uq_governance_gates_org_gate_name"


def scope_gate_names(connection):
    """Apply the change on ``connection``; return a list of actions taken."""
    from sqlalchemy import inspect, text

    insp = inspect(connection)
    if TABLE not in set(insp.get_table_names()):
        return []
    uniques = {u.get("name") for u in insp.get_unique_constraints(TABLE)}
    actions = []
    if NEW_CONSTRAINT not in uniques:
        connection.execute(text(
            f'ALTER TABLE "{TABLE}" ADD CONSTRAINT "{NEW_CONSTRAINT}" '
            f'UNIQUE (organization_id, gate_name)'
        ))
        actions.append(f"added {NEW_CONSTRAINT}")
    if OLD_CONSTRAINT in uniques:
        connection.execute(text(f'ALTER TABLE "{TABLE}" DROP CONSTRAINT IF EXISTS "{OLD_CONSTRAINT}"'))
        actions.append(f"dropped {OLD_CONSTRAINT}")
    return actions


@click.command("scope-governance-gate-names")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def scope_governance_gate_names(dry_run):
    """Make governance gate names unique per organisation, not platform-wide."""
    conn = db.session.connection()
    if dry_run:
        from sqlalchemy import inspect

        insp = inspect(conn)
        if TABLE not in set(insp.get_table_names()):
            click.echo(f"  - {TABLE}: table absent, nothing to do")
            return
        uniques = {u.get("name") for u in insp.get_unique_constraints(TABLE)}
        click.echo(f"  - {TABLE}: {NEW_CONSTRAINT} {'present' if NEW_CONSTRAINT in uniques else 'would be added'}; "
                   f"{OLD_CONSTRAINT} {'would be dropped' if OLD_CONSTRAINT in uniques else 'absent'}")
        return
    actions = scope_gate_names(conn)
    db.session.commit()
    for action in actions:
        click.echo(f"  + {TABLE}: {action}")
    click.echo("scope-governance-gate-names: done." if actions else
               f"scope-governance-gate-names: {TABLE} already scoped per organisation, nothing to do.")


def init_app(app):
    """Register the scope-governance-gate-names CLI command."""
    app.cli.add_command(scope_governance_gate_names)
