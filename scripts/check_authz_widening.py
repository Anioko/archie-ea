#!/usr/bin/env python
"""A role must never be granted from a field the user's own record carries.

On 30 Aug 2026 a read-only Viewer could create and delete ArchiMate elements.
`require_roles` had been taught to read `enterprise_role` -- for a good reason,
so a business_architect was not 403ed on the capability CRUD endpoints that
exist for that persona -- and it contributed the coarse tier the persona stands
for: any "*_architect" value added "architect" to the caller's role set, with no
reference to what the account was permitted to do.

Nearly every user carries an enterprise_role, because it is what drives the
sidebar. So the Viewer role -- permissions=0, added by A-03 precisely so an
account can read and never write -- was defeated on every
@require_roles("admin", "architect") route in the product. POST
/architecture/elements returned 201 where it must return 403.

The lesson, and the rule this gate holds:

    enterprise_role says what someone DOES.
    Role says what they are ALLOWED to do.
    A persona label must never manufacture the second from the first.

Concretely: inside a permission decorator, a statement that adds to the set of
roles the caller is credited with must not derive that value from a user
attribute unless the same function also consults `Permission` -- the bitfield
`user.can()` checks, which a Viewer fails by construction.

The escalation was caught by two hand-written regression tests
(tests/test_r32_ai_permission_gate.py, TestV04RegressionProtections). This gate
generalises them: the tests prove two routes, this proves the mechanism.

Escape hatch: `authz-widening-ok: <reason>` on the line.

    python scripts/check_authz_widening.py
    python scripts/check_authz_widening.py --count

Proven-against: the whole `may_write` / `may_administer` block (including its
`from app.models.user import Permission` import) removed from require_roles in
app/_decorators_base.py, reinstating the escalation -- red naming require_roles,
green at 0 when restored. Note the first probe left the import in place and the
gate correctly stayed green: it keys on the permission check being present, so
the known-bad must remove the check, not just the guard.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"authz-widening-ok:[ \t]*\S")

# Files that decide what a caller is allowed to do.
DECIDERS = ("app/_decorators_base.py", "app/decorators/requires_role.py",
            "app/middleware/tenant_decorators.py")

# A value read off the acting user's own record. Self-asserted, so it may
# describe them but must never authorise them.
USER_SOURCED = re.compile(
    r"getattr\(\s*current_user\s*,|current_user\.(enterprise_role|role_archetype|is_platform_admin)"
)


def scan(root: str) -> list[str]:
    problems = []
    for rel in DECIDERS:
        # A decorator is three nested functions, so one defect matches all three
        # scopes. The file IS the decision point; report it once.
        reported = False
        path = os.path.join(root, *rel.split("/"))
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.get_source_segment(source, func) or ""
            # Does this function credit the caller with a role at all?
            widens = re.search(r"\.add\(|\.update\(|user_roles\s*=", body)
            if not widens:
                continue
            if not USER_SOURCED.search(body):
                continue
            if ALLOW.search(body):
                continue
            # Consulting the permission bitfield is what makes it safe.
            if re.search(r"Permission\.\w+|\.can\(", body):
                continue
            if reported:
                continue
            reported = True
            problems.append(
                "%s:%d [authz-widening] %s() credits the caller with a role taken from "
                "their own user record without consulting Permission -- a persona label "
                "must not manufacture permission" % (rel, func.lineno, func.name)
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args()
    problems = scan(os.path.abspath(args.root))
    if not args.count:
        for line in problems:
            print("  " + line)
        if problems:
            print()
            print(
                "Gate the contribution on user.can(Permission.GENERAL) / ADMINISTER, or\n"
                "append 'authz-widening-ok: <reason>' if the value is not user-settable."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
