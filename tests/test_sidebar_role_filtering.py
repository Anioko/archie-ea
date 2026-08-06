"""The shipped sidebar must show each archetype only its own sections.

`role_access.py` has defined ROLE_SECTION_ACCESS for all nine enterprise roles
since NS-006, and `can_access_section` has been registered as a Jinja global -
but the sidebar that actually ships (components/admin_sidebar_northstar_phase2.html,
included unconditionally by layouts/admin_base.html and therefore by 293
templates) never called it. Only components/admin_sidebar.html did, and that file
is included by composer_base.html, used by two templates.

The effect was that all nine archetypes saw one identical 92-link navigation:
the Enterprise Architect's, plus Administration. Two archetypes - Procurement and
Application Manager - had complete, correctly-guarded modules (20 routes between
them) that no link in the product pointed at.

This renders the real sidebar once per role and asserts the visible section
headings match ROLE_SECTION_ACCESS.
"""

from __future__ import annotations

import os
import re

import pytest

# Sidebar heading text -> the NAVIGATION_SECTIONS key that gates it.
SECTION_HEADINGS = {
    "Home": "home",
    "Solutions": "solutions",
    "Portfolio": "portfolio",
    "Architecture": "architecture",
    "Governance": "governance",
    # Literal template text, so the ampersand is not HTML-escaped.
    "Data & Integration": "data_integration",
    "Procurement": "procurement",
    "My Applications": "my_applications",
}

HEADING_RE = re.compile(
    r'<div class="mb-2 px-2 text-xs font-semibold tracking-tight '
    r'text-muted-foreground uppercase">\s*(.+?)\s*</div>',
    re.DOTALL,
)


class _Any:
    """Permissive placeholder for User attributes the sidebar happens to touch."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()

    def __call__(self, *args, **kwargs):
        return _Any()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __str__(self):
        return ""

    def __html__(self):
        return ""


class FakeUser:
    """Enough of User for the sidebar.

    `enterprise_role` and `is_admin()` are real - they are what the gating reads.
    Everything else (full_name, avatar, organization, ...) resolves to a benign
    placeholder, so this test fails on a *gating* change rather than on the
    sidebar rendering one more profile field.
    """

    def __init__(self, enterprise_role, admin=False):
        self.enterprise_role = enterprise_role
        self.is_authenticated = True
        self._admin = admin

    def is_admin(self):
        return self._admin

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    return create_app("testing")


def _render_sidebar(app, user):
    """Render the shipped sidebar as *user* and return its visible headings."""
    from flask import render_template

    with app.test_request_context("/"):
        # Flask re-applies the explicit context last (update_template_context
        # copies the original and re-updates with it), so this genuinely
        # overrides flask_login's current_user rather than being overwritten.
        html = render_template(
            "components/admin_sidebar_northstar_phase2.html", current_user=user
        )
    return {m.group(1).strip() for m in HEADING_RE.finditer(html)}


@pytest.mark.parametrize(
    "role",
    [
        "solution_architect",
        "enterprise_architect",
        "business_architect",
        "arb_member",
        "portfolio_manager",
        "cto",
        "procurement",
        "application_manager",
        "platform_admin",
    ],
)
def test_each_role_sees_exactly_its_own_sections(app, role):
    from app.utils.role_access import ROLE_SECTION_ACCESS

    allowed = ROLE_SECTION_ACCESS[role]
    headings = _render_sidebar(app, FakeUser(role))

    wrong = []
    for heading, key in SECTION_HEADINGS.items():
        shown = heading in headings
        should = key in allowed
        if shown != should:
            wrong.append(
                "%s: %s but role_access says %s"
                % (heading, "shown" if shown else "hidden",
                   "allowed" if should else "denied")
            )

    assert not wrong, "%s sidebar does not match ROLE_SECTION_ACCESS:\n  %s" % (
        role, "\n  ".join(wrong)
    )


def test_procurement_can_reach_its_own_module(app):
    """The defining regression: procurement's 14 routes had no nav entry."""
    headings = _render_sidebar(app, FakeUser("procurement"))
    assert "Procurement" in headings, (
        "the procurement archetype still cannot navigate to app/modules/procurement/"
    )


def test_application_manager_can_reach_its_own_module(app):
    headings = _render_sidebar(app, FakeUser("application_manager"))
    assert "My Applications" in headings, (
        "the application_manager archetype still cannot navigate to "
        "app/modules/my_applications/"
    )


def test_roles_actually_differ(app):
    """A sidebar that ignored the role would give every role identical output,
    and every assertion above would still pass if ROLE_SECTION_ACCESS happened
    to allow everything. Prove two roles genuinely see different navigation."""
    procurement = _render_sidebar(app, FakeUser("procurement"))
    architect = _render_sidebar(app, FakeUser("enterprise_architect"))

    assert procurement != architect, "sidebar renders identically for every role"
    assert "Architecture" in architect and "Architecture" not in procurement
    assert "Procurement" in procurement and "Procurement" not in architect


def test_administration_is_permission_gated_not_role_gated(app):
    """Administration stays on Permission.ADMINISTER, which is stricter than the
    persona layer - a platform_admin enterprise_role without the permission must
    still not see it."""
    without = _render_sidebar(app, FakeUser("platform_admin", admin=False))
    with_perm = _render_sidebar(app, FakeUser("platform_admin", admin=True))

    assert "Administration" not in without
    assert "Administration" in with_perm
