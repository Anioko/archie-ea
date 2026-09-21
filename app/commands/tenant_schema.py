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

Each step runs in its own savepoint. A step that fails (for example a foreign
key over rows that name an organisation that does not exist) is rolled back on
its own and reported; it does not abort the caller's transaction, so the rows
the caller has just attributed are still committed.
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
