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
boot, which is exactly where docker-compose runs it.

This is the one place in the codebase allowed to write organization_id on an
existing row; a static check fails the build on a second one. The policy per
table, in order:

  1. Purge. A row whose link to its parent is always set at creation, and
     names a parent that no longer exists, is not unresolved provenance -- it
     is a leftover with nowhere to belong, and is deleted before anything
     else runs for that table.
  2. Derive. Where a row can state its own tenant through a link it already
     carries (a joined capability, a work package's creator, an initiative),
     that link fills organization_id first. A derivation statement can only
     fill a NULL; it can never move a row between tenants.
  3. Assign or defer. What is still NULL after derivation is the true orphan
     count. On a database with exactly one active, non-default organisation,
     those rows go to it. On a database with more than one -- or with none --
     no row is assigned, with or without --org-id: an unresolved row is
     another tenant's data, or nobody's yet, never a guess this command is
     allowed to make. Every such table is reported, not silently skipped.
  4. Index and harden. The index is always added. The NOT NULL constraint is
     added only when nothing was left NULL; a deferred table gets the index
     and is reported, not the constraint, which would only fail.

Each table's purge, derivation, assignment, index and hardening run in their
own transaction, committed before the next table starts (rolled back, always,
under --dry-run). A table whose statements raise is rolled back on its own,
recorded, and the run continues with every other table.

Exit codes: 0 whenever every statement issued here succeeded, however many
rows were left NULL -- an unresolved row is reported, not a failure. Non-zero
only for a real failure: a SQL error while repairing a table, a mapped table
the database still lacks the column for after the add, or an --org-id that
does not resolve to the one organisation eligible for it.

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
    # strategic_roadmap_items predates the tenant column; its one trustworthy
    # provenance is the initiative it belongs to. Moved here from
    # reconcile_schema.py, which now adds columns and constraints only, never
    # organization_id values -- this is the one place that does.
    "strategic_roadmap_items": """
        UPDATE strategic_roadmap_items AS r
           SET organization_id = p.organization_id
          FROM strategic_initiatives AS p
         WHERE r.initiative_id = p.id
           AND r.organization_id IS NULL
           AND p.organization_id IS NOT NULL
    """,
}

# Tables whose link column to a parent is set at every creation site (a NULL
# link is "no provenance", never "gone" -- it is not purged), keyed to
# (link_column, parent_table). A row whose link names a parent that no
# longer exists is deleted, idempotently, before that table's derivation or
# count runs.
#
# Empty on this base. The qualifying case is document_chunk_embeddings
# (document_id, set at its one creation site in
# document_processing_service.py's chunk_and_embed, joining ai_chat_document_
# uploads) -- but that table does not carry TenantMixin yet on this branch's
# base, so it is not among _tenant_tables() and this backfill's per-table
# loop never reaches it. Add its entry once it gains the mixin.
_PURGE_ORPHANS = {}


def _resolve_org_id(conn, explicit):
    """The one organisation orphaned rows may be assigned to, or None.

    Counts active, non-default organisations only: an inactive organisation
    and the "default" organisation an install starts with are never a home
    for another tenant's rows. Exactly one such organisation is the only
    case this command assigns automatically or accepts --org-id for; zero or
    several means no assignment happens at all, with or without --org-id --
    an unresolved row is another tenant's data, or nobody's yet, never a
    guess this command is allowed to make.
    """
    from sqlalchemy import text

    eligible = conn.execute(
        text(
            "SELECT id, name FROM organizations "
            "WHERE COALESCE(is_active, TRUE) AND slug <> 'default' "
            "ORDER BY id"
        )
    ).fetchall()

    if explicit is not None:
        if len(eligible) > 1:
            listing = ", ".join(f"{r[0]}={r[1]}" for r in eligible)
            raise click.ClickException(
                f"{len(eligible)} active, non-default organizations exist ({listing}); "
                "--org-id cannot choose among them. An unresolved row is another "
                "tenant's data, not a guess this command is allowed to make."
            )
        if len(eligible) == 1 and eligible[0][0] != explicit:
            raise click.ClickException(
                f"--org-id={explicit} does not match the one active, non-default "
                f"organization (id={eligible[0][0]}, {eligible[0][1]})."
            )
        row = conn.execute(text("SELECT id FROM organizations WHERE id = :i"), {"i": explicit}).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit

    if len(eligible) == 1:
        click.echo(
            f"  single active organization found: id={eligible[0][0]} ({eligible[0][1]}) "
            "— assigning orphans to it"
        )
        return eligible[0][0]

    # Zero, or more than one, eligible organisation: refuse to guess.
    return None


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


