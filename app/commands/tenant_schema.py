"""Index and foreign key for a tenant column added to an existing table.

``reconcile-schema`` adds ``organization_id`` to an existing table as a plain
nullable INTEGER: no index, no foreign key. The ``backfill-*-org`` commands
attribute the rows and then finish the column with
``ensure_organization_index_and_fk``, so the answer to "what does a tenant
column on an existing table need?" is written once.

What is already there is found by looking at the column, not at a constraint or
index name. A database built by ``create_all`` already carries a foreign key
under the name SQLAlchemy chose, and one that an earlier run of a backfill
added carries the conventional name; either one satisfies the check, so a
second, duplicate constraint is never added.

Each step runs in its own savepoint. By default a step that fails (for example a foreign
key over rows that name an organisation that does not exist) is rolled back on
its own and reported; it does not abort the caller's transaction, so the rows
the caller has just attributed can still be committed. Strict callers instead
use the read-only public schema planner and verify each DDL postcondition,
propagating failure for the caller to roll back its complete invocation.
"""

import re

from sqlalchemy import text

COLUMN = "organization_id"

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

_HAS_COLUMN = (
    "SELECT 1 FROM pg_attribute "
    "WHERE attrelid = to_regclass(:table) AND attname = :column AND NOT attisdropped"
)

# A valid index whose first key is the column.
_HAS_INDEX = (
    "SELECT 1 FROM pg_index i "
    "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0] "
    "WHERE i.indrelid = to_regclass(:table) AND a.attname = :column AND i.indisvalid "
    "LIMIT 1"
)

# A foreign key on the column that points at organizations.
_HAS_FOREIGN_KEY = (
    "SELECT 1 FROM pg_constraint c "
    "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
    "WHERE c.conrelid = to_regclass(:table) AND c.contype = 'f' "
    "AND c.confrelid = to_regclass('organizations') AND a.attname = :column"
)


def _step(conn, table, label, present_sql, ddl, echo, strict):
    """Run one of the two steps; return 'present', 'added' or 'failed: <reason>'."""
    if conn.execute(text(present_sql), {"table": f'"{table}"', "column": COLUMN}).first():
        status = "present"
        line = f"  = {table}: {label} already present"
    else:
        try:
            with conn.begin_nested():
                conn.execute(text(ddl))
            status = "added"
            line = f"  + {table}: {label}"
        except Exception as exc:  # noqa: BLE001 - reported, and re-raised when strict
            if strict:
                raise
            reason = " ".join(str(exc).split())[:100]
            status = f"failed: {reason}"
            line = f"  ! {table}: {label} skipped ({reason})"
    if echo is not None:
        echo(line)
    return status


def ensure_organization_index_and_fk(conn, table, *, echo=None, strict=False):
    """Give ``table.organization_id`` an index and a foreign key to organizations.

    ``conn`` is the connection the caller is already writing on. Returns
    ``{"index": status, "foreign_key": status}`` where each status is
    ``"present"`` (nothing to do), ``"added"`` or ``"failed: <reason>"``.
    ``echo`` is called with one line per step. With ``strict`` a failing step
    raises after its savepoint is rolled back, instead of being reported.
    The table must exist and carry the column.
    """
    if strict:
        return _ensure_strict(conn, table, echo)
    if not _IDENTIFIER.match(table):
        raise ValueError(f"not a plain table name: {table!r}")
    if not conn.execute(text(_HAS_COLUMN), {"table": f'"{table}"', "column": COLUMN}).first():
        raise ValueError(f"{table}.{COLUMN} does not exist")

    index_ddl = f'CREATE INDEX IF NOT EXISTS ix_{table}_{COLUMN} ON "{table}" ({COLUMN})'  # nosec B608 -- table is a validated identifier
    fk_ddl = (
        f'ALTER TABLE "{table}" ADD CONSTRAINT fk_{table}_organization '  # nosec B608 -- table is a validated identifier
        f"FOREIGN KEY ({COLUMN}) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    return {
        "index": _step(conn, table, "index", _HAS_INDEX, index_ddl, echo, strict),
        "foreign_key": _step(conn, table, "foreign key", _HAS_FOREIGN_KEY, fk_ddl, echo, strict),
    }


