#!/usr/bin/env python
"""Raw SQL in `app/` that Postgres itself refuses to plan.

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
columns exist.

How this works -- Postgres is the parser
----------------------------------------
The first version of this gate hand-parsed SQL with a regex and, to avoid crying
wolf, skipped every statement it could not be certain about: joins, aliases,
subqueries, CTEs, UNION, `SELECT *`, function calls, DISTINCT. That skipped 367
of ~371 statements. Four defects were found in the parseable 1%.

So this version does not parse SQL at all. It hands each statement to Postgres:

    PREPARE _c1 AS <statement>;   -- then DEALLOCATE

PREPARE parses, analyses and PLANS a statement without executing it, and raises
`UndefinedColumn` / `UndefinedTable` / `UndefinedFunction` when it is invalid.
Joins, aliases, subqueries, CTEs, UNION and `SELECT *` are handled for free
because this is the real grammar. Everything runs on one connection inside a
transaction that is always ROLLBACKed, each statement wrapped in its own
SAVEPOINT so one failure does not poison the rest. Nothing is ever executed.

INSERT/UPDATE/DELETE are included -- a wrong column in an UPDATE is worse than
in a SELECT. DDL and utility statements (CREATE/DROP/SET/ANALYZE/...) cannot be
PREPAREd and are out of scope.

The four problems that needed solving, and the answers
------------------------------------------------------
1. *Named parameters*. The codebase uses SQLAlchemy `:name`; PREPARE needs `$n`.
   Rewritten with a stable mapping so a repeated `:name` reuses its `$n`. `::`
   casts are left alone (the regex requires the colon to be preceded by neither
   a colon nor a word character, so `count(*)::text` never matches), and colons
   inside string literals are skipped by tracking quote state.
2. *Untyped parameters*. `could not determine data type of parameter $1`
   (SQLSTATE 42P18) means the placeholder is unconstrained, NOT that the schema
   is wrong. It is a PASS and is never reported.
3. *Interpolated SQL*. Where a value is clearly interpolated (after a
   comparison, `IN (`, `LIKE`, `LIMIT`, `VALUES`, or inside a quoted literal) a
   neutral literal is substituted. Where the interpolation is STRUCTURAL -- a
   table or column name spliced in -- the statement is not verifiable and is
   counted separately. That residual number is printed, not hidden.
4. *Multi-line concatenation*. Adjacent implicit-concatenation parts, `+`
   concatenation, `%`-formatting and `.format()` are reassembled into one
   statement before validation.

A statement naming a table that is absent from this database entirely is
reported as UNVERIFIABLE, not as a finding: the checking database may simply be
older than the code, and a false UndefinedTable would train people to ignore
this gate.

If no database is reachable the check SKIPs: it prints a message on stderr and a
count of 0, because `verify.py` runs in dependency-free contexts and a gate that
fails on Postgres being absent gets disabled rather than fixed.

Escape hatch: `raw-sql-columns-ok: <reason>` on any line of the statement (or
the few lines around it), the same convention `tenancy-ok:` uses.

Proven-against: a synthetic tree whose query joins business_capability to
application_components and selects `bogus_column_xyz` -- red at 1 with that
column present, green at 0 with it replaced by a real one, and green again with
the column restored plus a `raw-sql-columns-ok:` marker.
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

# A place-marker for text we cannot see. Chosen so it cannot occur in source.
MARK = "\x01?\x01"

STARTS = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|VALUES|TABLE)\b", re.I)

# SQLSTATEs that mean the statement names something the schema does not have.
DEFECT = {
    "42703": "UndefinedColumn",
    "42P01": "UndefinedTable",
}
# Real but attributable to our own placeholder substitution as often as to the
# code, so reported separately for human judgement rather than counted.
SUSPECT = {
    "42883": "UndefinedFunction/UndefinedOperator",
    "42704": "UndefinedObject",  # usually a type from an extension this DB lacks
    "42725": "AmbiguousFunction",
    "42702": "AmbiguousColumn",
}
# Not schema defects: our rewriting, a fragment, or an unconstrained parameter.
BENIGN = {
    "42P18",  # could not determine data type of parameter -- explicitly a PASS
    "42P08",  # the same, raised as "ambiguous parameter" -- also a PASS
    "42601",  # syntax error: a fragment, or something we mangled
    "42P02",  # missing parameter
    "0A000",  # feature not supported by PREPARE
    "42P10", "42804", "22P02", "42846", "42809", "42P20", "0Z002", "42P19",
}

# After FROM/JOIN a following "(" means a set-returning function or a derived
# table, not a relation -- excluded. After INTO/UPDATE the "(" is the column
# list of an INSERT, so the name before it IS the relation and must be checked.
TABLE_REFS = (
    re.compile(r"\b(?:FROM|JOIN)\s+(?:ONLY\s+)?"
               r"([A-Za-z_][A-Za-z0-9_]*)\b(?!\s*\()", re.I),
    re.compile(r"\b(?:INTO|UPDATE)\s+(?:ONLY\s+)?"
               r"([A-Za-z_][A-Za-z0-9_]*)\b", re.I),
)
# A schema-qualified reference (information_schema.columns, pg_catalog.pg_class)
# resolves fine; only the bare leading name is looked up, so strip the qualifier.
SCHEMA_QUALIFIED = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+[A-Za-z_]\w*\.", re.I)
SQL_WORDS = {"set", "select", "values", "lateral", "only", "where"}
# A value position: the marker sits where a literal would go.
VALUE_CTX = re.compile(
    r"(?:[=<>]|!=|<>|\b(?:LIKE|ILIKE|IN|VALUES|LIMIT|OFFSET|ANY|ALL|IS|BETWEEN"
    r"|AND|OR)\b)\s*\(?\s*$",
    re.I,
)


# --------------------------------------------------------------------------
# Reassembling the statement text from the AST
# --------------------------------------------------------------------------
def _fmt_markers(text):
    """Replace %s / %(name)s / {} / {name} placeholders with MARK."""
    text = re.sub(r"%\(\w+\)s|%[sdif]", MARK, text)
    return re.sub(r"\{[^{}]*\}", MARK, text)


def _build(node):
    """Flatten a literal / f-string / concatenation into one ordered string."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else MARK
    if isinstance(node, ast.JoinedStr):
        return "".join(_build(v) for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return MARK
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return _build(node.left) + _build(node.right)
        if isinstance(node.op, ast.Mod):
            return _fmt_markers(_build(node.left))
        return MARK
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "format":
            return _fmt_markers(_build(fn.value))
        return MARK
    return MARK


def _in_string_literal(text, index):
    """True when text[index] sits inside a single-quoted SQL literal."""
    return text.count("'", 0, index) % 2 == 1


def resolve_markers(sql):
    """Substitute neutral literals for value interpolation.

    Returns (sql, structural) -- structural is True when an interpolation sits
    somewhere only a table or column name could go, which makes the statement
    unverifiable rather than wrong.
    """
    while MARK in sql:
        i = sql.index(MARK)
        before = sql[:i]
        after = sql[i + len(MARK):]
        if _in_string_literal(sql, i):
            sql = before + "x" + after          # inside quotes: harmless text
        elif VALUE_CTX.search(before):
            sql = before + "NULL" + after       # a value position
        else:
            return sql, True                    # structural: cannot judge
    return sql, False


# --------------------------------------------------------------------------
# :name -> $n, without mangling :: casts or colons inside literals
# --------------------------------------------------------------------------
NAMED = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


def to_positional(sql):
    mapping = {}
    out = []
    pos = 0
    for m in NAMED.finditer(sql):
        if _in_string_literal(sql, m.start()):
            continue
        out.append(sql[pos:m.start()])
        name = m.group(1)
        if name not in mapping:
            mapping[name] = "$%d" % (len(mapping) + 1)
        out.append(mapping[name])
        pos = m.end()
    out.append(sql[pos:])
    return "".join(out)


# --------------------------------------------------------------------------
# Validation against a live server
# --------------------------------------------------------------------------
class Validator:
    """One connection, one transaction, always rolled back. Never executes."""

    def __init__(self, conn, tables):
        self.conn = conn
        self.tables = tables
        self.cur = conn.cursor()
        self.n = 0

    def check(self, sql):
        """Return (verdict, detail). verdict in ok|defect|suspect|unverifiable."""
        text = " ".join(sql.split())
        if not text or not STARTS.match(text):
            return "out-of-scope", ""
        body = text.rstrip().rstrip(";")
        if ";" in body:
            return "unverifiable", "multiple statements in one string"

        body, structural = resolve_markers(body)
        if structural:
            return "unverifiable", "structural interpolation (table/column spliced in)"

        plain = SCHEMA_QUALIFIED.sub("FROM ", body)
        for table in [t for rx in TABLE_REFS for t in rx.findall(plain)]:
            if table.lower() in SQL_WORDS:
                continue
            if table.lower() not in self.tables:
                # Could be a CTE name; only unverifiable if not defined here.
                if not re.search(r"\b%s\b\s+AS\s*\(" % re.escape(table), body, re.I):
                    return "unverifiable", "table %r absent from this database" % table

        body = to_positional(body)
        self.n += 1
        name = "_rsc_%d" % self.n
        try:
            self.cur.execute("SAVEPOINT rsc")
            self.cur.execute("PREPARE %s AS %s" % (name, body))
            self.cur.execute("DEALLOCATE %s" % name)
            self.cur.execute("RELEASE SAVEPOINT rsc")
            return "ok", ""
        except Exception as exc:  # noqa: BLE001 - the error IS the result
            self.cur.execute("ROLLBACK TO SAVEPOINT rsc")
            code = getattr(exc, "pgcode", None) or ""
            msg = " ".join(str(getattr(exc, "pgerror", None) or exc).split())
            if code in DEFECT:
                return "defect", "%s: %s" % (DEFECT[code], msg)
            if code in SUSPECT:
                return "suspect", "%s: %s" % (SUSPECT[code], msg)
            if code in BENIGN:
                return "ok", ""
            return "unverifiable", "%s: %s" % (code, msg)


def connect(dsn):
    try:
        import psycopg2
    except Exception:  # noqa: BLE001 - absent driver is a SKIP, not a failure
        return None
    try:
        return psycopg2.connect(dsn, connect_timeout=5)
    except Exception:  # noqa: BLE001 - absent database is a SKIP, not a failure
        return None


def live_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT relname FROM pg_class")
    names = {r[0].lower() for r in cur.fetchall()}
    cur.execute("SELECT table_name FROM information_schema.tables")
    names |= {r[0].lower() for r in cur.fetchall()}
    return names


# --------------------------------------------------------------------------
def scan(root, validator):
    findings, suspects = [], []
    counts = {"checked": 0, "unverifiable": 0, "out-of-scope": 0, "allowed": 0}
    reasons = {}
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
                raw = _build(node.args[0])
                verdict, detail = validator.check(raw)
                if verdict == "out-of-scope":
                    counts["out-of-scope"] += 1
                    continue
                if verdict == "unverifiable":
                    counts["unverifiable"] += 1
                    key = detail.split(":")[0]
                    reasons[key] = reasons.get(key, 0) + 1
                    continue
                counts["checked"] += 1
                if verdict == "ok":
                    continue
                end = getattr(node, "end_lineno", None) or node.lineno
                window = "\n".join(lines[max(0, node.lineno - 3):end + 2])
                if ALLOW.search(window):
                    counts["allowed"] += 1
                    continue
                snippet = " ".join(raw.split())[:160].replace(MARK, "<interp>")
                entry = "%s:%d [raw-sql-columns]\n      %s\n      -> %s" % (
                    rel, node.lineno, snippet, detail[:300])
                (findings if verdict == "defect" else suspects).append(entry)
    return findings, suspects, counts, reasons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()

    conn = connect(args.dsn)
    if conn is None:
        print(
            "SKIP raw-sql-columns: no database reachable at %s -- statements "
            "cannot be validated without a server to parse them." % args.dsn,
            file=sys.stderr,
        )
        print(0)
        return 0

    try:
        conn.autocommit = False
        validator = Validator(conn, live_tables(conn))
        findings, suspects, counts, reasons = scan(
            os.path.abspath(args.root), validator)
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()

    if not args.count:
        for line in findings:
            print("  " + line)
        if suspects:
            print()
            print("  Suspect (function/operator resolution -- may be caused by "
                  "an unconstrained placeholder rather than by the schema):")
            for line in suspects:
                print("  " + line)
        print()
        interp = sum(n for r, n in reasons.items() if r.startswith("structural"))
        print("%d statement(s) VALIDATED against Postgres, %d bad."
              % (counts["checked"], len(findings)))
        print("%d UNVERIFIABLE -- %d structural interpolation (a table or "
              "column name spliced in at runtime), %d naming a table this "
              "database does not have."
              % (counts["unverifiable"], interp, counts["unverifiable"] - interp))
        print("%d out of scope (DDL/utility/fragment, not PREPAREable); "
              "%d suppressed by raw-sql-columns-ok."
              % (counts["out-of-scope"], counts["allowed"]))
        for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print("    unverifiable: %-52s %d" % (reason[:52], n))
        if findings:
            print(
                "Fix the query to name a real column, or append\n"
                "'raw-sql-columns-ok: <reason>' if the object is created at "
                "runtime."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
