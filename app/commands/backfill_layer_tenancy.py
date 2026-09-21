"""Reconcile TenantMixin ownership with its declared nullable/required policy.

Nullable ownership is preserved for dedicated attribution commands. Required
ownership derives from supported parents before sole/explicit-org fallback.
All repairs use one transaction; dry runs only read the observed schema/data.
"""

import click
from flask.cli import with_appcontext

from app import db
from app.commands.tenant_schema import _HAS_INDEX


# Canonical parent derivation for required ownership. The same join predicate
# drives both the dry-run count and the UPDATE; only NULL owners are eligible.
_DERIVABLE_ORG = {
    "vendor_product_capabilities": ("business_capability", "business_capability_id"),
}


def _resolve_org_id(conn, explicit):
    from sqlalchemy import text

    if explicit is not None:
        row = conn.execute(
            text('SELECT id FROM public.organizations WHERE id = :i'), {"i": explicit}
        ).first()
        if not row:
            raise click.ClickException(f"No organization with id={explicit}.")
        return explicit
    rows = conn.execute(text("SELECT id, name FROM public.organizations ORDER BY id")).fetchall()
    if len(rows) == 1:
        return rows[0][0]
    listing = ", ".join(f"{r[0]}={r[1]}" for r in rows)
    raise click.ClickException(
        f"{len(rows)} organizations exist ({listing}). Re-run with --org-id to say which one "
        "owns the pre-existing rows."
    )


def _tenant_tables():
    """Return one sorted (name, nullable) inventory, refusing ambiguous mappings.

    Only ordinary tables on the default bind with an implicit public schema are
    supported. Retained mapper columns can differ from the canonical Table
    column after extend_existing; both must agree before any SQL is issued.
    """
    import re

    from sqlalchemy import Column, Integer, Table

    from app.models.mixins import TenantMixin

    safe = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    tables = {}
    errors = []
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if not issubclass(cls, TenantMixin):
            continue
        table = mapper.local_table
        label = f"{cls.__module__}.{cls.__qualname__} ({getattr(table, 'fullname', table)})"
        if not isinstance(table, Table):
            errors.append(f"{label}: unsupported table mapping")
            continue
        bind = table.metadata.info.get("bind_key")
        identity = (bind, table.schema, table.name)
        if (bind is not None or getattr(cls, "__bind_key__", None) is not None
                or table.schema is not None or not safe.fullmatch(table.name)):
            errors.append(f"{label}: unsupported bind/schema/table identity {identity!r}")
            continue
        canonical = table.c.get("organization_id")
        prop = mapper.column_attrs.get("organization_id")
        mapped = list(prop.columns) if prop is not None else []
        if canonical is None or len(mapped) != 1:
            errors.append(f"{label}: missing or ambiguous organization_id metadata")
            continue
        columns = [canonical, mapped[0]]
        if any(not isinstance(c, Column) or c.table is not table or c.name != "organization_id"
               or c.key != "organization_id" or not isinstance(c.type, Integer)
               or type(c.nullable) is not bool for c in columns):
            errors.append(f"{label}: unsupported organization_id column metadata")
            continue
        if mapped[0].nullable is not canonical.nullable:
            errors.append(f"{label}: mapped/canonical organization_id nullability conflict")
            continue
        tables.setdefault(identity, []).append((canonical.nullable, label))
    for identity, declarations in tables.items():
        if len({nullable for nullable, _ in declarations}) != 1:
            labels = ", ".join(sorted(label for _, label in declarations))
            errors.append(f"{identity!r}: conflicting organization_id policies: {labels}")
    if errors:
        raise click.ClickException("Invalid tenancy metadata: " + "; ".join(sorted(errors)))
    return sorted((identity[2], declarations[0][0]) for identity, declarations in tables.items())


