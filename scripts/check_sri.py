#!/usr/bin/env python
"""Verify every Subresource Integrity hash matches the file it guards.

    python scripts/check_sri.py            # report mismatches
    python scripts/check_sri.py --count    # count only

Why
---
An `integrity="sha384-..."` attribute makes the browser refuse to execute a script
whose bytes do not hash to the declared value. That is the point — but it means a
stale hash does not degrade, it BLOCKS. The symptom is a dead page with a console
error, not a server-side failure, so nothing in a normal test run notices.

This repository has already been bitten twice: `fix: the entire front-end framework
was blocked by bad SRI hashes`, then a revert of a rehash because it "would have
broken production".

It is especially easy to break while vendoring. Repointing a `src` from a CDN to a
local copy is safe only if the bytes are identical; the moment a version is pinned
differently — `alpinejs@3` to `@3.14.3`, say — the hash silently stops matching.
That exact mismatch was live on this branch and neither `vendor-integrity` (which
compares files to the vendor manifest) nor `air-gap` (which checks for external
origins) could see it, because neither relates a TEMPLATE's declared hash to the
FILE its src resolves to.

Only same-origin assets are checked. A hash on a remote URL cannot be verified
without fetching it, and the air-gap gate should have removed those anyway.
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import os
import re
import sys

STATIC_ROOT = os.path.join("app", "static")

# A tag carrying both a source and an integrity attribute, in either order.
TAG = re.compile(r"<(?:script|link)\b[^>]*?>", re.I | re.S)
INTEGRITY = re.compile(r"""integrity\s*=\s*["'](sha(?:256|384|512))-([A-Za-z0-9+/=]+)["']""", re.I)
URL_FOR = re.compile(r"""url_for\(\s*['"]static['"]\s*,\s*filename\s*=\s*['"]([^'"]+)['"]""")
PLAIN_SRC = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


def resolve(tag: str) -> str | None:
    """Return the on-disk path of the asset this tag loads, or None if not local."""
    m = URL_FOR.search(tag)
    if m:
        return os.path.join(STATIC_ROOT, m.group(1))
    m = PLAIN_SRC.search(tag)
    if not m:
        return None
    url = m.group(1)
    if url.startswith(("http://", "https://", "//")):
        return None  # remote: cannot verify without fetching
    if "/static/" in url:
        return os.path.join(STATIC_ROOT, url.split("/static/", 1)[1].split("?")[0])
    return None


def digest(path: str, algo: str) -> str:
    h = hashlib.new(algo.replace("sha", "sha"))
    with open(path, "rb") as fh:
        h.update(fh.read())
    return base64.b64encode(h.digest()).decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args(argv)

    problems: list[str] = []
    checked = 0

    for path in sorted(glob.glob("app/templates/**/*.html", recursive=True)):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        for tag in TAG.findall(text):
            found = INTEGRITY.search(tag)
            if not found:
                continue
            algo, declared = found.group(1).lower(), found.group(2)
            asset = resolve(tag)
            if asset is None:
                continue  # remote asset, or no resolvable source
            line = text.count("\n", 0, text.find(tag)) + 1
            if not os.path.exists(asset):
                problems.append(f"{path}:{line}: integrity set on a missing file: {asset}")
                continue
            checked += 1
            actual = digest(asset, algo)
            if actual != declared:
                problems.append(
                    f"{path}:{line}: {algo} mismatch for {asset}\n"
                    f"    declared {algo}-{declared[:40]}...\n"
                    f"    actual   {algo}-{actual[:40]}...\n"
                    f"    the browser will REFUSE to execute this asset"
                )

    if args.count:
        print(len(problems))
        return 0

    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} SRI problem(s) across {checked} checked asset(s).")
        print("Recompute with: python -c \"import base64,hashlib;"
              "print(base64.b64encode(hashlib.sha384(open('PATH','rb').read()).digest()).decode())\"")
        return 1

    print(f"All {checked} same-origin SRI hash(es) match their files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
