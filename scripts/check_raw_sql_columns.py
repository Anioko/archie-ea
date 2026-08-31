#!/usr/bin/env python
"""Raw SQL that selects a column the table does not have.

    python scripts/check_raw_sql_columns.py            # report
    python scripts/check_raw_sql_columns.py --count    # integer only
    python scripts/check_raw_sql_columns.py --root DIR # scan a synthetic tree

Why
---
`app/modules/capabilities/routes/maturity_routes.py::search_capabilities` built

    SELECT id, name, business_domain, ..., category, capability_type
    FROM business_capability

`business_capability` has no `capability_type` column. Postgres raises
UndefinedColumn, the handler catches it, flashes an error and renders an empty
result page with HTTP 200. The owner found it by using the product; nothing in
the estate could have.

Nothing could, because both existing schema controls compare MODELS to the
database: `flask reconcile-schema` diffs mapped columns and the `schema-drift`
gate re-runs that diff. A string handed to `text()` is not a mapped anything, so
it is invisible to both. The `raw-sql-tenancy` gate reads the same strings but
only asks whether an `organization_id` predicate is present -- never whether the
columns exist. 98 statements were being read by a gate that could not see this.

What it checks
--------------
A raw SQL string in `app/` of the shape

    SELECT <explicit column list> FROM <single table> [WHERE/ORDER BY/...]

Every name in the column list, plus every `<table>.<column>` reference anywhere
in the statement, must exist on that table in `information_schema.columns`.

What it SKIPS, deliberately
---------------------------
Parsing arbitrary SQL with a regex is how a gate earns a reputation for crying
wolf, and a gate nobody believes is a gate nobody runs. So a statement is
skipped whole rather than guessed at when it contains any of:

  * `SELECT *`, or any function call / expression in the column list
  * a JOIN, a comma-separated FROM list, a subquery (a second SELECT), a CTE
    (leading WITH), or a UNION
  * a column alias (`AS`), or `DISTINCT`
  * a qualified name whose prefix is not the FROM table (a table alias)
  * an interpolated Python value anywhere in the statement -- the text that
    reaches Postgres is not the text we can see
  * a FROM table absent from the live schema (a CTE name, a temp table, a typo
    this gate is not equipped to judge)

Non-SELECT statements (INSERT/UPDATE/DELETE) are out of scope for now. The
skipped count is printed alongside the finding count in report mode so the blind
spot is measured rather than assumed.

If no database is reachable the check SKIPs: it prints a message on stderr and a
count of 0, because `verify.py` runs in dependency-free contexts and a gate that
fails on Postgres being absent gets disabled rather than fixed.

Escape hatch: `raw-sql-columns-ok: <reason>` on any line of the statement (or
the few lines around it), the same convention `tenancy-ok:` uses.

Proven-against: a synthetic tree whose query selects `bogus_column_xyz` from
business_capability -- red at 1 with that column present, green at 0 with it
removed.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"raw-sql-columns-ok:[ \t]*\S")

DEFAULT_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/flask_test_utf8",
)

SELECT_SHAPE = re.compile(
    r"^\s*SELECT\s+(?P<cols>.+?)\s+FROM\s+"
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)(?P<rest>$|[\s;].*)$",
    re.I | re.S,
)
COMPLEX = re.compile(r"\b(JOIN|UNION|DISTINCT|WITH|AS)\b|\(", re.I)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
QUALIFIED = re.compile(
    r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)"
)
# Anything whose runtime text we cannot see, or which makes the FROM list plural.
UNSEEABLE = re.compile(r"[{}%]")


def live_schema(dsn):
    """{table: {columns}} from information_schema, or None when unreachable."""
    try:
        import psycopg2
    except Exception:  # noqa: BLE001 - absent driver is a SKIP, not a failure
        return None
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
    except Exception:  # noqa: BLE001 - absent database is a SKIP, not a failure
        return None
    schema = {}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
        for table, column in cur.fetchall():
            schema.setdefault(table.lower(), set()).add(column.lower())
    finally:
        conn.close()
    return schema or None


def _sql_text(node):
    """Flatten a literal / f-string / concatenation into one searchable string.

    An interpolated value becomes a brace marker, which UNSEEABLE then uses to
    skip the whole statement: we cannot check columns in text we cannot read.
    """
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
        elif isinstance(sub, ast.FormattedValue):
            out.append(" {interpolated} ")
        elif isinstance(sub, (ast.Name, ast.Attribute)):
            out.append(" {interpolated} ")
    return " ".join(out)


def _statement_problems(sql, schema):
    """Return (findings, skipped); findings is [(table, column), ...]."""
    text = " ".join(sql.split())
    if not re.match(r"^\s*SELECT\b", text, re.I):
        return [], False  # not the shape this gate reads; not a skip either
    match = SELECT_SHAPE.match(text)
    if not match:
        return [], True
    cols_src = match.group("cols")
    table = match.group("table").lower()
    rest = match.group("rest")
    if UNSEEABLE.search(text):
        return [], True
    if COMPLEX.search(cols_src) or COMPLEX.search(rest):
        return [], True
    if "*" in cols_src or "," in rest.split(" WHERE ")[0]:
        return [], True
    if re.search(r"\bSELECT\b", rest, re.I):
        return [], True
    if table not in schema:
        return [], True

    known = schema[table]
    names = set()
    for raw in cols_src.split(","):
        name = raw.strip()
        if "." in name:
            prefix, _, name = name.partition(".")
            if prefix.lower() != table:
                return [], True  # an alias, or another table: not judgeable
        if not IDENT.match(name):
            return [], True
        names.add(name.lower())
    for prefix, column in QUALIFIED.findall(rest):
        if prefix.lower() == table:
            names.add(column.lower())

    return [(table, c) for c in sorted(names) if c not in known], False


def scan(root, schema):
    problems = []
    skipped = 0
    base = os.path.join(root, "app")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            lines = source.split("\n")
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name != "text":
                    continue
                found, was_skipped = _statement_problems(
                    _sql_text(node.args[0]), schema
                )
                if was_skipped:
                    skipped += 1
                if not found:
                    continue
                end = getattr(node, "end_lineno", None) or node.lineno
                window = "\n".join(lines[max(0, node.lineno - 3):end + 2])
                if ALLOW.search(window):
                    continue
                for table, column in found:
                    problems.append(
                        "%s:%d [raw-sql-columns] SELECT names %r, which does not "
                        "exist on table %r -- Postgres raises UndefinedColumn at "
                        "request time" % (rel, node.lineno, column, table)
                    )
    return problems, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()

    schema = live_schema(args.dsn)
    if schema is None:
        print(
            "SKIP raw-sql-columns: no database reachable at %s -- column "
            "existence cannot be checked without information_schema."
            % args.dsn,
            file=sys.stderr,
        )
        print(0)
        return 0

    problems, skipped = scan(os.path.abspath(args.root), schema)
    if not args.count:
        for line in problems:
            print("  " + line)
        print()
        print("%d statement(s) skipped as too complex to parse safely "
              "(joins, subqueries, aliases, SELECT *, interpolation)." % skipped)
        if problems:
            print(
                "Fix the query to name a real column, or append\n"
                "'raw-sql-columns-ok: <reason>' if the column is created at "
                "runtime."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
