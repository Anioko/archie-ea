#!/usr/bin/env python
"""Find controls that look like they work and do nothing.

Three classes, all invisible to every other gate because the template compiles,
the route returns 200, and the button is present and styled:

  silent-fetch    `if (r.ok) { ... }` with no else. A 500, a 403 or a rejected
                  CSRF token produces no message, no error, no state change —
                  the user clicks and nothing happens. CLAUDE.md names this
                  directly: fetch does not reject on 4xx/5xx.

  dead-handler    `@click="foo()"` / `onclick="foo()"` where foo is defined
                  nowhere the page loads. Alpine reports it as a console warning
                  and swallows it; a plain onclick throws into the console. Both
                  look identical to a user: nothing happens.

  dead-action     `data-action="x"` with no matching consumer in any delegated
                  handler, so the click is collected and dropped.

Reported per finding with file:line so a fix is a fix, not a hunt.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
STATIC_JS = ROOT / "app" / "static" / "js"

# `if (<something>.ok)` / `if (resp.ok)` opening a block with no `else` before it closes.
_OK_GUARD = re.compile(r"if\s*\(\s*(?:!\s*)?([A-Za-z_$][\w$]*)\.ok\s*\)")

# Alpine and inline handlers that call a bare function: @click="foo()" / onclick="foo(...)"
_HANDLER = re.compile(r'(?:@click(?:\.\w+)*|onclick)\s*=\s*"([A-Za-z_$][\w$]*)\s*\(')

_DATA_ACTION = re.compile(r'data-action\s*=\s*"([a-z0-9-]+)"')

# Things that are defined elsewhere by design, or are not page functions at all.
_HANDLER_ALLOW = {
    "confirm", "alert", "print", "open", "close", "submit", "reset", "focus",
    "$dispatch", "$refs", "$el", "$store", "$nextTick", "$watch",
}


def _strip_comments(text: str) -> str:
    """Blank out // and /* */ comments, preserving offsets so line numbers hold.

    A comment describing this very anti-pattern matched as an instance of it —
    governance/dashboard.html documented a fix and was reported as the bug.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def _js_sources() -> str:
    """Every JS file that could define a global handler, concatenated once."""
    parts = []
    for path in sorted(STATIC_JS.rglob("*.js")):
        parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _defines(name: str, haystack: str) -> bool:
    return bool(
        re.search(r"\bfunction\s+%s\s*\(" % re.escape(name), haystack)
        or re.search(r"\b(?:const|let|var)\s+%s\s*=" % re.escape(name), haystack)
        or re.search(r"\bwindow\.%s\s*=" % re.escape(name), haystack)
        or re.search(r"\b%s\s*[:(]" % re.escape(name), haystack)   # object method / Alpine
    )


def _block_has_else(text: str, start: int) -> bool:
    """Walk the braces of the if-block at `start` and look for an else after it."""
    open_at = text.find("{", start)
    if open_at == -1:
        # single-statement if; an else would follow on the same or next statement
        tail = text[start:start + 400]
        return bool(re.search(r"\belse\b", tail))
    depth, i = 0, open_at
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    tail = text[i:i + 120]
    return bool(re.match(r"\s*\}?\s*else\b", tail) or re.search(r"^\s*else\b", tail))


def scan() -> list[str]:
    findings: list[str] = []
    all_js = _js_sources()

    files = sorted(TEMPLATES.rglob("*.html")) + sorted(STATIC_JS.rglob("*.js"))

    # ── silent-fetch ────────────────────────────────────────────────────────
    for path in files:
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        if ".ok" not in text:
            continue
        for m in _OK_GUARD.finditer(text):
            if m.group(0).lstrip("if").strip().startswith("(!"):
                continue  # `if (!r.ok)` is the correct form
            if "!" in text[m.start():m.start() + 8]:
                continue
            if _block_has_else(text, m.end()):
                continue
            line = text[:m.start()].count("\n") + 1
            findings.append(
                "%s:%d: silent-fetch: `if (%s.ok)` with no else — a failed request "
                "produces no message and no state change"
                % (path.relative_to(ROOT).as_posix(), line, m.group(1))
            )

    # ── silent-then: fetch(...).then(...) that never inspects .ok ───────────
    # Raw fetch only. Platform.fetch (app/static/js/core/03-fetch.js) already
    # checks !response.ok, extracts the server's message and toasts it, so a
    # Platform.fetch().then() chain is CORRECT — matching it flagged 400+
    # working call sites and buried the real ones. The bug is bypassing the
    # wrapper, not using it.
    _THEN = re.compile(r"(?<![.\w])fetch\(([^;]{0,400}?)\)\s*\.then\(", re.S)
    for path in files:
        text = _strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        for m in _THEN.finditer(text):
            # Look far enough to see the whole promise chain, and treat three
            # things as handling the failure:
            #   .ok / .status   an explicit HTTP check
            #   .catch(         a rejection handler (r.json() on an HTML error
            #                   page rejects, so this does catch 5xx)
            #   data.success /  the codebase's JSON convention: the server
            #   .error          returns {success: false, error: ...} and the
            #                   chain branches on it
            # Without this the check flagged 274 sites, most of which report
            # failure perfectly well — burying the ones that do not.
            tail = text[m.end():m.end() + 1200]
            if any(t in tail for t in (".ok", ".status", ".catch(",
                                       "success", ".error", "errorMsg")):
                continue
            line = text[:m.start()].count("\n") + 1
            findings.append(
                "%s:%d: silent-then: fetch().then() never inspects .ok — a failed "
                "request runs the success path anyway"
                % (path.relative_to(ROOT).as_posix(), line))

    # ── dead-handler ────────────────────────────────────────────────────────
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _HANDLER.finditer(text):
            name = m.group(1)
            if name in _HANDLER_ALLOW:
                continue
            if _defines(name, text) or _defines(name, all_js):
                continue
            line = text[:m.start()].count("\n") + 1
            findings.append(
                "%s:%d: dead-handler: `%s()` is called but defined nowhere the "
                "page loads — the click does nothing"
                % (path.relative_to(ROOT).as_posix(), line, name)
            )

    # ── dead-action ─────────────────────────────────────────────────────────
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _DATA_ACTION.finditer(text):
            verb = m.group(1)
            # Look for the verb quoted as a STRING anywhere (a delegated
            # handler matches on it), rather than subtracting occurrences of the
            # attribute — that subtraction also removed the handler's own
            # querySelector('[data-action="verb"]') and made a working handler
            # invisible.
            quoted = ("'%s'" % verb, '"%s"' % verb)
            consumed = any(q in text for q in quoted) or any(q in all_js for q in quoted)
            if consumed:
                continue
            line = text[:m.start()].count("\n") + 1
            findings.append(
                "%s:%d: dead-action: data-action=\"%s\" has no consumer — the "
                "click is collected and dropped" % (path.relative_to(ROOT).as_posix(), line, verb)
            )

    return sorted(set(findings))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--kind", choices=["silent-fetch", "silent-then", "dead-handler", "dead-action"])
    args = ap.parse_args()

    findings = scan()
    if args.kind:
        findings = [f for f in findings if ": %s:" % args.kind in f]

    if args.count:
        print(len(findings))
        return 0
    for f in findings:
        print(f)
    print("\n%d dead or silent interaction(s)." % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
