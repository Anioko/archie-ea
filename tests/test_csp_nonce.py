"""The CSP nonce must reach template-authored scripts and nothing else.

Before this, `add_security_headers` ran a regex over the finished HTML body and
gave every `<script` in it a nonce. An attacker who injected a script tag
through any XSS hole therefore received a valid nonce, and with 'strict-dynamic'
in the production policy that script could go on to load further code. The nonce
mechanism protected nothing - it was applied after the point where trusted and
untrusted markup had already been merged into one string.

CspNonceExtension moves the substitution to template *compile* time, which is
before interpolation, so the trust boundary lands in the right place.
"""

from __future__ import annotations

import os
import re

import pytest

NONCE_ATTR_RE = re.compile(r'<script([^>]*)>', re.IGNORECASE)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    return application


def _script_tags(html):
    return [m.group(1) for m in NONCE_ATTR_RE.finditer(html)]


def test_template_authored_script_receives_a_nonce(app):
    from flask import render_template_string

    with app.test_request_context("/"):
        html = render_template_string("<script>console.info(1)</script>")

    tags = _script_tags(html)
    assert len(tags) == 1
    assert "nonce=" in tags[0], "a template's own <script> must be nonce'd"


def test_injected_markup_does_not_receive_a_nonce(app):
    """The whole point. User data reaches the page after compilation, so the
    substitution has already happened and cannot reach it."""
    from flask import render_template_string
    from markupsafe import Markup

    payload = Markup("<script>steal()</script>")

    with app.test_request_context("/"):
        html = render_template_string(
            "<div>{{ body }}</div><script>legit()</script>", body=payload
        )

    tags = _script_tags(html)
    assert len(tags) == 2, tags

    injected = [t for t in tags if "nonce=" not in t]
    legitimate = [t for t in tags if "nonce=" in t]

    assert len(injected) == 1, (
        "the injected <script> was given a nonce, which is exactly the failure "
        "this change exists to prevent: %r" % tags
    )
    assert len(legitimate) == 1


def test_a_script_tag_is_not_nonced_twice(app):
    """preprocess must be idempotent, or attributes stack on recompilation."""
    from flask import render_template_string

    with app.test_request_context("/"):
        html = render_template_string('<script nonce="already">x()</script>')

    assert html.count("nonce=") == 1, html


def test_external_script_src_is_also_nonced(app):
    """'strict-dynamic' makes 'self' inert, so src= tags need the nonce too."""
    from flask import render_template_string

    with app.test_request_context("/"):
        html = render_template_string('<script src="/static/js/app.js"></script>')

    assert "nonce=" in html


def test_response_body_is_no_longer_rewritten(app):
    """A body-level rewrite would re-nonce everything and undo the fix."""
    import inspect

    from app._bootstrap import security

    source = inspect.getsource(security)
    assert "_SCRIPT_TAG_RE.sub" not in source, (
        "the after_request body rewrite is back; it nonces injected scripts too"
    )


def test_nonce_in_header_matches_the_one_in_the_page(app):
    """A nonce that does not match the header blocks every script instead."""
    from flask import g, render_template_string

    with app.test_request_context("/"):
        g.csp_nonce = "test-nonce-value"
        html = render_template_string("<script>x()</script>")

    assert 'nonce="test-nonce-value"' in html


# --------------------------------------------------------------------------
# The policy itself
# --------------------------------------------------------------------------

def _production_csp(app, **g_attrs):
    """Build the production CSP header without needing DEBUG toggled globally."""
    from flask import g

    with app.test_request_context("/"):
        g.csp_nonce = "n"
        for key, value in g_attrs.items():
            setattr(g, key, value)
        app.debug = False
        response = app.make_response("")
        response.content_type = "text/html"
        for func in app.after_request_funcs[None]:
            response = func(response)
        return response.headers.get("Content-Security-Policy", "")


# unpkg / jsdelivr / cdnjs / d3js have zero references left in app/templates or
# app/static/js after ADR 0005 vendored those libraries, but the policy still
# permitted them. A permitted-but-unused host is a standing invitation.
@pytest.mark.parametrize(
    "dead_host",
    ["unpkg.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "d3js.org"],
)
def test_dead_cdn_allowances_are_gone(app, dead_host):
    assert dead_host not in _production_csp(app), (
        "%s is permitted by the CSP but referenced by nothing" % dead_host
    )


def test_the_live_external_dependency_is_still_permitted(app):
    """esm.sh is real: codegen/workbench.html builds the URL in JS and imports
    CodeMirror 6 from it. Removing it would break the workbench."""
    assert "https://esm.sh" in _production_csp(app)


def test_frame_ancestors_agrees_with_x_frame_options(app):
    """codegen preview routes opt into framing via g.allow_framing; a flat
    'none' would block exactly the pages that asked to be embedded."""
    assert "frame-ancestors 'none'" in _production_csp(app)
    assert "frame-ancestors 'self'" in _production_csp(app, allow_framing=True)


def test_injection_hardening_directives_are_present(app):
    policy = _production_csp(app)
    assert "base-uri 'self'" in policy, "an injected <base> could rewrite every URL"
    assert "form-action 'self'" in policy, "an injected form could post off-site"
