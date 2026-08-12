"""Finding the accounts that became administrators by accident.

``User.enterprise_role`` is ``nullable=False`` with ``default=platform_admin``,
and ``invite_user`` never set it — so every colleague an administrator invited
was created as a platform administrator. The invite form now requires the
persona, but that only governs new accounts. On the development database 40 of
41 accounts hold the persona.

No code change can decide which of those should keep it. What code can do is
separate the accounts that show evidence of a deliberate choice from the ones
that do not, and make the correction a single reversible command instead of a
hand-written UPDATE.

The classification is deliberately conservative: an account is left alone if it
is the configured ADMIN_EMAIL, or if either admin flag is set — somebody set
that. Only a platform_admin persona with no flags and no claim to the
configured address is treated as inherited.
"""

from __future__ import annotations

import uuid

import pytest

from app.commands.audit_admin_personas import _candidates


def _user(db_session, org_id, *, email=None, enterprise_role="platform_admin",
          platform_admin=False, org_admin=False):
    from app.models.user import User

    user = User(
        email=email or f"persona-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Persona",
        last_name="Probe",
        organization_id=org_id,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    user.is_platform_admin = platform_admin
    user.is_org_admin = org_admin
    db_session.add(user)
    db_session.commit()
    return user


def test_an_account_with_no_admin_signal_is_classified_as_inherited(
    app, db_session, make_org, tenant_ctx
):
    org = make_org(f"persona-inherited-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _user(db_session, org.id)
        inherited, deliberate = _candidates()

    assert user.email in [u.email for u in inherited]
    assert user.email not in [u.email for u, _why in deliberate]


@pytest.mark.parametrize("flag", ["platform_admin", "org_admin"])
def test_an_account_with_an_admin_flag_is_left_alone(
    app, db_session, make_org, tenant_ctx, flag
):
    """Somebody set that flag. It is not an accident of the column default."""
    org = make_org(f"persona-flag-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _user(db_session, org.id, **{flag: True})
        inherited, deliberate = _candidates()

    assert user.email not in [u.email for u in inherited]
    assert user.email in [u.email for u, _why in deliberate]


def test_the_configured_admin_account_is_never_treated_as_inherited(
    app, db_session, make_org, tenant_ctx
):
    org = make_org(f"persona-configured-{uuid.uuid4().hex[:6]}")
    configured = (app.config.get("ADMIN_EMAIL") or "").strip().lower()
    if not configured:
        pytest.skip("no ADMIN_EMAIL configured in this environment")

    with tenant_ctx(org.id):
        inherited, deliberate = _candidates()

    assert configured not in [(u.email or "").lower() for u in inherited], (
        "demoting the configured administrator would lock the deployment out "
        "of its own admin surface"
    )


def test_a_non_admin_persona_is_not_a_candidate_at_all(
    app, db_session, make_org, tenant_ctx
):
    org = make_org(f"persona-other-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user = _user(db_session, org.id, enterprise_role="business_architect")
        inherited, deliberate = _candidates()

    everyone = [u.email for u in inherited] + [u.email for u, _why in deliberate]
    assert user.email not in everyone
