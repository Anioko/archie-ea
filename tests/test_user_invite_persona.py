"""An invited user must land in the workspace for the job they were invited to do.

``AdminUserService.invite_user`` set the legacy ``Role`` object and never
touched ``enterprise_role``. That column is ``nullable=False`` with
``default=ROLE_PLATFORM_ADMIN`` — a backward-compatibility choice made so that
users who predated the persona system kept full access — so every colleague an
administrator invited was created as a **platform administrator** of the
organisation.

Two consequences, and the second is the one an evaluator notices first:

* it is an escalation — invite a procurement lead, get an org administrator;
* ``enterprise_role`` drives the sidebar, so a business architect invited to
  model capabilities opened the platform to Organizations, Users and API
  Settings rather than to the capability map.

The invite form now requires the persona, and the service refuses to infer
``platform_admin`` from a missing or unrecognised value.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def _service():
    from app.modules.admin.services.admin_user_service import AdminUserService

    return AdminUserService


def _default_role(db_session):
    from app.models.user import Role

    role = Role.query.filter_by(default=True).first()
    assert role is not None
    return role


def _invite(_service, db_session, monkeypatch, **kwargs):
    # The invite sends mail and builds an external URL; neither is under test.
    monkeypatch.setattr(_service, "queue_email", staticmethod(lambda **_kw: None))
    monkeypatch.setattr(
        "app.modules.admin.services.admin_user_service.url_for",
        lambda *_a, **_kw: "http://localhost/invite",
    )
    return _service.invite_user(
        first_name="Iain",
        last_name="Tester",
        email=f"invited-{uuid.uuid4().hex[:8]}@example.com",
        role=_default_role(db_session),
        **kwargs,
    )


def test_the_invited_persona_is_the_one_that_was_chosen(
    app, db_session, make_org, tenant_ctx, _service, monkeypatch
):
    org = make_org(f"invite-ba-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _invite(
            _service, db_session, monkeypatch, enterprise_role="business_architect"
        )

    assert user.enterprise_role == "business_architect"


def test_an_invite_with_no_persona_does_not_create_an_administrator(
    app, db_session, make_org, tenant_ctx, _service, monkeypatch
):
    """The defect: the column default is platform_admin."""
    org = make_org(f"invite-none-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _invite(_service, db_session, monkeypatch)

    assert user.enterprise_role != "platform_admin", (
        "inviting a colleague made them an administrator of the organisation"
    )
    assert user.enterprise_role == "solution_architect"


def test_an_unrecognised_persona_does_not_escalate(
    app, db_session, make_org, tenant_ctx, _service, monkeypatch
):
    org = make_org(f"invite-bogus-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _invite(_service, db_session, monkeypatch, enterprise_role="wizard")

    assert user.enterprise_role == "solution_architect"


def test_the_invite_form_offers_every_persona(app):
    """A persona missing from the form cannot be assigned at invite time."""
    from app.models.user import ROLE_DISPLAY_NAMES, VALID_ROLES
    from app.modules.admin.forms.admin_forms import InviteUserForm

    with app.test_request_context("/"):
        form = InviteUserForm()
        offered = [value for value, _label in form.enterprise_role.choices]

    assert offered == VALID_ROLES
    assert "business_architect" in offered

    with app.test_request_context("/"):
        labels = dict(InviteUserForm().enterprise_role.choices)
    assert labels["business_architect"] == ROLE_DISPLAY_NAMES["business_architect"]


def test_the_form_does_not_preselect_a_persona(app):
    """A preselected first entry becomes a silent default nobody chose."""
    from app.modules.admin.forms.admin_forms import InviteUserForm

    with app.test_request_context("/"):
        form = InviteUserForm()
        assert form.enterprise_role.data in (None, "")
        assert not form.enterprise_role.validate(form), (
            "the persona must be required, or the invite falls back to the "
            "column default again"
        )
