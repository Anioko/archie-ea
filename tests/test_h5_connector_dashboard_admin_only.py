"""H5: /integrations/connectors (Connector Health Dashboard) told users to
"Configure connectors in connector_framework.py" -- a source-file reference
with no in-product config path, because there is none. Since connectors can
only ever be provisioned by someone with repo/deploy access, the page is
internal/admin-only, not a customer-facing surface -- but it was reachable to
any logged-in user (@login_required only). Fixed by adding @admin_required
to the page route and every API route behind it, and rewording the empty
state to stop naming a source file.
"""

import pytest


def test_connector_dashboard_rejects_non_admin(app, db_session, make_org, tenant_ctx):
    from app.models.user import User

    org = make_org("h5-connectors")
    with tenant_ctx(org.id):
        user = User(
            email=f"h5-nonadmin-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="business_stakeholder",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/integrations/connectors")
            assert resp.status_code in (302, 403), (
                f"expected a non-admin to be refused, got {resp.status_code}"
            )


def test_connector_dashboard_empty_state_does_not_name_a_source_file():
    body = open(
        "app/templates/integrations/connector_dashboard.html", encoding="utf-8"
    ).read()
    assert "connector_framework.py" not in body
