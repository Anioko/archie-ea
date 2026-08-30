#!/usr/bin/env python
"""An action branch a validator in the same function already rejected.

The concrete defect (30 Aug 2026, portfolio_manager journey):
POST /applications/rationalization/api/bulk-review validated

    valid_actions = {"approve", "defer", "request_data"}
    if action not in valid_actions:
        return jsonify(...), 400

and then, further down the same function, implemented

    elif action == "set_disposition":
        score.disposition_action = disposition_value
        ...

Every request for "set_disposition" was rejected with 400 before reaching that
branch. It was the portfolio_manager persona's core action -- recording a 7R
disposition against a scored application -- and it was dead code that read, to
anyone opening the file, as a live feature. Nothing caught it: the module
compiles, ruff sees a reachable elif, no template references it, and the
endpoint returns a well-formed 400 rather than an error.

This is not a lint about style. A handler branch behind a whitelist that
excludes it is either a feature the product silently does not have, or a
whitelist missing an entry -- and both are defects, which is why the check is
worth a gate even at zero instances.

Detection is deliberately narrow, so a finding is a fact rather than a
suspicion. All four must hold inside ONE function:

  1. a name is bound to a literal collection of strings;
  2. some variable is compared `not in` that collection;
  3. the same variable is later compared `== "literal"`;
  4. that literal is not in the collection.

Escape hatch: `unreachable-action-ok: <reason>` on the branch line, for a
comparison that is genuinely unreachable on purpose (a deprecated value kept
to log an explicit rejection, say).

    python scripts/check_unreachable_actions.py            # list them
    python scripts/check_unreachable_actions.py --count    # trailing line = count

Proven-against: 'set_disposition' removed from valid_actions in
rationalization_bulk_review -- red at 2, naming both branch lines; green at 0
when restored.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"unreachable-action-ok:[ \t]*\S")


def _literal_string_collections(func: ast.AST) -> dict:
    """Names bound in *func* to a collection of string literals only."""
    found = {}
    for node in ast.walk(func):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            continue
        elements = node.value.elts
        values = {
            e.value for e in elements
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
        # Every element must be a string literal, or we do not know the set.
        if values and len(values) == len(elements):
            found[target.id] = values
    return found


def _guarded_variables(func: ast.AST, collections: dict) -> dict:
    """Variables compared `not in <a literal collection>` inside *func*."""
    guarded = {}
    for node in ast.walk(func):
        if not (isinstance(node, ast.Compare) and node.ops
                and isinstance(node.ops[0], ast.NotIn)):
            continue
        if not isinstance(node.left, ast.Name):
            continue
        right = node.comparators[0]
        if isinstance(right, ast.Name) and right.id in collections:
            guarded[node.left.id] = (right.id, collections[right.id])
    return guarded


def scan(root: str) -> list:
    findings = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            lines = source.split("\n")

            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                collections = _literal_string_collections(func)
                if not collections:
                    continue
                guarded = _guarded_variables(func, collections)
                if not guarded:
                    continue

                for node in ast.walk(func):
                    if not (isinstance(node, ast.Compare) and node.ops
                            and isinstance(node.ops[0], ast.Eq)
                            and isinstance(node.left, ast.Name)
                            and node.left.id in guarded):
                        continue
                    right = node.comparators[0]
                    if not (isinstance(right, ast.Constant)
                            and isinstance(right.value, str)):
                        continue
                    name, allowed = guarded[node.left.id]
                    if right.value in allowed:
                        continue
                    line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if ALLOW.search(line):
                        continue
                    findings.append(
                        (os.path.relpath(path, root).replace(os.sep, "/"),
                         node.lineno, func.name, node.left.id, right.value,
                         name, sorted(allowed))
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true", help="print only the count")
    parser.add_argument("--root", default=ROOT, help="tree to scan")
    args = parser.parse_args()

    findings = scan(os.path.abspath(args.root))
    if not args.count:
        for path, lineno, func, var, value, name, allowed in findings:
            print(
                "  %s:%d  [unreachable-action] %s(): `%s == %r` can never run -- "
                "%s rejects it first (allows %s)"
                % (path, lineno, func, var, value, name, allowed)
            )
        if findings:
            print()
            print(
                "Either the branch is a feature the product does not actually have\n"
                "(delete it), or the whitelist is missing an entry (add it). If the\n"
                "comparison is unreachable on purpose, append\n"
                "'unreachable-action-ok: <reason>' to that line."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
