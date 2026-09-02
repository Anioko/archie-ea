"""DEF-036, Capgemini dry-run (pass 2): an account with is_platform_admin
True but no Permission.ADMINISTER (or vice versa) reached
/admin/organizations and listed every tenant on the instance — user PII,
plans, and Make Admin/Deactivate/Delete controls for organizations other
than its own. platform_admin_required now requires both.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_platform_admin_flag_alone_is_not_enough(app, db_session, make_org, tenant_ctx):
    from app.models import Permission, Role
    from app.models.user import User

    org = make_org("platform-admin-authz")
    with tenant_ctx(org.id):
        low_role = Role.query.filter_by(default=True).first()
        flagged_only = User(
            email=f"flagged-only-{org.id}@example.com", organization_id=org.id,
            is_platform_admin=True, role=low_role, confirmed=True,
        )
        db_session.add(flagged_only)
        db_session.commit()

        with app.app_context():
            assert flagged_only.can(Permission.ADMINISTER) is False

            from app.middleware.tenant_decorators import platform_admin_required

            @platform_admin_required
            def _protected():
                return "ok"

            from flask_login import login_user
            with app.test_request_context("/admin/organizations"):
                login_user(flagged_only)
                with pytest.raises(Exception):
                    # abort(403) raises an HTTPException inside the decorator
                    _protected()
