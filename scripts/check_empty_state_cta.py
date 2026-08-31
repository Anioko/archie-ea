#!/usr/bin/env python
"""An empty state with no way forward is a dead end wearing a friendly icon.

The product-architect question this gate asks is not "does the page render?"
-- every gate in this repository already answers that -- but "can the person
looking at this screen do the thing they came to do?" A new tenant sees empty
states on almost every surface before they see anything else. That first hour
IS the product, and 21 of the 40 empty states measured on 31 Aug 2026 ended the
user's journey rather than continuing it:

    applications/list_simple.html  empty_state(icon='layout-grid',
                                               title='No applications found.')

There is no argument that the user should be told "no applications found" and
left there. The whole point of the screen is to get applications into it.

The macro already supports the fix in both its variants -- `cta_text` +
`cta_href`/`cta_onclick` in components/empty_state.html, `cta_label` +
`cta_href` in macros/page_shell.html -- so this is a call-site omission, not a
missing capability. (That there are TWO empty_state macros is its own instance
of the canonical-store problem, one layer up; see check_canonical_store.py.)

Not every empty state needs a CTA, and the gate does not pretend otherwise. A
filtered result set whose way forward is "clear the filter" and a permission-
scoped surface where the user genuinely cannot act are both legitimate. Those
take the escape hatch and say so, which makes the judgement reviewable instead
of invisible.

A RATCHET at the measured 21. Writing 21 pieces of product copy, each naming
the right next action and the right endpoint, is a product decision per screen
rather than a mechanical edit -- but the number must not grow while that work
is outstanding, which no document was doing.

Detection: a call to the `empty_state` macro whose argument list contains
neither `cta_text` nor `cta_label`. Macro DEFINITIONS are skipped.

Escape hatch: `empty-state-ok: <reason>` inside the call or on the line above.

    python scripts/check_empty_state_cta.py
    python scripts/check_empty_state_cta.py --count

Proven-against: the `cta_label`/`cta_href` pair removed from the ARB queue's
empty state -- the count rises by one naming that call site, and returns when
restored. Pinned red-and-green on a synthetic tree by
tests/test_gates_actually_fail.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"empty-state-ok:[ \t]*\S")
CALL = re.compile(r"empty_state\s*\(")
CTA = ("cta_text", "cta_label")


def _argument_list(source: str, start: int) -> str:
    """The text of the call beginning at `start`, paren-balanced."""
    index = source.index("(", start) + 1
    depth = 1
    while index < len(source) and depth:
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
        index += 1
    return source[start:index]


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

            for match in CALL.finditer(source):
                before = source[:match.start()].rstrip()
                if before.endswith("macro"):
                    continue  # the definition, not a use
                segment = _argument_list(source, match.start())
                if any(name in segment for name in CTA):
                    continue
                line_no = source.count("\n", 0, match.start()) + 1
                lines = source.split("\n")
                context = "\n".join(lines[max(0, line_no - 2):line_no])
                if ALLOW.search(segment) or ALLOW.search(context):
                    continue
                title = re.search(r"title\s*=\s*'([^']*)'", segment)
                headline = title.group(1) if title else "(untitled)"
                problems.append(
                    "%s:%d [empty-state-cta] %r offers the user no next action "
                    "-- the screen tells them there is nothing here and stops"
                    % (rel, line_no, headline[:60])
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
                "Give the empty state the action the screen exists for --\n"
                "cta_text + cta_href (components/empty_state.html) or\n"
                "cta_label + cta_href (macros/page_shell.html). If the user\n"
                "genuinely cannot act here, append 'empty-state-ok: <reason>'."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