def repair_layer_tenancy(org_id=None, dry_run=False):
    """Repair declared ownership policy atomically, without moving existing owners.

    Returns {"repaired": [...], "skipped_healthy": n, "absent": [...]}.
    Dry-run repaired entries describe planned changes, never committed writes.
    """
    from sqlalchemy import inspect, text

    repaired, absent, messages = [], [], []
    healthy = 0
    resolved_org = None
    try:
        inventory = _tenant_tables()
        conn = db.session.connection()
        insp = inspect(conn)
        if conn.dialect.name != "postgresql" or insp.default_schema_name != "public":
            raise click.ClickException("Tenancy repair requires the default PostgreSQL public schema.")
        live = set(insp.get_table_names(schema="public"))
        for t, nullable in inventory:
            if t not in live:
                absent.append(t)
                continue
            target = f'"public"."{t}"'
            cols = {c["name"]: c for c in insp.get_columns(t, schema="public")}
            col = cols.get("organization_id")
            if col is not None and type(col.get("nullable")) is not bool:
                raise click.ClickException(f"{t}: catalog nullability is unavailable")
            missing = col is None
            actions = []
            if missing:
                actions.append("ADD COLUMN organization_id INTEGER (nullable, no default)")
            orphans = conn.execute(text(
                f'SELECT count(*) FROM {target}'
                + ("" if missing else " WHERE organization_id IS NULL")
            )).scalar_one()

            if nullable:
                if not missing and col["nullable"] is False:
                    actions.append("DROP NOT NULL")
                if not dry_run:
                    if missing:
                        conn.execute(text(f'ALTER TABLE {target} ADD COLUMN organization_id INTEGER'))
                    elif col["nullable"] is False:
                        conn.execute(text(f'ALTER TABLE {target} ALTER COLUMN organization_id DROP NOT NULL'))
                    insp.clear_cache()
                    actual = next(c for c in insp.get_columns(t, schema="public")
                                  if c["name"] == "organization_id")
                    if actual["nullable"] is not True:
                        raise click.ClickException(f"{t}: nullable ownership postcondition failed")
                messages.append(
                    f"  {t}: {orphans} NULL owner(s) preserved; "
                    "index/FK completion deferred to dedicated commands"
                )
            else:
                index_params = {"table": target, "column": "organization_id"}
                has_index = conn.execute(text(_HAS_INDEX), index_params).first() is not None
                index_name = f"ix_{t}_organization_id"
                if not has_index:
                    # Index names share the table's schema with all relations.
                    # PostgreSQL's name cast applies its identifier length limit;
                    # keep both the schema and quoted table identity exact.
                    occupied = conn.execute(text(
                        "SELECT c.oid FROM pg_catalog.pg_class c "
                        "WHERE c.relnamespace = (SELECT relnamespace FROM pg_catalog.pg_class "
                        "WHERE oid = to_regclass(:table)) "
                        "AND c.relname = CAST(:index_name AS name)"
                    ), {"table": target, "index_name": index_name}).first()
                    if occupied:
                        raise click.ClickException(
                            f'{t}: cannot add organization index; public."{index_name}" '
                            "is occupied and no valid organization-leading index exists"
                        )
                if not dry_run and missing:
                    conn.execute(text(f'ALTER TABLE {target} ADD COLUMN organization_id INTEGER'))
                derivation = _DERIVABLE_ORG.get(t)
                if derivation and orphans:
                    parent, link = derivation
                    predicate = f'v."{link}" = b.id AND b.organization_id IS NOT NULL'
                    if not (dry_run and missing):
                        predicate += " AND v.organization_id IS NULL"
                    if dry_run:
                        derived = conn.execute(text(
                            f'SELECT count(*) FROM {target} v JOIN public."{parent}" b ON {predicate}'
                        )).scalar_one()
                    else:
                        derived = conn.execute(text(
                            f'UPDATE {target} v SET organization_id = b.organization_id '
                            f'FROM public."{parent}" b WHERE {predicate}'
                        )).rowcount
                    if derived:
                        actions.append(f"derive {derived} owner(s) from linked entity")
                    if dry_run:
                        orphans -= derived
                    else:
                        orphans = conn.execute(text(
                            f'SELECT count(*) FROM {target} WHERE organization_id IS NULL'
                        )).scalar_one()
                if orphans:
                    if resolved_org is None:
                        resolved_org = _resolve_org_id(conn, org_id)
                    actions.append(f"assign {orphans} residual owner(s) to org {resolved_org}")
                    if not dry_run:
                        conn.execute(text(
                            f'UPDATE {target} SET organization_id = :o WHERE organization_id IS NULL'
                        ), {"o": resolved_org})
                if not has_index:
                    actions.append("add organization index")
                    if not dry_run:
                        conn.execute(text(
                            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                            f'ON {target} (organization_id)'
                        ))
                if missing or col["nullable"]:
                    actions.append("SET NOT NULL")
                    if not dry_run:
                        conn.execute(text(f'ALTER TABLE {target} ALTER COLUMN organization_id SET NOT NULL'))
                if not dry_run:
                    insp.clear_cache()
                    actual = next(c for c in insp.get_columns(t, schema="public")
                                  if c["name"] == "organization_id")
                    remaining = conn.execute(text(
                        f'SELECT count(*) FROM {target} WHERE organization_id IS NULL'
                    )).scalar_one()
                    if (actual["nullable"] is not False or remaining
                            or not conn.execute(text(_HAS_INDEX), index_params).first()):
                        raise click.ClickException(f"{t}: required ownership postcondition failed")
            if actions:
                repaired.append(t)
                messages.append(f"  {t}: {'would ' if dry_run else ''}" + "; ".join(actions))
            else:
                healthy += 1
        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, click.ClickException):
            raise
        raise click.ClickException(f"Tenancy repair failed; transaction rolled back: {exc}") from exc
    for message in messages:
        click.echo(message)
    return {"repaired": repaired, "skipped_healthy": healthy, "absent": absent}


@click.command("backfill-layer-tenancy")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@click.option("--org-id", type=int, default=None, help="Organization for unresolved required-tenant rows.")
@with_appcontext
def backfill_layer_tenancy(dry_run, org_id):
    """Reconcile declared nullable ownership and harden required ownership."""
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
