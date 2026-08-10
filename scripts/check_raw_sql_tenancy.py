#!/usr/bin/env python
"""Find raw SQL that reads a tenant-scoped table without an organization predicate.

    python scripts/check_raw_sql_tenancy.py            # report
    python scripts/check_raw_sql_tenancy.py --count    # count only
    python scripts/check_raw_sql_tenancy.py --json

Why
---
Multi-tenancy is enforced by a `do_orm_execute` listener that rewrites ORM
statements. Raw `db.session.execute(text(...))` is not an ORM statement, so it
goes to the database exactly as written. Nothing in the codebase noticed the
difference, and the convention that grew up instead was a comment:

    _org_filter3 = ""
    _org_params3 = {}
    capabilities = db.session.execute(  # tenant-filtered
        text(f"... FROM business_capability {_org_filter3} ORDER BY name"),

That comment has now been wrong twice. Ten queries in
business_capability_management_routes.py returned every organisation's rows, and
the dashboard's capability-coverage metric counted every organisation's mappings
and then divided by one organisation's application total, producing a percentage
that could exceed 100%.

A comment is not a control. This is.

What it does and does not catch
-------------------------------
It reports a raw SQL string that names a table backed by a TenantMixin model and
contains no `organization_id` anywhere in the statement. That is the exact shape
of both real findings.

It deliberately does NOT try to judge the far more common "scoped via parent FK"
case, where a query filters on a parent that was itself tenant-scoped. Deciding
whether the parent really was scoped needs to follow the value backwards through
the caller, which a regex cannot do — an earlier attempt to flag those produced
334 hits, essentially all false positives, and a check nobody believes is a check
nobody runs.

So a clean result here does not mean tenancy is proven. It means the one
mechanically detectable failure — no predicate at all — is absent.

Exemptions
----------
Append `tenancy-ok: <reason>` on the line to record a deliberate exception, the
same convention `design-tokens-ok` uses. Aggregates that are genuinely global,
and CLI paths with no request context, are the expected users of it.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Populated from the ORM at run time; falls back to a cached list so the check
# still works without a database.
CACHE = os.path.join(REPO_ROOT, "scripts", "tenant_tables.txt")

SQL_VERB = re.compile(r"\b(SELECT|UPDATE|DELETE\s+FROM|INSERT\s+INTO)\b", re.I)
FROM_TABLE = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([a-z_][a-z0-9_]*)", re.I)


# `organization_id` as a WHOLE identifier. Without the leading boundary,
# `vendor_organization_id` matched and was accepted as tenant scoping,
# which silently passed two live cross-tenant leaks.
_ORG_COL = re.compile(r"(?<![A-Za-z0-9_])organization_id(?![A-Za-z0-9_])")


def tenant_tables() -> set[str]:
    try:
        from app import create_app, db  # noqa: F401
        from app.models.mixins import TenantMixin

        create_app("testing")
        found = {
            m.class_.__tablename__
            for m in db.Model.registry.mappers
            if issubclass(m.class_, TenantMixin) and hasattr(m.class_, "__tablename__")
        }
        if found:
            with io.open(CACHE, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(sorted(found)) + "\n")
            return found
    except Exception:  # noqa: BLE001 — fall back rather than fail the gate
        pass
    if os.path.exists(CACHE):
        return {ln.strip() for ln in io.open(CACHE, encoding="utf-8") if ln.strip()}
    return set()


def _string_parts(node: ast.AST) -> str:
    """Flatten a literal / f-string / concatenation into searchable text."""
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
        elif isinstance(sub, ast.Name):
            out.append(f"{{{sub.id}}}")
        elif isinstance(sub, ast.Attribute):
            out.append(f"{{{sub.attr}}}")
    return " ".join(out)


def scan_file(path: str, tables: set[str]) -> list[tuple[int, str, str]]:
    try:
        source = io.open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    findings = []
    for node in ast.walk(tree):
        # Only text(...) / db.text(...) calls — that is what bypasses the listener.
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name != "text" or not node.args:
            continue
        sql = _string_parts(node.args[0])
        if not SQL_VERB.search(sql):
            continue
        hit = {t for t in FROM_TABLE.findall(sql) if t.lower() in tables}
        if not hit:
            continue
        # The whole statement, not just the string: the predicate is often built
        # into a variable interpolated in, or passed as a bound parameter.
        # Strip Python comments before looking for the predicate. The window is
        # searched because the clause is often built into a variable a few lines
        # up - but a COMMENT mentioning organization_id is not scoping, and this
        # gate accepted one. Proved by mutation: deleting a real org_scope() call
        # left the count at zero, because the comment above it explaining the fix
        # contained the word. This file's own docstring says 'a comment is not a
        # control'. It was one here.
        _window = lines[max(0, node.lineno - 10): node.lineno + 12]
        # Two different questions, two different windows.
        #   seg_raw  - does a deliberate `tenancy-ok:` marker exist? Markers
        #              live in comments by design, like the repo's other
        #              per-line hatches, so this must keep them.
        #   seg      - is there an actual organization_id predicate? A
        #              comment merely MENTIONING the column is not one, and
        #              accepting it made this gate satisfiable by prose -
        #              the precise failure its own docstring names.
        seg_raw = "".join(_window)
        seg = "\n".join(re.sub(r"#.*$", "", ln) for ln in _window)
        # Scoping evidence, in order of directness:
        #   - the predicate is written into the statement, or
        #   - a clause built by a helper is interpolated into it.
        # The first version looked only for a literal "organization_id" and so
        # reported the queries fixed by _org_scope() as unscoped — it scored
        # identically before and after that fix, which is the definition of a
        # check that measures nothing. Caught by reverting a known fix and
        # seeing the number not move.
        # A WORD-boundary match, not a substring. `vendor_organization_id` is a
        # different column on a different table, and the substring test accepted
        # it as proof of tenant scoping: it silently passed two live leaks in
        # routes_vendor_analysis.py and routes_hybrid_mapping.py, each of which
        # listed every organisation's elements by name. A false negative in a
        # gate is worse than a false positive, because nobody goes looking.
        if _ORG_COL.search(seg) or _ORG_COL.search(sql):
            continue
        # A clause built by the canonical helper and interpolated INTO this
        # statement. Both halves are required. An earlier version accepted any
        # `_org_*` name appearing nearby, which meant renaming the interpolated
        # variable while leaving an unused `_org_params` in scope still read as
        # scoped — the mutation test moved the count by zero, so the gate could
        # not have caught the regression it exists for.
        # The statement must interpolate a variable whose NAME says it carries the
        # org predicate. Two weaker rules were tried and both failed their own
        # mutation test: "any _org_* name nearby" and "the helper is nearby AND
        # something is interpolated". Neither could tell which variable actually
        # went into the SQL, so renaming the interpolated one while leaving an
        # unused _org_params in scope still read as scoped and the count moved by
        # zero. Requiring "org" in the interpolated name is checkable with a
        # regex and makes the convention explicit.
        if re.search(r"\{[A-Za-z0-9_]*org[A-Za-z0-9_]*\}", sql, re.I):
            continue
        if "tenancy-ok" in seg_raw:
            continue
        findings.append((node.lineno, sorted(hit)[0], sql.strip()[:90]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    tables = tenant_tables()
    if not tables:
        print("FAIL: could not determine the tenant-scoped tables", file=sys.stderr)
        return 1

    results = []
    for root, dirs, files in os.walk(os.path.join(REPO_ROOT, "app")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            for lineno, table, sql in scan_file(path, tables):
                results.append({
                    "file": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
                    "line": lineno, "table": table, "sql": sql,
                })

    if args.count:
        print(len(results))
        return 0
    if args.json:
        print(json.dumps({"tenant_tables": len(tables), "findings": results}, indent=2))
        return 1 if results else 0

    for r in results:
        print(f"  {r['file']}:{r['line']}  [{r['table']}]  {r['sql']}")
    if results:
        print(f"\n{len(results)} raw SQL statement(s) read a tenant-scoped table with no "
              f"organization_id predicate, across {len(tables)} tenant tables.")
        print("Scope the query, or append 'tenancy-ok: <reason>' if it is deliberately global.")
        return 1
    print(f"No unscoped raw SQL found against {len(tables)} tenant-scoped tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
