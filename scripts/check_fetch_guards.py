#!/usr/bin/env python3
"""A raw fetch() whose body is parsed without ever checking the response.

The other half of `error-signalling`. That gate made ~64 endpoints answer a
failure with an honest 4xx/5xx instead of 200 — and a caller written like this
throws that honesty away::

    const resp = await fetch(url);
    const data = await resp.json();          // a 500 body parses fine
    this.items = data.items || [];           // ...and yields an empty list

The user sees "no results", exactly as before. Both halves are required: the
server has to say it failed, and the client has to look.

`fetch` does not reject on 4xx/5xx — only on a network error — so without an
explicit check there is nothing to catch. `if (response.ok)` with no `else` has
the same defect: state is left at its initialiser.

NOT flagged
-----------
`Platform.fetch` (app/static/js/core/03-fetch.js) already checks `!response.ok`,
extracts the server's message and toasts it. Wrapping it in another check
produces double toasts, so its call sites are correct as written.

A guard anywhere near the call counts: `.ok`, `.status`, `data.success`, or a
`throw`. That window is what separates a genuinely unguarded call from one whose
check sits a few lines below — and it is why the raw match count of 341 is not
the answer; the honest figure is the ~62 that survive it.

Escape hatch: `fetch-guard-ok: <reason>` on the fetch line or the line above.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

_OK = re.compile(r"fetch-guard-ok:[ \t]*[A-Za-z0-9]")

# `await fetch(...)` followed, close by, by `await <name>.json()`.
_CALL = re.compile(
    r"await\s+fetch\([^;]{0,400}?\)\s*;[\s\S]{0,160}?await\s+(\w+)\.json\(\)")

# Any of these near the call means the response IS inspected.
_GUARD = re.compile(r"\.ok\b|\.status\b|\bthrow\b|\.success\b|Platform\.fetch")


def scan() -> list[str]:
    out: list[str] = []
    files = sorted((ROOT / "app" / "static" / "js").rglob("*.js")) + \
        sorted((ROOT / "app" / "templates").rglob("*.html"))
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        if "/static/js/vendor/" in rel:
            continue                      # third-party; editing breaks its SRI hash
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        for m in _CALL.finditer(text):
            window = text[max(0, m.start() - 400):m.end() + 400]
            if _GUARD.search(window):
                continue
            ln = text[:m.start()].count("\n") + 1
            marker_window = "\n".join(lines[max(0, ln - 2):ln])
            if _OK.search(marker_window):
                continue
            out.append(
                "%s:%d: fetch-guard: the response is parsed without checking it — "
                "a 4xx/5xx body yields an empty result the UI renders as data"
                % (rel, ln))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true")
    args = ap.parse_args()
    hits = scan()
    if args.count:
        print(len(hits))
        return 0
    for h in hits:
        print("  " + h)
    print("\n%d unguarded fetch(es)." % len(hits))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
