#!/usr/bin/env python
"""A checker script nobody registered is a control that does not exist.

F500-008 (3 Sep 2026 Fortune 500 qualification): six governance/AI-safety
scripts -- check_evidence_contract.py, check_role_gate_coverage.py, and the
four check_ai_*.py scripts -- existed, had their own unit tests, and were
described in CLAUDE.md and docs/DELIVERY_CONTRACT.md as actively enforcing
rules on every release. None were registered as a Gate(...) in verify.py's
build_gates(). None ever ran as part of `python scripts/verify.py`. The
prose was the only place they existed.

Re-scanning scripts/check_*.py against build_gates() while fixing that found
the real number was not six -- it was 34 more, including check_store_agreement.py,
which CLAUDE.md's "One system of record" section names by name as "Enforcement
... registered 31 Aug 2026". It was never wired in either. DEF-003's display
half (a mapped capability that persisted correctly but never appeared in the
UI, because the display read a different table than the write) is exactly the
class of bug that gate exists to catch, and it went undetected specifically
because the gate does not run.

A script under scripts/check_*.py is "registered" if its filename appears as
a string literal anywhere in scripts/verify.py -- that is how every existing
Gate(...) invokes its checker (`_run([sys.executable, "scripts/check_X.py", ...])`).
Wiring into a CI workflow instead of verify.py does not count: CLAUDE.md is
explicit that verify.py is the one command whose green means clean, so a
script `main` or `smoke` alone has still never gated a local run or a
pre-commit hook.

This is a RATCHET, baselined at the true current count rather than 0, for the
same reason CLAUDE.md gives for baselining store-agreement at 1 and not 0:
baselining an existing hole at 0 would make this checker immediately fail on
a codebase it has not changed, and the temptation to "fix" that by raising the
baseline back up defeats the checker's purpose before it has caught anything.
The number can only go down from here.

Escape hatch: `unregistered-check-ok: <reason>` as a comment on the first line
of the script, for a checker deliberately kept standalone (used only by a test
suite directly, say, never meant to gate a release).

    python scripts/check_unregistered_checks.py
    python scripts/check_unregistered_checks.py --count
    python scripts/check_unregistered_checks.py --root /path/to/tree

Proven-against: a new file scripts/check_zzz_probe.py (docstring only, no
escape-hatch comment) dropped into a scratch copy of the tree -- red at
baseline+1 naming it unregistered, green again at baseline once removed.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"unregistered-check-ok:[ \t]*\S")


def registered_scripts(root: str) -> set[str]:
    """Every check_*.py basename that appears as a string literal in verify.py."""
    path = os.path.join(root, "scripts", "verify.py")
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError):
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            base = os.path.basename(node.value)
            if base.startswith("check_") and base.endswith(".py"):
                names.add(base)
    return names


def _first_line(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.readline()
    except (OSError, UnicodeDecodeError):
        return ""


def scan(root: str) -> list[str]:
    scripts_dir = os.path.join(root, "scripts")
    try:
        candidates = sorted(
            f for f in os.listdir(scripts_dir)
            if f.startswith("check_") and f.endswith(".py")
        )
    except OSError:
        return []

    registered = registered_scripts(root)
    problems = []
    for base in candidates:
        if base in registered:
            continue
        if ALLOW.search(_first_line(os.path.join(scripts_dir, base))):
            continue
        problems.append(
            "scripts/%s [unregistered-check] never appears as a string literal "
            "in scripts/verify.py -- it has no Gate(...) entry, so it does not "
            "run as part of `python scripts/verify.py`, CI's static job, or "
            "pre-commit, regardless of what any doc says it enforces" % base
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
                "Register the checker as a Gate(...) in build_gates() with a\n"
                "Proven-against case (DELIVERY_CONTRACT.md Rule 2), or mark the\n"
                "first line of the script 'unregistered-check-ok: <reason>' if it\n"
                "is deliberately standalone."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
