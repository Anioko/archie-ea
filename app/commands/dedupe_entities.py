"""flask --app manage dedupe-entities — one-off remediation for ARCH-030's

existing duplicate ArchiMateElement and Solution rows (the 46% duplication the
August 2026 QA sweep found — see app/utils/duplicate_guard.py, which stops the
bleeding on the write path but deliberately does not touch what already
exists).

Strategy: keep-oldest-merge. Within each organisation, rows whose normalised
name (and, for ArchiMateElement, element type) match are a duplicate group.
The lowest id (oldest row — created_at is not always populated on legacy rows,
id order is the reliable proxy for creation order in this schema) is the
winner; every other row in the group is a loser. Every foreign key in the
database that points at a loser is repointed to the winner (discovered via
SQLAlchemy's reflected metadata, so this does not depend on a hand-maintained
table list going stale), and only then are the loser rows deleted. This is
reversible up to the point of DELETE: repointing is idempotent and safe to
re-run, and --dry-run never writes anything.

Never merges across organisations — a duplicate group is always
(organization_id, normalized_name[, element_type]), because two orgs
legitimately sharing a name are not a duplicate.

    flask --app manage dedupe-entities --dry-run
    flask --app manage dedupe-entities --dry-run --model archimate_element
    flask --app manage dedupe-entities --dry-run --model solution
    flask --app manage dedupe-entities                      # real run: pg_dump backup, then writes
    flask --app manage dedupe-entities --skip-backup         # real run, no backup (operator's call)

Real (non-dry-run) execution against the shared persistent test database is
NOT something this docstring endorses — see tests/test_dedupe_entities.py,
which exercises the real-write path only inside an isolated pytest fixture
(db_session, always rolled back).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

import click
from flask.cli import with_appcontext

from app import db
from app.utils.duplicate_guard import normalize_name

_MODELS = {}


def _get_models():
    """Deferred import — models must be registered before db.metadata is useful."""
    if not _MODELS:
        from app.models.archimate_core import ArchiMateElement
        from app.models.solution_models import Solution

        _MODELS["archimate_element"] = {
            "model": ArchiMateElement,
            "table": "archimate_elements",
            "name_field": "name",
            "group_extra": lambda r: getattr(r, "type", None),
        }
        _MODELS["solution"] = {
            "model": Solution,
            "table": "solutions",
            "name_field": "name",
            "group_extra": lambda r: None,
        }
    return _MODELS


def _find_referencing_fks(target_table: str):
    """Every (table, column, has_org_column) in the reflected metadata whose FK
    points at target_table.id. Generic over the schema — no hand-kept list."""
    refs = []
    for table in db.metadata.tables.values():
        if table.name == target_table:
            continue
        for fk in table.foreign_keys:
            try:
                if fk.column.table.name == target_table and fk.column.name == "id":
                    refs.append((table.name, fk.parent.name, "organization_id" in table.columns))
            except Exception:
                continue
    return refs


def _build_groups(model, name_field, group_extra):
    """Group rows by (organization_id, normalized_name, extra) -> [rows], id-sorted."""
    rows = model.query.all()  # CLI: no g.current_org_id -> unfiltered by design, must see every org
    groups: dict = {}
    for r in rows:
        norm = normalize_name(getattr(r, name_field, None))
        if not norm:
            continue
        key = (getattr(r, "organization_id", None), norm, group_extra(r))
        groups.setdefault(key, []).append(r)
    return {k: sorted(v, key=lambda r: r.id) for k, v in groups.items() if len(v) > 1}


def _pg_dump_backup(label: str) -> str | None:
    """Best-effort pg_dump before a real (non-dry-run) write. Returns the path
    on success, None on failure — caller decides whether that's fatal."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        return None
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    out_path = os.path.join(os.getcwd(), f"dedupe_backup_{label}_{ts}.sql")
    try:
        result = subprocess.run(
            ["pg_dump", db_url, "-f", out_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0 or not os.path.exists(out_path):
            return None
        return out_path
    except Exception:
        return None


def merge_duplicate_rows(
    model_key: str,
    winner_id: int,
    loser_ids: list[int],
    organization_id: int | None = None,
    dry_run: bool = False,
) -> dict:
    """ARCH-030(ii): the admin merge/reconcile workflow's engine.

    Same repoint-then-delete mechanism as dedupe_model's per-group loop,
    generalised to an admin-chosen winner and an explicit set of losers
    (rather than a normalized-name group), so the admin UI at
    /admin/duplicates/merge can drive it directly. Reversible up to the
    DELETE: repointing FKs is idempotent, and this never merges across
    organisations — loser_ids not belonging to organization_id are rejected.
    """
    spec = _get_models()[model_key]
    model = spec["model"]
    table = spec["table"]

    loser_ids = [i for i in loser_ids if i != winner_id]
    if not loser_ids:
        return {"model": model_key, "table": table, "rows_deleted": 0, "fk_tables_repointed": {}, "dry_run": dry_run, "rejected_ids": []}

    winner = model.query.get(winner_id)
    if winner is None:
        raise ValueError(f"Winner id {winner_id} not found in {table}")
    if organization_id is not None and getattr(winner, "organization_id", organization_id) != organization_id:
        raise ValueError("Winner does not belong to the given organization")

    candidates = model.query.filter(model.id.in_(loser_ids)).all()
    accepted_ids = []
    rejected_ids = []
    for row in candidates:
        row_org = getattr(row, "organization_id", None)
        if organization_id is not None and row_org != organization_id:
            rejected_ids.append(row.id)  # ARCH-030: never merge across organisations
        else:
            accepted_ids.append(row.id)

    fk_refs = _find_referencing_fks(table)
    fk_repoint_counts: dict = {}

    for fk_table, fk_col, has_org in fk_refs:
        org_clause = " AND organization_id = :org_id" if (has_org and organization_id is not None) else ""
        params = {"loser_ids": list(accepted_ids), "org_id": organization_id}
        if not accepted_ids:
            continue
        count_sql = db.text(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = ANY(:loser_ids){org_clause}")  # nosec B608 -- identifiers come from ORM metadata; IDs are bound
        affected = db.session.execute(count_sql, params).scalar() or 0
        if affected:
            fk_repoint_counts[fk_table] = affected
        if not dry_run and affected:
            update_sql = db.text(
                f"UPDATE {fk_table} SET {fk_col} = :winner_id WHERE {fk_col} = ANY(:loser_ids){org_clause}"  # nosec B608 -- identifiers come from ORM metadata; IDs are bound
            )
            db.session.execute(update_sql, {"winner_id": winner_id, "loser_ids": list(accepted_ids), "org_id": organization_id})

    if not dry_run and accepted_ids:
        model.query.filter(model.id.in_(accepted_ids)).delete(synchronize_session=False)
        db.session.commit()

    return {
        "model": model_key,
        "table": table,
        "winner_id": winner_id,
        "rows_deleted": len(accepted_ids) if not dry_run else 0,
        "would_delete": accepted_ids if dry_run else [],
        "fk_tables_repointed": fk_repoint_counts,
        "dry_run": dry_run,
        "rejected_ids": rejected_ids,
    }


def dedupe_model(model_key: str, dry_run: bool = True) -> dict:
    """Run (or report) keep-oldest-merge dedupe for one model. Returns a report
    dict with exact counts — used by both the CLI command and tests."""
    spec = _get_models()[model_key]
    model = spec["model"]
    table = spec["table"]
    groups = _build_groups(model, spec["name_field"], spec["group_extra"])

    fk_refs = _find_referencing_fks(table)
    fk_repoint_counts: dict = {}
    total_losers = 0
    group_reports = []

    for (org_id, norm_name, extra), rows in groups.items():
        winner = rows[0]
        losers = rows[1:]
        loser_ids = [r.id for r in losers]
        total_losers += len(loser_ids)

        group_reports.append(
            {
                "organization_id": org_id,
                "normalized_name": norm_name,
                "extra": extra,
                "winner_id": winner.id,
                "loser_ids": loser_ids,
            }
        )

        for fk_table, fk_col, has_org in fk_refs:
            org_clause = " AND organization_id = :org_id" if (has_org and org_id is not None) else ""
            params = {"loser_ids": list(loser_ids), "org_id": org_id}

            count_sql = db.text(
                f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = ANY(:loser_ids){org_clause}"  # nosec B608 -- identifiers come from ORM metadata; IDs are bound
            )
            affected = db.session.execute(count_sql, params).scalar() or 0
            if affected:
                fk_repoint_counts[fk_table] = fk_repoint_counts.get(fk_table, 0) + affected

            if not dry_run and affected:
                update_sql = db.text(
                    f"UPDATE {fk_table} SET {fk_col} = :winner_id "  # nosec B608 -- identifiers come from ORM metadata; IDs are bound
                    f"WHERE {fk_col} = ANY(:loser_ids){org_clause}"
                )
                db.session.execute(
                    update_sql, {"winner_id": winner.id, "loser_ids": list(loser_ids), "org_id": org_id}
                )

        if not dry_run:
            model.query.filter(model.id.in_(loser_ids)).delete(synchronize_session=False)

    if not dry_run:
        db.session.commit()
    # dry-run performs no writes (the UPDATE/DELETE branches above are gated on
    # `not dry_run`), so there is nothing of this call's own to roll back --
    # doing so unconditionally would also discard anything the caller had
    # already flushed earlier in the same session/transaction.

    return {
        "model": model_key,
        "table": table,
        "groups": len(groups),
        "rows_deleted": total_losers,
        "fk_tables_repointed": fk_repoint_counts,
        "group_detail": group_reports,
        "dry_run": dry_run,
    }


@click.command("dedupe-entities")
@click.option("--dry-run", is_flag=True, help="Report exact counts; change nothing.")
@click.option(
    "--model",
    type=click.Choice(["archimate_element", "solution", "all"]),
    default="all",
    help="Which model to dedupe. Default: both.",
)
@click.option(
    "--skip-backup",
    is_flag=True,
    help="Skip the pg_dump backup before a real (non-dry-run) write. Operator's explicit call.",
)
@with_appcontext
def dedupe_entities(dry_run, model, skip_backup):
    """One-off remediation: merge existing duplicate ArchiMateElement/Solution rows."""
    if not dry_run and not skip_backup:
        click.echo("Taking pg_dump backup before real write…")
        backup_path = _pg_dump_backup(model)
        if backup_path:
            click.echo(f"  backup written to {backup_path}")
        else:
            click.echo(
                "  pg_dump backup FAILED or pg_dump is not on PATH. Refusing to run without a "
                "backup. Re-run with --skip-backup if you have verified a backup exists another "
                "way, or --dry-run to just see the report.",
                err=True,
            )
            sys.exit(1)

    keys = ["archimate_element", "solution"] if model == "all" else [model]
    for key in keys:
        report = dedupe_model(key, dry_run=dry_run)
        verb = "would delete" if dry_run else "deleted"
        click.echo(f"\n[{report['table']}] {report['groups']} duplicate group(s), {verb} {report['rows_deleted']} row(s)")
        if report["fk_tables_repointed"]:
            click.echo("  FK repoints:")
            for fk_table, count in sorted(report["fk_tables_repointed"].items()):
                verb2 = "would repoint" if dry_run else "repointed"
                click.echo(f"    {fk_table}: {verb2} {count} row(s)")
        else:
            click.echo("  no foreign keys reference the losers.")


def init_app(app):
    app.cli.add_command(dedupe_entities)
