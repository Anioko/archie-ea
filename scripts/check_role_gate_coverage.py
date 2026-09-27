#!/usr/bin/env python
"""A role with no gate is a role being claimed rather than played.

CLAUDE.md instructs every agent working this repository to act as "the CTO,
solution/software/technical architect, and delivery + QA lead at once". In
practice agents act as developers only: they implement what was asked and skip
every architectural role, because nothing measures whether those roles were
played. The owner is non-technical, so nobody downstream notices the omission.

docs/DELIVERY_CONTRACT.md answers that with the only durable definition of a
role this codebase has: a role IS its family of gates. "ML / AI architect | 0"
sat in that table while 154 `ai_chat` routes shipped unguarded -- and it was
right, which is why four `ai-*` gates now exist. The number was doing work the
prose was not.

The failure this gate catches is the table drifting back into decoration: a role
declared in DELIVERY_CONTRACT.md whose tags resolve to ZERO gates in the
verify.py registry. Such a role can be recited in a report, agreed to in a
session, and enforced by nothing -- which is indistinguishable, from the owner's
side, from the role being played.

Both halves are read mechanically: the roles from the table in
docs/DELIVERY_CONTRACT.md, the gates and their `tags=[...]` from `build_gates`
in scripts/verify.py, parsed with ast rather than imported (verify.py boots
machinery a checker has no business booting).

This is a RATCHET. The zeros in the table today are honest holes, not typos --
naming them is the point, and the number cannot grow while they are open.

Escape hatch: `role-gate-ok: <reason>` on the role's table row, for a role
deliberately carried with no machinery yet. Say what would gate it.

    python scripts/check_role_gate_coverage.py
    python scripts/check_role_gate_coverage.py --count
    python scripts/check_role_gate_coverage.py --root /path/to/tree

Proven-against: the `ai` tag removed from the "AI / ML architect" row of
docs/DELIVERY_CONTRACT.md -- red at 3 naming that role as ungated, green at 2
when restored.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"role-gate-ok:[ \t]*\S")
TAG = re.compile(r"`([a-z0-9][a-z0-9-]*)`")


def registry_tags(root: str) -> set[str]:
    """Every tag carried by a gate in verify.py's build_gates registry."""
    path = os.path.join(root, "scripts", "verify.py")
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    tags = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "build_gates"):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            for kw in call.keywords:
                if kw.arg != "tags" or not isinstance(kw.value, ast.List):
                    continue
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        tags.add(elt.value)
    return tags


def declared_roles(root: str) -> list[tuple[int, str, set[str]]]:
    """[(lineno, role, tags)] from the role table in DELIVERY_CONTRACT.md."""
    path = os.path.join(root, "docs", "DELIVERY_CONTRACT.md")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except (OSError, UnicodeDecodeError):
        return []
    roles = []
    for lineno, line in enumerate(lines, 1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.strip().startswith("|"):
            continue
        role = cells[0].strip("* ")
        if not role or role.lower() == "role" or set(role) <= set("-: "):
            continue
        if ALLOW.search(line):
            continue
        roles.append((lineno, role, set(TAG.findall(cells[1]))))
    return roles


def scan(root: str) -> list[str]:
    tags = registry_tags(root)
    problems = []
    for lineno, role, wanted in declared_roles(root):
        if wanted & tags:
            continue
        problems.append(
            "docs/DELIVERY_CONTRACT.md:%d [role-gate-coverage] role %r resolves to "
            "no gate in verify.py's registry (tags declared: %s) -- it can be "
            "recited in a report and enforced by nothing, which from the owner's "
            "side is indistinguishable from the role being played"
            % (lineno, role, ", ".join(sorted(wanted)) or "none")
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
                "Build a gate for the role and tag it, or append\n"
                "'role-gate-ok: <reason>' to that row of the table saying what\n"
                "would gate the role and why it is not being built now."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
