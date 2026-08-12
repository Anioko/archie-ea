"""``flask scope-unique-to-tenant`` — make authored identifiers unique per organisation.

The models in ``app/models/tenant_unique_registry.py::SCOPE_PER_TENANT`` used to
declare ``unique=True`` on a ``TenantMixin`` table. That is unique across *every*
organisation, so a value the tenant authors — "SAP", "CUST", "AD-001",
"ARCH-142" — became first-come-first-served: the second organisation to use it
was refused, and the error said only that the value was taken.

The declarations are fixed. This applies the same change to a database that
already exists, because ``reconcile-schema`` adds columns and never touches an
index, so ``create_all`` on an existing table leaves the old unique index in
place and the defect survives the upgrade.

Two things this gets right that the earlier value-stream version did not:

* it drops **both** spellings. ``unique=True, index=True`` produces a unique
  INDEX (``ix_<table>_<column>``); ``unique=True`` alone produces a table
  CONSTRAINT (``<table>_<column>_key``). Dropping only the constraint was a
  silent no-op that reported success — see
  ``backfill_value_stream_tenancy``, where exactly that left every upgraded
  database still rejecting a second organisation's value-stream code.
* it creates the replacement **before** dropping the original, so there is no
  window in which neither is enforced.

Where existing rows would violate the new constraint the table is skipped and
the duplicates are printed. Nothing is guessed: two organisations' rows that
have collided under a global constraint are a data question, not a schema one.

    flask --app manage scope-unique-to-tenant --dry-run
    flask --app manage scope-unique-to-tenant
    flask --app manage scope-unique-to-tenant --table vendor_taxonomy
"""

from __future__ import annotations

import re

import click
from flask.cli import with_appcontext
from sqlalchemy import MetaData, Table, func, select, text

from app import db
from app.models.tenant_unique_registry import (
    SCOPE_PER_TENANT,
    tenant_unique_index_name,
)


_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _identifier(value: str) -> str:
    """Return *value* only if it is a plain lower-case SQL identifier.

    Table and column names cannot be bound as parameters, so the statements
    below interpolate them. Every one comes from SCOPE_PER_TENANT, a literal
    list in the source — but "the caller is trusted" is an argument that stops
    being true the moment someone wires this to anything else, and it is not
    checkable at the point of use. This makes it checkable: anything that is
    not a bare identifier raises instead of reaching a query.
    """
    if not _IDENTIFIER.match(value or ""):
        raise ValueError(f"refusing to build SQL with {value!r} as an identifier")
    return value


def _table_exists(conn, table) -> bool:
    return bool(
        conn.execute(
            text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
        ).scalar()
    )


def _column_exists(conn, table, column) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
    )


def _duplicates(conn, table, column):
    """Rows that would violate UNIQUE (organization_id, column).

    Built with SQLAlchemy Core against the reflected table rather than as an
    f-string. The identifiers cannot be bound as parameters, so a string
    version has to interpolate them — which is both a real hazard if this is
    ever wired to anything but the literal registry, and a finding the SAST
    gate is right to raise. Core quotes them instead.
    """
    reflected = Table(
        _identifier(table), MetaData(), autoload_with=conn.engine
    )
    target = reflected.c[_identifier(column)]
    org = reflected.c.organization_id
    tally = func.count().label("n")
    return conn.execute(
        select(org, target.label("value"), tally)
        .where(target.isnot(None))
        .group_by(org, target)
        .having(func.count() > 1)
        .order_by(tally.desc())
        .limit(10)
    ).fetchall()


