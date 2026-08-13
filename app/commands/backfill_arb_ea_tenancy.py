"""
flask backfill-arb-ea-tenancy — give the 14 ARB/EA-workflow tables a tenant,
derived from their FK parents.

Wave 4 (Phase A, Task 2) added a nullable `organization_id` column to every
ARB and EA-workflow model (see app/models/architecture_review_board.py and
app/models/workflow_models.py). The columns are nullable *on purpose* — the
plan enables TenantMixin filtering (Phase B) only after this command has run
and every row has a correct organization_id. Enabling the filter first would
make every existing NULL-org row invisible to every org (`= org_id` never
matches NULL) — a governance-data outage.

Unlike a single-org value-stream backfill, an ARB/EA row cannot be handed to
"the org that owns this install" — a wrong guess here mis-assigns a
governance record to the wrong tenant, which is a tenant-isolation breach, not
a cosmetic bug. So every row's organization is DERIVED from an already-scoped
FK parent, never guessed:

  arb_review_items          arb_session_id -> architecture_review_boards.org,
                             else solution_id -> solutions.org,
                             else submitter_id -> users.org (NOT NULL, always present)
  arb_review_comments       review_item_id -> arb_review_items.org
  arb_capability_impacts    review_item_id -> arb_review_items.org
  arb_board_members         arb_session_id -> architecture_review_boards.org (NOT NULL)
  arb_exceptions            review_item_id -> arb_review_items.org,
                             else requested_by_id -> users.org
  arb_documents             review_item_id -> arb_review_items.org,
                             else change_request_id -> architecture_change_requests.org
  arb_governance_standards  owner_id -> users.org (no other org-bearing FK; ORPHAN if unset)
  arb_audit_logs            user_id -> users.org (plain int, no FK constraint; ORPHAN if unset)
  arb_workflow_stages       no org-bearing FK at all (global lookup table) -> always ORPHAN
  ea_workflow_definitions   created_by_id -> users.org (ORPHAN if unset)
  ea_workflow_instances     started_by_id -> users.org,
                             else workflow_definition_id -> ea_workflow_definitions.org
  ea_workflow_step_executions instance_id -> ea_workflow_instances.org
  ea_workflow_schedules     workflow_definition_id -> ea_workflow_definitions.org,
                             else created_by_id -> users.org
  ea_workflow_notifications workflow_instance_id -> ea_workflow_instances.org,
                             else recipient_id -> users.org

Processed in dependency order (parents before children, within one
transaction) so a child's derivation can see its parent's just-written org.

Idempotent: every UPDATE is guarded by `organization_id IS NULL`, so a
non-NULL org (already backfilled, or set some other way) is never touched and
re-running is a no-op for rows already resolved.

Runs OUTSIDE request context (no g.current_org_id) — every read is scoped
explicitly by the FK joins below, not by the tenant middleware.

Usage:
    flask --app manage backfill-arb-ea-tenancy --dry-run   # report only
    flask --app manage backfill-arb-ea-tenancy              # derive + write
    flask --app manage backfill-arb-ea-tenancy --org-id 3   # + assign ORPHANs to org 3

Exits non-zero if ORPHAN rows remain and --org-id was not given, so a deploy
runbook can gate the Phase-B deploy on 0 orphans.
"""

import click
from flask.cli import with_appcontext

from app import db

