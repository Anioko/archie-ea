"""
Tenancy backfills: backfill-principle-org, backfill-initiative-org.

Both give a pre-existing table's rows an owning organisation after the model
gained TenantMixin. Same mechanics; `_backfill` holds the logic.

`Principle` (app/models/models.py) shipped without an organization_id. The tenant
filter in app/middleware/tenant_isolation.py attaches
``organization_id == g.current_org_id`` to every SELECT on a TenantMixin model, so
a model without that column is not merely unfiltered — it is structurally
impossible to filter. Any authenticated user of any tenant could read every other
tenant's architecture principles.

Principle now uses TenantMixin. This command completes the change on an existing
database:

  `flask reconcile-schema` adds a missing column as plain nullable, with no FK and
  no index. Rows predating the change therefore hold NULL, and because the filter
  compares with `=`, NULL matches NOTHING — every existing principle silently
  vanishes from the governance dashboard, the ARB screens and the AI chat tools
  for every user. This command assigns them an owner.

Unlike backfill-value-stream-tenancy, this does NOT set the column NOT NULL: the
model deliberately declares organization_id as nullable so the column can land via
reconcile-schema without a maintenance window (see the comment on Principle).
Tightening to NOT NULL is a follow-up once every install is known to be backfilled;
doing it here would put the database out of step with the ORM and trip the
schema-drift gate.

Idempotent; safe to re-run. Run AFTER reconcile-schema:

    flask --app manage backfill-principle-org --dry-run
    flask --app manage backfill-principle-org
    flask --app manage backfill-principle-org --org-id 3
    flask --app manage backfill-initiative-org --dry-run
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import inspect, text

from app import db
from app.commands.tenant_schema import (
    ensure_organization_index_and_fk,
    plan_organization_index_and_fk,
)


# SQL identifiers are restricted to the three registered command call sites.
_FALLBACK_TABLES = {"principles", "enterprise_initiatives"}
_PARENT_IDENTITY = ("kanban_cards", "kanban_boards", "board_id")


def _resolve_org_id(conn, explicit):
    if explicit is not None:
        row = conn.execute(
            text("SELECT id FROM public.organizations WHERE id = :i"), {"i": explicit}
        ).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit
    rows = conn.execute(text("SELECT id, name FROM public.organizations ORDER BY id")).all()
    if not rows:
        raise click.ClickException("No organizations exist; create one before backfilling.")
    if len(rows) == 1:
        return rows[0][0]
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which one "
        "owns the pre-existing rows."
    )


def _commit_outcome_unknown(exc):
    """A server rejection is definitive; a missing acknowledgement is not."""
    original = getattr(exc, "orig", exc)
    code = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    return (getattr(exc, "connection_invalidated", False) or not code
            or code.startswith("08") or code in {"40003", "57P01", "57P02", "57P03"})


def _run_backfill(table, dry_run, org_id=None, *, parent_table=None, fk_column=None):
    messages = []
    result = {"examined_null": 0, "eligible": 0, "attributed": 0,
              "remaining_nulls": 0, "schema": {}, "dry_run": dry_run}
    committing = False
    try:
        if parent_table is None:
            if table not in _FALLBACK_TABLES:
                raise ValueError("Unsupported fallback table")
        elif (table, parent_table, fk_column) != _PARENT_IDENTITY:
            raise ValueError("Unsupported parent attribution identity")
        conn = db.session.connection()
        insp = inspect(conn)
        if conn.dialect.name != "postgresql" or insp.default_schema_name != "public":
            raise ValueError("Tenancy repair requires the default PostgreSQL public schema")
        live = set(insp.get_table_names(schema="public"))
        if table not in live:
            db.session.rollback()
            click.echo(f"  - {table}: table absent, nothing to do")
            return result
        target = f'"public"."{table}"'
        if parent_table is not None and parent_table not in live:
            columns = {c["name"] for c in insp.get_columns(table, schema="public")}
            predicate = "organization_id IS NULL" if "organization_id" in columns else "TRUE"
            remaining = conn.execute(text(
                f'SELECT count(*) FROM {target} WHERE {predicate}'  # nosec B608 -- literal-call-site table and fixed predicate
            )).scalar_one()
            result.update(examined_null=remaining, remaining_nulls=remaining)
            db.session.rollback()
            click.echo(f"  - {table}: parent absent, remaining_nulls={remaining}; nothing changed")
            return result
        if not dry_run:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            # Acquire the strongest target lock up front: no later DDL lock
            # upgrade can deadlock two cooperating repair invocations.
            for name in sorted({table, "organizations"} | ({parent_table} if parent_table else set())):
                mode = "ACCESS EXCLUSIVE" if name == table else "SHARE"
                conn.execute(text(f'LOCK TABLE "public"."{name}" IN {mode} MODE'))
        cols = {c["name"]: c for c in insp.get_columns(table, schema="public")}
        col = cols.get("organization_id")
        missing = col is None
        if col is not None and type(col.get("nullable")) is not bool:
            raise ValueError(f"{table}: catalog nullability unavailable")
        if parent_table:
            parent_cols = {c["name"] for c in insp.get_columns(parent_table, schema="public")}
            if "organization_id" not in parent_cols:
                raise ValueError(f"{parent_table}.organization_id is absent; run reconcile-schema first")
            if fk_column not in cols or "id" not in parent_cols:
                raise ValueError(f"{table}: parent link is absent; run reconcile-schema first")
        plan = plan_organization_index_and_fk(conn, table, column_missing=missing)
        result["schema"] = {"column": "add" if missing else "present",
                            "nullability": "drop_not_null" if col and not col["nullable"] else "present",
                            **plan}
        null_predicate = "TRUE" if missing else "c.organization_id IS NULL"
        examined = conn.execute(text(
            f'SELECT count(*) FROM {target} c WHERE {null_predicate}'  # nosec B608 -- literal-call-site table and fixed predicate
        )).scalar_one()
        result["examined_null"] = examined
        if parent_table:
            parent = f'"public"."{parent_table}"'
            predicate = f'c."{fk_column}" = p.id AND {null_predicate} AND p.organization_id IS NOT NULL'
            eligible = conn.execute(text(
                f'SELECT count(*) FROM {target} c JOIN {parent} p ON {predicate}'  # nosec B608 -- identities and predicate derive only from literal call sites
            )).scalar_one()
            # A broken legacy parent must be refused before column/owner writes.
            if conn.execute(text(
                f'SELECT 1 FROM {target} c JOIN {parent} p ON {predicate} '  # nosec B608 -- identities and predicate derive only from literal call sites
                "WHERE NOT EXISTS (SELECT 1 FROM public.organizations o "
                "WHERE o.id = p.organization_id) LIMIT 1"
            )).first():
                raise ValueError(f"{parent_table}: eligible parent has an invalid organization owner")
        else:
            eligible = examined
            owner = _resolve_org_id(conn, org_id) if eligible else None
        result["eligible"] = eligible
        result["remaining_nulls"] = examined - eligible
        if dry_run:
            db.session.rollback()
            click.echo(f"{table}: would attribute={eligible} remaining_nulls={examined - eligible}; "
                       f"schema={result['schema']}")
            click.echo("dry-run: no changes committed.")
            return result
        if missing:
            conn.execute(text(f'ALTER TABLE {target} ADD COLUMN organization_id INTEGER'))
            messages.append(f"  + {table}: added organization_id")
        elif not col["nullable"]:
            conn.execute(text(f'ALTER TABLE {target} ALTER COLUMN organization_id DROP NOT NULL'))
            messages.append(f"  + {table}: nullable ownership restored")
        if eligible:
            if parent_table:
                # The virtual missing-column predicate becomes its real NULL
                # equivalent after ADD COLUMN; preview and apply select the same rows.
                predicate = (f'c."{fk_column}" = p.id AND c.organization_id IS NULL '
                             'AND p.organization_id IS NOT NULL')
                updated = conn.execute(text(
                    f'UPDATE {target} c SET organization_id = p.organization_id '  # nosec B608 -- literal-call-site identities; owner derives from the joined parent
                    f'FROM {parent} p WHERE {predicate} RETURNING c.id, c.organization_id, p.organization_id'
                )).all()
                if any(actual_owner != expected_owner for _, actual_owner, expected_owner in updated):
                    raise ValueError(f"{table}: attributed owner postcondition failed")
            else:
                updated = conn.execute(text(
                    f'UPDATE {target} SET organization_id = :o '  # nosec B608 -- literal-call-site table; organization value is bound
                    'WHERE organization_id IS NULL RETURNING id, organization_id'
                ), {"o": owner}).all()
                if any(actual_owner != owner for _, actual_owner in updated):
                    raise ValueError(f"{table}: attributed owner postcondition failed")
            result["attributed"] = len(updated)
        remaining = conn.execute(text(
            f'SELECT count(*) FROM {target} WHERE organization_id IS NULL'  # nosec B608 -- table is a validated literal-call-site identity
        )).scalar_one()
        if result["attributed"] != eligible or remaining != examined - eligible:
            raise ValueError(f"{table}: attribution count postcondition failed")
        result["remaining_nulls"] = remaining
        result["schema"].update(ensure_organization_index_and_fk(
            conn, table, strict=True, echo=messages.append,
        ))
        insp.clear_cache()
        actual = next(c for c in insp.get_columns(table, schema="public")
                      if c["name"] == "organization_id")
        if actual["nullable"] is not True or (missing and actual.get("default") is not None):
            raise ValueError(f"{table}: nullable ownership postcondition failed")
        if plan_organization_index_and_fk(conn, table) != {"index": "present", "foreign_key": "present"}:
            raise ValueError(f"{table}: schema completion postcondition failed")
        final_remaining = conn.execute(text(
            f'SELECT count(*) FROM {target} WHERE organization_id IS NULL'  # nosec B608 -- table is a validated literal-call-site identity
        )).scalar_one()
        if final_remaining != result["remaining_nulls"]:
            raise ValueError(f"{table}: final attribution count postcondition failed")
        committing = True
        db.session.commit()
    except Exception as exc:
        unknown = committing and _commit_outcome_unknown(exc)
        try:
            db.session.rollback()
        except Exception as rollback_error:
            if not unknown:
                raise click.ClickException(
                    f"{table}: repair failed; transaction cleanup failed; inspect before retry: {rollback_error}"
                ) from exc
        if unknown:
            raise click.ClickException(
                f"{table}: commit outcome unknown; inspect data and schema on a new connection before retry."
            ) from exc
        if isinstance(exc, click.ClickException):
            raise
        raise click.ClickException(
            f"{table}: repair failed; transaction rolled back; retry after resolving the cause: {exc}"
        ) from exc
    for message in messages:
        click.echo(message)
    click.echo(f"{table}: attributed={result['attributed']} remaining_nulls={result['remaining_nulls']}")
    if result["remaining_nulls"]:
        click.echo(f"  {table}: unresolved rows remain NULL; parent ownership is unavailable")
    click.echo(f"backfill {table}: done.")
    return result


def _backfill(TABLE, dry_run, org_id):
    """Assign NULL owners using the existing sole/explicit organization policy."""
    return _run_backfill(TABLE, dry_run, org_id)


@click.command("backfill-principle-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_principle_org(dry_run, org_id):
    """Backfill organization_id on the principles table."""
    _backfill("principles", dry_run, org_id)


@click.command("backfill-initiative-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization to assign orphaned rows to.")
@with_appcontext
def backfill_initiative_org(dry_run, org_id):
    """Backfill organization_id on the enterprise_initiatives table.

    EnterpriseInitiative gained TenantMixin. Until this runs, pre-existing
    programmes have a NULL organization_id and are hidden from the portfolio
    views — which is the safe direction to fail, but it is still wrong.
    """
    _backfill("enterprise_initiatives", dry_run, org_id)


def _backfill_from_parent(table, parent_table, fk_column, dry_run):
    """Derive only NULL child owners from non-NULL parent owners, without fallback."""
    return _run_backfill(table, dry_run, parent_table=parent_table, fk_column=fk_column)


@click.command("backfill-kanban-card-org")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def backfill_kanban_card_org(dry_run):
    """Backfill kanban_cards.organization_id from the owning board.

    KanbanCard gained TenantMixin. board_id is NOT NULL and KanbanBoard is
    already tenant-scoped, so every card's organisation is derivable exactly.
    """
    _backfill_from_parent("kanban_cards", "kanban_boards", "board_id", dry_run)


def init_app(app):
    """Register the tenancy backfill CLI commands."""
    app.cli.add_command(backfill_principle_org)
    app.cli.add_command(backfill_initiative_org)
    app.cli.add_command(backfill_kanban_card_org)
