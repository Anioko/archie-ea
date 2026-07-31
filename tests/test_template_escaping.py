"""User-supplied text must not reach the page as live HTML.

`{{ x | safe }}` turns autoescaping off for that expression. That is correct for
`| tojson | safe`, where the JSON serialiser has already escaped `<` to `\\u003c`
so the value is safe inside a <script> block and re-escaping it would corrupt the
JSON. It is wrong for anything else carrying user data.

The case that was live: admin_routes.py flashes

    flash("User {} successfully created".format(user.full_name()), "form-success")

and login.html / register.html pass get_flashed_messages() into form_macros.html,
which rendered `{{ message | safe }}`. A user whose name is an HTML payload
executes it in the browser of the next admin to create or invite one - stored
XSS, on a page reachable before authentication.

These tests assert the property (nothing user-supplied is rendered unescaped)
rather than the specific fix, so they keep holding if the macros are rewritten.
"""

import io
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader

TEMPLATES = "app/templates"
PAYLOAD = "<img src=x onerror=alert(document.domain)>"

# `| safe` is only defensible on one of these:
#   - tojson output: already escaped for <script>; re-escaping would break the JSON
#   - a string literal in the template: no user data can reach it
SAFE_EXPR = re.compile(r"tojson|^\s*[\"']|^\s*\(.*[\"']")

RAW_SAFE = re.compile(r"\{\{\s*([^}]*?)\|\s*safe\s*\}\}")


def _templates():
    for dirpath, _dirnames, filenames in os.walk(TEMPLATES):
        for name in filenames:
            if name.endswith(".html"):
                yield os.path.join(dirpath, name).replace(os.sep, "/")


def test_no_template_renders_a_bare_variable_unescaped():
    offenders = []
    for path in _templates():
        src = io.open(path, encoding="utf-8", errors="ignore").read()
        for match in RAW_SAFE.finditer(src):
            expr = match.group(1).strip()
            if SAFE_EXPR.search(expr):
                continue
            line = src[: match.start()].count("\n") + 1
            offenders.append("%s:%d  {{ %s|safe }}" % (path, line, expr[:60]))

    assert not offenders, (
        "%d expression(s) bypass autoescaping on a value that is not tojson output "
        "or a literal:\n  %s\n\nIf the value is genuinely trusted HTML, render it "
        "through a filter that says so; otherwise drop |safe."
        % (len(offenders), "\n  ".join(sorted(offenders)))
    )


def test_a_flash_message_carrying_a_payload_is_escaped():
    """End-to-end on the macro that was vulnerable."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    rendered = env.from_string(
        "<ul>{% for message in messages %}<li>{{ message }}</li>{% endfor %}</ul>"
    ).render(messages=["User %s successfully created" % PAYLOAD])
    assert "<img src=x" not in rendered
    assert "&lt;img" in rendered


def test_tojson_is_still_safe_to_mark_safe():
    """Guards against over-correcting.

    Stripping `| safe` from `| tojson | safe` would double-escape the JSON and
    break every page that embeds server data into a <script> block, so the rule
    above must keep permitting it - and tojson must keep earning that permission.
    """
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context():
        from flask import render_template_string

        out = render_template_string(
            "<script>const d = {{ items|tojson|safe }};</script>",
            items=[{"name": "</script><img src=x onerror=alert(1)>"}],
        )
    assert "</script><img" not in out, "tojson no longer escapes; |safe on it is unsafe"
    assert "\\u003c" in out


@pytest.mark.parametrize(
    "label,forbidden",
    [("<img src=x onerror=alert(1)>", "<"), ('<script>alert(1)</script>', "<")],
)
def test_mermaid_labels_cannot_carry_html(label, forbidden):
    """Diagram source is rendered with |safe into <div class="mermaid">.

    The browser parses that as HTML before Mermaid runs, so an element named with
    a payload would execute. Labels are user-named ArchiMate elements.
    """
    from app.services.mermaid_diagram_generator import MermaidDiagramGenerator

    escaped = MermaidDiagramGenerator()._escape_label(label)
    assert forbidden not in escaped, "angle brackets survive escaping: %r" % escaped
    assert ">" not in escaped
