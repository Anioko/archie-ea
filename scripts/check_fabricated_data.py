#!/usr/bin/env python
"""Find fabricated / invented data that can reach the UI.

Archie is a system of record. A screen that invents a plausible number when the
real one is missing is worse than a screen that shows nothing: the user cannot
tell the difference, and acts on it. This checker flags the four shapes that
produced every real instance found in the tree:

  catch-returns-fake   a catch/except block that assigns a literal collection,
                       so an API failure silently renders invented content
  python-zero-fill     a Python `except` (or falsy-result guard) returning a dict
                       whose values are all zeros, empty strings or a severity
                       word. This is the same defect as catch-returns-fake seen
                       from the server side, and every rule above it was written
                       JS-first, so it went unseen: `{"pending": 0}` returned
                       from an except renders as a confident stat card after a
                       database failure, and "LOW" renders as a risk assessment
                       nobody made
  unknown-ok-marker    a `fabricated-*-ok` spelling the ALLOW pattern does not
                       recognise. `fabricated-values-ok` does not contain
                       `fabricated-ok`, so it suppressed nothing while reading to
                       every later author exactly like a filed exception. A
                       silent non-exception is worse than no exception: it stops
                       the next reader looking
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
# Any other `fabricated-…-ok` spelling. Matched deliberately so a near-miss is
# reported rather than ignored: the author intended to file an exception, and
# needs to be told the file never received one.
NEAR_MISS_MARKER = re.compile(r"fabricated-(?!ok:)[a-z-]*ok\b")

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

# A Python `except` (or falsy-result guard) whose body returns/assigns a dict
# literal made entirely of zeros, empty strings, empty collections or a severity
# word. Deliberately narrow: a dict containing any real expression, or any None,
# is NOT matched, because None is the prescribed honest answer and flagging it
# would make the rule impossible to satisfy.
_DEAD_VALUE = (
    r"(?:0(?:\.0)?|''|\"\"|\[\]|\{\}|"
    r"'(?:LOW|OK|HEALTHY|PASS|GREEN|NONE|GOOD)'|"
    r"\"(?:LOW|OK|HEALTHY|PASS|GREEN|NONE|GOOD)\")"
)
PY_ZERO_FILL = re.compile(
    r"except\b[^\n]*:\s*(?:\n\s*(?:#[^\n]*|logger\.[^\n]*|pass)\s*)*"
    r"\n\s*(?:return|[\w.\[\]'\"]+\s*=)\s*\{"
    r"(?:\s*(?:'[^']*'|\"[^\"]*\")\s*:\s*" + _DEAD_VALUE + r"\s*,?)+\s*\}",
    re.M,
)
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
    ("python-zero-fill", PY_ZERO_FILL, (".py",)),
    ("unknown-ok-marker", NEAR_MISS_MARKER, (".js", ".html", ".jinja", ".j2", ".py")),
    ("fictional-entity", FICTION, (".js", ".html", ".jinja", ".j2")),
)


def walk(app_dir=None):
    for dirpath, dirnames, filenames in os.walk(app_dir or APP):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in {".js", ".html", ".jinja", ".j2", ".py"}:
                yield os.path.join(dirpath, fn)


COMMENT = re.compile(r"^\s*(?://|#|\{#|<!--|\*|/\*)")
# A name inside an input placeholder is example text the user overwrites, not
# data the platform asserts. Same for aria-label.
ATTR_ONLY = re.compile(r"placeholder\s*=|aria-label\s*=")


def excused(lines: list[str], idx: int, name: str = "") -> bool:
    """Allow the marker on the hit line or the line immediately above.

    `unknown-ok-marker` is never excusable: the whole point of the finding is
    that the marker on that line does not work, so honouring it would restore
    exactly the silence being reported.
    """
    if name == "unknown-ok-marker":
        return False
    if idx < len(lines) and ALLOW.search(lines[idx]):
        return True
    return idx > 0 and ALLOW.search(lines[idx - 1])


def _block_comment_spans(src: str) -> list[tuple[int, int]]:
    """Character spans of Jinja `{# … #}` and HTML `<!-- … -->` comment blocks.

    These span multiple lines, so a per-line check misses their interior. That
    matters more than it looks: annotating a line *inside* a `{# … #}` block with
    another `{# … #}` closes the outer block early and turns the remainder of the
    file into live template code (jinja2 TemplateSyntaxError). Recognising the
    block means no annotation is needed there at all.
    """
    spans = []
    for opener, closer in (("{#", "#}"), ("<!--", "-->")):
        pos = 0
        while True:
            start = src.find(opener, pos)
            if start == -1:
                break
            end = src.find(closer, start + len(opener))
            if end == -1:
                spans.append((start, len(src)))
                break
            spans.append((start, end + len(closer)))
            pos = end + len(closer)
    return spans


def is_noise(name: str, line: str, idx: int = -1, spans=(), offset: int = -1) -> bool:
    """Comments never render; placeholders are example text, not asserted data."""
    if name != "fictional-entity":
        return False
    if COMMENT.match(line) or ATTR_ONLY.search(line):
        return True
    return any(a <= offset < b for a, b in spans)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print only the count")
    ap.add_argument(
        "--select",
        action="append",
        default=None,
        metavar="RULE",
        help="only run this rule (repeatable). Exists so the long-standing "
        "must-be-zero gate keeps counting exactly the four rules it was green "
        "on, while the two rules added later -- which surface a population that "
        "was always there but invisible -- ratchet separately. Folding them "
        "together would have meant relaxing a zero guarantee to accommodate "
        "newly-found debt, which is the wrong direction for a gate to move.",
    )
    ap.add_argument(
        "--root",
        default=ROOT,
        help="tree to scan (its app/ subdirectory); defaults to the repository. "
        "Exists so the checker's own behaviour can be tested against fixtures "
        "rather than against today's debt count, which would make every test a "
        "hostage to unrelated cleanups.",
    )
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    app_dir = os.path.join(root, "app")

    findings = []
    for path in sorted(walk(app_dir)):
        ext = os.path.splitext(path)[1]
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue
        lines = src.split("\n")
        spans = _block_comment_spans(src) if ext != ".py" else ()
        for name, pattern, exts in CHECKS:
            if ext not in exts:
                continue
            if args.select and name not in args.select:
                continue
            for m in pattern.finditer(src):
                idx = src.count("\n", 0, m.start())
                if excused(lines, idx, name) or is_noise(
                    name, lines[idx], idx, spans, m.start()
                ):
                    continue
                rel = os.path.relpath(path, root).replace("\\", "/")
                findings.append((rel, idx + 1, name, lines[idx].strip()[:120]))

    if not args.count:
        for rel, line, name, text in findings:
            print(f"{rel}:{line}: [{name}] {text}")
        if findings:
            print()
            print(
                "Render an explicit empty/error state instead of inventing data.\n"
                "Return None (which renders as an em dash) rather than 0 or a\n"
                "severity word: a 0 meaning 'not computed' is indistinguishable\n"
                "from a measured zero.\n"
                "If a hit is genuinely fine, append 'fabricated-ok: <reason>' --\n"
                "that exact spelling. Any other 'fabricated-*-ok' variant is\n"
                "reported as unknown-ok-marker because it suppresses nothing."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
