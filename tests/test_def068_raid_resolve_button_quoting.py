"""DEF-068, Capgemini dry-run pass 3: the RAID Resolve/Close button's
@click="setStatus(id, {{ 'resolved' if ... else 'closed' }})" rendered the
ternary's output as a bare (unquoted) JS identifier, not a string literal.
Alpine evaluated the undefined identifier as `undefined`, so the PATCH body
JSON.stringify'd to {} (no status key), and the route replied 200 having
updated nothing -- "Resolve" silently did nothing. Assert the rendered page
now carries a quoted JS string literal.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_raid_resolve_button_renders_quoted_status(app, db_session, make_org, tenant_ctx):
    from app.models.raid_item import RaidItem, RaidKind, RaidStatus
    from app.models.user import User

    org = make_org("def068-raid-button-quoting")
    with tenant_ctx(org.id):
        item = RaidItem(title="ZZ-VERIFY RAID button quoting", kind=RaidKind.ISSUE,
                         status=RaidStatus.OPEN, organization_id=org.id)
        db_session.add(item)
        user = User(email=f"def068btn-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()
        item_id = item.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/risks/")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)

            # The bug: an unquoted bare identifier in the click handler.
            assert f"setStatus({item_id}, resolved)" not in html
            # The fix: a real JS string literal.
            assert f'setStatus({item_id}, "resolved")' in html
