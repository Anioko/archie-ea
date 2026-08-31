#!/usr/bin/env python
"""One concept, one store. Two model classes on one table is how screens disagree.

The 30 Aug 2026 QA audit's most consequential finding was not a bug:

    "The domain model duplicates core concepts across unreconciled stores, and
     the contradictions are visible to users: four gap counts, two
     capability-coverage percentages, three work-package populations, five
     capability stores. This is the finding most likely to erode trust once real
     users compare two screens."

It measured the symptom -- /capability-map/ showing "Total Capabilities 191"
directly above a table reading "Showing 1-10 of 0 results", and traceability
reporting 48% coverage where the capability map reported 0%. Both are two stores
answering one question.

This gate holds the smallest mechanically checkable part of that: no NEW table
gains a second mapped model class. Ten already have, which CLAUDE.md records as
"a known legacy hazard" that init-db works around by de-duplicating same-named
indexes before create_all(). Acknowledged and ungated means it can still grow,
and every addition creates another pair of surfaces that can disagree.

Two classes on one table diverge in three ways that all reach the user:
different columns selected, different defaults on write, and different
to_dict() shapes feeding different screens. `architecture_decisions` currently
carries two ArchitectureDecision classes in two files -- exactly the shape that
produces two screens disagreeing about one record.

This is a RATCHET, and the baseline is honest debt rather than a target. Paying
it down means choosing a canonical class per table and repointing callers, which
is a migration, not a lint fix. What the gate buys is that the number cannot
grow while that work is outstanding -- which a paragraph in a document does not.

Escape hatch: `canonical-store-ok: <reason>` on the __tablename__ line, for a
deliberate read-model projection over a shared table. Say why the second class
cannot diverge from the first.

    python scripts/check_canonical_store.py
    python scripts/check_canonical_store.py --count

Proven-against: a second `__tablename__ = "risks"` class added to
app/models/risk.py -- red at 11 naming both classes, green at 10 when removed.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"canonical-store-ok:[ \t]*\S")


def _mapped_tables(root: str) -> dict:
    """{table name: [(relpath, class name, lineno), ...]} across app/models."""
    tables = defaultdict(list)
    base = os.path.join(root, "app", "models")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            lines = source.split("\n")
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                for node in cls.body:
                    if not isinstance(node, ast.Assign):
                        continue
                    target = node.targets[0]
                    if getattr(target, "id", "") != "__tablename__":
                        continue
                    if not isinstance(node.value, ast.Constant):
                        continue
                    line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if ALLOW.search(line):
                        continue
                    tables[node.value.value].append((rel, cls.name, node.lineno))
    return tables


def scan(root: str) -> list[str]:
    problems = []
    for table, mappings in sorted(_mapped_tables(root).items()):
        if len(mappings) < 2:
            continue
        where = ", ".join("%s.%s" % (rel.split("/")[-1], name)
                          for rel, name, _ in mappings)
        problems.append(
            "%s:%d [canonical-store] table %r is mapped by %d model classes "
            "(%s) -- they can select different columns, apply different defaults "
            "and feed different screens the same record"
            % (mappings[0][0], mappings[0][2], table, len(mappings), where)
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
                "Choose one canonical class per table and repoint its callers, or\n"
                "append 'canonical-store-ok: <reason>' to the __tablename__ line\n"
                "explaining why the second mapping cannot diverge from the first."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
