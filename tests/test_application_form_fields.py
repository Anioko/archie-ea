"""F-09/F-10, Capgemini walkthrough:
- F-09: Lifecycle Status was displayed/filtered on but no create/edit form
  ever exposed it.
- F-10(a): Business Criticality was silently dropped on create for the live,
  JSON-posting form — ApplicationCreateSchema names the field `criticality`,
  the route read `business_criticality`, a key the schema-validated proxy
  never has.
- F-10(b): the edit route double-HTML-escaped name/description
  (sanitize_html() entity-encodes, then Jinja autoescape encodes again),
  turning "Billing & Invoicing" into "Billing &amp;amp; Invoicing" after any
  edit.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_create_via_json_persists_criticality_and_lifecycle_status(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.user import User

    org = make_org("app-form-create")
    with tenant_ctx(org.id):
        user = User(email=f"afc-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            # Matches the real applicationCreateForm() JS: business_criticality
            # is translated to the schema's `criticality` key before posting.
            resp = c.post("/applications/create", json={
                "name": "SCADE Plant Control",
                "criticality": "critical",
                "lifecycle_status": "3. sunset",
            })
            assert resp.status_code in (200, 201), resp.get_data(as_text=True)
            body = resp.get_json()
            assert body.get("success") is not False, body

            # Read back independently.
            created = db_session.query(ApplicationComponent).filter_by(
                name="SCADE Plant Control"
            ).first()
            assert created is not None
            assert created.business_criticality == "critical"
            assert created.lifecycle_status == "3. sunset"


@pytest.mark.usefixtures("db_session")
def test_edit_sets_lifecycle_status_and_does_not_double_escape_name(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.user import User

    org = make_org("app-form-edit")
    with tenant_ctx(org.id):
        application = ApplicationComponent(name="Old Name", organization_id=org.id)
        db_session.add(application)
        db_session.commit()
        app_id = application.id

        user = User(email=f"afe-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(f"/applications/{app_id}/edit", data={
                "name": "SCADE Plant Control & Reporting",
                "lifecycle_status": "4.2 decom planned",
            })
            assert resp.status_code == 302, resp.get_data(as_text=True)

            reloaded = db_session.get(ApplicationComponent, app_id)
            assert reloaded.name == "SCADE Plant Control & Reporting"
            assert "&amp;" not in reloaded.name
            assert reloaded.lifecycle_status == "4.2 decom planned"

            # And via the actual rendered detail/edit pages — the real check,
            # not just the stored value.
            edit_page = c.get(f"/applications/{app_id}/edit")
            assert edit_page.status_code == 200
            html = edit_page.get_data(as_text=True)
            assert "SCADE Plant Control &amp; Reporting" in html  # Jinja's single, correct autoescape
            assert "&amp;amp;" not in html
            assert 'value="4.2 decom planned" selected' in html
