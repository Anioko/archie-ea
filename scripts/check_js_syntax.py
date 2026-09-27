#!/usr/bin/env python
"""Parse every shipped JS file in a real JavaScript engine.

Why this exists: on 26 Aug 2026 a bulk refactor left
``app/static/js/capability_map/index_inline.js`` with ``await`` in a
non-async function and an orphaned ``.then()`` tail. The file was a hard
SyntaxError, so the ENTIRE script never executed and the capability map lost
every handler it defines. Every static gate passed -- ruff does not read JS,
and the grep-based gates only match patterns, they do not parse. The only
thing that caught it was a browser console assertion in one smoke test, and
only because that page happened to be covered.

A syntax error in a shipped script is not a style issue: the browser discards
the whole file, so one bad character silently removes every function in it.
This parses each file with the same engine the user runs.

Uses Chromium via Playwright (already a test dependency) and compiles each
file with ``new Function(source)``, which raises on a parse error without
executing anything.

Usage:
    python scripts/check_js_syntax.py            # list failures
    python scripts/check_js_syntax.py --count    # count only
"""

from __future__ import annotations

import argparse
import glob
import json
import sys

BACKSLASH = chr(92)
EXCLUDED_DIRS = ("/vendor/", "/node_modules/")


def shipped_files() -> list[str]:
    found = []
    for path in glob.glob("app/static/js/**/*.js", recursive=True):
        norm = path.replace(BACKSLASH, "/")
        if any(part in norm for part in EXCLUDED_DIRS):
            continue
        found.append(path)
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed; cannot parse JS", file=sys.stderr)
        return 2

    paths = shipped_files()
    failures: list[tuple[str, str]] = []

    with sync_playwright() as engine:
        browser = engine.chromium.launch()
        page = browser.new_page()
        for path in paths:
            with open(path, encoding="utf-8", errors="replace") as handle:
                source = handle.read()
            # new Function parses without running. A module-level `return` is
            # legal inside a function body, so wrap nothing else around it.
            result = page.evaluate(
                """(src) => {
                    try { new Function(src); return null; }
                    catch (e) { return String(e && e.message ? e.message : e); }
                }""",
                source,
            )
            if result:
                failures.append((path.replace(BACKSLASH, "/"), result))
        browser.close()

    if args.count:
        print(len(failures))
        return 0 if not failures else 1

    for path, message in failures:
        print(f"{path}: {message}")
    print(f"\n{len(failures)} file(s) with JavaScript syntax errors "
          f"out of {len(paths)} parsed")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
