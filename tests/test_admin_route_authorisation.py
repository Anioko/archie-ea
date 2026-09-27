"""Admin-surface routes must enforce admin, not merely authentication.

Eleven routes on privileged paths carried `@login_required` alone, so any
authenticated user of any tenant could reach them. Two classes mattered most:

    /admin/integrations/{salesforce,power-platform}/{save,test,discover,import}
        writes OAuth client secrets into APISettings. 92 sibling routes in the
        same module already carried @admin_required; these eight missed it.

    /settings, /api/system-settings, /api/system-settings/save
        reads and writes `system_settings`, a GLOBAL table with no
        organization_id - so it is platform configuration, not tenant
        configuration, and one tenant could rewrite it for everybody.

This asserts enforcement against the real url_map rather than by grepping for a
decorator name, so it still passes if the guard is later expressed differently
and still fails if the guard is removed.
"""

from __future__ import annotations

import os

import pytest

# Endpoint name -> why it must be admin-only.
MUST_BE_ADMIN = {
    "admin.salesforce_save_credentials": "writes Salesforce OAuth client secret",
    "admin.salesforce_test_connection": "uses stored Salesforce credentials",
    "admin.salesforce_discover": "reads a connected Salesforce org",
    "admin.salesforce_import": "imports into the portfolio from Salesforce",
    "admin.power_platform_save_credentials": "writes Power Platform client secret",
    "admin.power_platform_test_connection": "uses stored Power Platform credentials",
    "admin.power_platform_discover": "reads a connected Power Platform tenant",
    "admin.power_platform_import": "imports into the portfolio from Power Platform",
    "main.settings": "renders global system settings",
    "main.get_system_settings": "reads the global system_settings table",
    "main.save_system_settings": "writes the global system_settings table",
}


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    return create_app("testing")


def _guarded(view):
    """True when *view* is wrapped by a permission check requiring ADMINISTER.

    Decorator *names* are useless here: permission_required uses functools.wraps,
    which copies __name__/__qualname__ from the view it wraps, so the wrapper is
    indistinguishable from the view by name. What does survive is the closure -
    `decorated_function` closes over the `permission` value it will test - so the
    check looks for Permission.ADMINISTER in the closure chain.
    """
    from app.models import Permission

    seen = set()
    stack = [view]
    while stack:
        fn = stack.pop()
        if id(fn) in seen:
            continue
        seen.add(id(fn))

        for cell in getattr(fn, "__closure__", None) or ():
            try:
                content = cell.cell_contents
            except ValueError:
                continue
            if content is Permission.ADMINISTER or content == Permission.ADMINISTER:
                return True
            if callable(content):
                stack.append(content)

        wrapped = getattr(fn, "__wrapped__", None)
        if wrapped is not None:
            stack.append(wrapped)
    return False


def test_privileged_routes_require_admin(app):
    unguarded = []
    missing = []
    for endpoint, why in sorted(MUST_BE_ADMIN.items()):
        view = app.view_functions.get(endpoint)
        if view is None:
            missing.append(endpoint)
            continue
        if not _guarded(view):
            unguarded.append("%s — %s" % (endpoint, why))

    assert not missing, (
        "endpoint(s) not registered, so this test is not actually checking them: %s"
        % ", ".join(missing)
    )
    assert not unguarded, (
        "%d privileged route(s) enforce authentication but not authorisation, so "
        "any logged-in user of any tenant can reach them:\n  %s"
        % (len(unguarded), "\n  ".join(unguarded))
    )


def test_the_guard_detector_can_tell_the_difference(app):
    """A detector that always returns True would make the test above vacuous."""
    from flask_login import login_required

    @login_required
    def only_authenticated():
        return ""

    assert _guarded(only_authenticated) is False, (
        "_guarded() reports a login_required-only view as guarded, which would "
        "make test_privileged_routes_require_admin pass no matter what"
    )

    from app.decorators import admin_required

    @admin_required
    def admin_only():
        return ""

    assert _guarded(admin_only) is True