# (table, subquery SQL selecting `id` and `derived_org` for its currently-NULL
# rows). Order matters: children appear after the parents their subquery joins
# against, so a child's UPDATE (run later, same transaction/connection) can see
# the parent's org that this command just wrote.
MODEL_SPECS = [
    (
        "arb_review_items",
        """
        SELECT t.id AS id,
               COALESCE(sess.organization_id, sol.organization_id, usr.organization_id) AS derived_org
        FROM arb_review_items t
        LEFT JOIN architecture_review_boards sess ON sess.id = t.arb_session_id
        LEFT JOIN solutions sol ON sol.id = t.solution_id
        LEFT JOIN users usr ON usr.id = t.submitter_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_review_comments",
        """
        SELECT t.id AS id, ri.organization_id AS derived_org
        FROM arb_review_comments t
        LEFT JOIN arb_review_items ri ON ri.id = t.review_item_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_capability_impacts",
        """
        SELECT t.id AS id, ri.organization_id AS derived_org
        FROM arb_capability_impacts t
        LEFT JOIN arb_review_items ri ON ri.id = t.review_item_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_board_members",
        """
        SELECT t.id AS id, sess.organization_id AS derived_org
        FROM arb_board_members t
        LEFT JOIN architecture_review_boards sess ON sess.id = t.arb_session_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_exceptions",
        """
        SELECT t.id AS id, COALESCE(ri.organization_id, usr.organization_id) AS derived_org
        FROM arb_exceptions t
        LEFT JOIN arb_review_items ri ON ri.id = t.review_item_id
        LEFT JOIN users usr ON usr.id = t.requested_by_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_documents",
        """
        SELECT t.id AS id, COALESCE(ri.organization_id, cr.organization_id) AS derived_org
        FROM arb_documents t
        LEFT JOIN arb_review_items ri ON ri.id = t.review_item_id
        LEFT JOIN architecture_change_requests cr ON cr.id = t.change_request_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_governance_standards",
        """
        SELECT t.id AS id, usr.organization_id AS derived_org
        FROM arb_governance_standards t
        LEFT JOIN users usr ON usr.id = t.owner_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_audit_logs",
        """
        SELECT t.id AS id, usr.organization_id AS derived_org
        FROM arb_audit_logs t
        LEFT JOIN users usr ON usr.id = t.user_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "arb_workflow_stages",
        # No org-bearing FK exists on this model at all (code/name/order/is_active
        # only) — it is a global lookup table. Every NULL row is an ORPHAN by
        # construction; never guessed.
        """
        SELECT t.id AS id, NULL::integer AS derived_org
        FROM arb_workflow_stages t
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "ea_workflow_definitions",
        """
        SELECT t.id AS id, usr.organization_id AS derived_org
        FROM ea_workflow_definitions t
        LEFT JOIN users usr ON usr.id = t.created_by_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "ea_workflow_instances",
        """
        SELECT t.id AS id, COALESCE(usr.organization_id, defn.organization_id) AS derived_org
        FROM ea_workflow_instances t
        LEFT JOIN users usr ON usr.id = t.started_by_id
        LEFT JOIN ea_workflow_definitions defn ON defn.id = t.workflow_definition_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "ea_workflow_step_executions",
        """
        SELECT t.id AS id, inst.organization_id AS derived_org
        FROM ea_workflow_step_executions t
        LEFT JOIN ea_workflow_instances inst ON inst.id = t.instance_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "ea_workflow_schedules",
        """
        SELECT t.id AS id, COALESCE(defn.organization_id, usr.organization_id) AS derived_org
        FROM ea_workflow_schedules t
        LEFT JOIN ea_workflow_definitions defn ON defn.id = t.workflow_definition_id
        LEFT JOIN users usr ON usr.id = t.created_by_id
        WHERE t.organization_id IS NULL
        """,
    ),
    (
        "ea_workflow_notifications",
        """
        SELECT t.id AS id, COALESCE(inst.organization_id, usr.organization_id) AS derived_org
        FROM ea_workflow_notifications t
        LEFT JOIN ea_workflow_instances inst ON inst.id = t.workflow_instance_id
        LEFT JOIN users usr ON usr.id = t.recipient_id
        WHERE t.organization_id IS NULL
        """,
    ),
]


