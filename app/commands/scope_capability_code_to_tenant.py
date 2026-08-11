"""Make ``business_capability.code`` unique per organisation instead of globally.

``code`` shipped as ``db.Column(db.String(50), unique=True)``, which Postgres
implements as ``ix_business_capability_code``, a globally unique index. Every
enterprise capability model uses codes — CAP-001, BC.1.2, APQC process ids — so
that constraint made them a first-come-first-served resource **across tenants**:
the second organisation to import its own model collided on the first row, and
the failure it saw said only that the code was taken.

The model now declares ``UniqueConstraint(organization_id, code)``. That is
enough for a database created by ``create_all()``, and not enough for one that
already exists: ``reconcile-schema`` adds columns and never drops an index, so
the old global index survives an upgrade and keeps rejecting the same rows. This
command performs the swap.

It is safe to run repeatedly, and it refuses to drop the global index while a
duplicate would violate the new per-tenant one — you would otherwise get a
half-applied state with neither constraint enforced.

    flask --app manage scope-capability-code-to-tenant --dry-run
    flask --app manage scope-capability-code-to-tenant
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app import db

TABLE = "business_capability"
GLOBAL_INDEX = "ix_business_capability_code"
TENANT_INDEX = "uq_business_capability_org_code"


def _duplicates(conn):
    """Rows that would violate unique(organization_id, code)."""
    return conn.execute(
        text(
            f"""
            SELECT organization_id, code, COUNT(*) AS n
            FROM "{TABLE}"
            WHERE code IS NOT NULL
            GROUP BY organization_id, code
            HAVING COUNT(*) > 1
            ORDER BY n DESC
            """
        )
    ).fetchall()


@click.command("scope-capability-code-to-tenant")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def scope_capability_code_to_tenant(dry_run):
    """Swap the global unique index on business_capability.code for a per-tenant one."""
    conn = db.session.connection()

    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = :t"), {"t": TABLE}
        ).fetchall()
    }

    if TENANT_INDEX in existing and GLOBAL_INDEX not in existing:
        click.echo("already scoped per tenant — nothing to do.")
        return

    dupes = _duplicates(conn)
    if dupes:
        click.echo(
            f"! {len(dupes)} (organization_id, code) pair(s) are duplicated. "
            "Resolve these before scoping, or the new constraint cannot be created:"
        )
        for org_id, code, n in dupes[:20]:
            click.echo(f"    org {org_id}: code {code!r} used by {n} capabilities")
        if len(dupes) > 20:
            click.echo(f"    … and {len(dupes) - 20} more")
        db.session.rollback()
        raise SystemExit(1)

    steps = [
        (
            f'CREATE UNIQUE INDEX IF NOT EXISTS {TENANT_INDEX} '
            f'ON "{TABLE}" (organization_id, code)',
            "added unique(organization_id, code)",
        ),
        # The global index is dropped only after the per-tenant one exists, so
        # there is no window in which neither is enforced.
        (f"DROP INDEX IF EXISTS {GLOBAL_INDEX}", "dropped global unique(code)"),
        (
            f'CREATE INDEX IF NOT EXISTS ix_{TABLE}_code ON "{TABLE}" (code)',
            "restored the plain lookup index on code",
        ),
    ]

    if dry_run:
        for _ddl, label in steps:
            click.echo(f"  - would run: {label}")
        click.echo("dry-run: no changes committed.")
        db.session.rollback()
        return

    for ddl, label in steps:
        try:
            conn.execute(text(ddl))
            click.echo(f"  + {label}")
        except Exception as exc:  # noqa: BLE001 - report and continue; each step is idempotent
            click.echo(f"  ! {label} skipped ({str(exc)[:120]})")

    db.session.commit()
    click.echo("scope-capability-code-to-tenant: done.")


def init_app(app):
    """Register the scope-capability-code-to-tenant CLI command."""
    app.cli.add_command(scope_capability_code_to_tenant)
