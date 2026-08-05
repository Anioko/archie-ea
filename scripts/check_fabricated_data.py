#!/usr/bin/env python
"""Find fabricated / invented data that can reach the UI.

Archie is a system of record. A screen that invents a plausible number when the
real one is missing is worse than a screen that shows nothing: the user cannot
tell the difference, and acts on it. This checker flags the four shapes that
produced every real instance found in the tree:

  catch-returns-fake   a catch/except block that assigns a literal collection,
                       so an API failure silently renders invented content
  self-admitted-fake   "// Mock data", "// Sample data for demonstration", …
  random-data          random.randint()/Math.random() feeding displayed values
  fictional-entity     Acme / Contoso / John Doe et al. in shipped markup

Escape hatch: append `fabricated-ok: <reason>` on the flagged line (or the line
above it) when a hit is genuinely fine — e.g. a documented demo fixture, or
Math.random() used for a DOM id rather than a displayed value.

Usage:
    python scripts/check_fabricated_data.py            # list findings
    python scripts/check_fabricated_data.py --count    # trailing line = count
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "vendor", "migrations", "tests"}
ALLOW = re.compile(r"fabricated-ok:")

# A catch/except body that assigns an array-of-objects or object literal.
CATCH_FAKE = re.compile(
    r"catch\s*\([^)]*\)\s*\{(?:(?!\}|catch).){0,400}?"
    r"(?:this\.)?[\w.]+\s*=\s*\[\s*\{",
    re.S,
)
SELF_ADMITTED = re.compile(
    r"//\s*(?:mock|sample|fake|dummy|demo|hardcoded)\s+data"
    r"|#\s*(?:mock|sample|fake|dummy|demo)\s+data",
    re.I,
)
# Displayed-value randomness. Toast/DOM-id randomness is excluded by the
# allow-comment, which those call sites carry.
RANDOM = re.compile(r"\brandom\.(?:randint|uniform|choice)\b|\bnp\.random\.")
FICTION = re.compile(
    r"\b(?:Acme\s+(?:Manufacturing|Industries)|Contoso|Globex|Initech"
    r"|Global Industries|Tech Solutions Inc|Precision Engineering"
    r"|John Doe|Jane Doe|Lorem ipsum)\b",
    re.I,
)

CHECKS = (
    ("catch-returns-fake", CATCH_FAKE, (".js", ".html", ".jinja", ".j2")),
    ("self-admitted-fake", SELF_ADMITTED, (".js", ".html", ".jinja", ".j2", ".py")),
    ("random-data", RANDOM, (".py",)),
    ("fictional-entity", FICTION, (".js", ".html", ".jinja", ".j2")),
)


def walk():
    for dirpath, dirnames, filenames in os.walk(APP):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in {".js", ".html", ".jinja", ".j2", ".py"}:
                yield os.path.join(dirpath, fn)


COMMENT = re.compile(r"^\s*(?://|#|\{#|<!--|\*|/\*)")
# A name inside an input placeholder is example text the user overwrites, not
# data the platform asserts. Same for aria-label.
ATTR_ONLY = re.compile(r"placeholder\s*=|aria-label\s*=")


def excused(lines: list[str], idx: int) -> bool:
    """Allow the marker on the hit line or the line immediately above."""
    if idx < len(lines) and ALLOW.search(lines[idx]):
        return True
    return idx > 0 and ALLOW.search(lines[idx - 1])


def is_noise(name: str, line: str) -> bool:
    """Comments never render; placeholders are example text, not asserted data."""
    if name != "fictional-entity":
        return False
    return bool(COMMENT.match(line) or ATTR_ONLY.search(line))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print only the count")
    args = ap.parse_args()

    findings = []
    for path in sorted(walk()):
        ext = os.path.splitext(path)[1]
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue
        lines = src.split("\n")
        for name, pattern, exts in CHECKS:
            if ext not in exts:
                continue
            for m in pattern.finditer(src):
                idx = src.count("\n", 0, m.start())
                if excused(lines, idx) or is_noise(name, lines[idx]):
                    continue
                rel = os.path.relpath(path, ROOT).replace("\\", "/")
                findings.append((rel, idx + 1, name, lines[idx].strip()[:120]))

    if not args.count:
        for rel, line, name, text in findings:
            print(f"{rel}:{line}: [{name}] {text}")
        if findings:
            print()
            print(
                "Render an explicit empty/error state instead of inventing data.\n"
                "If a hit is genuinely fine, append 'fabricated-ok: <reason>'."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
