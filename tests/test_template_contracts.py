"""Static template contracts found by a live browser audit of every route.

Three defect classes were confirmed in the browser and are pinned here so they
cannot come back. All but one check is a pure source scan — no database, no
request — because the defects are properties of the templates themselves and a
scan covers *every* template rather than the handful a journey test happens to
render.

1. **CSRF** — a ``<form method="post">`` with no CSRF token submits to a 400.
   The feature is not degraded, it is completely dead for every user, and
   nothing on the page says so. Two forms had no token at all; two more wrote
   ``{{ csrf_token() }}`` bare, which renders the token as visible page text
   under no field name, so the POST carried nothing.
2. **Data honesty** — a nullable column piped through ``|title`` or ``|replace``
   is coerced with ``str()`` before it reaches the page, so a Python ``None``
   renders as the literal word "None". CLAUDE.md requires the em dash.
3. **Accessibility** — a page with no ``<h1>`` is announced with no name, and a
   second ``<main>`` landmark (with a duplicate ``id="main-content"``) makes
   both the skip link and landmark navigation ambiguous.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "app" / "templates"

JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)


def _markup(template: str) -> str:
    """Template source with Jinja comments stripped.

    The comments explaining these very fixes mention ``<h1>`` and ``<main>``,
    and Jinja never emits them, so counting them would make the test assert
    against its own documentation.
    """
    source = (TEMPLATE_ROOT / template).read_text(encoding="utf-8")
    return JINJA_COMMENT.sub("", source)


FORM_OPEN = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
POST_METHOD = re.compile(r"""method\s*=\s*["']?post""", re.IGNORECASE)


def _post_forms():
    """Yield (path, line, body) for every POST form in every template."""
    for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
        source = path.read_text(encoding="utf-8", errors="replace")
        for match in FORM_OPEN.finditer(source):
            if not POST_METHOD.search(match.group(0)):
                continue
            close = source.lower().find("</form>", match.end())
            body = source[match.end(): close if close != -1 else len(source)]
            line = source[: match.start()].count("\n") + 1
            yield path, line, body


def test_every_post_form_carries_a_csrf_token():
    """A POST form without a token is a 400 on submit — a dead feature."""
    offenders = [
        f"{path.relative_to(TEMPLATE_ROOT)}:{line}"
        for path, line, body in _post_forms()
        # form.hidden_tag() is WTForms' own token renderer and counts.
        if "csrf_token" not in body and "hidden_tag" not in body
    ]
    assert offenders == [], (
        "POST forms with no CSRF token — every submission returns 400:\n  "
        + "\n  ".join(offenders)
    )


def test_csrf_tokens_are_rendered_as_a_named_form_field():
    """``{{ csrf_token() }}`` on its own renders the token as page *text*.

    It looks correct in the source and is worse than useless at runtime: the
    token is printed to the screen and submitted under no field name, so
    Flask-WTF rejects the POST exactly as if it were absent. It must be a
    hidden input named ``csrf_token``.
    """
    bare = re.compile(r"^\s*\{\{\s*csrf_token\(\)\s*\}\}\s*$", re.MULTILINE)
    offenders = [
        str(path.relative_to(TEMPLATE_ROOT))
        for path in sorted(TEMPLATE_ROOT.rglob("*.html"))
        if bare.search(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert offenders == [], (
        "csrf_token() rendered as bare text instead of a hidden input named "
        "'csrf_token':\n  " + "\n  ".join(offenders)
    )


# Templates behind /ea-workflows/definitions, /integration/ and
# /integration/workflows, and the nullable columns each one printed.
NULLABLE_RENDERS = {
    "ea_workflows/definitions.html": [
        "defn.automation_level",
        "defn.adm_phase_name",
        "defn.workflow_description",
        "defn.workflow_category",
    ],
    "integration/dashboard.html": [
        "instance.status",
        "def.workflow_category",
        "def.workflow_type",
        "def.workflow_description",
        "def.execution_count",
    ],
    "integration/workflow_list.html": [
        "def.workflow_type",
        "def.automation_level",
        "def.workflow_description",
        "def.execution_count",
    ],
}


@pytest.mark.parametrize(
    ("template", "expression"),
    [(t, e) for t, exprs in NULLABLE_RENDERS.items() for e in exprs],
)
def test_nullable_columns_render_through_the_dash_filter(template, expression):
    """Every one of these printed the literal string "None" in the browser.

    The guard has to sit *first* in the filter chain: ``|title`` and
    ``|replace`` both stringify their input, so ``None|title`` is already the
    word "None" by the time any later filter runs.
    """
    source = (TEMPLATE_ROOT / template).read_text(encoding="utf-8")
    unguarded = re.findall(
        r"\{\{\s*" + re.escape(expression) + r"\s*(?:\|(?!dash)|\}\})",
        source,
    )
    assert not unguarded, (
        f"{template}: {{{{ {expression} }}}} is not piped through |dash, so a NULL "
        "renders as the literal text 'None' instead of an em dash"
    )


def test_dash_filter_never_emits_the_word_none(app):
    """The filter itself, exercised through the real Jinja environment."""
    render = app.jinja_env.from_string("{{ value|dash|replace('_', ' ')|title }}").render
    assert render(value=None) == "—"
    assert render(value="fully_automated") == "Fully Automated"


# Pages the audit found with no <h1>. /archimate/viewpoints is not listed: it
# 302s to the composer, so composer.html carries its heading too.
NEEDS_H1 = [
    "account/register.html",
    "ai_chat/entity_matching_chat_interface.html",
    "archimate/composer.html",
    "codegen/workflow_designer.html",
]


@pytest.mark.parametrize("template", NEEDS_H1)
def test_page_has_exactly_one_h1(template):
    count = len(re.findall(r"<h1\b", _markup(template), re.IGNORECASE))
    assert count == 1, (
        f"{template} has {count} <h1> elements; a screen reader announces no page "
        "name with none, and an ambiguous one with two"
    )


def test_register_page_does_not_duplicate_the_main_landmark():
    """public_base.html already renders <main id="main-content">.

    A second one gave the register page two main landmarks and two elements
    sharing an id, which breaks the "Skip to main content" link.
    """
    markup = _markup("account/register.html")
    assert "<main" not in markup
    assert 'id="main-content"' not in markup
