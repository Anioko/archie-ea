#!/usr/bin/env python
"""A row you cannot act on is a report, and this product is not a report.

Found 31 Aug 2026 by the owner, on /archimate-roadmap:

    Name              Type       Severity   Status
    QA Test Gap       coverage   Medium     Identified
    QA Test Gap 2     coverage   Medium     Identified
    QA Recheck Gap A  coverage   Medium     Identified

Three gaps, correctly stored, correctly rendered -- and nothing a human can do
with any of them. No link to the gap, no button to plan it, no route to the work
package it should become. The row names a record and then stops.

Which roles this belongs to, and why no existing gate caught it:

* the INTERACTION ARCHITECT owns whether a rendered control can be operated,
  and a row with no control is the same dead end as an icon with no label;
* the SERVICE DESIGNER owns the handoff -- a gap moves to "Identified" and is
  then handed to nobody, which is a queue no one can open;
* the PRODUCT ARCHITECT owns whether the persona can finish the job, and seeing
  the work is not doing it.

check_handoff_continuity.py measures workflow STATES and reads 0, honestly: the
state is written and read back. This is one level down -- the state is fine and
the ROW is inert. check_empty_state_cta.py covers the opposite case, a table
with nothing in it. Between them sat the case that actually shipped: a table
full of records that go nowhere.

Measured at 112 of 158 collection-iterating tables, which is 71% and is
certainly not all defect -- a status breakdown or a computed summary is
legitimately read-only. That is exactly why this is a RATCHET with a reason-
bearing escape hatch rather than a wall: the number must not grow while the real
ones are worked through, and each exemption has to say why the user has nothing
to do with the row.

Detection: a <tbody> containing a Jinja `{% for %}` over a collection, in which
no <a href>, <button>, <form> or click handler appears anywhere in the row
markup.

Deliberately NOT detected, and stated so the blind spot is a fact rather than an
impression: a table whose action lives outside the tbody (a bulk toolbar above
it), a row made clickable by JavaScript attaching to the <tr> at runtime, and
any table rendered entirely client-side from JSON. The first two are real
patterns in this codebase and will read as false negatives here.

Escape hatch: `actionable-rows-ok: <reason>` inside the tbody -- for a genuine
read-only summary. Say what the user is meant to do instead.

    python scripts/check_actionable_rows.py
    python scripts/check_actionable_rows.py --count

Proven-against: the detail link removed from a table row -- the count rises by
one naming that file and line, and returns when restored. Pinned red-and-green
on a synthetic tree by tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"actionable-rows-ok:[ \t]*\S")
TBODY = re.compile(r"<tbody\b.*?</tbody>", re.S | re.I)
LOOP = re.compile(r"{%-?\s*for\s+\w+\s+in\s+[\w.]+", re.I)

# Anything that gives the user somewhere to go or something to press.
ACTIONS = ("<a ", "href=", "<button", "<form", "@click", "x-on:click", "onclick")


def scan(root: str) -> list:
    problems = []
    base = os.path.join(root, "app", "templates")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".html"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            except (OSError, UnicodeDecodeError):
                continue

            for match in TBODY.finditer(source):
                body = match.group(0)
                if not LOOP.search(body):
                    continue  # a static tbody is not a record listing
                if any(marker in body for marker in ACTIONS):
                    continue
                if ALLOW.search(body):
                    continue
                line_no = source.count("\n", 0, match.start()) + 1
                problems.append(
                    "%s:%d [actionable-rows] a table of records with no link, "
                    "button or form in the row -- the user can see the work and "
                    "cannot act on it" % (rel, line_no)
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
                "Give the row the action it exists for -- a link to the record,\n"
                "or the control that moves it to its next state. If the table is\n"
                "genuinely a read-only summary, append\n"
                "'actionable-rows-ok: <reason>' saying what the user does instead."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
