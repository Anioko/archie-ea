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


def _auto_synced_models(root: str) -> set:
    """Models whose rows get an ArchiMateElement without anyone asking.

    Five of the six business-layer types create their element in a SQLAlchemy
    ``before_insert``/``after_insert`` mapper event -- see
    app/models/business_capabilities.py:572. That fires on exactly the ORM path
    this gate inspects, so the invariant IS held; it is simply held by a
    mechanism the first version of this checker could not see. It reported 18
    findings and every one was a false positive, while the remedy it prescribed
    was a no-op: ELEMENT_TYPES in app/services/archimate_backbone.py contains no
    business-layer type, so sync_archimate_element() returns None for all six.

    Scoping a gate to a MECHANISM rather than to the CONDITION is the recurring
    flaw in this estate; this function is the correction.
    """
    synced = set()
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app", "models")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            try:
                with open(os.path.join(dirpath, filename), encoding="utf-8") as fh:
                    source = fh.read()
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = ast.get_source_segment(source, func) or ""
                if "ArchiMateElement" not in body:
                    continue
                for deco in func.decorator_list:
                    if not isinstance(deco, ast.Call):
                        continue
                    fn = deco.func
                    target = getattr(fn, "attr", None) or getattr(fn, "id", "")
                    if target != "listens_for" or not deco.args:
                        continue
                    event_name = ""
                    if len(deco.args) > 1 and isinstance(deco.args[1], ast.Constant):
                        event_name = str(deco.args[1].value)
                    if not event_name.endswith("_insert"):
                        continue
                    arg0 = deco.args[0]
                    model = getattr(arg0, "id", None) or getattr(arg0, "attr", "")
                    if model:
                        synced.add(model)
    return synced


def scan(root: str) -> list:
    problems = []
    auto_synced = _auto_synced_models(root)
    # ast.walk visits nested defs too, and the outer function's source segment
    # contains the inner one -- so both matched and the same path was counted
    # twice. Track spans and keep only the outermost.
    spans = []
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
                if all(name in auto_synced for name in created):
                    continue
                end = getattr(func, "end_lineno", func.lineno) or func.lineno
                if any(f == rel and lo <= func.lineno and end <= hi
                       for (f, lo, hi) in spans):
                    continue
                spans.append((rel, func.lineno, end))
                problems.append(
                    "%s:%d [business-layer-backbone] %s() creates %s, which has "
                    "no insert listener, so the row reaches the database with no "
                    "ArchiMateElement and the capability lenses cannot see it"
                    % (rel, func.lineno, func.name, ", ".join(created))
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
                "Give the model a before_insert listener that creates its\n"
                "ArchiMateElement, the way the other 61 models do -- see\n"
                "app/models/business_capabilities.py:572. Calling\n"
                "sync_archimate_element() will NOT work here: ELEMENT_TYPES in\n"
                "app/services/archimate_backbone.py carries no business-layer\n"
                "type, so it returns None. Or append 'business-backbone-ok:\n"
                "<reason>' if the row is deliberately detached."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
