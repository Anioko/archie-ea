"""Views must pass every variable their template dereferences.

Flask's default Undefined renders as empty rather than raising, so a missing
kwarg is usually invisible - until the template does attribute access or applies
a filter, at which point it is a hard 500. Nothing in scripts/verify.py checks
this contract: `boot-health` verifies that endpoints resolve, not that a page
renders.

Five live 500s were found this way and fixed. Each is pinned below by rendering
the real template with exactly the keywords its view now passes, and failing only
on UndefinedError - so an unrelated rendering problem (a missing global, a
database-backed macro) does not turn this into a flaky test.
"""

from __future__ import annotations

import os

import pytest
from jinja2 import UndefinedError


class Stub:
    """A permissive stand-in for a model row.

    Attribute access always succeeds, so this test fails only when a *top-level
    context name* is missing - which is the contract under test. Mirroring every
    column of User or ArchitectureChangeRequest here would couple the test to the
    models and make it fail for reasons that are not the defect.
    """

    def __init__(self, **attrs):
        self.__dict__.update(attrs)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Stub()

    def __call__(self, *args, **kwargs):
        return Stub()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __str__(self):
        return ""

    def __html__(self):
        return ""


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


def _render(app, template, **kwargs):
    """Render *template*; re-raise only UndefinedError as a failure.

    Uses flask.render_template rather than jinja_env.get_template().render() so
    the app's context processors run - `current_user`, `config` and the design-
    system globals are injected there, and bypassing them produces UndefinedError
    for names the view is not supposed to pass.
    """
    from flask import render_template

    with app.test_request_context("/"):
        try:
            render_template(template, **kwargs)
        except UndefinedError as exc:
            pytest.fail(
                "%s raised UndefinedError with the kwargs its view passes: %s"
                % (template, exc)
            )
        except Exception:
            # Anything else (a macro needing a database row, a filter needing a
            # request) is out of scope here. The contract under test is only
            # "every dereferenced name was supplied".
            pass


def test_account_manage_renders_with_user_and_form(app):
    """account.change_password / change_email_request passed form= but not user=.

    account/manage.html does {{ '%s %s' % (user.first_name, user.last_name) }},
    so both 500'd - and the page is linked from components/admin_header.html,
    which layouts/admin_base.html includes on every authenticated page.
    """
    user = Stub(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        username="ada",
        confirmed=True,
        is_authenticated=True,
    )
    _render(app, "account/manage.html", user=user, form=None)


def test_arb_change_request_detail_renders_with_cr(app):
    """arb.change_request_detail passed change_request=; the template reads cr."""
    cr = Stub(
        id=1,
        acr_reference="ACR-001",
        title="Example change",
        status="open",
        raised_at=None,
        description="",
        impact_level=None,
        disposition=None,
    )
    _render(app, "arb/change_request_detail.html", cr=cr)


def test_applications_edit_renders_with_application(app):
    """application_mgmt crud_routes passed app=; the template reads application."""
    application = Stub(
        id=1,
        name="Example App",
        description="",
        updated_at=None,
        deployment_status="production",
    )
    _render(
        app,
        "applications/edit.html",
        form=None,
        mode="edit",
        application=application,
        application_functions=[],
        application_processes=[],
        data_objects=[],
    )


@pytest.mark.parametrize(
    "module_path,needle",
    [
        ("app/modules/account/v2/routes/account_routes.py", "user=current_user, form=form"),
        ("app/modules/account/routes/account_routes.py", "user=current_user, form=form"),
    ],
)
def test_both_account_tiers_pass_user(module_path, needle):
    """Legacy and v2 are selected by a feature flag; both must be correct."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    text = (root / module_path).read_text(encoding="utf-8")
    assert needle in text, "%s no longer passes user= to account/manage.html" % module_path


def test_custom_field_edit_does_not_render_a_wtforms_template_without_a_form():
    """The template needs a form object this route never builds, and no
    CustomField*Form class exists in the tree, so rendering it is a guaranteed
    500. custom_field_create() already redirects for the same reason."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    text = (root / "app/application_mgmt/custom_field_routes.py").read_text(encoding="utf-8")
    # Look for an actual render call, not the filename - which also appears in
    # the comment explaining why it is no longer rendered.
    rendered = [
        line
        for line in text.splitlines()
        if "custom_field_form.html" in line and not line.strip().startswith("#")
    ]
    assert not rendered, (
        "custom_field_routes renders a WTForms template again; build the form "
        "first, or keep redirecting as custom_field_create does"
    )