def _backfill_one(conn, table, subquery_sql, dry_run, org_id):
    """Derive and (unless dry_run) write organization_id for one table.

    Returns a per-model stats dict: total / null / derivable / orphan /
    backfilled / assigned_orphans.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if table not in set(insp.get_table_names()):
        return {
            "table": table, "present": False,
            "total": 0, "null": 0, "derivable": 0, "orphan": 0,
            "backfilled": 0, "assigned_orphans": 0,
        }

    total = conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
    null_count = conn.execute(
        text(f'SELECT count(*) FROM "{table}" WHERE organization_id IS NULL')
    ).scalar()

    stats = {
        "table": table, "present": True,
        "total": total, "null": null_count, "derivable": 0, "orphan": 0,
        "backfilled": 0, "assigned_orphans": 0,
    }

    if null_count == 0:
        return stats

    derivable = conn.execute(
        text(f"SELECT count(*) FROM ({subquery_sql}) sub WHERE sub.derived_org IS NOT NULL")
    ).scalar()
    orphan = null_count - derivable
    stats["derivable"] = derivable
    stats["orphan"] = orphan

    if dry_run:
        return stats

    if derivable:
        result = conn.execute(
            text(
                f'UPDATE "{table}" AS t '
                f'SET organization_id = sub.derived_org '
                f'FROM ({subquery_sql}) AS sub '
                f'WHERE t.id = sub.id AND t.organization_id IS NULL AND sub.derived_org IS NOT NULL'
            )
        )
        stats["backfilled"] = result.rowcount or 0

    if orphan and org_id is not None:
        result = conn.execute(
            text(f'UPDATE "{table}" SET organization_id = :o WHERE organization_id IS NULL'),
            {"o": org_id},
        )
        stats["assigned_orphans"] = result.rowcount or 0
        stats["orphan"] = 0

    return stats


def run_backfill(dry_run=False, org_id=None, echo=None):
    """Run the ARB/EA tenancy backfill. Returns a list of per-model stats dicts.

    ``echo`` is an optional callable (click.echo by default when invoked from
    the CLI) so tests can call this directly without a CliRunner.
    """
    from sqlalchemy import text

    if echo is None:
        echo = lambda *a, **k: None  # noqa: E731

    if org_id is not None:
        row = db.session.connection().execute(
            text("SELECT id FROM organizations WHERE id = :i"), {"i": org_id}
        ).first()
        if not row:
            raise click.ClickException(f"No organization with id={org_id}.")

    conn = db.session.connection()
    all_stats = []
    for table, subquery_sql in MODEL_SPECS:
        stats = _backfill_one(conn, table, subquery_sql, dry_run, org_id)
        all_stats.append(stats)
        if not stats["present"]:
            echo(f"  - {table}: table absent, skipping")
            continue
        echo(
            f"  {table}: total={stats['total']} null={stats['null']} "
            f"derivable={stats['derivable']} orphan={stats['orphan']}"
            + (
                f" backfilled={stats['backfilled']} assigned_orphans={stats['assigned_orphans']}"
                if not dry_run else ""
            )
        )

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return all_stats


@click.command("backfill-arb-ea-tenancy")
@click.option("--dry-run", is_flag=True, help="Report per-model coverage; change nothing.")
@click.option(
    "--org-id", type=int, default=None,
    help="Assign ORPHAN rows (no derivable FK org) to this organization. Manual cleanup only.",
)
@with_appcontext
def backfill_arb_ea_tenancy(dry_run, org_id):
    """Backfill organization_id on the 14 ARB/EA-workflow tables, derived from FK parents."""
    click.echo("backfill-arb-ea-tenancy" + (" (dry-run)" if dry_run else "") + ":")
    all_stats = run_backfill(dry_run=dry_run, org_id=org_id, echo=click.echo)

    total_backfilled = sum(s["backfilled"] + s["assigned_orphans"] for s in all_stats)
    total_orphans = sum(s["orphan"] for s in all_stats)

    click.echo("")
    if dry_run:
        total_derivable = sum(s["derivable"] for s in all_stats)
        click.echo(f"dry-run summary: derivable={total_derivable} orphan={total_orphans}")
        click.echo("dry-run: no changes committed.")
    else:
        click.echo(f"summary: backfilled={total_backfilled} orphans_remaining={total_orphans}")

    if total_orphans and org_id is None:
        click.echo(
            f"{total_orphans} orphan row(s) have no derivable organization and --org-id "
            "was not given. Re-run with --org-id N to assign them, or investigate why their "
            "FK parents have no organization."
        )
        raise SystemExit(1)


def init_app(app):
    """Register the backfill-arb-ea-tenancy CLI command."""
    app.cli.add_command(backfill_arb_ea_tenancy)
