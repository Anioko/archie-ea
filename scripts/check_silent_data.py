#!/usr/bin/env python3
"""Server-side silent-empty: a failure returned as data.

`check_broken_surfaces.py --kind silent-empty` finds this shape in the front
end. This is the same defect one layer down, and nothing had ever looked for
it:

    except Exception:
        return []        # the caller cannot tell this from "no rows"
    except Exception:
        return 0         # ...or from a measured zero

CLAUDE.md: "Archie is a system of record: a screen that fabricates a plausible
value when the real one is missing is worse than one showing nothing, because
the user cannot tell the difference and acts on it." A service that answers a
database error with `[]` fabricates exactly that, and it does it below the UI
where no amount of front-end care can detect it.

The worst instances found when this was first run were in
`ai_chat/services/portfolio_context.py`, which grounds the AI assistant:
`_quick_completeness` answered an exception with `0`, so a database error
became "this solution is 0% complete" — asserted to the user in confident
prose by an LLM that had no way to know the number was invented.

SCOPE, and why it is drawn here
-------------------------------
Only **broad** handlers (`except Exception`, `except BaseException`, bare
`except:`) count. Narrow handlers are overwhelmingly deliberate control flow —

    try:    cap_id = int(raw)
    except ValueError:  pass        # fall through to the 404 below

— and flagging those 185 cases would bury the 43 that matter.

Only handlers that return an **empty collection or a number** count. A bare
`return None` usually means "not found", which callers already handle; an empty
list means "I looked and there was nothing", which is a claim about the data.

A handler that logs, re-raises, flashes or aborts is reporting the failure and
is not flagged, however it then returns.

Escape hatch: `silent-data-ok: <reason>` on the handler line or the line above.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"

_OK = re.compile(r"silent-data-ok:[ \t]*[A-Za-z0-9]")

# Names that mean the failure reached a log, a user, or the caller.
_REPORTS = ("log", "logger", "warn", "error", "exception", "critical",
            "capture", "flash", "abort", "sentry", "raygun")


def _serves_users(path: str) -> bool:
    """Routes and services only: code whose output reaches a user."""
    return ("/routes/" in path or path.endswith("_routes.py")
            or "/api/" in path or "/services/" in path
            or path.endswith("_service.py"))


def _is_broad(h: ast.ExceptHandler) -> bool:
    t = h.type
    if t is None:
        return True
    if isinstance(t, ast.Name) and t.id in ("Exception", "BaseException"):
        return True
    if isinstance(t, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id in ("Exception", "BaseException")
                   for e in t.elts)
    return False


def _reports(h: ast.ExceptHandler) -> bool:
    for n in ast.walk(h):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call):
            f, name = n.func, ""
            if isinstance(f, ast.Attribute):
                name = f.attr
                if isinstance(f.value, ast.Name):
                    name = f.value.id + "." + name
                elif isinstance(f.value, ast.Attribute):
                    name = f.value.attr + "." + name
            elif isinstance(f, ast.Name):
                name = f.id
            if any(k in name.lower() for k in _REPORTS):
                return True
    return False


def _empty_kind(node) -> str | None:
    """An empty COLLECTION or a number - values that read as measured data."""
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)) and v == 0:
            return "0"
        return None
    if isinstance(node, ast.List) and not node.elts:
        return "[]"
    if isinstance(node, ast.Dict) and not node.keys:
        return "{}"
    return None


def scan() -> list[str]:
    out: list[str] = []
    for p in sorted(APP.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if not _serves_users(rel):
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue                      # the `compile` gate owns syntax
        for h in ast.walk(tree):
            if not isinstance(h, ast.ExceptHandler):
                continue
            if not _is_broad(h) or _reports(h):
                continue
            body = [s for s in h.body
                    if not (isinstance(s, ast.Expr)
                            and isinstance(s.value, ast.Constant)
                            and isinstance(s.value.value, str))]
            if not body or not isinstance(body[-1], ast.Return):
                continue
            if len(body) > 3 or not all(
                    isinstance(s, (ast.Expr, ast.Assign, ast.Return)) for s in body):
                continue
            kind = _empty_kind(body[-1].value)
            if not kind:
                continue
            window = "\n".join(lines[max(0, h.lineno - 2):h.lineno])
            if _OK.search(window):
                continue
            out.append(
                "%s:%d: silent-data: a broad except returns %s - the caller "
                "cannot tell this from real data" % (rel, h.lineno, kind))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true", help="print only the total")
    args = ap.parse_args()
    hits = scan()
    if args.count:
        print(len(hits))
        return 0
    for h in hits:
        print("  " + h)
    print("\n%d silent-data handler(s)." % len(hits))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
