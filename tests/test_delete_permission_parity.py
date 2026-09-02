"""DEF-074/DEF-075, Capgemini dry-run pass 3: delete endpoints for value
streams, value stream stages, and business cases required Role "admin"
while their own create/edit endpoints on the same blueprint accept
admin/architect/business_architect — so the very persona that could create
a record got a 403 trying to delete it. Both now use the same role set as
create/edit.
"""

import pytest


def _make_architect(db_session, org, email):
    from app.models import Permission, Role
    from app.models.user import User

    role = Role.query.filter_by(name="Contributor").first() or Role.query.filter_by(
        default=True
    ).first()
    user = User(email=email, organization_id=org.id, enterprise_role="business_architect",
                role=role, confirmed=True)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.usefixtures("db_session")
def test_business_architect_can_delete_own_value_stream(app, db_session, make_org, tenant_ctx):
    from app.models.unified_capability import ValueStream

    org = make_org("value-stream-delete-authz")
    with tenant_ctx(org.id):
        user = _make_architect(db_session, org, f"vsdel-{org.id}@example.com")
        vs = ValueStream(name="ZZ-AUDIT stream", organization_id=org.id)
        db_session.add(vs)
        db_session.commit()
        vs_id = vs.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(f"/value-streams/{vs_id}/delete")
            assert resp.status_code in (200, 302), resp.get_data(as_text=True)
            assert db_session.get(ValueStream, vs_id) is None


@pytest.mark.usefixtures("db_session")
def test_business_architect_can_delete_own_business_case(app, db_session, make_org, tenant_ctx):
    from app.models.business_case import BusinessCase

    org = make_org("business-case-delete-authz")
    with tenant_ctx(org.id):
        user = _make_architect(db_session, org, f"bcdel-{org.id}@example.com")
        bc = BusinessCase(title="ZZ-AUDIT case", organization_id=org.id)
        db_session.add(bc)
        db_session.commit()
        bc_id = bc.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(f"/business-case/{bc_id}/delete")
            assert resp.status_code in (200, 302), resp.get_data(as_text=True)
            assert db_session.get(BusinessCase, bc_id) is None
