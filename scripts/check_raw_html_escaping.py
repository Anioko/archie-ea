#!/usr/bin/env python
"""Unescaped interpolation into hand-built HTML strings (Python f-strings).

WHY THIS EXISTS (incident, 10 Sep 2026): app/_bootstrap/_digest_emails.py's
error-digest email renderer interpolated ErrorEvent.message directly into an
HTML table cell via an f-string -- `f'...">{e.message}</td>'` -- with zero
escaping. message is reachable from an unauthenticated caller via
/api/client-error, so a crafted client-error report would have injected live
HTML/script into an email sent to every platform admin. It shipped verified
only by a unit test that asserted a result COUNT, and a CLI run whose only
visible output was "Done: N new events, M recipients" -- nobody, human or
gate, ever looked at the actual HTML string the function produced.

Every other HTML-escaping protection in this codebase is Jinja's
autoescaping on `.html` templates. Nothing covers HTML assembled by hand in
a `.py` file via string formatting -- and Jinja's autoescape provides
*zero* protection there, because it isn't Jinja rendering the string at all.
This gate is that missing coverage.

DETECTION (necessarily a heuristic, not a real parser -- same tradeoff as
check_raw_fetch.py and check_fabricated_data.py in this same directory):
flags a line where an f-string interpolates a `{expr}` immediately between
two HTML-tag delimiters (`>{expr}<`) or as a bare, unquoted-by-escape
attribute value (`="{expr}"`), UNLESS that same line also calls
escape(/markupsafe.escape(/flask.escape(/html.escape( on the expression, or
carries the `raw-html-ok: <reason>` escape hatch.

NOT flagged: Jinja templates (`.html` files -- autoescape already covers
them), f-strings with no HTML-tag shape (log messages, SQL, plain text
emails), and any line already passing its interpolated value through an
escape() call.

Usage:
    python scripts/check_raw_html_escaping.py            # list occurrences
    python scripts/check_raw_html_escaping.py --count    # count only

Proven-against: app/_bootstrap/_digest_emails.py's error-digest renderer
before its fix (10 Sep 2026) -- the line
`f'<td ...>{(e.message or "")[:160]}</td>'` with no escape() call flagged
here; wrapping it as `escape((e.message or "")[:160])` cleared that finding
(and the count dropped by 17 once the file's other two digests, found to
carry the identical unescaped pattern, were fixed the same way).
"""

from __future__ import annotations

import argparse
import glob
import re
import sys

# >{...}<  -- content interpolated directly between two tags, e.g.
#   f'<td>{message}</td>'
# The [^}]+ inside deliberately does not try to balance nested braces --
# real interpolated Python expressions in this codebase are short attribute/
# call chains (`e.message`, `(x or "")[:160]`), not further f-strings.
TAG_CONTENT_INTERPOLATION = re.compile(r">\{[^{}]+\}<")

# ="{...}"  -- an entire attribute value is a bare interpolation, e.g.
#   f'<a href="{url}">'
ATTRIBUTE_INTERPOLATION = re.compile(r'=[\'"]\{[^{}]+\}[\'"]')

ESCAPE_CALL = re.compile(r"\b(?:escape|markupsafe\.escape|flask\.escape|html\.escape)\s*\(")

EXCLUDED_DIRS = ("/vendor/", "/tests/", "/migrations/", "/__pycache__/")


def default_paths() -> list[str]:
    return sorted(glob.glob("app/**/*.py", recursive=True))


def scan_file(path: str) -> list[tuple[int, str]]:
    norm = path.replace("\\", "/")
    if any(d in norm for d in EXCLUDED_DIRS):
        return []
    hits: list[tuple[int, str]] = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, start=1):
                if "raw-html-ok" in line:
                    continue
                if not (TAG_CONTENT_INTERPOLATION.search(line) or ATTRIBUTE_INTERPOLATION.search(line)):
                    continue
                if ESCAPE_CALL.search(line):
                    continue
                hits.append((lineno, line.strip()))
    except OSError:
        return []
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args(argv)

    paths = args.paths or default_paths()
    total = 0
    for path in paths:
        hits = scan_file(path)
        total += len(hits)
        if not args.count:
            for lineno, text in hits:
                print(f"{path}:{lineno}: unescaped interpolation into hand-built HTML: {text[:160]}")
    if args.count:
        print(total)
        return 0
    print(f"\n{total} unescaped HTML interpolation site(s). Wrap the interpolated "
          "value in escape(...) (from html or markupsafe), or mark a deliberate "
          "exception with 'raw-html-ok: <reason>'.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
