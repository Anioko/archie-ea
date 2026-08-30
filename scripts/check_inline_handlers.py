#!/usr/bin/env python
"""An inline event handler attribute, which this app's CSP refuses to run.

Archie ships an enforcing Content-Security-Policy whose script-src is

    script-src 'self' 'nonce-...' 'strict-dynamic'

with no 'unsafe-inline' and no 'unsafe-hashes'. Under that policy the browser
REFUSES to execute an inline event handler attribute -- onclick=, onchange=,
onsubmit= and the rest -- and a nonce does not help, because nonces do not
apply to attributes. The control renders, looks correct, and does nothing. The
only trace is a console line nobody is reading:

    Refused to execute inline event handler because it violates the following
    Content Security Policy directive: "script-src 'self' 'nonce-...'"

Found on 30 Aug 2026 by driving the tech radar in a real browser: a classified
technology's ring could never be changed, because the reclassify control was
a <select onchange="this.form.submit()"> and the onchange never fired. The
sweep that followed found fifteen more, including:

  * six destructive forms carrying
    onsubmit="return Platform.modal.confirmSubmit(event, 'Delete ...')" --
    so the confirmation dialog never appeared and Delete submitted straight
    through, unconfirmed, on organisations, applications and ARB sessions;
  * the admin team page's role <select onchange="this.form.submit()">, so
    changing a colleague's role silently did nothing;
  * the SSO settings protocol switch, so choosing SAML never revealed the
    SAML fields.

No other gate could see any of it. The templates parse, the JS is valid, every
route returns 200, and the handlers are syntactically fine -- they are simply
never run.

The CSP-safe replacements, both already wired in app/static/js/ui/modal.js:

    <form data-confirm="Delete X? This cannot be undone.">
    <select data-autosubmit>

or bind the listener in a <script> block, which IS nonce'd (template-authored
script tags are nonce'd at compile time -- app/_bootstrap/security.py).

Alpine's @click / @submit are NOT inline handlers in this sense: Alpine reads
them as directives and evaluates them through the CSP-safe evaluator in
app/static/js/csp/alpine-csp-adapter.js, so they are not matched here.

Escape hatch: `inline-handler-ok: <reason>` on the line, for markup that is
never served under the app's CSP (an emailed HTML body, a generated artefact).

    python scripts/check_inline_handlers.py            # list them
    python scripts/check_inline_handlers.py --count    # trailing line = count

Proven-against: data-autosubmit reverted to onchange="this.form.submit()" in
app/templates/admin/team.html -- red at 1 on that line, green at 0 when
restored. Confirmed it does NOT match Alpine @click/@submit or a Jinja macro's
onclick= keyword argument, against the five real instances of the latter.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every handler attribute the HTML spec defines that a page here plausibly uses.
EVENTS = (
    "abort|blur|cancel|canplay|change|click|close|contextmenu|copy|cut|dblclick|"
    "drag|dragend|dragenter|dragleave|dragover|dragstart|drop|durationchange|"
    "ended|error|focus|focusin|focusout|input|invalid|keydown|keypress|keyup|"
    "load|loadeddata|loadstart|mousedown|mouseenter|mouseleave|mousemove|"
    "mouseout|mouseover|mouseup|paste|play|pause|progress|reset|resize|scroll|"
    "search|seeked|select|submit|toggle|touchend|touchmove|touchstart|"
    "transitionend|wheel"
)

# Must be preceded by whitespace INSIDE a tag, so a Jinja macro keyword argument
# -- stat_card(..., onclick="setStatusFilter('')") -- is not matched: that value
# is rendered by the macro as Alpine's @click, not as an attribute. Requiring an
# open tag before it on the same line is what separates the two.
HANDLER = re.compile(
    r"<[a-zA-Z][a-zA-Z0-9-]*\b[^>]*?\son(?:%s)\s*=" % EVENTS
)
ALLOW = re.compile(r"inline-handler-ok:[ \t]*\S")

TEMPLATE_DIRS = ("app/templates",)


def template_files(root: str):
    seen = set()
    roots = [os.path.join(root, d) for d in TEMPLATE_DIRS]
    modules = os.path.join(root, "app", "modules")
    if os.path.isdir(modules):
        for name in sorted(os.listdir(modules)):
            candidate = os.path.join(modules, name, "templates")
            if os.path.isdir(candidate):
                roots.append(candidate)
    for base in roots:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in sorted(filenames):
                if not filename.endswith((".html", ".jinja", ".jinja2")):
                    continue
                path = os.path.join(dirpath, filename)
                if path not in seen:
                    seen.add(path)
                    yield path


def scan(root: str) -> list:
    findings = []
    for path in template_files(root):
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, 1):
            if ALLOW.search(line):
                continue
            match = HANDLER.search(line)
            if match:
                attribute = match.group(0).rsplit(" ", 1)[-1].rstrip("=")
                findings.append(
                    (os.path.relpath(path, root).replace(os.sep, "/"), number, attribute)
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", action="store_true", help="print only the count")
    parser.add_argument("--root", default=ROOT, help="tree to scan")
    args = parser.parse_args()

    findings = scan(os.path.abspath(args.root))
    if not args.count:
        for path, number, attribute in findings:
            print(
                "  %s:%d  [inline-handler] %s= is refused by the app's CSP and never runs"
                % (path, number, attribute)
            )
        if findings:
            print()
            print(
                "Use the CSP-safe equivalents wired in app/static/js/ui/modal.js --\n"
                "  <form data-confirm=\"...\">   for a confirmation before submit\n"
                "  <select data-autosubmit>     for submit-on-change\n"
                "-- or bind the listener in a <script> block, which is nonce'd at\n"
                "compile time. Alpine's @click / @submit are also fine. If this markup\n"
                "is never served under the app's CSP, append 'inline-handler-ok: <reason>'."
            )
    print(len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
