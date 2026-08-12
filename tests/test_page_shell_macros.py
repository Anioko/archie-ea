"""Render tests for the screen-system macros (macros/page_shell.html).

These four macros — page_shell, empty_state, stat_card, section_card — become
the only sanctioned page header / empty state / stat card / section container
for every screen rebuilt in docs/superpowers/plans/2026-08-12-shell-wave-1.md.
Later tasks in that plan consume these exact signatures, so these tests pin
both the signature and the rendered shape (single <h1>, breadcrumb nav, dash
for missing values, variant sizing) that those callers rely on.
"""

from __future__ import annotations

import re

from flask import render_template_string


def _render(app, template, **ctx):
    with app.test_request_context("/"):
        return render_template_string(template, **ctx)


def test_page_shell_renders_single_h1_and_breadcrumb_nav(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import page_shell %}
        {{ page_shell('Applications', subtitle='Portfolio', breadcrumb=[('Home', '/'), ('Applications', None)]) }}
        """,
    )
    assert html.count("<h1") == 1
    assert "Applications" in html
    assert re.search(r'<h1[^>]*>\s*Applications', html)
    assert html.count('<nav aria-label="Breadcrumb"') == 1


def test_page_shell_actions_and_h1_share_flex_row(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import page_shell %}
        {% macro actions() %}<a href="/new">New</a>{% endmacro %}
        {{ page_shell('Applications', actions_caller=actions) }}
        """,
    )
    # The h1 and the actions block must both live inside the same
    # "flex items-start justify-between" row container.
    row_match = re.search(
        r'<div class="flex items-start justify-between gap-4">(.*?)</div>\s*'
        r'(?:<ul|\{%|$)',
        html,
        re.DOTALL,
    )
    assert row_match, html
    row_html = row_match.group(1)
    assert "<h1" in row_html
    assert 'href="/new"' in row_html


def test_page_shell_tabs_render(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import page_shell %}
        {{ page_shell('Applications', tabs=[('Overview', '/a', True), ('Detail', '/b', False)]) }}
        """,
    )
    assert 'href="/a"' in html
    assert 'href="/b"' in html
    assert 'aria-current="page"' in html


def test_empty_state_with_cta_renders_one_link(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import empty_state %}
        {{ empty_state('inbox', 'No applications yet', 'Get started by adding one.', cta_label='Add application', cta_href='/applications/new') }}
        """,
    )
    assert html.count("<a ") == 1
    assert 'href="/applications/new"' in html
    assert "Add application" in html
    assert "No applications yet" in html


def test_empty_state_without_cta_renders_no_link(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import empty_state %}
        {{ empty_state('inbox', 'No applications yet', 'Get started by adding one.') }}
        """,
    )
    assert html.count("<a ") == 0


def test_stat_card_none_value_renders_dash_not_zero(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import stat_card %}
        {{ stat_card('Health Score', None) }}
        """,
    )
    assert "—" in html
    assert ">0<" not in html


def test_stat_card_hero_variant_uses_larger_text_class_than_standard(app):
    hero_html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import stat_card %}
        {{ stat_card('Health Score', 92, variant='hero') }}
        """,
    )
    standard_html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import stat_card %}
        {{ stat_card('Health Score', 92, variant='standard') }}
        """,
    )
    assert "text-3xl" in hero_html
    assert "text-3xl" not in standard_html
    assert "text-2xl" in standard_html


def test_section_card_body_via_caller(app):
    html = _render(
        app,
        """
        {% from 'macros/page_shell.html' import section_card %}
        {% call section_card(title='Recent activity') %}
        <p>Nothing yet.</p>
        {% endcall %}
        """,
    )
    assert "Recent activity" in html
    assert "Nothing yet." in html
