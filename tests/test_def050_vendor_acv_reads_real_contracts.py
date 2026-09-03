"""DEF-050, Capgemini dry-run: after creating an active contract, Vendor
Catalogue still showed "Portfolio ACV —". The stat summed
VendorOrganization.contract_value_annual / read
VendorOrganization.contract_status/contract_end_date -- fields nothing
writes to. The real "Add Contract" flow creates a VendorContract row
(vendor_id FK, annual_cost, status, end_date) in a different table
entirely.
"""

from datetime import date, timedelta

import pytest


@pytest.mark.usefixtures("db_session")
def test_active_contract_is_reflected_in_portfolio_acv(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import VendorContract
    from app.models.vendor.vendor_organization import VendorOrganization
    from app.models.user import User

    org = make_org("def050-vendor-acv")
    with tenant_ctx(org.id):
        vendor = VendorOrganization(name="ZZ-VERIFY Vendor ACV")
        db_session.add(vendor)
        db_session.commit()

        db_session.add(VendorContract(
            contract_name="ZZ-VERIFY Contract", vendor_id=vendor.id,
            annual_cost=180000.0, status="active",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335),
            organization_id=org.id,
        ))
        db_session.commit()

        user = User(email=f"def050-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/applications/vendors")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert "Portfolio ACV" in html
            # 180000 annual -> $180K per the template's K-scale branch.
            assert "$180K" in html
