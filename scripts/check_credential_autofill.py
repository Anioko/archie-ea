#!/usr/bin/env python
"""A credential field without an autocomplete override invites a real password.

From the 30 Aug 2026 pre-release QA audit, Critical #1, observed live rather
than theorised:

    "on a fresh page load, Chrome's own autofill populated the Anthropic API key
     field (Admin -> API Settings) and the Salesforce Consumer Secret field with
     a genuine saved email address and password from the browser profile used
     for this test, because both password-type fields are missing an
     autocomplete override."

Chrome pattern-matches a text input followed by a password input as a login
form and offers a saved credential. It does not care that the label says "API
Key". An administrator who misses the autofill highlight submits their own
email and password as a third-party secret; the backend stores it and uses it
in real outbound calls to Anthropic or Salesforce.

It fired even where the inputs were not wrapped in a <form>, so this is not
avoidable by markup structure. The fix was already proven inside this same
codebase before the audit ran -- the Power Platform integration's client_secret
carries autocomplete="new-password" and never autofilled under identical
testing.

The audit found two instances because two were reachable from its route list. A
full-tree scan found FIVE unprotected password inputs in templates and
NINETEEN WTForms PasswordField definitions with no render_kw at all. That gap
between "what a careful tester reached" and "what exists" is the reason this is
a gate and not a fix.

Two rules:

1. Every <input type="password"> in a template carries an autocomplete value.
2. Every WTForms PasswordField declares render_kw with an autocomplete key.

The right value is contextual, so this gate checks that a choice was MADE, not
which one: `current-password` where the user's own password belongs and a
password manager should fill; `new-password` on any third-party secret, and on
any field that sets a new password.

Escape hatch: `autofill-ok: <reason>` on the line.

    python scripts/check_credential_autofill.py
    python scripts/check_credential_autofill.py --count

Proven-against: autocomplete removed from the Salesforce Consumer Secret input
and render_kw removed from APISettingsForm.api_key -- red at 2 naming both,
green at 0 when restored.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = re.compile(r"autofill-ok:[ \t]*\S")
INPUT_TAG = re.compile(r"<input\b[^>]*>", re.S)


def _template_dirs(root: str):
    yield os.path.join(root, "app", "templates")
    modules = os.path.join(root, "app", "modules")
    if os.path.isdir(modules):
        for name in sorted(os.listdir(modules)):
            candidate = os.path.join(modules, name, "templates")
            if os.path.isdir(candidate):
                yield candidate


def scan(root: str) -> list[str]:
    problems = []

    for base in _template_dirs(root):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in sorted(filenames):
                if not filename.endswith((".html", ".jinja", ".jinja2")):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                try:
                    with open(path, encoding="utf-8") as fh:
                        source = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
                for match in INPUT_TAG.finditer(source):
                    tag = match.group(0)
                    if 'type="password"' not in tag or "autocomplete=" in tag:
                        continue
                    if ALLOW.search(tag):
                        continue
                    line = source[:match.start()].count("\n") + 1
                    problems.append(
                        "%s:%d [credential-autofill] <input type=\"password\"> with no "
                        "autocomplete -- Chrome will offer a saved email and password "
                        "here" % (rel, line)
                    )

    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "app")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                if "PasswordField" not in source:
                    continue
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            lines = source.split("\n")
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                    continue
                func = node.value.func
                if getattr(func, "id", getattr(func, "attr", "")) != "PasswordField":
                    continue
                render_kw = next(
                    (k for k in node.value.keywords if k.arg == "render_kw"), None
                )
                segment = ast.get_source_segment(source, node) or ""
                if render_kw is not None and "autocomplete" in (
                    ast.get_source_segment(source, render_kw.value) or ""
                ):
                    continue
                if ALLOW.search(segment):
                    continue
                name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else "?"
                problems.append(
                    "%s:%d [credential-autofill] PasswordField %r has no "
                    "render_kw autocomplete -- it renders as a bare password input"
                    % (rel, node.lineno, name)
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
                'Add autocomplete: "current-password" where the user\'s OWN password\n'
                'belongs and a manager should fill it; "new-password" on any third-party\n'
                'secret (API key, client secret, token) and on any set-a-new-password\n'
                "field. Or append 'autofill-ok: <reason>'."
            )
    print(len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
