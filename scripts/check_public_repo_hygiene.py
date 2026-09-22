#!/usr/bin/env python
r"""This repository is public; the orchestrator repository that plans its
work is not. A path reference to that repository's `docs/buckets/<slug>/`
folder structure, or a copy of that folder committed here, tells a public
reader exactly what to go looking for and where -- and once, 82 files and
17,550 lines of it were committed here directly (removed 21 Sep 2026).

This checker holds three things:

1. No `docs/buckets/` directory tracked in this repository at all. (zero)
2. No tracked source file (app/, scripts/, tests/, templates) contains the
   literal string `docs/buckets/` -- a reference to that structure, even
   without the files themselves, still describes it. (zero)
3. Review-record-id tokens and pipeline role words, committed to tracked
   source or to a commit message, name the *process* that produced a change
   rather than the change itself -- the orchestrator repository's own bucket
   rows, ledger ids and role names, meaningless (or worse, a map of what to
   go looking for) to a public reader. Twice a builder wrote one of these
   into a product file or a commit message and (1)/(2) above matched none of
   it: `app/modules/intelligence/services/query_service.py:538` ("# D-5
   (refuter): ...") and `app/modules/intelligence/routes/api.py:159` ("#
   No tenant_scope() here (round-1 refuter finding D4): ..."). (ratchet --
   see "Why a ratchet, not zero" below)

Per-line escape hatch for rules 2 and 3 (source), per-commit for rule 3
(commit messages): `hygiene-ok: <reason>` anywhere on the line / anywhere in
the message, for a reference that is itself the point (this file's own
docstring, or a test asserting the pattern is absent).

Why a ratchet, not zero (rule 3's record-id half)
--------------------------------------------------
The brief that asked for this checker gave the shape as "a capital letter or
two, optional digits, a dash, digits" (e.g. D2-7, T4-3) and named an
allowlist of real identifiers to exclude: CVE-, RFC-, ISO-, IEC-, UTF-, and
WCAG references shaped like A-11. Checked against this tree, as the same
brief asked, before deciding anything:

* CVE-/RFC-/ISO-/IEC-/UTF- never match RECORD_ID_PATTERN at all: each prefix
  is three-plus letters, and the pattern's `[A-Z]{1,2}` caps at two, with no
  `\b` boundary available mid-word to start matching later ("UTF-8" cannot
  match starting at "U" -- next character is "T", neither digit nor dash --
  nor at "T" or "F", neither preceded by a word boundary). Kept in
  RECORD_ID_ALLOWLIST_PREFIXES anyway, spelled out, so a reader does not have
  to re-derive that they are already inert.
* No genuinely WCAG-shaped "A-11" reference exists in this tree. What DOES
  exist under the "A-" prefix is this codebase's own readiness-table finding
  numbers (A-01 .. A-50+, e.g. tests/test_admin_org_member_idor.py's own
  docstring: "A-01 (S1): a tenant administrator must not be able to...").
* The pattern's exact shape -- one or two capital letters, a dash, one to
  four digits, optionally with digits between the letters and the dash -- is
  ALSO this codebase's own permanent, load-bearing business-reference-number
  convention, used at scale: AD-001 is an Architecture Decision's own unique
  database column (app/utils/reference_numbers.py); F-06, F-07, T-001..T-006,
  R7-1..R7-6, R2-1..R2-5, R5-1, S0-01..S0-03 and 500+ more, all pre-existing,
  all load-bearing, none of them a leaked pipeline artifact. R7-1 through
  R7-6 share the EXACT shape of the brief's own "D2-7" example (a single
  digit between the letter and the dash) -- there is no regex that tells a
  leaked review-record-id apart from this codebase's own reference-number
  convention by shape alone, because the brief's example and this codebase's
  real, permanent identifiers are the same shape by construction (both are
  short business reference codes).

A hard-zero rule here would fail on day one against hundreds of these, all
of them permanent, most of them user-facing. A per-token allowlist naming
every one is not maintainable either: this convention grows with every new
feature area (a new AD-048, a new F-08) as a matter of course. So rule 3's
record-id half is a ratchet, exactly the same shape as this codebase's other
static-analysis-heuristic ratchets (see unrendered_model_fields, baselined
at 387 for the identical reason: real findings that need triage, not 387
confirmed defects). The role-word half of rule 3 has no such ambiguity --
"refuter", "tech-lead", "orchestrator", "the brief" and "build report" do
not occur in ordinary product prose -- but is measured and ratcheted
alongside it rather than split into its own zero-tolerance rule, so that one
`--rule content` invocation and one baseline key cover both halves of "a
record id or a role word ended up in a product file", and a genuinely new
role-word hit is still visible immediately in the count going up by exactly
one, distinguishable in the listing from the record-id noise by its own
message text.

Commit messages (rule 3's other surface) are handled the same way for a
different reason: they are immutable without rewriting already-pushed public
history, which this repository's own standing instructions forbid doing
except to a role's own not-yet-merged branch. The baseline is therefore a
frozen count of today's history, not something later cleanup can lower --
only a future bad commit can raise it.

Proven-against: a docs/buckets/ directory tracked in a synthetic tree, and
a tracked file containing the literal string "docs/buckets/" -- both
observed red, then green once removed (the original two rules, unchanged
here). Rule 3: a tracked file containing "D2-7" and a file containing
"refuter" -- both observed red, then green once removed or marked
hygiene-ok; a commit message containing "round-1 refuter finding" observed
red in a synthetic git repository, then green once amended.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCAN_DIRS = ("app", "scripts", "tests", "templates")
PATTERN = "docs/buckets/"
SELF_NAME = os.path.basename(__file__)
ESCAPE_HATCH = "hygiene-ok:"

# ---------------------------------------------------------------- rule 3: review-record-id tokens and pipeline role words

# "A capital letter or two, optional digits, a dash, one to four digits" --
# e.g. D2-7, T4-3 (the brief's own examples). See the module docstring's "Why
# a ratchet, not zero" for why this also matches this codebase's own
# permanent reference-number convention, and cannot be told apart from it by
# shape.
RECORD_ID_PATTERN = re.compile(r"\b[A-Z]{1,2}[0-9]*-[0-9]{1,4}\b")

# Never actually matches RECORD_ID_PATTERN (see the module docstring) --
# kept explicit because the brief that asked for this checker named these
# prefixes by hand.
RECORD_ID_ALLOWLIST_PREFIXES = ("CVE-", "RFC-", "ISO-", "IEC-", "UTF-")

# Case-insensitive, whole word; "round" only when immediately followed by a
# digit (round-1, round 2, round3), the shape a pipeline round number takes,
# not the ordinary English word.
ROLE_WORDS = [
    (re.compile(r"\brefuter\b", re.IGNORECASE), "refuter"),
    (re.compile(r"\btech-lead\b", re.IGNORECASE), "tech-lead"),
    (re.compile(r"\borchestrator\b", re.IGNORECASE), "orchestrator"),
    (re.compile(r"\bthe brief\b", re.IGNORECASE), "the brief"),
    (re.compile(r"\bbuild report\b", re.IGNORECASE), "build report"),
    (re.compile(r"\bround[\s-]?[0-9]", re.IGNORECASE), 'round<N>'),
]

COMMIT_MESSAGE_PATTERNS = ROLE_WORDS + [
    (re.compile(r"co-authored-by", re.IGNORECASE), "Co-Authored-By"),
]

# .js so app/static's authored JS is covered; vendor/bundles/*.min.js are
# third-party or built output, never authored comments, and would be pure
# noise (minified variable names and CSS/coordinate data happen to match
# RECORD_ID_PATTERN by the thousand).
CONTENT_EXTENSIONS = (".py", ".html", ".j2", ".md", ".js")
CONTENT_SKIP_DIRNAMES = {"__pycache__", "node_modules", ".git", "vendor", "bundles"}
CONTENT_SKIP_SUFFIXES = (".min.js",)


def _tracked_bucket_paths(root: str) -> list[str]:
    bucket_dir = os.path.join(root, "docs", "buckets")
    if not os.path.isdir(bucket_dir):
        return []
    found = []
    for dirpath, _dirnames, filenames in os.walk(bucket_dir):
        for name in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
    return found


def _scan_for_references(root: str) -> list[str]:
    problems = []
    for scan_dir in SCAN_DIRS:
        base = os.path.join(root, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules", ".git")]
            for name in filenames:
                if name == SELF_NAME:
                    continue
                if not name.endswith((".py", ".html", ".j2", ".md")):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as fh:
                        lines = fh.readlines()
                except OSError:
                    continue
                for lineno, line in enumerate(lines, start=1):
                    if PATTERN in line and ESCAPE_HATCH not in line:
                        rel = os.path.relpath(path, root).replace(os.sep, "/")
                        problems.append(f"{rel}:{lineno}: references '{PATTERN}'")
    return problems


def _iter_content_files(root: str):
    for scan_dir in SCAN_DIRS:
        base = os.path.join(root, scan_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in CONTENT_SKIP_DIRNAMES]
            for name in filenames:
                if name == SELF_NAME:
                    continue
                if not name.endswith(CONTENT_EXTENSIONS):
                    continue
                if name.endswith(CONTENT_SKIP_SUFFIXES):
                    continue
                yield os.path.join(dirpath, name)


def _scan_record_ids_and_role_words(root: str) -> list[str]:
    """Rule 3, source half: review-record-id tokens and pipeline role words
    in comments, docstrings and string literals under app/, scripts/,
    tests/, templates and static JS."""
    problems = []
    for path in _iter_content_files(root):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        for lineno, line in enumerate(lines, start=1):
            if ESCAPE_HATCH in line:
                continue
            for m in RECORD_ID_PATTERN.finditer(line):
                token = m.group(0)
                if any(token.startswith(p) for p in RECORD_ID_ALLOWLIST_PREFIXES):
                    continue
                problems.append(f"{rel}:{lineno}: looks like a review record id: '{token}'")
            for word_pattern, label in ROLE_WORDS:
                if word_pattern.search(line):
                    problems.append(f"{rel}:{lineno}: pipeline role word '{label}'")
    return problems


def _iter_commit_messages(root: str, rev_range: str | None):
    """(sha, full message) for every commit `git -C root log` can reach,
    oldest first. Uses ASCII unit/record separators (not present in any
    real commit message) to split reliably on multi-line messages."""
    args = ["git", "-C", root, "log", "--format=%H%x1f%B%x1e"]
    if rev_range:
        args.append(rev_range)
    try:
        # encoding/errors pinned explicitly: text=True alone decodes with the
        # PARENT's locale encoding (cp1252 on a default Windows console)
        # regardless of the child's actual output, and this repository's own
        # history contains non-cp1252 bytes -- see scripts/verify.py's _run()
        # for the same fix, made once there already; reused here rather than
        # re-discovering it (this script has no import of verify.py to share
        # the helper directly -- each scripts/check_*.py is standalone).
        proc = subprocess.run(
            args, capture_output=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    records = [r for r in (proc.stdout or "").split("\x1e") if r.strip()]
    result = []
    for rec in records:
        if "\x1f" not in rec:
            continue
        sha, message = rec.split("\x1f", 1)
        result.append((sha.strip(), message))
    return result


def _scan_commit_messages(root: str, rev_range: str | None = None) -> list[str]:
    """Rule 3, commit-message half: pipeline role words and a
    Co-Authored-By trailer in the commit message itself -- not the diff.
    Ratchet: see the module docstring for why past commits are frozen debt,
    not something a later cleanup commit can lower."""
    problems = []
    for sha, message in _iter_commit_messages(root, rev_range):
        if ESCAPE_HATCH in message:
            continue
        for word_pattern, label in COMMIT_MESSAGE_PATTERNS:
            if word_pattern.search(message):
                problems.append(f"{sha[:8]}: '{label}' in the commit message")
    return problems


def scan(root: str) -> list[str]:
    problems = [f"tracked in docs/buckets/: {p}" for p in _tracked_bucket_paths(root)]
    problems += _scan_for_references(root)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    parser.add_argument(
        "--rule", action="append", choices=["buckets", "content", "commits"],
        help="which rule(s) to run; repeatable. Default: buckets only, "
             "matching this script's original, still-zero-tolerance behaviour.",
    )
    parser.add_argument("--range", dest="rev_range", default=None,
                        help="commit range for --rule commits (default: full history)")
    args = parser.parse_args()

    rules = args.rule or ["buckets"]
    root = os.path.abspath(args.root)

    problems: list[str] = []
    if "buckets" in rules:
        problems += scan(root)
    if "content" in rules:
        problems += _scan_record_ids_and_role_words(root)
    if "commits" in rules:
        problems += _scan_commit_messages(root, args.rev_range)

    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "Remove the docs/buckets/ content or reference, the review-record-id\n"
                "token, or the pipeline role word -- it belongs in the orchestrator\n"
                "repository or the bucket working copy, not here. Mark a genuinely\n"
                "necessary line (or commit message) with 'hygiene-ok: <reason>'\n"
                "(e.g. this checker's own docstring)."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
