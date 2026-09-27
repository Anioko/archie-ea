#!/usr/bin/env python
"""Two destinations behind one icon is a menu the user has to memorise.

The information architect's question, per CLAUDE.md: "where does this live in
the navigation, and is its icon and label distinguishable from its neighbours?"

Written 31 Aug 2026 from a screenshot. The owner sent the sidebar in its
COLLAPSED state -- 4rem wide, icons only -- and it showed several destinations
behind what looked like the same grid glyph, with labels clipped to "All mo..."
and "Bui...". Seventy gates were green at the time.

Across the whole product 98 sidebar links share 50 distinct icons, and
`layout-dashboard` alone serves eight destinations (ARB Dashboard, Command
Center, Dashboard Overview, My Applications, Portfolio and more). Reuse across
DIFFERENT personas is fine -- no user sees both -- so this gate deliberately
does not count it. What it counts is reuse WITHIN one persona's own sidebar,
where the two entries appear in the same list, one above the other, and the icon
is the only thing distinguishing them once the rail is collapsed.

Detection: within a single ROLE_* link list in app/utils/role_access.py, one
icon used for two different endpoints.

Escape hatch: `nav-icon-ok: <reason>` on the line, for a pair where the icon is
genuinely the right one for both and the labels carry the distinction.

    python scripts/check_nav_icon_ambiguity.py
    python scripts/check_nav_icon_ambiguity.py --count

Proven-against: a second `_link(..., "compass")` added to the enterprise
architect's list -- the count rises naming both entries, and returns when
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
ALLOW = re.compile(r"nav-icon-ok:[ \t]*\S")
LINK = re.compile(r'_link\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"')


def scan(root: str) -> list:
    path = os.path.join(root, "app", "utils", "role_access.py")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    problems = []
    blocks = re.split(r"\n\s{4}(ROLE_[A-Z_]+)\s*:", source)
    for index in range(1, len(blocks), 2):
        role = blocks[index]
        body = blocks[index + 1].split("\n    ROLE_")[0]
        seen = collections.defaultdict(list)
        for match in LINK.finditer(body):
            label, endpoint, icon = match.groups()
            line = body[: match.start()].count("\n")
            if ALLOW.search(body.split("\n")[line]):
                continue
            seen[icon].append((label, endpoint))
        for icon, entries in sorted(seen.items()):
            endpoints = {endpoint for _, endpoint in entries}
            if len(endpoints) < 2:
                continue
            labels = ", ".join(sorted(label for label, _ in entries))
            problems.append(
                "app/utils/role_access.py [nav-icon-ambiguity] %s shows %d "
                "destinations behind the icon %r (%s) -- collapsed, they are "
                "the same button" % (role, len(endpoints), icon, labels)
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
            print("Give each destination its own icon, or append "
                  "'nav-icon-ok: <reason>' to the link.")
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
