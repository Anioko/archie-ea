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
#
# Ordering is load-bearing: _tenant_tables() sorts alphabetically, and
# "application_ownership" < "organization_units", so application_ownership's
# organization_id is always derived (or left NULL) before organization_units'
# derivation reads it. If that alphabetical relationship ever changes, the
# organization_units entry below must still run after application_ownership's.
_DERIVABLE_ORG = {
    "vendor_product_capabilities": """
        UPDATE vendor_product_capabilities v
           SET organization_id = b.organization_id
          FROM business_capability b
         WHERE v.business_capability_id = b.id
           AND v.organization_id IS NULL
           AND b.organization_id IS NOT NULL
    """,
    # An ownership row's tenant is its application's tenant — every production
    # row resolves this way (nothing in app/ writes this table independently
    # of a component). A row whose application itself has no organization_id
    # is per-row provenance this statement cannot resolve; see
    # _PROVENANCE_ONLY below for what happens to it.
    "application_ownership": """
        UPDATE application_ownership o
           SET organization_id = c.organization_id
          FROM application_components c
         WHERE o.application_id = c.id
           AND o.organization_id IS NULL
           AND c.organization_id IS NOT NULL
    """,
    # A unit's tenant is derived from its own ownership rows, never guessed: a
    # unit referenced by exactly one organisation's ownership rows takes that
    # organisation; a unit referenced by more than one, or by none at all,
    # stays NULL here. It is excluded from the residual sweep below
    # (_PROVENANCE_ONLY), so with several organisations in the database it
    # stays NULL and is reported, never assigned, with or without --org-id;
    # with exactly one organisation the ordinary single-organisation rule
    # still applies, same as every other table.
    "organization_units": """
        UPDATE organization_units u
           SET organization_id = s.org_id
          FROM (
                SELECT organization_unit_id, MIN(organization_id) AS org_id
                  FROM application_ownership
                 WHERE organization_id IS NOT NULL
                 GROUP BY organization_unit_id
                HAVING COUNT(DISTINCT organization_id) = 1
               ) s
         WHERE u.id = s.organization_unit_id
           AND u.organization_id IS NULL
    """,
    # An options analysis belongs to the organisation that owns the capability it
    # analyses: capability_id is NOT NULL and points at business_capability, which
    # is already tenant-fenced. An analysis whose capability itself has no
    # organisation cannot be resolved here; see _PROVENANCE_ONLY.
    "options_analysis": """
        UPDATE options_analysis a
           SET organization_id = b.organization_id
          FROM business_capability b
         WHERE a.capability_id = b.id
           AND a.organization_id IS NULL
           AND b.organization_id IS NOT NULL
    """,
    # A stakeholder input belongs to its analysis. Ordering is load-bearing in the
    # same way as above: "options_analysis" < "stakeholder_inputs", so the analysis
    # is derived (or left NULL) before this reads it.
    "stakeholder_inputs": """
        UPDATE stakeholder_inputs i
           SET organization_id = a.organization_id
          FROM options_analysis a
         WHERE i.analysis_id = a.id
           AND i.organization_id IS NULL
           AND a.organization_id IS NOT NULL
    """,
}

