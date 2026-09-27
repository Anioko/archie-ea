#!/usr/bin/env python
"""Rows loaded only to be counted. Cheap at demo scale, a hang at customer scale.

`len(SomeModel.query.filter(...).all())` pulls every matching row across the
wire, builds an ORM object for each, and throws them away to learn a number
`.count()` would have returned from one aggregate. On the seeded demo estate
this is invisible. On a real portfolio it is the difference between a page and
a timeout, and it will be found by a customer rather than by us.

This exists because of a near miss. On 30 Aug 2026 the audit reported
/dashboard/health timing out at 45s, and the assumption -- reasonable, wrong --
was that its four full-table scans were the cause. Measured: 0.04s over 17,738
elements, and the timeout was a cold start. A fix was nearly shipped to a page
that was fine. But the measurement also showed the real gap: nothing in 53
gates measures query cost at all, so an N+1 that only bites at 100,000 rows has
no way of being caught before a customer finds it.

Deliberately narrow, so every finding is a fact rather than a suspicion. Only
`len(<something>.all())` is reported -- an unambiguous count that loaded its
rows. Loops that aggregate while iterating are a judgement call about
readability and are left alone.

Escape hatch: `page-cost-ok: <reason>` on the line, for a set small and bounded
by construction (an enum table, a per-request cache).

    python scripts/check_page_cost.py
    python scripts/check_page_cost.py --count

Proven-against: `len(ArchiMateElement.query.all())` added to
app/modules/tech_radar/service.py -- red on that line, green when replaced with
`.count()`.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"page-cost-ok:[ \t]*\S")


def scan(root: str) -> list[str]:
    problems = []
    seen = set()
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if "/tests/" in rel or filename.startswith("test_"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            lines = source.split("\n")
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "len"
                        and node.args):
                    continue
                inner = node.args[0]
                if not (isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr == "all"):
                    continue
                line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                if ALLOW.search(line):
                    continue
                # ast.walk visits a nested len(...) through more than one parent,
                # so the same site can be reached twice. Report each site once.
                if (rel, node.lineno) in seen:
                    continue
                seen.add((rel, node.lineno))
                problems.append(
                    "%s:%d [page-cost] len(....all()) loads every row to count them; "
                    "use .count() so the database does the counting"
                    % (rel, node.lineno)
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    problems = scan(os.path.abspath(args.root))
    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "Replace len(q.all()) with q.count(), or append 'page-cost-ok: <reason>'\n"
                "if the result set is small and bounded by construction."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
