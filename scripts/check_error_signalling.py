#!/usr/bin/env python3
"""API error paths that answer a failure with success.

This is the shape that quietly undermines every front-end fix in the
dead-control audit. Client code now correctly does::

    if (!response.ok) throw new Error(...)

and that check is worth nothing if the server catches the exception and returns
HTTP 200. Flask defaults to 200 whenever a view returns a bare ``jsonify(...)``,
so both of these tell the browser everything went fine::

    except Exception:
        return jsonify({"items": []})            # 200 OK, "there are none"

    except Exception:
        return jsonify({"success": True, ...})   # explicitly claims success

The front end cannot detect either, however carefully it is written. That is
what makes this worth its own gate rather than a note in a review: it is the
one defect the layer above is structurally unable to compensate for.

Classes
-------
success-true-on-error   the payload literally says success/ok after an except
empty-payload-200       an empty collection returned at 200 from an except
status-200-on-error     any other response at 200 from an except

Calibration
-----------
A DYNAMIC status expression (``e.status_code``, ``HTTPStatus.NOT_FOUND``) is the
developer deliberately propagating a code this cannot evaluate statically, and
is not flagged - treating it as 200 reported five correct handlers in
vendor_analysis_routes.py, each already returning ``success: False`` with the
exception's own status.

An explicit 4xx/5xx is correct and never flagged: the failure IS signalled.

Escape hatch: ``error-signalling-ok: <reason>`` on the return or the line above.
A fail-closed gate verdict is the usual legitimate case - a policy check that
denies on error is answering the question honestly.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"

_OK = re.compile(r"error-signalling-ok:[ \t]*[A-Za-z0-9]")

# Only API responses. render_template in an except handler is a page-level
# concern with different remedies (render an error state, not an empty one).
_API_FUNCS = {"jsonify", "success_response", "make_response"}


def _response_call(node):
    if not isinstance(node, ast.Call):
        return None
    f = node.func
    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
    return name if name in _API_FUNCS else None


def _split_status(ret: ast.Return):
    v = ret.value
    if isinstance(v, ast.Tuple) and len(v.elts) >= 2:
        status = v.elts[1]
        if isinstance(status, ast.Constant):
            return v.elts[0], status.value
        return v.elts[0], "dynamic"
    return v, None


def _claims_success(call) -> bool:
    for n in ast.walk(call):
        if isinstance(n, ast.Dict):
            for k, val in zip(n.keys, n.values):
                if not isinstance(k, ast.Constant):
                    continue
                if k.value in ("success", "ok") and isinstance(val, ast.Constant) and val.value is True:
                    return True
                if k.value == "status" and isinstance(val, ast.Constant) and val.value in ("ok", "success"):
                    return True
    return False


def _has_empty_collection(call) -> bool:
    for n in ast.walk(call):
        if isinstance(n, ast.Dict):
            for val in n.values:
                if (isinstance(val, ast.List) and not val.elts) or \
                   (isinstance(val, ast.Dict) and not val.keys):
                    return True
    return False


def scan() -> list[str]:
    out: list[str] = []
    for p in sorted(APP.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        src = p.read_text(encoding="utf-8", errors="ignore")
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        seen: set[int] = set()
        for h in ast.walk(tree):
            if not isinstance(h, ast.ExceptHandler):
                continue
            for stmt in ast.walk(h):
                if not isinstance(stmt, ast.Return) or stmt.value is None:
                    continue
                call, code = _split_status(stmt)
                if not _response_call(call):
                    continue
                if code == "dynamic" or (isinstance(code, int) and code >= 400):
                    continue
                if code not in (None, 200):
                    continue
                window = "\n".join(lines[max(0, stmt.lineno - 2):stmt.lineno])
                if _OK.search(window):
                    continue
                if stmt.lineno in seen:
                    continue
                seen.add(stmt.lineno)
                if _claims_success(call):
                    kind, why = "success-true-on-error", "the payload claims success"
                elif _has_empty_collection(call):
                    kind, why = "empty-payload-200", "an empty collection is returned at 200"
                else:
                    kind, why = "status-200-on-error", "the response is 200"
                out.append("%s:%d: %s: %s, so the client's !response.ok check "
                           "cannot see the failure" % (rel, stmt.lineno, kind, why))
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
    print("\n%d error path(s) that do not signal failure." % len(hits))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
