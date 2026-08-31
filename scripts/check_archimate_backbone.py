#!/usr/bin/env python
"""A motivation entity created without an ArchiMate element is invisible to the model.

CLAUDE.md states the rule as the product's spine, not a convention:

    "ArchiMate is the backbone, not a view. Every backend CREATE for a motivation
     entity (Driver, Goal, Constraint, Requirement, Risk, Metric, Plateau,
     WorkPackage) must call _sync_archimate_element() so a matching
     ArchiMateElement row exists ... A plain textarea is not an acceptable
     substitute -- the field IS the element."

app/services/archimate_backbone_audit.py already answers the RUNTIME half of
this: for a given organisation, which motivation rows have no element. Its own
docstring records why that mattered -- the sync swallows failures and returns
None, and no call site inspects the return, so a Driver could commit with no
element and "traceability, impact analysis, line of sight and every capability
lens would simply return a quieter answer than the truth".

This is the other half, and it is the one that runs before the rows exist: a
creation path that never calls the sync at all cannot produce a complete
backbone no matter how healthy the data looks today. The audit finds the
consequence; this finds the cause.

The measurement on 31 Aug 2026 was 53 such functions, including four of the AI
agent's own write tools -- _tool_create_driver, _tool_create_goal,
_tool_create_constraint and _tool_create_requirement. Every motivation entity
the assistant proposes and a human approves has been landing outside the
backbone, so the capability lenses that read from it have been answering with
less than the truth.

A ratchet, deliberately. Fixing 53 call sites is a wave of work with real
regression risk -- some of these paths batch-create dozens of rows and the sync
is not free. What the gate buys is that the number cannot grow while that work
is scheduled, which the paragraph in CLAUDE.md did not.

Detection: a function that constructs a motivation model AND calls
db.session.add, but whose body never mentions _sync_archimate_element. Model
modules are excluded (they define the classes, they do not create rows through a
route), as is the audit service itself.

Escape hatch: `backbone-ok: <reason>` in the function, for a path that
deliberately creates a detached row -- an import staging buffer, a dry run.

    python scripts/check_archimate_backbone.py
    python scripts/check_archimate_backbone.py --count

Proven-against: the `_sync_archimate_element` call removed from
strategic_service.py's driver creation -- the count rises by one naming that
function, and returns when restored.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"backbone-ok:[ \t]*\S")
# The canonical helper is app/services/archimate_backbone.sync_archimate_element.
# Matching without the leading underscore also matches the three legacy
# _sync_archimate_element implementations it replaced, so this accepts both
# rather than forcing a rename before a path can comply.
SYNC = "sync_archimate_element"

# The domain entities DESIGN.md maps onto ArchiMate motivation elements, plus the
# Solution* variants the journey layer writes.
MOTIVATION = {
    "Driver", "Goal", "Constraint", "Requirement", "Risk", "Metric",
    "Plateau", "WorkPackage",
    "SolutionDriver", "SolutionGoal", "SolutionConstraint",
    "SolutionRequirement", "SolutionRisk",
}

# Excluded, with reasons: model modules declare the classes rather than creating
# rows through a request path, and the audit service exists to READ the gap.
EXCLUDED = ("/models/", "archimate_backbone_audit")


def scan(root: str) -> list[str]:
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
                    and node.func.id in MOTIVATION
                })
                if not created:
                    continue
                problems.append(
                    "%s:%d [archimate-backbone] %s() creates %s and never calls "
                    "%s -- the row exists and the model does not know about it"
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
                "Call _sync_archimate_element() after the create so a matching\n"
                "ArchiMateElement exists, or append 'backbone-ok: <reason>' if the\n"
                "row is deliberately detached (an import buffer, a dry run)."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
