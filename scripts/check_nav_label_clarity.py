#!/usr/bin/env python
"""The same word in two places in one menu is two things with one name.

The content designer's question, per CLAUDE.md: "what are these words, and do
they fit the space they are given?"

Added 31 Aug 2026 alongside the two other UI-role gates. This one currently
measures ZERO, and that is the point: it is a must-stay-clean gate rather than
debt. Nav labelling in role_access.py is right today -- 63 distinct labels, none
naming two destinations, none long enough to truncate at 16rem -- and the
cheapest way to keep it that way is to measure it rather than to trust it. The
sibling gates were both written from a real defect; this one is written from
the absence of one, so that the absence is enforced instead of assumed.

Two defects, either of which makes a menu unusable without changing any code
path:

1. One label naming two different endpoints. The user picks one, gets the other
   half the time, and has nothing to tell them apart.
2. A label too long for the rail. At 16rem, minus the icon, gap and padding,
   roughly 26 characters survive; past that the label truncates to an ellipsis
   and stops naming its destination. That is how "All modules" became
   "All mo..." in the collapsed sidebar -- the same failure one state earlier.

Escape hatch: `nav-label-ok: <reason>` on the line.

    python scripts/check_nav_label_clarity.py
    python scripts/check_nav_label_clarity.py --count

Proven-against: a second link labelled "Applications" pointing at a different
endpoint -- the count rises naming both destinations, and returns to zero when
removed. Pinned red-and-green on a synthetic tree by
tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"nav-label-ok:[ \t]*\S")
LINK = re.compile(r'_link\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"')

# 16rem rail, less icon, gap and padding, at text-sm. Past this the label
# truncates and the entry stops saying what it is.
MAX_LABEL = 26


def scan(root: str) -> list:
    path = os.path.join(root, "app", "utils", "role_access.py")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    lines = source.split("\n")

    problems = []
    by_label = collections.defaultdict(set)
    for match in LINK.finditer(source):
        label, endpoint, _icon = match.groups()
        line_no = source.count("\n", 0, match.start())
        if line_no < len(lines) and ALLOW.search(lines[line_no]):
            continue
        by_label[label].add(endpoint)
        if len(label) > MAX_LABEL:
            problems.append(
                "app/utils/role_access.py:%d [nav-label-clarity] %r is %d "
                "characters and truncates at %d -- the entry stops naming its "
                "destination" % (line_no + 1, label, len(label), MAX_LABEL)
            )

    for label, endpoints in sorted(by_label.items()):
        if len(endpoints) > 1:
            problems.append(
                "app/utils/role_access.py [nav-label-clarity] %r names %d "
                "different destinations (%s) -- the user cannot tell which one "
                "they are picking"
                % (label, len(endpoints), ", ".join(sorted(endpoints)))
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
                "Give each destination its own name and keep it under %d\n"
                "characters, or append 'nav-label-ok: <reason>'." % MAX_LABEL
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
