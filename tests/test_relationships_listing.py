"""F-05(b), Capgemini walkthrough: /architecture/relationships showed "20 rows
of bare numeric IDs with a — type" — reproducible from TWO independent causes
on the two routes that share this template: one queried an abandoned legacy
table (empty everywhere), the other queried the canonical table but fed the
template attributes (rel.source_element, rel.relationship_type) that
ArchiMateRelationship never declares, so Jinja silently fell back to the bare
id for both. These tests pin the fix: real element names, on both routes.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_relationships_listing_shows_real_names_not_bare_ids(app, db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.user import User

    org = make_org("rel-listing")
    with tenant_ctx(org.id):
        source = ArchiMateElement(name="MuleSoft Integration Layer", type="ApplicationComponent",
                                   layer="Application", organization_id=org.id)
        target = ArchiMateElement(name="SCADE Plant Control", type="ApplicationComponent",
                                   layer="Application", organization_id=org.id)
        db_session.add_all([source, target])
        db_session.commit()

        rel = ArchiMateRelationship(type="serving", source_id=source.id, target_id=target.id)
        db_session.add(rel)
        db_session.commit()

        user = User(email=f"rl-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)

            resp = c.get("/architecture/relationships")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert "MuleSoft Integration Layer" in html
            assert "SCADE Plant Control" in html
            assert "serving" in html

            resp2 = c.get("/enterprise/architecture/relationships")
            assert resp2.status_code == 200
            html2 = resp2.get_data(as_text=True)
            assert "MuleSoft Integration Layer" in html2
            assert "SCADE Plant Control" in html2
            assert "serving" in html2