def plan_organization_index_and_fk(conn, table, *, column_missing=False):
    """Read the public catalogs/data; return present/add or raise a conflict.

    The caller owns transaction lifetime and any serialization. A preview of a
    missing column treats it as nullable INTEGER without querying its values.
    Existing valid FK names and delete actions are deliberately immaterial.
    """
    if not _IDENTIFIER.fullmatch(table):
        raise ValueError(f"not a plain table name: {table!r}")
    if conn.dialect.name != "postgresql":
        raise ValueError("Tenant schema planning requires PostgreSQL")
    target = f'"public"."{table}"'
    params = {"table": target, "column": COLUMN,
              "index_name": f"ix_{table}_{COLUMN}", "fk_name": f"fk_{table}_organization"}
    relation = conn.execute(text(
        "SELECT relkind FROM pg_catalog.pg_class WHERE oid = to_regclass(:table)"
    ), params).scalar_one_or_none()
    if relation not in {"r", "p"}:
        raise ValueError(f"{target}: public table does not exist")
    attribute = conn.execute(text(
        "SELECT attnum FROM pg_catalog.pg_attribute "
        "WHERE attrelid = to_regclass(:table) AND attname = :column AND NOT attisdropped"
    ), params).scalar_one_or_none()
    if (attribute is None) != column_missing:
        raise ValueError(f"{table}.{COLUMN}: column does not exist or preview shape changed")
    organization = conn.execute(text(
        "SELECT a.attrelid, a.attnum FROM pg_catalog.pg_attribute a "
        "JOIN pg_catalog.pg_class c ON c.oid = a.attrelid "
        "WHERE a.attrelid = to_regclass('public.organizations') AND a.attname = 'id' "
        "AND NOT a.attisdropped AND c.relkind IN ('r', 'p')"
    )).first()
    if organization is None:
        raise ValueError("public.organizations.id does not exist; run reconcile-schema first")
    has_index = conn.execute(text(_HAS_INDEX), params).first() is not None
    if not has_index and conn.execute(text(
        "SELECT 1 FROM pg_catalog.pg_class c "
        "WHERE c.relnamespace = (SELECT relnamespace FROM pg_catalog.pg_class "
        "WHERE oid = to_regclass(:table)) AND c.relname = CAST(:index_name AS name)"
    ), params).first():
        raise ValueError(f"{table}: organization index name is occupied; no qualifying index exists")

    constraints = conn.execute(text(
        "SELECT c.conname, c.contype, c.convalidated, c.conkey, c.confrelid, c.confkey "
        "FROM pg_catalog.pg_constraint c WHERE c.conrelid = to_regclass(:table) "
        "AND (c.conname = CAST(:fk_name AS name) OR "
        "(c.contype = 'f' AND :attribute = ANY(c.conkey))) ORDER BY c.conname"
    ), {**params, "attribute": attribute}).all()
    has_fk = False
    for name, kind, validated, keys, referenced, referenced_keys in constraints:
        if (attribute is not None and kind == "f" and validated
                and list(keys or []) == [attribute] and referenced == organization[0]
                and list(referenced_keys or []) == [organization[1]]):
            has_fk = True
        else:
            raise ValueError(
                f"{table}: conflicting constraint {name}; a validated single-column "
                "organization_id foreign key to public.organizations.id is required"
            )
    if not column_missing and conn.execute(text(
        f'SELECT 1 FROM {target} t WHERE t.organization_id IS NOT NULL '  # nosec B608 -- table is validated and public-qualified
        "AND NOT EXISTS (SELECT 1 FROM public.organizations o WHERE o.id = t.organization_id) LIMIT 1"
    )).first():
        raise ValueError(f"{table}: invalid existing organization owner; repair requires explicit authority")
    return {"index": "present" if has_index else "add",
            "foreign_key": "present" if has_fk else "add"}


def _ensure_strict(conn, table, echo):
    # Catalog SQL can fail too. Its savepoint preserves caller usability even
    # when PostgreSQL, rather than Python validation, rejects the preflight.
    with conn.begin_nested():
        plan = plan_organization_index_and_fk(conn, table)
    target = f'"public"."{table}"'
    ddls = {
        "index": f'CREATE INDEX "ix_{table}_{COLUMN}" ON {target} ({COLUMN})',
        "foreign_key": (
            f'ALTER TABLE {target} ADD CONSTRAINT "fk_{table}_organization" '
            f'FOREIGN KEY ({COLUMN}) REFERENCES public.organizations(id) ON DELETE CASCADE'
        ),
    }
    statuses, lines = {}, []
    for key, action in plan.items():
        if action == "add":
            with conn.begin_nested():
                conn.execute(text(ddls[key]))
                if plan_organization_index_and_fk(conn, table)[key] != "present":
                    raise ValueError(f"{table}: {key} postcondition failed")
            statuses[key] = "added"
        else:
            statuses[key] = "present"
        label = key.replace("_", " ")
        lines.append(f"  + {table}: {label}" if action == "add"
                     else f"  = {table}: {label} already present")
    with conn.begin_nested():
        if plan_organization_index_and_fk(conn, table) != {
            "index": "present", "foreign_key": "present",
        }:
            raise ValueError(f"{table}: tenant schema postcondition failed")
    if echo is not None:
        for line in lines:
            echo(line)
    return statuses
