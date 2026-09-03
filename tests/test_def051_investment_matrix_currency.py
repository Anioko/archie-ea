"""DEF-051, Capgemini dry-run: /architecture/investment-priorities always
rendered a literal "$", ignoring the tenant's configured currency, while
Spend Analytics and Contracts on the same tenant use £.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_investment_matrix_uses_configured_currency_symbol(app, db_session, make_org, tenant_ctx):
    from app.models.user import User

    org = make_org("def051-investment-currency")
    with tenant_ctx(org.id):
        user = User(email=f"def051-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/investment-priorities")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            # No hard-coded literal dollar sign should be attached to
            # "Total Investment" — the actual configured symbol is used
            # (default £ per config.CurrencyConfig).
            assert "value='$'" not in html