# Tables whose remaining NULL rows carry per-row provenance rather than a
# single owning entity this command can always resolve: an ownership row
# whose own application has no organization_id, or a unit referenced by more
# than one organisation's ownership rows, or by none. Handing either to an
# operator-chosen --org-id would move another tenant's row into view, so with
# several organisations in the database the row stays NULL here and is only
# reported, never a candidate for the single-organisation or --org-id orphan
# assignment below. With exactly one organisation there is no other one it
# could belong to, so the ordinary single-organisation rule still applies.
_PROVENANCE_ONLY = {"application_ownership", "options_analysis", "organization_units", "stakeholder_inputs"}


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

    Names are re-checked against a strict identifier pattern before being
    returned. They come from mapped classes rather than from any request, so
    this cannot fail in practice — it exists so the f-string interpolation
    below (bandit B608, which cannot know the source is trusted) is guarded by
    something executable rather than by a comment.
    """
    import re

    from app.models.mixins import TenantMixin

    safe = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    tables = set()
    for mapper in db.Model.registry.mappers:
        if issubclass(mapper.class_, TenantMixin):
            name = mapper.local_table.name
            if not safe.match(name):
                raise RuntimeError(
                    f"refusing to interpolate unexpected table name {name!r}"
                )
            tables.add(name)
    return sorted(tables)


def repair_layer_tenancy(org_id=None, dry_run=False):
    """Repair organization_id on every TenantMixin table that needs it.

    Returns {"repaired": [...], "skipped_healthy": n, "absent": [...],
    "unresolved": {table: count}}.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    live = set(insp.get_table_names())
    conn = db.session.connection()

    repaired, absent = [], []
    healthy = 0
    resolved_org = None
    unresolved = {}

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
        # never reach the guess-based orphan pass below. This runs in
        # dry-run too (rolled back with everything else at the end of this
        # function): the orphan count taken right after must reflect rows
        # with no provenance at all, not rows a real run would derive a
        # moment later, or a dry-run's residual report for a _PROVENANCE_ONLY
        # table would overstate it.
        if t in _DERIVABLE_ORG:
            derived = conn.execute(text(_DERIVABLE_ORG[t])).rowcount
            if derived:
                verb, prefix = ("would derive", "-") if dry_run else ("derived", "+")
                click.echo(f"  {prefix} {t}: {verb} org for {derived} row(s) from the linked entity")

        orphans = conn.execute(
            text(f'SELECT count(*) FROM "{t}" WHERE organization_id IS NULL')
        ).scalar()

        if not orphans and col.get("nullable") is False and has_index:
            healthy += 1
            continue

        # application_ownership and organization_units (_PROVENANCE_ONLY)
        # never hand a row _DERIVABLE_ORG could not resolve to an
        # operator-chosen organisation: with several tenants in the database
        # an unresolved row is another tenant's data, not a guess this
        # command is allowed to make. With exactly one tenant there is no
        # other organisation it could belong to, so the ordinary
        # single-organisation rule still applies.
        deferred = False
        if orphans and t in _PROVENANCE_ONLY:
            org_count = conn.execute(text("SELECT count(*) FROM organizations")).scalar()
            if org_count != 1:
                deferred = True
                unresolved[t] = orphans
                verb, prefix = ("would leave", "-") if dry_run else ("left", "!")
                click.echo(
                    f"  {prefix} {t}: {orphans} row(s) have no tenant provenance; "
                    f"{verb} NULL and reported, not assigned"
                )

        if orphans and not deferred:
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

        # Index before NOT NULL, both idempotent; reconcile-schema adds
        # neither. A deferred table (unresolved provenance rows still NULL)
        # gets the index but not the NOT NULL constraint, which would only
        # fail; that is reported explicitly instead of via the try/except.
        ddls = [(f'CREATE INDEX IF NOT EXISTS {wanted_index} ON "{t}" (organization_id)', "index")]
        if deferred:
            click.echo(f"  ! {t}: not-null deferred: {orphans} unresolved row(s)")
        else:
            ddls.append((f'ALTER TABLE "{t}" ALTER COLUMN organization_id SET NOT NULL', "not-null"))
        for ddl, label in ddls:
            try:
                conn.execute(text(ddl))
            except Exception as exc:  # noqa: BLE001 — report, keep repairing other tables
                click.echo(f"  ! {t}: {label} skipped ({str(exc)[:100]})")
        click.echo(f"  + {t}: hardened (index{'' if deferred else ', NOT NULL'})")
        repaired.append(t)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "repaired": repaired,
        "skipped_healthy": healthy,
        "absent": absent,
        "unresolved": unresolved,
    }


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
    for table, count in stats.get("unresolved", {}).items():
        click.echo(f"  {table}: {count} row(s) left without a tenant; no provenance found")


def init_app(app):
    app.cli.add_command(backfill_layer_tenancy)
