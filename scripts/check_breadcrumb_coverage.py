"""Gate: every routed page with a header carries a breadcrumb.

Fortune-500 UI baseline — a page that shows a title must show a breadcrumb trail
so the user always knows where they are. A UI audit (1 Sep 2026) found 116/312
admin pages with no breadcrumb of any kind; 107 already called page_shell/
page_header and simply omitted the breadcrumb argument. Those were fixed. This
gate keeps the number from creeping back: it counts routed page templates that
render a header macro (page_shell/page_header) but pass NO breadcrumb and do NOT
override the {% block breadcrumb %} escape hatch.

PARTIALS ARE EXCLUDED — a fragment (`_`-prefixed, or under a partials/ directory)
is included by a page and must NOT carry its own breadcrumb; the parent page owns
it. Pages that render no header at all are a separate concern (they need a header
first) and are not counted here.

Ratchet @ 0 in verify.py. Escape hatch: a page that deliberately has no breadcrumb
can carry the marker `breadcrumb-ok:` on any line.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOTS = ("app/templates", "app/modules")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".worktrees", ".claude"}
_HEADER = re.compile(r"page_(?:shell|header)\s*\(")
_BC_ARG = re.compile(r"breadcrumbs?\s*=")
_ALLOW = re.compile(r"breadcrumb-ok:")


def _is_partial(path: Path) -> bool:
    if path.name.startswith("_"):
        return True
    return "partials" in path.parts


def _missing(root: Path) -> list[str]:
    hits = []
    for path in root.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if _is_partial(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if _ALLOW.search(text):
            continue
        if "{% block breadcrumb %}" in text:
            continue  # renders its own breadcrumb via the block
        if not _HEADER.search(text):
            continue  # no header macro — a different (header-first) concern
        # a header macro is present; does ANY header call carry a breadcrumb arg?
        has_bc = any(
            _BC_ARG.search(text[m.start():m.start() + 800])
            for m in _HEADER.finditer(text)
        )
        if not has_bc:
            hits.append(str(path.relative_to(root.parent.parent) if False else path.as_posix()))
    return hits


def main() -> int:
    count_only = "--count" in sys.argv
    root = Path(".").resolve()
    hits = []
    for r in ROOTS:
        rp = root / r
        if rp.exists():
            hits.extend(_missing(rp))
    hits.sort()
    if count_only:
        print(len(hits))
        return 1 if hits else 0
    for h in hits:
        print(f"{h}: header macro present but no breadcrumb (and no {{% block breadcrumb %}})")
    print(f"\n{len(hits)} page(s) with a header but no breadcrumb.")
    if hits:
        print("Add breadcrumb=[('Home','/'), (<title>, none)] to the page_shell call "
              "(or breadcrumbs=[{'label':'Home','href':'/'}, {'label': <title>}] for "
              "page_header), or mark the line 'breadcrumb-ok: <reason>'.")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