def _process_table(conn, insp, t, resolved_org, dry_run):
    """Purge, derive, assign, index and harden one table.

    Returns (status, extra): status is "healthy" or "repaired"; extra is the
    unresolved-orphan count when the table was deferred, else None.

    Raises on an SQL error the caller could not have anticipated -- nothing
    here commits or rolls back on its own; the caller does that once, around
    the whole call, so a failure here undoes only this table's work. An
    *expected* DDL failure (SET NOT NULL skipped for a deferred table) is
    reported and swallowed here instead, because it is not a reason to
    discard everything else this table did.
    """
    from sqlalchemy import text

    if t in _PURGE_ORPHANS:
        link, parent = _PURGE_ORPHANS[t]
        purged = conn.execute(
            text(
                f'DELETE FROM "{t}" WHERE {link} IS NOT NULL '
                f'AND {link} NOT IN (SELECT id FROM "{parent}")'
            )
        ).rowcount
        if purged:
            click.echo(f"  - {t}: purged {purged} row(s) whose parent is gone")

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
            return "repaired", None
        conn.execute(text(f'ALTER TABLE "{t}" ADD COLUMN IF NOT EXISTS organization_id INTEGER'))
        click.echo(f"  + {t}: added organization_id")
        col = {"nullable": True}

    # A table that can state its own tenant does so first, so those rows
    # never reach the guess-based orphan pass below. Run this in dry-run
    # too (it is rolled back with everything else this table did): the
    # orphan count taken right after must reflect rows with no provenance at
    # all, not rows a real run would derive a moment later, or the "would
    # leave NULL" line below overstates how many rows actually have none.
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
        return "healthy", None

    # Every table takes the branch #112 wrote only for roadmap_tasks: with no
    # single active, non-default organisation to assign to, residual rows
    # stay NULL and are reported, never guessed -- with or without --org-id,
    # which _resolve_org_id already refused up front on such a database.
    deferred = False
    if orphans:
        if resolved_org is not None:
            if dry_run:
                click.echo(f"  - {t}: would assign {orphans} orphaned row(s) to org {resolved_org}")
            else:
                conn.execute(
                    text(f'UPDATE "{t}" SET organization_id = :o WHERE organization_id IS NULL'),
                    {"o": resolved_org},
                )
                click.echo(f"  + {t}: assigned {orphans} orphaned row(s) to org {resolved_org}")
        else:
            deferred = True
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

    if dry_run:
        if col.get("nullable") is not False or not has_index:
            click.echo(f"  - {t}: would add index / SET NOT NULL as needed")
        return "repaired", (orphans if deferred else None)

    # Index before NOT NULL, both idempotent; reconcile-schema adds neither.
    # A deferred table (unresolved provenance rows still NULL) gets the
    # index but not the NOT NULL constraint, which would only fail; that is
    # reported explicitly instead of via the try/except below.
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
    return "repaired", (orphans if deferred else None)


def repair_layer_tenancy(org_id=None, dry_run=False):
    """Repair organization_id on every TenantMixin table that needs it.

    --org-id is resolved once, before any table's statements run, so a
    database with more than one active, non-default organisation rejects it
    up front rather than partway through the run. Each table then runs its
    purge, derivation, assignment, index and hardening in its own
    transaction, committed before the next table starts (rolled back, always,
    under dry_run). A table whose statements raise is rolled back on its
    own, recorded in "failed", and every other table still runs.

    Returns {"repaired": [...], "skipped_healthy": n, "absent": [...],
    "unresolved": {table: count}, "failed": {table: reason}}.
    """
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    live = set(insp.get_table_names())

    repaired, absent = [], []
    healthy = 0
    unresolved = {}
    failed = {}

    resolved_org = _resolve_org_id(db.session.connection(), org_id)

    for t in _tenant_tables():
        if t not in live:
            absent.append(t)
            continue

        conn = db.session.connection()
        try:
            status, deferred_count = _process_table(conn, insp, t, resolved_org, dry_run)
        except Exception as exc:  # noqa: BLE001 — isolate this table, keep going
            db.session.rollback()
            failed[t] = str(exc)[:200]
            click.echo(f"  ! {t}: failed and rolled back ({str(exc)[:150]})")
            continue

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

        if status == "healthy":
            healthy += 1
        else:
            repaired.append(t)
            if deferred_count is not None:
                unresolved[t] = deferred_count

    return {
        "repaired": repaired,
        "skipped_healthy": healthy,
        "absent": absent,
        "unresolved": unresolved,
        "failed": failed,
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
    if stats["failed"]:
        click.echo(f"\n{len(stats['failed'])} table(s) FAILED:")
        for table, reason in stats["failed"].items():
            click.echo(f"  ! {table}: {reason}")
        raise SystemExit(1)


def init_app(app):
    app.cli.add_command(backfill_layer_tenancy)
