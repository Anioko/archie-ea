#!/usr/bin/env python
"""Find test fixture names filtered out of production queries.

The Architecture Journey hub carried this, in the query that lists a user's own
in-progress work:

    ~Solution.name.ilike("J1-AutoTest-%"),
    ~Solution.name.ilike("J7-E2E-Test%"),
    ~Solution.name.ilike("%-AutoTest-%"),

Those are this repository's own test fixture names, excluded from what a real user
sees in production. It is wrong twice over. A customer who legitimately names a
solution "Migration-AutoTest-Rig" watches it vanish from their own screen with no
explanation and no way to get it back. And a test suite that leaves rows behind
should be fixed in the suite, not hidden from the product -- the exclusion makes
the leak invisible, so it never gets fixed, and the workaround becomes permanent.

Once one exists, more follow: it is a cheap-looking fix under deadline, and there
was nothing to say it had happened. This counts them.

What it flags: a query predicate on a user-visible model that filters on a literal
looking like test scaffolding -- AutoTest, E2E-Test, TestData, DummyData, SAMPLE-,
and the like -- anywhere under app/.

Escape hatch: `test-filter-ok: <reason>` on the flagged line or the one above,
for the genuine case (a fixture-cleanup CLI, a seeding command).

    python scripts/check_test_data_in_queries.py            # list findings
    python scripts/check_test_data_in_queries.py --count    # trailing line = count
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "vendor", "migrations", "tests"}
ALLOW = re.compile(r"test-filter-ok:")

# Literals that name test scaffolding rather than customer data. Deliberately
# specific: a bare "test" would match "Latest", "Contest" and half the estate, and a
# checker that cries wolf gets ignored, which is worse than not having it.
TEST_LITERAL = re.compile(
    r"""["'][^"']*(?:
          AutoTest
        | Auto-Test
        | E2E[-_]?Test
        | TestData
        | Test[-_]Data
        | DummyData
        | Dummy[-_]Data
        | FixtureData
        | SmokeTest
        | Smoke[-_]Test
        | QA[-_]?Fixture
        | SAMPLE[-_]
        | DELETEME
        | DO[-_]NOT[-_]USE
    )[^"']*["']""",
    re.X | re.I,
)

# The predicate shapes that actually filter rows. A test literal in a log line,
# a docstring or a comment is not a query and is not a finding.
PREDICATE = re.compile(
    r"\.(?:ilike|like|notlike|notilike|contains|startswith|endswith|in_|not_in)\s*\(|"
    r"\bfilter(?:_by)?\s*\(|"
    r"\bwhere\s*\(",
    re.I,
)

COMMENT = re.compile(r"^\s*(?:#|//|\*|\"\"\"|''')")


def walk(root):
    app_dir = os.path.join(root, "app")
    for dirpath, dirnames, filenames in os.walk(app_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def excused(lines, idx):
    if idx < len(lines) and ALLOW.search(lines[idx]):
        return True
    return idx > 0 and ALLOW.search(lines[idx - 1])


def findings_for(path, root):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return out

    for idx, line in enumerate(lines):
        if COMMENT.match(line) or not TEST_LITERAL.search(line):
            continue
        # The predicate may sit on this line or the one above it, since these are
        # usually formatted one filter per line inside a multi-line call.
        window = line + "\n" + (lines[idx - 1] if idx else "")
        if not PREDICATE.search(window):
            continue
        if excused(lines, idx):
            continue
        rel = os.path.relpath(path, root).replace("\\", "/")
        out.append((rel, idx + 1, line.strip()[:120]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print only the count")
    ap.add_argument("--root", default=ROOT, help="tree to scan (its app/ subdirectory)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    findings = []
    for path in sorted(walk(root)):
        findings.extend(findings_for(path, root))

    if not args.count:
        for rel, line, text in findings:
            print(f"{rel}:{line}: [test-data-filter] {text}")
        if findings:
            print()
            print(
                "A production query is hiding rows whose names look like test\n"
                "fixtures. A customer whose data matches the pattern loses it from\n"
                "their own screen with no explanation. Fix the suite so it does not\n"
                "leave rows behind, rather than filtering them out of the product.\n"
                "If a hit is genuinely fine -- a cleanup CLI, a seeder -- append\n"
                "'test-filter-ok: <reason>'."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
