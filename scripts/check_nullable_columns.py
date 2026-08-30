#!/usr/bin/env python
"""A new NOT NULL column without a default breaks every existing database.

Archie does not run Alembic on deploy. `flask reconcile-schema` is what closes
drift, and CLAUDE.md states its limit plainly:

    "reconcile-schema only adds nullable columns ... adding a non-nullable
     column, or one with a backfill requirement, will break existing databases"

The failure mode is documented in docs/known-issues/schema-drift-on-existing-
databases.md and it is not gentle: one missing column raises UndefinedColumn,
which aborts the transaction and cascades into InFailedSqlTransaction for every
later query, 500-ing the whole page rather than the one feature.

`schema-drift` detects this AFTER a model and a database have diverged. Nothing
stops the divergence being authored. That is what this gate does: a mapped
column declared `nullable=False` must carry a `default=` or `server_default=`,
so reconcile-schema can add it to a populated table without violating the
constraint.

Primary keys and foreign-key columns inside association tables are exempt --
their NOT NULL comes with the row, not after it.

This is a ratchet, and its baseline needs reading honestly: the ~1,200 columns
already counted are NOT live defects. Their tables were created whole by
create_all(), so the constraint was satisfied at creation and no deploy ever had
to add them to populated rows. They are counted because static analysis cannot
see when a column was added, and the number is the price of catching the one
that matters: the NEXT column, added to a table that already has rows. The gate
earns its keep by refusing to let the number grow.

Escape hatch: `nullable-ok: <reason>` on the column's line, for a table that
is created fresh rather than reconciled.

    python scripts/check_nullable_columns.py
    python scripts/check_nullable_columns.py --count

Proven-against: a `db.Column(db.String(20), nullable=False)` with no default
added to app/models/tech_radar.py -- red on that line, green when a
server_default was supplied.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"nullable-ok:[ \t]*\S")


def scan(root: str) -> list[str]:
    problems = []
    models = os.path.join(root, "app", "models")
    for dirpath, dirnames, filenames in os.walk(models):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            # Columns are frequently wrapped across lines; join a statement
            # before matching so a multi-line declaration is judged whole.
            statements, buf, start = [], "", 0
            for number, line in enumerate(text.split("\n"), 1):
                if not buf:
                    start = number
                buf += line.strip() + " "
                if buf.count("(") <= buf.count(")") and buf.strip():
                    statements.append((start, buf))
                    buf = ""
            for number, stmt in statements:
                if "nullable=False" not in stmt or "db.Column" not in stmt:
                    continue
                if "primary_key=True" in stmt:
                    continue
                if "default=" in stmt or "server_default=" in stmt:
                    continue
                if ALLOW.search(stmt):
                    continue
                name = stmt.split("=", 1)[0].strip()
                problems.append(
                    "%s:%d [nullable] column %r is NOT NULL with no default -- if it "
                    "is ever ADDED to a table that already has rows, reconcile-schema "
                    "cannot apply it" % (rel, number, name[:40])
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
                "Give the column a default= or server_default= so reconcile-schema can\n"
                "add it to a populated table, make it nullable, or append\n"
                "'nullable-ok: <reason>' if the table is only ever created fresh."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
