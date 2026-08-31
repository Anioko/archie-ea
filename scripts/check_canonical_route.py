#!/usr/bin/env python
"""Two handlers on one URL, and no reader can tell which one answers.

ADR 0008 rule 3: one accessor per concept. This is the runtime half of it.

Measured 31 Aug 2026 by booting the app: 24 (URL, method) pairs are claimed by
more than one endpoint. Werkzeug resolves them by registration order, which is
decided in app/_bootstrap/blueprints.py and is invisible from either handler's
source. Whichever loses is dead code that still looks live -- it has a route
decorator, it has tests, and it never runs.

The clusters, and what they say about this codebase:

  7  /admin/solution-prompts/*   admin.* vs solution_prompt_admin.*
  4  /api/vendors/*              unified_vendors_api vs vendors_api
  4  /solutions/<id>/{slas,quality-attributes}  solution_design vs solution_sad
  2  /solutions/<id>/comments    THREE endpoints on one URL
  2  /api/solutions/<id>/issues* issue_tracking vs governance_api
  1  GET /health                 global_health_check vs health.health

The first cluster is the app/<domain> vs app/modules/<domain> duplication that
ADR 0004 describes, showing up as shadowed routes rather than as two files.
The /health pair is the sharper lesson: a /health disagreement was found, fixed
and deployed earlier the same day, and two handlers still claim the URL. The
symptom was treated; the duplicate was not.

WHY THIS MUST BOOT THE APP. A static scan of @route decorators cannot know the
url_prefix a blueprint is registered with, whether a USE_*_GUARDRAILS flag
selected a legacy or modules variant, or whether registration was skipped
because an import failed (init_blueprints logs and continues rather than
raising). A static version of this gate would be confidently wrong in exactly
the cases that matter. It is therefore in the same family as broken-surfaces
and the boot half of csrf-coverage, and like them it cannot run in CI's
dependency-free static job.

Compare on (rule, method), never on rule alone, and drop HEAD and OPTIONS:
Werkzeug adds those automatically, so keying on the rule reports 287 phantom
collisions against 24 real ones -- and a gate that cries wolf stops being read.

A RATCHET, expected to fall. Resolving one means deciding which handler is
authoritative and deleting or renaming the other; it is never just a rename.

Escape hatch: `canonical-route-ok: <reason>` on the losing handler's def line,
for a deliberate override -- say which endpoint wins and why.

    python scripts/check_canonical_route.py
    python scripts/check_canonical_route.py --count

Proven-against: a duplicate rule added to a blueprint -- the count rises by one
naming both endpoints, and returns when it is removed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"canonical-route-ok:[ \t]*\S")

# Werkzeug synthesises these; they are never a collision anyone authored.
IMPLICIT = {"HEAD", "OPTIONS"}


def _rules(root: str):
    sys.path.insert(0, root)
    from app import create_app

    application = create_app("testing")
    return application, list(application.url_map.iter_rules())


def _waived(application, endpoint: str) -> bool:
    """True when the losing handler's own source waives this."""
    import inspect

    view = application.view_functions.get(endpoint)
    if view is None:
        return False
    try:
        source = inspect.getsource(view)
    except (OSError, TypeError):
        return False
    return bool(ALLOW.search(source))


def collisions(rules, is_waived=lambda endpoint: False) -> list:
    """The collision logic, separated from booting so it can be proven.

    Kept independent of the application object on purpose: every other gate in
    this repository is pinned red-and-green against a synthetic tree by
    tests/test_gates_actually_fail.py, and a function that can only run by
    booting the whole product cannot be pinned that way. This one takes any
    iterable of Werkzeug rules, so the proof builds a two-line Flask app with a
    deliberate duplicate instead of a fake package tree.
    """
    claims = {}
    for rule in rules:
        for method in (rule.methods or set()) - IMPLICIT:
            claims.setdefault((str(rule), method), []).append(rule.endpoint)

    problems = []
    for (path, method), endpoints in sorted(claims.items()):
        unique = sorted(set(endpoints))
        if len(unique) < 2:
            continue
        if any(is_waived(e) for e in unique):
            continue
        problems.append(
            "%s %s [canonical-route] claimed by %d endpoints (%s) -- which one "
            "answers is decided by registration order, and the others are dead "
            "code that still looks live"
            % (method, path, len(unique), ", ".join(unique))
        )
    return problems


def scan(root: str) -> list:
    application, rules = _rules(root)
    return collisions(rules, lambda endpoint: _waived(application, endpoint))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    try:
        problems = scan(os.path.abspath(args.root))
    except Exception as exc:
        # Booting is the whole method here, so a boot failure must be loud
        # rather than reported as zero collisions.
        print("  could not boot the app to read its url_map: %s" % exc)
        print(-1)
        return 1
    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "Decide which endpoint is authoritative and remove or rename the\n"
                "other. If the shadowing is deliberate, put\n"
                "'canonical-route-ok: <reason>' on the losing handler naming the\n"
                "winner."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
