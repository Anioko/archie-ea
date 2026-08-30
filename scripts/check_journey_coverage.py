#!/usr/bin/env python
"""Every persona must have a journey test that proves they can do their job.

A wave once shipped with 47 green gates and a page the owner found broken on
sight. Every gate was telling the truth: the gates ask "does this break?", and
none of them ask "can a person achieve their goal?" A screen can return 200,
carry perfect labels, leak nothing and still be a workflow nobody can complete.

The smoke suite has "one journey per archetype", but those assert *a page was
reached*, which is the same conflation one level down:

    resp = client.get("/capability-analysis/unmapped")
    assert resp.status_code == 200        # passes while the feature is unusable

That exact page returned 200 for months while never querying the data it exists
to show -- the view's own name shadowed the query result, `len()` raised, and the
except branch rendered an empty "could not load" state to every user. A status
assertion could never have caught it. This one would:

    client.post("/capabilities/create", data={...})     # do the work
    assert db.session.scalar(select(Capability)...)     # it persisted
    page = client.get("/capability-analysis/unmapped")  # and it is visible
    assert NAME in page.get_data(as_text=True)          # where the user looks

So this gate requires, for each persona in `VALID_ROLES`, at least one test under
tests/journeys/ that names the persona AND performs a write AND asserts something
afterwards. It counts personas with no such test.

The persona list is read from app/models/user.py's VALID_ROLES rather than
hardcoded here, so adding a persona to the product automatically demands a
journey for it instead of silently passing.

Escape hatch: `journey-coverage-ok: <reason>` on a line in any journeys file,
naming the persona, for one that genuinely cannot act (a read-only role).

    python scripts/check_journey_coverage.py            # list uncovered personas
    python scripts/check_journey_coverage.py --count    # trailing line = count
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A write. A journey that only reads cannot show the user achieved anything.
WRITE = re.compile(r"\.(post|put|patch|delete)\s*\(", re.I)
ALLOW = re.compile(r"journey-coverage-ok:[ \t]*\S")
ROLE_LITERAL = "[\"']%s[\"']"


def _writing_helpers(tree, source):
    """Module-level helpers in this file whose body performs a write.

    A journey that factors its POST into a helper -- ``_create(client, name)``
    -- is still a journey that writes. Without this the gate silently demands
    the request be inlined, which is a style rule dressed up as a coverage rule
    and would be satisfied by copying the same call into four tests.
    """
    helpers = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("test"):
            continue
        body = ast.get_source_segment(source, node) or ""
        if WRITE.search(body):
            helpers.add(node.name)
    return helpers


def valid_roles(root: str) -> list[str]:
    """Read VALID_ROLES out of app/models/user.py without importing the app.

    Parsing beats importing here: the model module pulls in the whole ORM, and a
    gate that needs a database to tell you your tests are thin is a gate that
    gets skipped.
    """
    path = os.path.join(root, "app", "models", "user.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    constants: dict[str, str] = {}
    roles: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants[target.id] = node.value.value
        elif target.id == "VALID_ROLES" and isinstance(node.value, ast.List):
            for element in node.value.elts:
                if isinstance(element, ast.Name) and element.id in constants:
                    roles.append(constants[element.id])
                elif isinstance(element, ast.Constant):
                    roles.append(element.value)
    return roles


def covered_personas(root: str, roles: list[str]) -> tuple[set[str], set[str]]:
    """Personas with a real journey, and personas explicitly excused."""
    journeys = os.path.join(root, "tests", "journeys")
    covered: set[str] = set()
    excused: set[str] = set()
    if not os.path.isdir(journeys):
        return covered, excused

    for filename in sorted(os.listdir(journeys)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(journeys, filename)
        with open(path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        for line in source.split("\n"):
            if ALLOW.search(line):
                for role in re.findall(r"[a-z_]{4,}", line):
                    excused.add(role)

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        helpers = _writing_helpers(tree, source)

        # Per test function: does it name a persona, write, and then assert?
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            body = ast.get_source_segment(source, node) or ""
            calls_writing_helper = any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in helpers
                for n in ast.walk(node)
            )
            if not (WRITE.search(body) or calls_writing_helper):
                continue
            if not any(isinstance(n, ast.Assert) for n in ast.walk(node)):
                continue
            # Match the ROLE NAMES the product actually defines, not any quoted
            # lowercase word of four or more characters. The old pattern could
            # never match "cto" -- three characters -- so that persona was
            # permanently uncoverable: writing its journey moved the count by
            # zero and left the gate red with no way to satisfy it.
            for role in roles:
                if re.search(ROLE_LITERAL % re.escape(role), body):
                    covered.add(role)
    return covered, excused


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true", help="print only the count")
    parser.add_argument("--root", default=ROOT, help="tree to scan")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    roles = valid_roles(root)
    covered, excused = covered_personas(root, roles)

    missing = [r for r in roles if r not in covered and r not in excused]

    if not args.count:
        for role in missing:
            print(
                f"tests/journeys: [journey-coverage] persona {role!r} has no journey "
                f"test that writes something and asserts the result"
            )
        if missing:
            print()
            print(
                "A persona with no journey test is a persona nobody has proved can\n"
                "do their job. Add a test under tests/journeys/ that signs in as them,\n"
                "performs the write their role exists to perform, and asserts the result\n"
                "both persisted AND is visible on the page they would look at next.\n"
                "See docs/TESTING_STANDARD.md, Level 9. If a persona genuinely cannot\n"
                "act, append 'journey-coverage-ok: <reason>' naming it."
            )
    print(len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
