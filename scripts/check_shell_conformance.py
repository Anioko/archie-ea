"""Count page-shell conformance violations in templates.

The 14 Aug 2026 UX audit found the platform ships three competing page-header
systems and two page widths, which is why adjacent modules look like different
products (docs/plans/audit-20260814-ai-gaps-and-ux-consistency.md). This
checker makes that drift a number so verify.py can ratchet it downward.

Two violation classes, counted per file:

1. header-less page: a template that ``extends`` an admin layout but imports
   neither ``page_header`` nor ``page_shell`` — it is hand-rolling its own
   header (or shipping none).
2. off-width page: a template using the ``container mx-auto`` wrapper instead
   of the documented ``p-6 space-y-6`` (DESIGN.md).

A file-level escape hatch ``{# shell-ok: <reason> #}`` excludes a template
that is deliberately non-standard (e.g. print/export layouts), keeping the
exception reviewable rather than silent.

Usage:
    python scripts/check_shell_conformance.py --count   # total violations
    python scripts/check_shell_conformance.py --list    # file: reason lines
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE_DIRS = [
    ROOT / "app" / "templates",
    *(p for p in (ROOT / "app" / "modules").glob("*/templates")),
]

EXTENDS_RE = re.compile(r"{%-?\s*extends\s+['\"]([^'\"]+)['\"]")
HEADER_RE = re.compile(r"\b(page_header|page_shell)\b")
OK_RE = re.compile(r"shell-ok:\s*\S")
CONTAINER_RE = re.compile(r"\bcontainer\s+mx-auto\b")

# Layouts whose children are full pages and owe the platform a header.
PAGE_LAYOUTS = ("layouts/admin_base.html",)


def find_violations() -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for base in TEMPLATE_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.html")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if OK_RE.search(text):
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            extends = EXTENDS_RE.search(text)
            is_page = bool(extends and extends.group(1) in PAGE_LAYOUTS)
            if is_page and not HEADER_RE.search(text):
                violations.append((rel, "no page_header/page_shell"))
            if CONTAINER_RE.search(text):
                violations.append((rel, "container mx-auto wrapper"))
    return violations


def main() -> int:
    violations = find_violations()
    if "--list" in sys.argv:
        for rel, reason in violations:
            print(f"{rel}: {reason}")
    print(len(violations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