@click.command("scope-unique-to-tenant")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--table", "only_table", default=None, help="Restrict to one table.")
@with_appcontext
def scope_unique_to_tenant(dry_run, only_table):
    """Swap global unique constraints for per-organisation ones."""
    conn = db.session.connection()
    scoped = skipped = absent = 0
    # Buffered so a table's steps are only reported after its transaction
    # commits. Echoing as each statement ran told the operator a change had
    # been applied that a later failure then rolled back.
    applied: list[str] = []

    for table, column in SCOPE_PER_TENANT:
        if only_table and table != only_table:
            continue
        # Validate before anything is interpolated into DDL below.
        _identifier(table), _identifier(column)

        if not _table_exists(conn, table) or not _column_exists(conn, table, column):
            absent += 1
            continue

        # Derived through the same helper the models use. Built inline here it
        # would exceed PostgreSQL's 63-byte identifier limit for the longest
        # table, Postgres would truncate what it created, and the
        # already_unique_per_tenant check below would then never match the
        # index it had just made — re-running the create on every boot.
        tenant_index = tenant_unique_index_name(table, column)
        legacy_index = f"ix_{table}_{column}"
        legacy_constraint = f"{table}_{column}_key"

        existing = {
            row[0]
            for row in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = :t"),
                {"t": table},
            ).fetchall()
        }
        already_unique_per_tenant = tenant_index in existing
        legacy_present = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i "
                "AND indexdef ILIKE '%UNIQUE%'"
            ),
            {"t": table, "i": legacy_index},
        ).first() is not None
        constraint_present = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint WHERE conname = :c "
                "AND conrelid = to_regclass(:t)"
            ),
            {"c": legacy_constraint, "t": f"public.{table}"},
        ).first() is not None

        if already_unique_per_tenant and not legacy_present and not constraint_present:
            continue

        dupes = _duplicates(conn, table, column)
        if dupes:
            skipped += 1
            click.echo(
                f"  ! {table}.{column}: {len(dupes)} duplicated "
                f"(organization_id, value) pair(s) — resolve these first:"
            )
            for org_id, value, n in dupes:
                click.echo(f"        org {org_id}: {value!r} x{n}")
            continue

        steps = [
            (
                f'CREATE UNIQUE INDEX IF NOT EXISTS {tenant_index} '
                f'ON "{table}" (organization_id, "{column}")',
                f"unique(organization_id, {column})",
            ),
        ]
        if constraint_present:
            steps.append(
                (f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS {legacy_constraint}',
                 "dropped the global unique constraint")
            )
        if legacy_present:
            steps.append(
                (f"DROP INDEX IF EXISTS {legacy_index}", "dropped the global unique index")
            )
            steps.append(
                (f'CREATE INDEX IF NOT EXISTS {legacy_index} ON "{table}" ("{column}")',
                 "restored the plain lookup index")
            )

        if dry_run:
            click.echo(f"  - {table}.{column}: would apply {len(steps)} step(s)")
            scoped += 1
            continue

        # One transaction per table, committed before moving on.
        #
        # These steps were previously wrapped in try/except inside a single
        # transaction spanning all 24 tables, on the reasoning that each step is
        # idempotent so a failure could be reported and skipped. That is not how
        # PostgreSQL behaves: one failed statement aborts the whole transaction,
        # so every later step AND every later table fails with
        # InFailedSqlTransaction, and the final commit raises — discarding the
        # tables that had genuinely succeeded, after their "+" lines had already
        # told the operator they were applied. It also held index locks on all
        # 24 tables until the end.
        failed = None
        try:
            with db.session.begin_nested():
                for ddl, label in steps:
                    conn.execute(text(ddl))
                    applied.append(f"  + {table}.{column}: {label}")
        except Exception as exc:  # noqa: BLE001 - one table's failure must not stop the rest
            failed = str(exc)[:140]

        if failed:
            click.echo(f"  ! {table}.{column}: not scoped ({failed})")
            skipped += 1
            continue

        db.session.commit()
        for line in applied:
            click.echo(line)
        applied.clear()
        scoped += 1

    if dry_run:
        db.session.rollback()
        click.echo(f"dry-run: {scoped} table(s) would change, {skipped} blocked, "
                   f"{absent} not present. No changes committed.")
        return

    click.echo(
        f"scope-unique-to-tenant: {scoped} scoped, {skipped} blocked by duplicates, "
        f"{absent} not present in this database."
    )


def init_app(app):
    """Register the scope-unique-to-tenant CLI command."""
    app.cli.add_command(scope_unique_to_tenant)
