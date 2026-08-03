"""
flask reconcile-schema — bring an existing database's columns in line with the
ORM models.

`db.create_all()` (run by `flask init-db`) creates missing *tables* but never
adds *columns* to tables that already exist. When a model gains a column in a
later release, a long-lived database drifts: the ORM SELECTs a column Postgres
doesn't have, the request 500s, and one bad column can blank a whole page.

This command diffs every mapped model's columns against the live table and runs
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for each missing one. It is:
  - SAFE: adds columns only — never drops, retypes, or reorders. Added columns
    are nullable (no DEFAULT backfill), so it never rewrites existing rows.
  - IDEMPOTENT: `IF NOT EXISTS` means re-running is a no-op.

It intentionally does NOT create missing tables — `flask init-db` (create_all)
already does that. Run them together:  flask init-db && flask reconcile-schema

Usage:
    flask --app manage reconcile-schema            # apply
    flask --app manage reconcile-schema --dry-run  # report drift, change nothing
"""
import click
from flask.cli import with_appcontext

from app import db


def _reconcile(dry_run=False):
    """Return (added, failed, missing_tables, blocking) lists of "table.column".

    `blocking` is the REVERSE direction: columns the live database has that the
    models do not declare, restricted to NOT NULL columns with no server default.
    Those are the ones that break writes — the ORM omits the column from its INSERT
    and Postgres rejects the row.

    This direction was previously invisible. `value_streams.organization_id` was
    NOT NULL in production while the ValueStream model did not declare the column
    at all, so every attempt to create a value stream failed with NotNullViolation,
    and this command still reported "0 column(s) would add" because it only ever
    compared model -> database.
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names())
    dialect = db.engine.dialect
    added, failed, missing_tables, blocking = [], [], [], []

    for table in db.metadata.tables.values():
        if table.name not in existing_tables:
            continue
        model_cols = {c.name for c in table.columns}
        for live in insp.get_columns(table.name):
            if live["name"] in model_cols:
                continue
            if live.get("nullable", True):
                continue  # extra but harmless: the ORM simply never writes it
            if live.get("default") is not None or live.get("autoincrement"):
                continue  # the database fills it
            blocking.append(f"{table.name}.{live['name']} :: NOT NULL, no default")

    # .tables.values() (not sorted_tables) so FK-cycle tables are still checked.
    for table in db.metadata.tables.values():
        if table.name not in existing_tables:
            missing_tables.append(table.name)
            continue
        live_cols = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in live_cols:
                continue
            try:
                coltype = col.type.compile(dialect=dialect)
            except Exception:
                coltype = "TEXT"
            label = f"{table.name}.{col.name}"
            if dry_run:
                added.append(f"{label} :: {coltype}")
                continue
            ddl = (
                f'ALTER TABLE "{table.name}" '
                f'ADD COLUMN IF NOT EXISTS "{col.name}" {coltype}'
            )
            try:
                db.session.execute(text(ddl))
                db.session.commit()
                added.append(f"{label} :: {coltype}")
            except Exception as exc:  # noqa: BLE001 — keep going, report at end
                db.session.rollback()
                failed.append(f"{label}: {str(exc)[:120]}")

    return added, failed, missing_tables, blocking


@click.command("reconcile-schema")
@click.option("--dry-run", is_flag=True, help="Report drift without altering anything.")
@with_appcontext
def reconcile_schema(dry_run):
    """Add columns the models declare but existing tables lack (safe, idempotent)."""
    added, failed, missing_tables, blocking = _reconcile(dry_run=dry_run)

    verb = "would add" if dry_run else "added"
    click.echo(f"reconcile-schema: {len(added)} column(s) {verb}.")
    for a in added:
        click.echo(f"  + {a}")
    if missing_tables:
        click.echo(
            f"\n{len(missing_tables)} table(s) absent — run 'flask init-db' to "
            f"create them: {', '.join(sorted(missing_tables)[:10])}"
            + (" ..." if len(missing_tables) > 10 else "")
        )
    if blocking:
        click.echo(
            f"\n{len(blocking)} column(s) present in the DATABASE but absent from the "
            "models, NOT NULL with no default — INSERTs into these tables will fail:"
        )
        for b in blocking:
            click.echo(f"  ! {b}")

    if failed:
        click.echo(f"\n{len(failed)} column(s) FAILED:")
        for f in failed:
            click.echo(f"  ! {f}")
        raise SystemExit(1)
    if not added and not dry_run:
        click.echo("Schema already matches the models. Nothing to do.")


def init_app(app):
    """Register the reconcile-schema CLI command."""
    app.cli.add_command(reconcile_schema)
