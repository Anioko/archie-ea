"""flask backfill-hybrid-tenancy-scope — classify existing shared-catalogue rows.

HybridTenantMixin (app/models/mixins/core.py) added `tenancy_scope` as a
nullable column, so `reconcile-schema` creates it with every existing row left
NULL. The tenant read filter in app/middleware/tenant_isolation.py only
treats a row as shared when `organization_id IS NULL AND tenancy_scope ==
"reference"`; an unclassified NULL-organisation row is excluded either way,
which means every pre-existing shared-catalogue row is invisible to every
organisation until this runs.

The classification itself is purely mechanical, unlike
`cutover_capability_tenancy.py`'s relationship-evidence resolution for
UnifiedCapability: a HybridTenantMixin row already carries its own owner on
`organization_id`, so there is nothing ambiguous to infer. Set NULL to
"reference", set is already set to "tenant".
"""

import re

import click
from flask.cli import with_appcontext

from app import db

_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _hybrid_tenant_tables():
    """Every table mapped by a HybridTenantMixin model, deduplicated and sorted.

    Derived from the mapper registry, the same way _tenant_tables() in
    backfill_layer_tenancy.py derives its own worklist, so the next class to
    gain the mixin is covered without editing this file.
    """
    from app.models.mixins.core import HybridTenantMixin

    tables = set()
    for mapper in db.Model.registry.mappers:
        if issubclass(mapper.class_, HybridTenantMixin):
            name = mapper.local_table.name
            if not _SAFE_NAME.match(name):
                raise RuntimeError(f"refusing to interpolate unexpected table name {name!r}")
            tables.add(name)
    return sorted(tables)


def repair_hybrid_tenancy_scope(dry_run=False):
    """Set tenancy_scope on every unclassified row of every HybridTenantMixin table.

    Returns {"repaired": {table: count}, "absent": [...]}.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    conn = db.session.connection()

    repaired = {}
    absent = []
    for table in _hybrid_tenant_tables():
        if table not in live:
            absent.append(table)
            continue

        if dry_run:
            pending = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table}" WHERE tenancy_scope IS NULL')
            ).scalar()
            if pending:
                repaired[table] = pending
            continue

        result = conn.execute(
            text(
                f'UPDATE "{table}" SET tenancy_scope = '
                f"CASE WHEN organization_id IS NULL THEN 'reference' ELSE 'tenant' END "
                f'WHERE tenancy_scope IS NULL'
            )
        )
        if result.rowcount:
            repaired[table] = result.rowcount

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {"repaired": repaired, "absent": absent}


@click.command("backfill-hybrid-tenancy-scope")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def backfill_hybrid_tenancy_scope(dry_run):
    """Classify existing shared-catalogue rows as reference/tenant."""
    stats = repair_hybrid_tenancy_scope(dry_run=dry_run)
    if stats["absent"]:
        click.echo(
            f"  {len(stats['absent'])} mapped table(s) absent (created by init-db later): "
            + ", ".join(stats["absent"][:6]) + ("…" if len(stats["absent"]) > 6 else "")
        )
    if not stats["repaired"]:
        click.echo("  every table already classified.")
        return
    verb = "would classify" if dry_run else "classified"
    for table, count in stats["repaired"].items():
        click.echo(f"  + {table}: {verb} {count} row(s)")


def init_app(app):
    app.cli.add_command(backfill_hybrid_tenancy_scope)
