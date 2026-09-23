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
    # roadmap_tasks rows predate the tenant column and carry no single
    # provenance link; each statement fills only NULLs, in precedence order.
    # The per-object links (the work package's creator, the consolidation
    # entry's application) are checked before the task's own creating user:
    # a user can be moved to a different organisation after the task was
    # created (an admin route reassigns a removed user to another
    # organisation), which would misattribute the task if the creating-user
    # statement ran first. The work package's creator can move too, but it
    # is ordinarily a different user than the task's own creator, and the
    # consolidation entry's application is not read off a user at all, so
    # checking both first is strictly safer than checking the task's own
    # creator first.
    "roadmap_tasks": [
        # 1. the creator of the work package the task belongs to
        """
        UPDATE roadmap_tasks t
           SET organization_id = u.organization_id
          FROM unified_work_packages w
          JOIN users u ON u.id = w.created_by
         WHERE w.id = t.unified_work_package_id
           AND t.organization_id IS NULL
        """,
        # 2. the application whose consolidation entry created the task
        """
        UPDATE roadmap_tasks t
           SET organization_id = a.organization_id
          FROM consolidation_list_entries e
          JOIN application_components a ON a.id = e.application_id
         WHERE e.roadmap_item_id = t.id
           AND t.organization_id IS NULL
           AND a.organization_id IS NOT NULL
        """,
        # 3. the user who created the task (set by the roadmap UI route);
        # checked last because this user's own organization_id can change
        # after the task was created
        """
        UPDATE roadmap_tasks t
           SET organization_id = u.organization_id
          FROM users u
         WHERE u.id = t.created_by
           AND t.organization_id IS NULL
        """,
    ],
    # monitoring_baselines/monitoring_alerts predate TenantMixin and carry no
    # foreign key to their owning tenant. Per-object provenance runs first
    # (ADR-0007 point 1): a baseline's own snapshot_data carries the ids of the
    # capabilities it captured, and an organisation-owned capability (not a
    # shared reference row) names its tenant directly, which is more reliable
    # than the creating user -- a removed user is moved to the Default
    # organisation, so the per-user statement alone would misattribute a
    # baseline created in a real tenant to Default once its creator is
    # removed. The id inside each JSON array element is guarded before the
    # cast, never a bare CAST, the same rule every other statement here
    # follows; a malformed snapshot_data is skipped by the leading shape
    # check rather than aborting the row. Only the first statement (or
    # neither) can fill a given row, since both guard on organization_id IS
    # NULL; a row the first statement resolves never reaches the second.
    "monitoring_baselines": [
        # 1. an organisation-owned capability referenced in the baseline's
        # own snapshot (skip when the snapshot holds only reference rows,
        # i.e. every referenced capability has organization_id IS NULL).
        # Known limit: a snapshot naming capabilities from more than one
        # organisation (ORDER BY mb.id, uc.organization_id below, kept by
        # DISTINCT ON) is assigned the lowest of those organisations' ids --
        # not detected or reported as an ambiguous row.
        """
        UPDATE monitoring_baselines b
           SET organization_id = src.organization_id
          FROM (
                SELECT DISTINCT ON (mb.id) mb.id AS row_id, uc.organization_id
                  FROM monitoring_baselines mb
                  CROSS JOIN LATERAL jsonb_array_elements(
                        COALESCE(mb.snapshot_data::jsonb -> 'capabilities', '[]'::jsonb)
                      ) AS cap_elem
                  JOIN unified_capabilities uc
                    ON uc.id = CASE WHEN (cap_elem ->> 'id') ~ '^[0-9]+$'
                                     THEN (cap_elem ->> 'id')::bigint END
                 WHERE mb.organization_id IS NULL
                   AND mb.snapshot_data ~ '^\\s*\\{'
                   AND uc.organization_id IS NOT NULL
                 ORDER BY mb.id, uc.organization_id
               ) AS src
         WHERE src.row_id = b.id
           AND b.organization_id IS NULL
        """,
        # 2. the user who created the baseline; cast the integer id to text,
        # never the reverse, which would raise on a non-numeric value such as
        # the literal string "system" a caller may have written before this
        # backfill existed, and abort the whole schema deploy
        """
        UPDATE monitoring_baselines b
           SET organization_id = u.organization_id
          FROM users u
         WHERE u.id::text = b.created_by
           AND b.organization_id IS NULL
        """,
    ],
    # monitoring_alerts carries no column referencing its baseline (only gap
    # ids in alert_metadata), so its only provenance is the acknowledging
    # user; same cast direction as above.
    "monitoring_alerts": """
        UPDATE monitoring_alerts a
           SET organization_id = u.organization_id
          FROM users u
         WHERE u.id::text = a.acknowledged_by
           AND a.organization_id IS NULL
    """,
}

# Tables whose rows carry per-row provenance rather than a single owning
# entity: a row that cannot be derived from that provenance is another
# tenant's data, never a candidate for the single-organisation or --org-id
# orphan assignment below.
#
# An alert never acknowledged, or a baseline whose created_by names no user
# (or predates the column, or is the literal "system"), has no provenance at
# all: it stays NULL and reported, the same as a roadmap_tasks row with no
# linked user, work package or consolidation entry.
_PROVENANCE_ONLY = {"roadmap_tasks", "monitoring_alerts", "monitoring_baselines"}


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
        # never reach the guess-based orphan pass below. Run this in dry-run
        # too (it is rolled back with everything else at the end of this
        # function): the orphan count taken right after must reflect rows
        # with no provenance at all, not rows a real run would derive a
        # moment later, or the "would leave NULL" line below overstates how
        # many rows actually have no provenance.
        if t in _DERIVABLE_ORG:
            stmts = _DERIVABLE_ORG[t]
            stmts = [stmts] if isinstance(stmts, str) else stmts
            derived = sum(conn.execute(text(s)).rowcount for s in stmts)
            if derived:
                verb, prefix = ("would derive", "-") if dry_run else ("derived", "+")
                click.echo(f"  {prefix} {t}: {verb} org for {derived} row(s) from the linked entity")

        orphans = conn.execute(
            text(f'SELECT count(*) FROM "{t}" WHERE organization_id IS NULL')
        ).scalar()

        if not orphans and col.get("nullable") is False and has_index:
            healthy += 1
            continue

        # roadmap_tasks (and any other per-row-provenance table) never hands
        # an orphan to an operator-chosen organisation: with several tenants
        # in the database an unresolved row is another tenant's plan, not a
        # guess this command is allowed to make. With exactly one tenant
        # there is no other organisation it could belong to, so the ordinary
        # single-organisation rule still applies.
        deferred = False
        if orphans and t in _PROVENANCE_ONLY:
            org_count = conn.execute(text("SELECT count(*) FROM organizations")).scalar()
            if org_count != 1:
                deferred = True
                unresolved[t] = orphans
                if dry_run:
                    click.echo(
                        f"  - {t}: {orphans} row(s) have no tenant provenance; "
                        "would leave NULL and report, not assigned"
                    )
                else:
                    click.echo(
                        f"  ! {t}: {orphans} row(s) have no tenant provenance; "
                        "left NULL and reported, not assigned"
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
