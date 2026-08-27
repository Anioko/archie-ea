#!/usr/bin/env python
"""Count console.* calls in shipped JS and templates.

CLAUDE.md: "No console.log in shipped templates/JS ... User-facing
notifications go through Platform.toast."

The rule is usually read as being about noise. It is not: a console.error is a
failure reported to NOBODY. The user sees a control that did nothing, or a panel
that stayed empty, and cannot tell a failure from an empty result -- the same
harm as fabricating data, arrived at from the other direction. Every one of
these is either a failure that needs surfacing through Platform.toast or an
inline error state, or a diagnostic that should not ship.

console.log is already at zero and stays there. This ratchet freezes the
remaining error/warn/debug/info calls so the number can only fall.

Excluded: vendored code, and js/bundles/* (a concatenation of js/core/*, so
counting both double-counts the same source). A line carrying a
``console-ok: <reason>`` marker is excluded and thereby made reviewable.

Usage:
    python scripts/check_console_reporting.py            # list occurrences
    python scripts/check_console_reporting.py --count    # count only
"""

from __future__ import annotations

import argparse
import glob
import re
import sys

BACKSLASH = chr(92)
CONSOLE = re.compile(r"console\.(?:error|warn|log|debug|info)\s*\(")
ALLOW = "console-ok:"
EXCLUDED_DIRS = ("/vendor/", "/js/bundles/", "/node_modules/")
PATTERNS = (
    "app/static/js/**/*.js",
    "app/templates/**/*.html",
    "app/templates/**/*.js",
)


def occurrences() -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in PATTERNS:
        for path in glob.glob(pattern, recursive=True):
            norm = path.replace(BACKSLASH, "/")
            if norm in seen or any(part in norm for part in EXCLUDED_DIRS):
                continue
            seen.add(norm)
            with open(path, encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    if ALLOW in line:
                        continue
                    if CONSOLE.search(line):
                        found.append(f"{norm}:{number}: {line.strip()[:110]}")
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args()

    found = occurrences()
    if args.count:
        print(len(found))
        return 0

    for item in found:
        print(item)
    print(f"\n{len(found)} console.* call(s) in shipped JS and templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
