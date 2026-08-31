#!/usr/bin/env python
"""A capability that is not an ArchiMate element is a row in a table, not a model.

The business architect's question, per CLAUDE.md's role list: "which capability
or value stream does this serve, and is it modelled as an ArchiMate element
rather than a textarea?"

check_archimate_backbone.py answers that for the MOTIVATION layer -- Driver,
Goal, Requirement, Risk, Plateau, WorkPackage. It says nothing about the
BUSINESS layer, which is the layer the business architect actually owns:
BusinessCapability, ValueStream, BusinessProcess, BusinessFunction,
BusinessActor, BusinessService.

That gap mattered because capability modelling is the product's headline
feature. A BusinessCapability created without a matching ArchiMateElement is
invisible to the capability lenses, to traceability, and to every cross-layer
view that walks the model rather than the table -- which is exactly the shape of
"/capability-map/ shows Total Capabilities 191 above a table reading Showing
1-10 of 0 results" from the 30 Aug 2026 QA audit. One store answers from the
domain table, another from the ArchiMate model, and they disagree.

Measured 31 Aug 2026: 18 creation paths, including the capability seeder and the
vendor-capability linker.

A ratchet. Some of these are bulk seeders where syncing row-by-row is the wrong
shape and a batch sync belongs instead, so this is scheduled work rather than a
one-line fix -- but the number must not grow while it is outstanding.

Detection: a function that constructs a business-layer model AND calls
db.session.add, but whose body never mentions sync_archimate_element. Model
modules are excluded (they declare the classes, they do not create rows).

Escape hatch: `business-backbone-ok: <reason>` in the function, for a path that
deliberately creates a detached row -- an import staging buffer, a dry run.

    python scripts/check_business_layer_backbone.py
    python scripts/check_business_layer_backbone.py --count

Proven-against: the sync_archimate_element call removed from a
BusinessCapability creation path -- the count rises by one naming that function,
and returns when restored. Pinned red-and-green on a synthetic tree by
tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"business-backbone-ok:[ \t]*\S")
SYNC = "sync_archimate_element"

# The ArchiMate 3.2 business layer, as modelled in this codebase.
BUSINESS = {
    "BusinessCapability", "ValueStream", "BusinessProcess",
    "BusinessFunction", "BusinessActor", "BusinessService",
}

EXCLUDED = ("/models/", "archimate_backbone_audit")


def scan(root: str) -> list:
    problems = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if any(marker in rel for marker in EXCLUDED):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = ast.get_source_segment(source, func) or ""
                if "db.session.add" not in body or SYNC in body:
                    continue
                if ALLOW.search(body):
                    continue
                created = sorted({
                    node.func.id
                    for node in ast.walk(func)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in BUSINESS
                })
                if not created:
                    continue
                problems.append(
                    "%s:%d [business-layer-backbone] %s() creates %s and never "
                    "calls %s -- the capability lenses read the model, so this "
                    "row is invisible to them"
                    % (rel, func.lineno, func.name, ", ".join(created), SYNC)
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
                "Call sync_archimate_element() after the create so the business\n"
                "layer is in the model, or append 'business-backbone-ok: <reason>'\n"
                "if the row is deliberately detached (an import buffer, a dry run)."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
