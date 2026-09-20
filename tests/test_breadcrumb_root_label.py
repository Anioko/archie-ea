"""Every breadcrumb trail must start at "Home", never "Dashboard".

Reported problem: most screens read "Home > ..." but Transformation Programmes and Vendor Catalogue read
"Dashboard > ...". Both point at the same destination, so a user learning to navigate by breadcrumb has no
consistent anchor.

Measured before the fix, not just the two screens the audit happened to see: 48 templates start their trail
with "Dashboard" and 135 with "Home". The callers pass their own first crumb, so the shared point is the
three macros that render a trail (page_header, page_shell, breadcrumb_nav); each now maps a first crumb of
"Dashboard" to "Home" through one small macro. A handful of templates hand-roll their own trail and print
the word directly; they are checked separately below, by scanning for the root anchor itself rather than
for any one macro's markup shape.

A fourth mechanism, components/breadcrumb.html (breadcrumb/breadcrumb_item/breadcrumb_separator), is used
by the analytics, batch-import and capability-map templates. It is out of scope here: every current caller
passes an icon-only root, never the word "Dashboard", so there is nothing to fix today, but it does not
route through crumb_label and a future caller that types "Dashboard" there would not be caught by it.

The macros are rendered with the real templates. No database is needed.
"""
import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
MACRO_FILES = {"components/breadcrumb_nav.html", "components/page_header.html", "macros/page_shell.html"}


def _env():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals["url_for"] = lambda *a, **kw: "/"
    return env


def _crumb_texts(html):
    """Visible text of each breadcrumb item, in order."""
    nav = re.search(r'<nav[^>]*aria-label="Breadcrumb".*?</nav>', html, re.S)
    assert nav, "no breadcrumb <nav> rendered"
    items = re.findall(r"<li\b.*?</li>", nav.group(0), re.S)
    texts = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", i)).strip() for i in items]
    return [t for t in texts if t]


def test_page_header_renders_a_dashboard_root_as_home():
    html = _env().from_string(
        "{% from 'components/page_header.html' import page_header %}"
        "{{ page_header(title='Vendor Catalogue', breadcrumbs=["
        "{'label': 'Dashboard', 'href': '/dashboard'}, {'label': 'Vendors'}]) }}"
    ).render()
    assert _crumb_texts(html) == ["Home", "Vendors"]


def test_page_shell_renders_a_dashboard_root_as_home():
    html = _env().from_string(
        "{% from 'macros/page_shell.html' import page_shell %}"
        "{{ page_shell(title='Workbench', breadcrumb=[('Dashboard', '/dashboard'), ('Workbench', none)]) }}"
    ).render()
    assert _crumb_texts(html) == ["Home", "Workbench"]


def test_breadcrumb_nav_renders_a_dashboard_root_as_home():
    html = _env().from_string(
        "{% from 'components/breadcrumb_nav.html' import breadcrumb_nav %}"
        "{{ breadcrumb_nav(items=[{'text': 'Dashboard', 'href': '/dashboard'}, {'text': 'Vendors'}]) }}"
    ).render()
    assert _crumb_texts(html) == ["Home", "Vendors"]


@pytest.mark.parametrize("macro,call", [
    ("components/page_header.html import page_header",
     "page_header(title='T', breadcrumbs=[{'label': 'Home', 'href': '/'}, {'label': 'Dashboard'}])"),
    ("macros/page_shell.html import page_shell",
     "page_shell(title='T', breadcrumb=[('Home', '/'), ('Dashboard', none)])"),
])
def test_only_the_first_crumb_is_renamed(macro, call):
    """A later crumb genuinely called "Dashboard" must be left alone."""
    html = _env().from_string("{% from '" + macro.split(" import ")[0] + "' import " + macro.split(" import ")[1]
                              + " %}{{ " + call + " }}").render()
    assert _crumb_texts(html) == ["Home", "Dashboard"]


def test_other_roots_are_not_renamed():
    html = _env().from_string(
        "{% from 'components/page_header.html' import page_header %}"
        "{{ page_header(title='T', breadcrumbs=[{'label': 'Admin', 'href': '/admin'}, {'label': 'Audit log'}]) }}"
    ).render()
    assert _crumb_texts(html) == ["Admin", "Audit log"]


def test_hand_rolled_trails_do_not_print_dashboard_as_the_root():
    """Templates that draw their own breadcrumb trail bypass the macros, so they are checked directly.

    Not scoped to `<nav aria-label="Breadcrumb">`: a hand-rolled trail may skip the `<nav>` wrapper
    entirely, omit `aria-label`, or spell it lowercase (`components/breadcrumb.html` does). What every
    trail actually shares is its root link: an anchor to `main.index` (the page "Home" and "Dashboard"
    both used to mean). Whatever wraps it, that anchor must not still read "Dashboard".
    """
    offenders = []
    root_link = re.compile(
        r"<a\s[^>]*href=\"\{\{\s*url_for\('main\.index'\)\s*\}\}\"[^>]*>\s*Dashboard\s*<",
    )
    for path in TEMPLATES.rglob("*.html"):
        rel = path.relative_to(TEMPLATES).as_posix()
        if rel in MACRO_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if root_link.search(text):
            offenders.append(rel)
    assert offenders == [], f"hand-rolled breadcrumb roots still say Dashboard: {offenders}"
