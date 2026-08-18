#!/usr/bin/env python
"""Build committed JS bundles for the platform core script sequence.

    python scripts/build_js.py           # build all bundles, overwrite committed output
    python scripts/build_js.py --check   # verify the committed bundles are up to date

Mirrors ``scripts/build_css.py``: bundles are built locally and the OUTPUT IS
COMMITTED, so the Docker image stays Python-only and a fresh clone needs no
Node/npm/bundler toolchain at all — there is nothing to install, this script
uses only the Python standard library. ``--check`` exists so CI/verify.py can
catch a bundle that has drifted from its sources, exactly as
``build_css.py --check`` catches stale CSS.

Why bundles are defined per base-layout, not one global bundle
----------------------------------------------------------------
``app/templates/layouts/{admin,composer,public}_base.html`` each load a
different *prefix* of the numbered ``js/core/NN-*.js`` sequence (public stops
at 05-error.js, composer adds 06-session-timeout.js, admin adds
07-dialog.js too). Concatenating a superset into every layout would start
executing session-timeout/dialog code on pages that never loaded it before
(e.g. the public login page) — an unintended behaviour change. So each
layout gets its own bundle containing exactly the files it already loads,
in exactly the same order. Concatenation order is load-bearing: 00-namespace
defines ``window.Platform`` before 01-logger attaches ``Platform.log``, and
so on down the numbered chain (see ``app/static/js/core/load-order.js``).

Each source file is wrapped in a ``// >>> path`` / ``// <<< path`` marker so
a stack trace pointing at a bundle line is still traceable to its source file
by inspection, without needing a source map.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "app" / "static" / "js" / "core"
BUNDLE_DIR = REPO_ROOT / "app" / "static" / "js" / "bundles"

# name -> ordered list of source files, exactly matching the <script> sequence
# each base layout currently loads. Keep in sync with:
#   app/templates/layouts/public_base.html    (core-public)
#   app/templates/layouts/composer_base.html  (core-composer)
#   app/templates/layouts/admin_base.html     (core-admin)
BUNDLES: dict[str, list[str]] = {
    "core-public.js": [
        "00-namespace.js",
        "01-logger.js",
        "02-sanitize.js",
        "03-fetch.js",
        "04-toast.js",
        "05-error.js",
    ],
    "core-composer.js": [
        "00-namespace.js",
        "01-logger.js",
        "02-sanitize.js",
        "03-fetch.js",
        "04-toast.js",
        "05-error.js",
        "06-session-timeout.js",
    ],
    "core-admin.js": [
        "00-namespace.js",
        "01-logger.js",
        "02-sanitize.js",
        "03-fetch.js",
        "04-toast.js",
        "05-error.js",
        "06-session-timeout.js",
        "07-dialog.js",
    ],
}

HEADER = """/**
 * {name} — GENERATED FILE, do not edit directly.
 *
 * Built by `python scripts/build_js.py` from the numbered files in
 * app/static/js/core/, concatenated in load order. Edit the source file
 * under app/static/js/core/ and rerun the build; `--check` fails CI if this
 * file has drifted from its sources.
 *
 * Source order:
{sources}
 */
"""


def render(bundle_name: str, files: list[str]) -> str:
    sources = "\n".join(f" *   {i:02d}. {f}" for i, f in enumerate(files))
    parts = [HEADER.format(name=bundle_name, sources=sources)]
    for f in files:
        path = CORE / f
        if not path.exists():
            print(f"error: missing source {path}", file=sys.stderr)
            sys.exit(2)
        text = path.read_text(encoding="utf-8")
        parts.append(f"\n// >>> app/static/js/core/{f}\n")
        parts.append(text.rstrip("\n"))
        parts.append(f"\n// <<< app/static/js/core/{f}\n")
    return "".join(parts)


def build() -> int:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    for bundle_name, files in BUNDLES.items():
        out = BUNDLE_DIR / bundle_name
        content = render(bundle_name, files)
        out.write_text(content, encoding="utf-8", newline="\n")
        print(f"built {out.relative_to(REPO_ROOT)} ({len(content)} bytes, {len(files)} sources)")
    return 0


def check() -> int:
    failed = []
    for bundle_name, files in BUNDLES.items():
        out = BUNDLE_DIR / bundle_name
        expected = render(bundle_name, files)
        if not out.exists():
            failed.append(f"{out.relative_to(REPO_ROOT)}: missing")
            continue
        actual = out.read_text(encoding="utf-8")
        if actual != expected:
            failed.append(f"{out.relative_to(REPO_ROOT)}: stale (rebuild changes it)")
    if failed:
        print("FAIL: committed JS bundle(s) out of date:", file=sys.stderr)
        for f in failed:
            print(f"  - {f}", file=sys.stderr)
        print("Run: python scripts/build_js.py   and commit the result.", file=sys.stderr)
        return 1
    print("committed JS bundles are up to date")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="verify committed bundles are current")
    args = parser.parse_args(argv)
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
