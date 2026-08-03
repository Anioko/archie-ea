#!/usr/bin/env python
"""Enforce the semantic colour-token rule from DESIGN.md.

DESIGN.md states that raw Tailwind colour scales are forbidden and that "the
pre-commit hook check_token_migration.py will block the commit". That hook does
not exist in this repository, so the rule has been documented-but-unenforced.
This script is that gate.

What is flagged
--------------
Raw Tailwind colour utilities on the neutral/blue/red families, which all have
semantic token equivalents (see the mapping table in DESIGN.md), plus bare
``bg-white`` / ``text-white``.

What is deliberately allowed
----------------------------
``emerald`` / ``amber`` scales: DESIGN.md explicitly says green and yellow have
no semantic tokens and these should be used directly for status colours. Arbitrary
values (``bg-[#fff]``) are out of scope — a separate concern.

Usage
-----
    python scripts/check_design_tokens.py                  # scan all templates
    python scripts/check_design_tokens.py --count          # print violation count only
    python scripts/check_design_tokens.py FILE [FILE ...]  # scan specific files
"""

from __future__ import annotations

import argparse
import glob
import re
import sys

# Colour families that have a semantic token replacement and are therefore banned.
BANNED_FAMILIES = ("gray", "grey", "slate", "zinc", "neutral", "stone", "blue", "red")

# e.g. bg-gray-50, text-blue-600, border-gray-200, hover:bg-red-500, ring-slate-300
SCALED = re.compile(
    r"\b(?:[a-z-]+:)*(bg|text|border|ring|divide|from|via|to|placeholder|decoration|outline|shadow)"
    r"-(" + "|".join(BANNED_FAMILIES) + r")-(\d{2,3})\b"
)

# Bare white utilities — DESIGN.md maps these to bg-background / text-primary-foreground.
BARE_WHITE = re.compile(r"\b(?:[a-z-]+:)*(bg|text|border)-white\b")

SUGGESTIONS = {
    "bg": "bg-background / bg-card / bg-muted",
    "text": "text-foreground / text-muted-foreground / text-primary",
    "border": "border-border / border-input",
    "ring": "ring-ring",
    "divide": "divide-border",
}


def scan_file(path: str) -> list[tuple[int, str, str]]:
    """Return [(line_no, matched_text, suggestion)] for *path*."""
    findings: list[tuple[int, str, str]] = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return findings

    for lineno, line in enumerate(lines, start=1):
        # A file may opt out of a specific line with an explicit acknowledgement.
        if "design-tokens-ok" in line:
            continue
        for match in SCALED.finditer(line):
            utility = match.group(1)
            findings.append((lineno, match.group(0), SUGGESTIONS.get(utility, "a semantic token")))
        for match in BARE_WHITE.finditer(line):
            utility = match.group(1)
            findings.append((lineno, match.group(0), SUGGESTIONS.get(utility, "a semantic token")))
    return findings


def default_paths() -> list[str]:
    return sorted(glob.glob("app/templates/**/*.html", recursive=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="files to scan (default: all templates)")
    parser.add_argument("--count", action="store_true", help="print only the total count")
    parser.add_argument("--max", type=int, default=None, help="fail if count exceeds this")
    args = parser.parse_args(argv)

    paths = args.paths or default_paths()
    # Only templates are in scope; tolerate being handed other files by pre-commit.
    paths = [p for p in paths if p.endswith((".html", ".jinja", ".jinja2"))]

    total = 0
    report: list[str] = []
    for path in paths:
        findings = scan_file(path)
        total += len(findings)
        for lineno, text, suggestion in findings:
            report.append(f"{path}:{lineno}: {text}  ->  use {suggestion}")

    if args.count:
        print(total)
        return 0

    if report:
        print("\n".join(report))
        print(f"\n{total} raw Tailwind colour utility/utilities found in {len(paths)} file(s).")
        print("See the forbidden-classes table in DESIGN.md for the semantic replacement.")
        print("If a line is a deliberate exception, append a 'design-tokens-ok' comment.")
    else:
        print(f"No raw Tailwind colour utilities found in {len(paths)} file(s).")

    if args.max is not None and total > args.max:
        print(f"\nFAIL: {total} exceeds the allowed maximum of {args.max}.")
        return 1
    if args.max is None and total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
