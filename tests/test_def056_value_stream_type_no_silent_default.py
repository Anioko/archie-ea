"""DEF-056, Capgemini dry-run: the New Value Stream form's Type select had
no placeholder option, so a browser pre-selects the first real option
("Customer Facing") — a value stream saved without the user ever touching
the field looked identical to one where Customer Facing was deliberately
chosen. Empty-string submission must persist as unset (None), not the
literal empty string.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_empty_value_stream_type_persists_as_none(app, db_session, make_org, tenant_ctx):
    from app.models.unified_capability import ValueStream
    from app.models.user import User

    org = make_org("def056-value-stream-type")
    with tenant_ctx(org.id):
        user = User(email=f"def056-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post("/value-streams/create", data={
                "name": "ZZ-VERIFY value stream no type",
                "value_stream_type": "",
            })
            assert resp.status_code in (200, 302), resp.get_data(as_text=True)

            vs = ValueStream.query.filter_by(name="ZZ-VERIFY value stream no type").first()
            assert vs is not None
            assert vs.value_stream_type is None
