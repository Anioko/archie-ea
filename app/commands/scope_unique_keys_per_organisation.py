"""
Schema fix: scope-unique-keys-per-organisation.

Some tenant-owned tables (``TenantMixin``) were created with a platform-wide
uniqueness rule on a business key that each organisation chooses for itself:

* ``governance_gates.gate_name`` - each organisation overrides a system-default
  gate by name;
* ``vendor_contracts.contract_number`` - each organisation numbers its own
  contracts.

The routes' duplicate checks run through the tenant filter, so they passed,
and the INSERT then hit the global rule: once one organisation used a name,
every other organisation got an error for it (and, for contracts, learned
that another tenant holds that number).

The models now declare the rule per organisation. ``create_all`` builds a
fresh table correctly; ``reconcile-schema`` never touches constraints or
indexes, so this command brings an existing database into line: it adds the
per-organisation unique constraint, then removes the platform-wide rule
(a unique constraint is dropped; a unique index is replaced by a plain index
of the same name, so lookups by the key stay indexed).

Idempotent; safe to re-run.

    flask --app manage scope-unique-keys-per-organisation [--dry-run]
"""

import click
from flask.cli import with_appcontext

from app import db

# (table, key column, per-organisation constraint, platform-wide rule, rule kind)
SPECS = (
    ("governance_gates", "gate_name", "uq_governance_gates_org_gate_name",
     "governance_gates_gate_name_key", "constraint"),
    ("vendor_contracts", "contract_number", "uq_vendor_contracts_org_contract_number",
     "ix_vendor_contracts_contract_number", "index"),
)


def _plan(insp, table, new_name, old_name, old_kind):
    """What still needs doing for one table: (add_new, remove_old)."""
    if table not in set(insp.get_table_names()):
        return False, False
    uniques = {u.get("name") for u in insp.get_unique_constraints(table)}
    add_new = new_name not in uniques
    if old_kind == "constraint":
        remove_old = old_name in uniques
    else:
        remove_old = any(ix.get("name") == old_name and ix.get("unique")
                         for ix in insp.get_indexes(table))
    return add_new, remove_old


def scope_unique_keys(connection):
    """Apply the change on ``connection``; return a list of actions taken."""
    from sqlalchemy import inspect, text

    actions = []
    for table, column, new_name, old_name, old_kind in SPECS:
        add_new, remove_old = _plan(inspect(connection), table, new_name, old_name, old_kind)
        if add_new:
            connection.execute(text(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{new_name}" UNIQUE (organization_id, "{column}")'
            ))
            actions.append(f"{table}: added {new_name}")
        if remove_old and old_kind == "constraint":
            connection.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{old_name}"'))
            actions.append(f"{table}: dropped {old_name}")
        elif remove_old:
            connection.execute(text(f'DROP INDEX IF EXISTS "{old_name}"'))
            connection.execute(text(f'CREATE INDEX IF NOT EXISTS "{old_name}" ON "{table}" ("{column}")'))
            actions.append(f"{table}: {old_name} is no longer unique")
    return actions


@click.command("scope-unique-keys-per-organisation")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def scope_unique_keys_per_organisation(dry_run):
    """Make organisation-chosen business keys unique per organisation."""
    conn = db.session.connection()
    if dry_run:
        from sqlalchemy import inspect

        for table, _column, new_name, old_name, old_kind in SPECS:
            add_new, remove_old = _plan(inspect(conn), table, new_name, old_name, old_kind)
            click.echo(f"  - {table}: {'would add ' + new_name if add_new else new_name + ' in place'}; "
                       f"{'would remove platform-wide ' + old_name if remove_old else 'no platform-wide rule'}")
        return
    actions = scope_unique_keys(conn)
    db.session.commit()
    for action in actions:
        click.echo(f"  + {action}")
    click.echo("scope-unique-keys-per-organisation: done." if actions else
               "scope-unique-keys-per-organisation: already scoped per organisation, nothing to do.")


def init_app(app):
    """Register the scope-unique-keys-per-organisation CLI command."""
    app.cli.add_command(scope_unique_keys_per_organisation)
