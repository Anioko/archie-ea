#!/usr/bin/env python
r"""A number in prose that nobody re-measures becomes a lie by inertia.

3 Sep 2026: CLAUDE.md's "Verification" section said `design_tokens` and
`raw_sql_tenancy` carried 88 and 98 units of ratchet debt (both actually
measured 0) and documented "All 19 gates" against the 44 actually registered
in build_gates(). Neither number had been wrong on the day it was written --
the codebase moved and the sentence did not follow. The same audit found
docs/DELIVERY_CONTRACT.md's role-to-gate table claiming 67 registered gates
and per-role counts derived from gate tags that no longer exist on any real
gate (12 of 15 roles actually measured 0, not the 1-8 claimed).

This checker re-derives the two claims that CLAUDE.md's own gate table and
docs/DELIVERY_CONTRACT.md's own role table make about `verify.py`, and fails
when prose and code disagree:

1. CLAUDE.md's "All N gates ... (`scripts/verify.py`, `build_gates`)" line,
   and the number of `| \`gate-name\` |` rows in the table under it, must
   both equal len(build_gates()).
2. Each role row in docs/DELIVERY_CONTRACT.md's table
   ("| Role | Gate tags | Gates |") must equal the count of distinct gates
   in build_gates() whose tags intersect that row's declared tags -- the
   same computation scripts/check_role_gate_coverage.py already does for the
   zero/nonzero question; this checker holds the row to its own stated
   number, not just to being nonzero.

Both are read with `ast`/regex rather than importing verify.py, matching
check_role_gate_coverage.py's reasoning: a checker has no business booting
the machinery it is auditing.

This is a zero-tolerance check, not a ratchet: a doc either matches the code
it describes or it does not, and there is no "acceptable current debt" for a
false statement once the debt has been named and corrected once (3 Sep 2026).

Escape hatch: `docs-drift-ok: <reason>` on the same line as the disagreeing
number, for a number that is deliberately a snapshot dated in the surrounding
prose rather than a live claim.

    python scripts/check_docs_drift.py
    python scripts/check_docs_drift.py --count
    python scripts/check_docs_drift.py --root /path/to/tree

Proven-against: the gate table heading in a scratch copy of CLAUDE.md edited
from "All 44 gates" to "All 19 gates" with the table itself left at 44 rows --
red, naming the 19-vs-44 mismatch; green again once reverted.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"docs-drift-ok:[ \t]*\S")

GATE_TABLE_ROW = re.compile(r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|")
GATE_COUNT_CLAIM = re.compile(r"All (\d+) gates")
TAG = re.compile(r"`([a-z0-9][a-z0-9-]*)`")


def gate_names_and_tags(root: str) -> tuple[list[str], dict[str, set[str]]]:
    """([gate names in build_gates order], {gate name: tags}) from verify.py."""
    path = os.path.join(root, "scripts", "verify.py")
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return [], {}
    names: list[str] = []
    tags_by_name: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "build_gates"):
            continue
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and call.args):
                continue
            first = call.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            name = first.value
            gate_tags: set[str] = set()
            for kw in call.keywords:
                if kw.arg == "tags" and isinstance(kw.value, ast.List):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            gate_tags.add(elt.value)
            # Only Gate(...) calls have a name that is also a real gate id; a
            # bare string constant elsewhere in the function is not a gate.
            # Every Gate() in this codebase's build_gates is called with the
            # gate name as its first positional argument, so require the
            # enclosing call's func name to be "Gate" specifically.
            func = call.func
            func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if func_name != "Gate":
                continue
            names.append(name)
            tags_by_name[name] = gate_tags
    return names, tags_by_name


def _read(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().split("\n")
    except (OSError, UnicodeDecodeError):
        return []


def check_claude_md(root: str, gate_names: list[str]) -> list[str]:
    problems = []
    lines = _read(os.path.join(root, "CLAUDE.md"))
    actual = len(gate_names)

    claim_lineno = None
    claimed = None
    for lineno, line in enumerate(lines, 1):
        match = GATE_COUNT_CLAIM.search(line)
        if match:
            claim_lineno = lineno
            claimed = int(match.group(1))
            break
    if claimed is not None and claimed != actual and not ALLOW.search(lines[claim_lineno - 1]):
        problems.append(
            "CLAUDE.md:%d [docs-drift] says 'All %d gates' but build_gates() "
            "registers %d" % (claim_lineno, claimed, actual)
        )

    # Scope the table scan to the section starting at the "All N gates" claim
    # and ending at the next markdown heading (`## ...` or `### ...`) -- this
    # file has a second, unrelated `| \`name\` |`-shaped table further down
    # ("CI enforces more than verify.py can", CI job names, not gate names),
    # and a bare pattern match across the whole file conflates the two.
    if claim_lineno is None:
        table_lines: list[str] = []
    else:
        table_lines = []
        for line in lines[claim_lineno:]:
            if line.startswith("#"):
                break
            table_lines.append(line)
    table_gate_names = [
        GATE_TABLE_ROW.match(line).group(1)
        for line in table_lines
        if GATE_TABLE_ROW.match(line)
    ]
    if len(table_gate_names) != actual:
        problems.append(
            "CLAUDE.md [docs-drift] gate table lists %d gates but build_gates() "
            "registers %d" % (len(table_gate_names), actual)
        )
    missing = set(gate_names) - set(table_gate_names)
    extra = set(table_gate_names) - set(gate_names)
    if missing:
        problems.append(
            "CLAUDE.md [docs-drift] gate table is missing registered gate(s): %s"
            % ", ".join(sorted(missing))
        )
    if extra:
        problems.append(
            "CLAUDE.md [docs-drift] gate table lists gate(s) not in build_gates(): %s"
            % ", ".join(sorted(extra))
        )
    return problems


def check_delivery_contract(root: str, tags_by_name: dict[str, set[str]]) -> list[str]:
    problems = []
    lines = _read(os.path.join(root, "docs", "DELIVERY_CONTRACT.md"))
    for lineno, line in enumerate(lines, 1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not line.strip().startswith("|"):
            continue
        role = cells[0].strip("* ")
        if not role or role.lower() == "role" or set(role) <= set("-: "):
            continue
        if ALLOW.search(line):
            continue
        wanted_tags = set(TAG.findall(cells[1]))
        try:
            claimed = int(cells[2])
        except ValueError:
            continue
        actual = sum(1 for gate_tags in tags_by_name.values() if gate_tags & wanted_tags)
        if actual != claimed:
            problems.append(
                "docs/DELIVERY_CONTRACT.md:%d [docs-drift] role %r claims %d "
                "gate(s) but tags %s currently resolve to %d in build_gates()"
                % (lineno, role, claimed, sorted(wanted_tags), actual)
            )
    return problems


def scan(root: str) -> list[str]:
    gate_names, tags_by_name = gate_names_and_tags(root)
    if not gate_names:
        return ["[docs-drift] could not parse scripts/verify.py's build_gates() -- refusing to compare against an empty registry"]
    return check_claude_md(root, gate_names) + check_delivery_contract(root, tags_by_name)


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
                "Update the doc's number to match verify.py's build_gates(), or\n"
                "mark the line 'docs-drift-ok: <reason>' if the number is a\n"
                "deliberately dated snapshot rather than a live claim."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
