#!/usr/bin/env python
"""A governance state nobody can see is where the workflow stops.

The service designer's question, per CLAUDE.md: does the work reach the next
actor. Every other role owns one persona's screen. This one owns the seam
between two personas -- and Archie is a governance workflow product, so the
seam IS the product. The 30 Aug 2026 QA audit put it as "the governance chain
is untraversable", and it is still open.

The concrete shape: a route writes a handoff state onto a record -- a state
whose whole meaning is "somebody else must now act on this" -- and no surface
any persona can reach from their sidebar ever reads that value back. The
solution architect presses submit, the record moves, and the ARB's queue does
not list it. Nothing 500s, nothing is logged. The submitter believes it was
sent and the reviewer never sees it, which is the most expensive failure this
product can have, because both parties are confident.

Measured shape, deliberately narrow:

  * WRITE -- ``<obj>.<status attr> = "<value>"`` in a module under app/ that
    defines a Blueprint, where the value is one of HANDOFF_STATES: a fixed
    vocabulary of states that hand work to another actor (submitted,
    under_review, pending_approval, escalated ...). Terminal outcomes
    (approved, rejected, cancelled, withdrawn) end the chain, nothing is
    waiting on them, and they are not counted.
  * READ -- the same value as a whole token anywhere else: in any module
    defining a blueprint that some persona's sidebar links into
    (app/utils/role_access.py, the same _link(...) lists the nav gates read),
    or in ANY Jinja template. Templates are not blueprint-attributed, so one
    mention anywhere under app/templates/ counts as reachable. Read detection
    is deliberately generous, so a finding is hard to produce.

A finding is a handoff state with writers and no reachable reader.

Real measurement, 31 Aug 2026: **0**, and that number was measured, not
assumed. Five handoff states are written across app/ -- arb_submitted,
deferred, in_review, proposed, under_review -- and every one of them is read
back by at least one sidebar-reachable blueprint and named in at least one
template. This is therefore a MUST-STAY-CLEAN gate at 0, not a ratchet
carrying debt: today the chain is continuous by this measure, and the gate
exists so the next state added cannot be written into a void.

The near-miss is worth recording, because it is what this gate would catch one
edit earlier. ``governance_status = "arb_submitted"`` is written by
architecture_assistant_routes.py; the code that reads it back is
arb_workflow_routes.py -- an API blueprint in no persona's sidebar -- plus
solution_design, which IS reachable, and a rationalization template. So the
value survives this gate on solution_design alone. The ``arb`` UI blueprint,
which owns the ARB dashboard and the reviews queue a board member actually
opens, never mentions the value at all. That is a real hole in the governance
chain, but it is a hole in WHICH surface reads the state, not in whether any
reachable one does -- and the second is the only half a static reader can
decide without guessing. Saying so here is the point: an honest 0 that names
what it cannot see is worth more than a fabricated 1.

What this does NOT measure, and why: whether a reachable surface's query would
actually return the row (a filter can read the value and still exclude it), and
whether the persona holding that sidebar has permission to act. Both need
runtime, and a static guess at either produces false positives -- which, per
docs/DELIVERY_CONTRACT.md, is worse than no gate.

Escape hatch: `handoff-ok: <reason>` on the assignment line, for a state that
is genuinely internal and hands work to nobody.

    python scripts/check_handoff_continuity.py
    python scripts/check_handoff_continuity.py --count
    python scripts/check_handoff_continuity.py --root /path/to/tree

Proven-against: a synthetic tree whose only writer sets "pending_approval" with
no reader anywhere -- red at 1 naming the state as unseen, green at 0 once a
sidebar-linked blueprint reads the value back. Pinned red-and-green on every
run by tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"handoff-ok:[ \t]*\S")
LINK = re.compile(r'_link\(\s*"[^"]+"\s*,\s*"([^"]+)"')
BLUEPRINT = re.compile(r"""\w+\s*=\s*Blueprint\(\s*["']([^"']+)["']""")
STATUS_ATTR = (
    r"(?:status|state|governance_status|workflow_state|approval_status"
    r"|review_status|stage)"
)
WRITE = re.compile(r"""\.%s\s*=\s*["']([a-z][a-z0-9_]*)["']""" % STATUS_ATTR)
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# States whose meaning is "another actor must now act".
HANDOFF_STATES = frozenset({
    "submitted",
    "arb_submitted",
    "pending_review",
    "pending_approval",
    "awaiting_approval",
    "awaiting_review",
    "under_review",
    "in_review",
    "for_review",
    "escalated",
    "needs_revision",
    "returned",
    "conditionally_approved",
    "proposed",
    "endorsed",
    "assigned",
    "deferred",
})


def _python_files(root: str):
    base = os.path.join(root, "app")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


def reachable_blueprints(root: str) -> set:
    """Blueprint names some persona's sidebar links into."""
    path = os.path.join(root, "app", "utils", "role_access.py")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return set()
    return {e.split(".")[0] for e in LINK.findall(source) if "." in e}


def _template_tokens(root: str) -> set:
    """Every whole-word token appearing in any Jinja template."""
    tokens = set()
    base = os.path.join(root, "app", "templates")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if not filename.endswith((".html", ".jinja", ".j2")):
                continue
            try:
                with open(os.path.join(dirpath, filename), encoding="utf-8",
                          errors="replace") as fh:
                    tokens.update(TOKEN.findall(fh.read()))
            except OSError:
                continue
    return tokens


def scan(root: str) -> list:
    reachable = reachable_blueprints(root)
    template_tokens = _template_tokens(root)

    writes = {}
    readers = {}
    for path in _python_files(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            continue
        owners = set(BLUEPRINT.findall(source))
        if not owners:
            continue
        lines = source.split("\n")
        written_here = {}
        for match in WRITE.finditer(source):
            value = match.group(1)
            written_here[value] = written_here.get(value, 0) + 1
            if value not in HANDOFF_STATES:
                continue
            lineno = source[: match.start()].count("\n") + 1
            if ALLOW.search(lines[lineno - 1]):
                continue
            writes.setdefault(value, []).append((rel, lineno))
        # Any whole-token mention beyond the assignments themselves is a read.
        for value in HANDOFF_STATES:
            mentions = len(re.findall(r"\b%s\b" % re.escape(value), source))
            if mentions > written_here.get(value, 0):
                readers.setdefault(value, set()).update(owners)

    problems = []
    for value in sorted(writes):
        if readers.get(value, set()) & reachable:
            continue
        if value in template_tokens:
            continue
        rel, lineno = writes[value][0]
        elsewhere = sorted(readers.get(value, set()) - reachable)
        where = ("read only by the unreachable blueprint(s) %s" % ", ".join(elsewhere)
                 if elsewhere else "nothing reads it at all")
        problems.append(
            "%s:%d [handoff-continuity] work is moved to the handoff state %r by "
            "%d write(s), and no surface any persona can reach from their sidebar "
            "reads that value back (%s) -- the sender believes the work was handed "
            "on and the next actor never sees it"
            % (rel, lineno, value, len(writes[value]), where)
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
                "Surface the state on a screen a persona can navigate to -- a\n"
                "queue, a filter, a badge -- or append 'handoff-ok: <reason>' to\n"
                "the assignment saying who the work is handed to instead."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
