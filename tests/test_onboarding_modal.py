"""The onboarding modal must not interrogate a user who already has a role.

Found by driving a real browser: signing in as the SG Tadley business architect
put a "Welcome to A.R.C.H.I.E. — What's your role?" modal over the dashboard.
Three things were wrong with that, in ascending order of severity:

  1. It blocks the first screen of the product for a user who is not onboarding.
  2. Its list of eight roles did not include ``business_architect`` — the role
     that user actually holds. Production carries nine.
  3. Completing it POSTs ``enterprise_role`` to
     /dashboard/api/onboarding-complete, so answering the question **overwrites
     the real role**, silently re-scoping the sidebar and permissions. A user
     whose role is missing from the list cannot answer correctly, so the only
     available outcomes were "wrong role" or "dismiss".

The modal is now gated on the user having no ``enterprise_role`` at all, and
``business_architect`` is a first-class option for those who genuinely need it.
"""

import re

import pytest

MODAL_MARKER = "What&#39;s your role?"
MODAL_MARKER_RAW = "What's your role?"


def _render_base(app, user):
    """Render a page extending layouts/admin_base.html as *user*."""
    from flask import render_template_string
    from flask_login import login_user

    with app.test_request_context("/"):
        login_user(user)
        return render_template_string(
            "{% extends 'layouts/admin_base.html' %}{% block content %}x{% endblock %}"
        )


@pytest.fixture
def make_user(db_session, make_org):
    from app.models.user import User

    def _make(role):
        org = make_org(f"onboard-{role or 'none'}")
        user = User(
            email=f"onboard-{role or 'none'}-{org.id}@example.com",
            first_name="On",
            last_name="Board",
            confirmed=True,
        )
        user.organization_id = org.id
        user.enterprise_role = role
        user.onboarding_completed_at = None
        db_session.add(user)
        db_session.commit()
        return user

    return _make


def test_the_users_current_role_is_preselected(app, make_user):
    """Completing the modal POSTs enterprise_role, so the default must be the truth.

    Preselection is what makes the write harmless for a user who already has a
    role: they confirm what they are rather than picking something else. It only
    works if the role is actually in the list — before this change a business
    architect was preselected to a value the picker could not render, so the
    first radio they touched would have changed their role.
    """
    user = make_user("business_architect")
    html = _render_base(app, user)

    assert "selectedRole: 'business_architect'" in html, (
        "the modal did not preselect the user's real enterprise_role, so "
        "completing it would overwrite that role"
    )


def test_modal_is_still_shown_to_a_genuinely_new_user(app, make_user):
    """The feature still works for whom it was built."""
    html = _render_base(app, make_user(None))

    assert MODAL_MARKER in html or MODAL_MARKER_RAW in html, (
        "a user with no enterprise_role should still be onboarded"
    )


# The enterprise roles the product actually assigns — one seeded user per role
# exists in production for exactly this set.
ASSIGNABLE_ROLES = (
    "solution_architect",
    "enterprise_architect",
    "business_architect",
    "arb_member",
    "portfolio_manager",
    "cto",
    "application_manager",
    "procurement",
    "platform_admin",
)


def test_every_assignable_role_is_offered_by_the_picker(app, make_user):
    """A role the product assigns must be answerable in the picker.

    business_architect was assignable but absent from roleLabels, so a business
    architect's only options were a role that was not theirs, or dismissal —
    and picking one would have overwritten the real value.
    """
    html = _render_base(app, make_user(None))
    offered = set(re.findall(r"^\s*(\w+): '[^']+',\s*$", html, re.M))

    missing = [r for r in ASSIGNABLE_ROLES if r not in offered]
    assert not missing, (
        f"assignable but not offered by the onboarding role picker: {missing}"
    )
