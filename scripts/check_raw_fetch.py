#!/usr/bin/env python
"""Count raw fetch() call sites in templates and static JS.

Platform.fetch (app/static/js/core/03-fetch.js) is the sanctioned HTTP path:
it injects CSRF, shows error toasts, integrates the loading store, and throws
on non-ok responses. Raw ``fetch(`` sites bypass all of that and ride only the
CSRF safety net. This ratchet freezes the count so it can only fall as call
sites migrate.

Excluded: 03-fetch.js itself (it wraps the native fetch), `Platform.fetch`
invocations, and lines carrying a ``raw-fetch-ok: <reason>`` marker (e.g. a
streaming endpoint where the wrapper's JSON handling doesn't fit).

Usage:
    python scripts/check_raw_fetch.py            # list occurrences
    python scripts/check_raw_fetch.py --count    # count only
"""

from __future__ import annotations

import argparse
import glob
import re
import sys

# A raw call: `fetch(` not preceded by a word char or dot (excludes
# Platform.fetch(, this.fetch(, window.fetch = assignments still count the
# call site itself elsewhere) — and not a definition like `function fetch`.
RAW_FETCH = re.compile(r"(?<![\w.])fetch\s*\(")

EXCLUDED_FILES = ("core/03-fetch.js",)
# Generated build output. app/static/js/bundles/* is a CONCATENATION of the
# numbered core sequence (ARCH-063), so every fetch site inside it is already
# counted in its source file — scanning both double-counts the same debt and
# makes the ratchet rise when nothing was added. Same reasoning as the
# committed tailwind-output.css: measure sources, not artefacts.
EXCLUDED_DIRS = ("/vendor/", "/js/bundles/")


def default_paths() -> list[str]:
    return sorted(
        glob.glob("app/templates/**/*.html", recursive=True)
        + glob.glob("app/modules/*/templates/**/*.html", recursive=True)
        + glob.glob("app/static/js/**/*.js", recursive=True)
    )


def scan_file(path: str) -> list[int]:
    norm = path.replace("\\", "/")
    if any(norm.endswith(e) for e in EXCLUDED_FILES) or any(d in norm for d in EXCLUDED_DIRS):
        return []
    hits: list[int] = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, start=1):
                if "raw-fetch-ok" in line:
                    continue
                hits.extend(lineno for _ in RAW_FETCH.findall(line))
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
            for lineno in hits:
                print(f"{path}:{lineno}: raw fetch( — use Platform.fetch")
    if args.count:
        print(total)
        return 0
    print(f"\n{total} raw fetch() site(s). Migrate to Platform.fetch, or mark "
          "a deliberate exception with 'raw-fetch-ok: <reason>'.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
