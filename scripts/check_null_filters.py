#!/usr/bin/env python
"""Find `|default(...)` chained into a filter that calls len() on its input.

Jinja's `default` replaces an **undefined** value, not a `None` one. Every
nullable database column arrives as `None`, which is defined, so it sails past
`default()` and straight into the next filter:

    {{ cap.description|default('No description')|truncate(100) }}

`truncate` calls `len()` on it, raising "object of type 'NoneType' has no
len()". The damage is not one blank field - it aborts the whole render. Found in
production on /enterprise/capability-map/capabilities, where the route's own
`except` then re-rendered the same template with an empty list, so the page
returned 200 with "Error loading capabilities" and no rows while the
capabilities existed in the database. A reader cannot tell that from an empty
portfolio.

The fix is the second, boolean argument, which makes `default` treat any falsy
value - including None - as absent:

    {{ cap.description|default('No description', true)|truncate(100) }}

Usage:
    python scripts/check_null_filters.py            # list offenders
    python scripts/check_null_filters.py --count    # trailing line is the count
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"

# Filters that call len() (or iterate) on their input and so raise on None.
LEN_FILTERS = (
    "truncate",
    "wordwrap",
    "length",
    "count",
    "first",
    "last",
    "sum",
    "join",
)

CHAIN = re.compile(
    r"\|\s*default\(([^()]*)\)\s*\|\s*(" + "|".join(LEN_FILTERS) + r")\b"
)

# `default(x, true)` / `default(x, boolean=True)` already handles None.
SAFE_ARG = re.compile(r",\s*(true|True|1)\s*$")


def offenders():
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in CHAIN.finditer(line):
                arg = match.group(1).strip()
                if SAFE_ARG.search(arg) or "boolean" in arg:
                    continue
                yield path.relative_to(ROOT), lineno, match.group(2), line.strip()


def main() -> int:
    count_only = "--count" in sys.argv
    found = list(offenders())
    if not count_only:
        for rel, lineno, filt, line in found:
            print(f"{rel}:{lineno}: default() feeds |{filt} without boolean=true")
            print(f"    {line[:160]}")
        if not found:
            print("no unsafe default() -> len-filter chains")
    if count_only:
        print(len(found))
    return 0 if count_only else (1 if found else 0)


if __name__ == "__main__":
    raise SystemExit(main())
