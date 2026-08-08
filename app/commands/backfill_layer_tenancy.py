"""flask backfill-layer-tenancy — give every TenantMixin table a hardened tenant column.

ADR-0002 records the structural bind this command resolves: `reconcile-schema`
can only ever ADD nullable columns, while `TenantMixin.organization_id` is
declared NOT NULL. So when a model gains the mixin, an existing database is left
with a nullable, unindexed column that the model says cannot be null — and, per
ADR-0003, the tenant filter compares with `=`, so any row left at NULL silently
vanishes from every organisation's view rather than failing loudly.

`backfill-value-stream-tenancy` solved this for three tables. The ADR-0003
completion put `TenantMixin` on ~28 more models across the business, data,
technology and physical layers, and hard-coding another table list per adoption
wave does not scale. This command derives its worklist from the mapper registry
instead: every mapped `TenantMixin` model's table is a candidate, and a table is
touched only when something is actually wrong with it —

  * the column is missing entirely (model gained the mixin before any
    reconcile-schema ran here), or
  * rows hold NULL (pre-mixin rows never assigned to a tenant), or
  * the column is still nullable or unindexed (reconcile-schema adds plain
    nullable columns with no index).

Healthy tables are read and skipped, so the command is safe to run on every
boot, which is exactly where docker-compose runs it. Orphan assignment follows
the house refusal-to-guess rule: with one organisation the rows go to it, with
several the command demands --org-id rather than guessing a tenant.

    flask --app manage backfill-layer-tenancy --dry-run
    flask --app manage backfill-layer-tenancy
    flask --app manage backfill-layer-tenancy --org-id 7
"""

import click
from flask.cli import with_appcontext

from app import db


# Tables whose tenant can be READ from a row they already reference rather than
# guessed. Each statement fills organization_id only where it is NULL, so it is
# idempotent and can never move a row between tenants.
#
# vendor_product_capabilities records how well a vendor product covers a business
# capability. The capability is tenant-owned, so the assessment belongs to that
# capability's organisation — every production row resolves this way, which is
# strictly better than the refuse-to-guess fallback (they would otherwise all be
# assigned to one operator-chosen org).
# tenancy-ok: this backfill is what gives the column its values; it derives the
# tenant from the joined row rather than assuming one.
_DERIVABLE_ORG = {
    "vendor_product_capabilities": """
        UPDATE vendor_product_capabilities v
           SET organization_id = b.organization_id
          FROM business_capability b
         WHERE v.business_capability_id = b.id
           AND v.organization_id IS NULL
           AND b.organization_id IS NOT NULL
    """,
}


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
    # Refuse to guess. Picking wrongly hands one tenant's data to another,
    # which is the exact failure this command exists to prevent.
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which one "
        "owns the pre-existing rows."
    )


def _tenant_tables():
    """Every table mapped by a TenantMixin model, deduplicated and sorted.

    Derived from the mapper registry rather than a hand-kept list so the next
    model to gain the mixin is covered without editing this file. Dual-mapped
    tables (`extend_existing`) appear once.
    """
    from app.models.mixins import TenantMixin

    tables = set()
    for mapper in db.Model.registry.mappers:
        if issubclass(mapper.class_, TenantMixin):
            tables.add(mapper.local_table.name)
    return sorted(tables)


def repair_layer_tenancy(org_id=None, dry_run=False):
    """Repair organization_id on every TenantMixin table that needs it.

    Returns {"repaired": [...], "skipped_healthy": n, "absent": [...]}.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    conn = db.session.connection()

    repaired, absent = [], []
    healthy = 0
    resolved_org = None

    for t in _tenant_tables():
        if t not in live:
            absent.append(t)
            continue

        cols = {c["name"]: c for c in insp.get_columns(t)}
        col = cols.get("organization_id")
        indexes = {i["name"] for i in insp.get_indexes(t)}
        wanted_index = f"ix_{t}_organization_id"
        has_index = wanted_index in indexes or any(
            i["column_names"] == ["organization_id"] for i in insp.get_indexes(t)
        )

        if col is None:
            if dry_run:
                click.echo(f"  - {t}: would ADD COLUMN organization_id")
                repaired.append(t)
                continue
            conn.execute(text(f'ALTER TABLE "{t}" ADD COLUMN IF NOT EXISTS organization_id INTEGER'))
            click.echo(f"  + {t}: added organization_id")
            col = {"nullable": True}

        # A table that can state its own tenant does so first, so those rows
        # never reach the guess-based orphan pass below.
        if not dry_run and t in _DERIVABLE_ORG:
            derived = conn.execute(text(_DERIVABLE_ORG[t])).rowcount
            if derived:
                click.echo(f"  + {t}: derived org for {derived} row(s) from the linked entity")

        orphans = conn.execute(
            text(f'SELECT count(*) FROM "{t}" WHERE organization_id IS NULL')
        ).scalar()

        if not orphans and col.get("nullable") is False and has_index:
            healthy += 1
            continue

        if orphans:
            if resolved_org is None:
                resolved_org = _resolve_org_id(conn, org_id)
            if dry_run:
                click.echo(f"  - {t}: would assign {orphans} orphaned row(s) to org {resolved_org}")
            else:
                conn.execute(
                    text(f'UPDATE "{t}" SET organization_id = :o WHERE organization_id IS NULL'),
                    {"o": resolved_org},
                )
                click.echo(f"  + {t}: assigned {orphans} orphaned row(s) to org {resolved_org}")

        if dry_run:
            if col.get("nullable") is not False or not has_index:
                click.echo(f"  - {t}: would add index / SET NOT NULL as needed")
            repaired.append(t)
            continue

        # Index before NOT NULL, both idempotent; reconcile-schema adds neither.
        for ddl, label in (
            (f'CREATE INDEX IF NOT EXISTS {wanted_index} ON "{t}" (organization_id)', "index"),
            (f'ALTER TABLE "{t}" ALTER COLUMN organization_id SET NOT NULL', "not-null"),
        ):
            try:
                conn.execute(text(ddl))
            except Exception as exc:  # noqa: BLE001 — report, keep repairing other tables
                click.echo(f"  ! {t}: {label} skipped ({str(exc)[:100]})")
        click.echo(f"  + {t}: hardened (index, NOT NULL)")
        repaired.append(t)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {"repaired": repaired, "skipped_healthy": healthy, "absent": absent}


@click.command("backfill-layer-tenancy")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_layer_tenancy(dry_run, org_id):
    """Backfill and harden organization_id on every TenantMixin table."""
    stats = repair_layer_tenancy(org_id=org_id, dry_run=dry_run)
    if stats["absent"]:
        click.echo(f"  {len(stats['absent'])} mapped table(s) absent (created by init-db later): "
                   + ", ".join(stats["absent"][:6]) + ("…" if len(stats["absent"]) > 6 else ""))
    click.echo(
        f"  {'would repair' if dry_run else 'repaired'} {len(stats['repaired'])} table(s); "
        f"{stats['skipped_healthy']} already healthy."
    )


def init_app(app):
    app.cli.add_command(backfill_layer_tenancy)
