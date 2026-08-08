#!/usr/bin/env python
"""Front-end surfaces that cannot work, checked against the real route table.

Every other gate proves a page renders. None of them proves the things ON that
page go anywhere. This boots the app, takes its url_map, and resolves what the
templates and scripts actually point at.

Classes, each a distinct user-visible failure:

  dead-link      href="/x" where no route matches /x. The user clicks and gets
                 a 404 on a link the product itself rendered.
  dead-fetch     fetch('/api/x') where no route matches. The request 404s, and
                 combined with a silent `if (r.ok)` guard the user sees nothing
                 at all. (check_dead_interactions.py covers the guard; this
                 covers the target.)
  swallowed      catch blocks whose entire body is empty or a lone console call.
                 The failure happened, the user was told nothing, and no
                 telemetry recorded it.
  form-no-action <form> with neither an action nor a submit handler: pressing
                 Enter reloads the page and loses what was typed.
  forbidden-ui   alert() / confirm() in shipped UI code. DESIGN.md forbids both;
                 they are unstyled, unblockable and untestable.
  orphan-page    a template that extends a layout — so it is a PAGE, not a
                 partial — that no render_template() call names and no other
                 template includes. It cannot be reached by any URL. Either
                 dead code, or a feature that was built and never wired up.

Dynamic URLs (anything containing a template expression or string
concatenation) are skipped rather than guessed at — a false positive here costs
more attention than it saves.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
STATIC_JS = ROOT / "app" / "static" / "js"

_SKIP_PREFIX = ("http://", "https://", "//", "mailto:", "tel:", "#", "javascript:", "data:")



def _blank_comments(text: str, jinja: bool) -> str:
    """Blank comments while preserving offsets, so line numbers stay correct.

    Every remaining false positive in this checker was a comment: JS docstrings
    in core/04-toast.js and core/07-dialog.js documenting the REPLACEMENT for
    alert()/confirm(), and Jinja `{# ... #}` blocks in components/drawer.html and
    macros/form_macros.html showing example <form> markup. Documentation that
    names an anti-pattern is not an instance of it — flagging it trains readers
    to ignore the checker, which is the only thing that makes a checker useless.
    """
    out = list(text)

    def blank(a, b):
        for k in range(a, min(b, len(out))):
            if out[k] != "\n":
                out[k] = " "

    spans = []
    i, n = 0, len(text)
    while i < n:
        if jinja and text.startswith("{#", i):
            j = text.find("#}", i + 2)
            j = n if j == -1 else j + 2
            spans.append((i, j))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            spans.append((i, j))
            i = j
        elif text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j == -1 else j
            spans.append((i, j))
            i = j
        else:
            i += 1
    for a, b in spans:
        blank(a, b)
    return "".join(out)


def _route_matcher():
    """Return a predicate that says whether a concrete path resolves to a route."""
    os.environ.setdefault("FLASK_CONFIG", "testing")
    sys.path.insert(0, str(ROOT))
    from app import create_app

    app = create_app("testing")
    rules = list(app.url_map.iter_rules())

    # Convert each rule into a regex. <path:x> matches slashes; every other
    # converter does not. Collapsing both to [^/]+ made every /static/vendor/...
    # link look dead when the file was there all along — a scanner that cries
    # wolf costs more attention than it saves, so the distinction matters.
    patterns = []
    for rule in rules:
        pat = re.escape(rule.rule)
        pat = re.sub(r"\<path:[^>]+\>", ".+", pat)
        pat = re.sub(r"\<[^>]+\>", "[^/]+", pat)
        patterns.append(re.compile("^" + pat.rstrip("/") + "/?$"))

    def resolves(path: str) -> bool:
        p = path.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
        return any(rx.match(p) for rx in patterns)

    return resolves, len(rules)


def _is_dynamic(url: str) -> bool:
    return any(t in url for t in ("{{", "{%", "${", "' +", '" +', "+ '", '+ "', "<%"))


def scan() -> dict[str, list[str]]:
    resolves, _n = _route_matcher()
    out: dict[str, list[str]] = {k: [] for k in
                                ("dead-link", "dead-fetch", "swallowed",
                                 "form-no-action", "forbidden-ui", "orphan-page")}

    html = sorted(TEMPLATES.rglob("*.html"))
    js = sorted(STATIC_JS.rglob("*.js"))

    href_re = re.compile(r'href\s*=\s*"([^"]+)"')
    fetch_re = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")
    form_re = re.compile(r"<form\b([^>]*)>", re.I)
    swallow_re = re.compile(r"catch\s*\([^)]*\)\s*\{\s*(?:/\*.*?\*/\s*)?(?:console\.\w+\([^;]*\);?\s*)?\}",
                            re.S)
    forbidden_re = re.compile(r"(?<![\w.])(alert|confirm)\s*\(")

    def rel(p): return p.relative_to(ROOT).as_posix()
    def line_of(text, idx): return text[:idx].count("\n") + 1

    for path in html:
        text = _blank_comments(path.read_text(encoding="utf-8", errors="ignore"), jinja=True)
        for m in href_re.finditer(text):
            url = m.group(1).strip()
            if not url or url.startswith(_SKIP_PREFIX) or _is_dynamic(url):
                continue
            if not url.startswith("/"):
                continue
            if not resolves(url):
                out["dead-link"].append(
                    "%s:%d: dead-link: href=\"%s\" matches no route — the product "
                    "renders a link to its own 404" % (rel(path), line_of(text, m.start()), url))
        for m in form_re.finditer(text):
            attrs = m.group(1)
            if "action=" in attrs or "@submit" in attrs or "onsubmit" in attrs:
                continue
            if 'id="' not in attrs:      # a handler may bind by id; only flag anonymous forms
                out["form-no-action"].append(
                    "%s:%d: form-no-action: <form> with no action and no submit handler — "
                    "Enter reloads the page and discards the input"
                    % (rel(path), line_of(text, m.start())))

    for path in html + js:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = _blank_comments(raw, jinja=path.suffix == ".html")
        for m in fetch_re.finditer(text):
            url = m.group(1).strip()
            if not url.startswith("/") or _is_dynamic(url):
                continue
            # The literal may be only the PREFIX of a concatenated URL:
            #     fetch('/ai-chat/approvals/' + id + '/approve')
            # _is_dynamic sees only the captured substring, in which the `+`
            # does not appear — so every such call was reported as a dead route
            # at its bare prefix. Look past the closing quote instead.
            after = text[m.end():m.end() + 12].lstrip()
            if after.startswith(("+", "$", "`")):
                continue
            if not resolves(url):
                out["dead-fetch"].append(
                    "%s:%d: dead-fetch: fetch(\"%s\") matches no route — the request 404s"
                    % (rel(path), line_of(text, m.start()), url))
        # Deliberately the RAW text, not the comment-blanked copy: a catch
        # containing only a comment is DOCUMENTED intent, which is materially
        # different from a bare `catch {}`. Blanking the comment first turned
        # every considered no-op into an ignored one and inflated this by 27.
        for m in swallow_re.finditer(raw):
            out["swallowed"].append(
                "%s:%d: swallowed: catch block tells neither the user nor the logs"
                % (rel(path), line_of(text, m.start())))
        for m in forbidden_re.finditer(text):
            out["forbidden-ui"].append(
                "%s:%d: forbidden-ui: %s() — DESIGN.md requires Platform.toast/modal"
                % (rel(path), line_of(text, m.start()), m.group(1)))


    # ── orphan-page ─────────────────────────────────────────────────────────
    # Extending a layout is what distinguishes a page from a partial or a macro
    # file. A page nothing renders and nothing includes has no URL at all.
    #
    # Verified against dynamic dispatch before trusting this: the whole codebase
    # contains exactly ONE render_template() with a variable template name
    # (solution_narrative_service.py, for narrative documents), so a template
    # cannot be reached by indirection that this check cannot see.
    py_src = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (ROOT / "app").rglob("*.py")
    )
    tpl_src = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in TEMPLATES.rglob("*.html")
    )
    extends_layout = re.compile(r"{%-?\s*extends\s+['\"]layouts/")
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not extends_layout.search(text):
            continue                      # partial, macro file, or component
        name = path.relative_to(TEMPLATES).as_posix()
        if name in py_src or name in tpl_src:
            continue                      # rendered by a route, or included
        out["orphan-page"].append(
            "%s:1: orphan-page: extends a layout but no route renders it and no "
            "template includes it — the page has no URL" % path.relative_to(ROOT).as_posix())

    return {k: sorted(set(v)) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--kind")
    args = ap.parse_args()

    found = scan()
    if args.kind:
        found = {args.kind: found.get(args.kind, [])}

    total = sum(len(v) for v in found.values())
    if args.count:
        print(total)
        return 0
    for kind, items in found.items():
        if not items:
            continue
        print("\n=== %s (%d) ===" % (kind, len(items)))
        for i in items:
            print("  " + i)
    print("\n%d broken surface(s)." % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
