"""H6: /architecture/motivation showed "unavailable" for the Connected tile
even though GET /architecture/api/layer/motivation/elements returned valid
data. Root cause: api_layer_elements' "portfolio" branch (domain-model rows
reached through their linked ArchiMateElement, e.g. a Driver/Goal row) always
serialized rel_count=None, while the parallel "architecture" branch computed
a real count -- so the dashboard's relationshipMetrics getter
(app/static/js/archimate_crud/dashboard.js) never saw a usable number for any
element sourced from a dedicated per-type table, which is most of them.

Fixed in app/modules/architecture/routes/archimate_crud/routes.py: the
portfolio branch now batch-counts ArchiMateRelationship rows keyed by the
same linked ae_id already used for the plateau lookup.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_portfolio_element_serializes_real_rel_count(app, db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.business_layer import BusinessRole
    from app.models.user import User

    org = make_org("h6-relcount")
    with tenant_ctx(org.id):
        role = BusinessRole(name="Data Governance Lead", organization_id=org.id)
        db_session.add(role)
        db_session.commit()  # before_insert listener creates the linked element

        other = ArchiMateElement(
            name="Some other node", type="Node", layer="Technology", organization_id=org.id
        )
        db_session.add(other)
        db_session.commit()

        rel = ArchiMateRelationship(
            source_id=role.archimate_element_id,
            target_id=other.id,
            type="Serving",
        )
        db_session.add(rel)

        user = User(
            email=f"h6-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/api/layer/business/elements")
            assert resp.status_code == 200
            body = resp.get_json()
            match = next(
                (e for e in body["elements"] if e["name"] == "Data Governance Lead"), None
            )
            assert match is not None, "element not found in API response"
            # This is the exact field the dashboard's relationshipMetrics getter
            # checks `typeof count === 'number'` on -- must be a real int, not
            # the old hardcoded None.
            assert match["rel_count"] == 1, f"expected a real relationship count, got {match.get('rel_count')!r}"


@pytest.mark.usefixtures("db_session")
def test_portfolio_element_with_no_relationships_is_zero_not_none(
    app, db_session, make_org, tenant_ctx
):
    """A linked element genuinely has zero relationships -- rel_count must be
    the measured 0, not None (None means "no linked ArchiMateElement at all",
    a different and rarer condition per CLAUDE.md's ArchiMate-backbone rule)."""
    from app.models.business_layer import BusinessRole
    from app.models.user import User

    org = make_org("h6-relcount-zero")
    with tenant_ctx(org.id):
        role = BusinessRole(name="Unconnected Role", organization_id=org.id)
        db_session.add(role)
        user = User(
            email=f"h6z-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/api/layer/business/elements")
            assert resp.status_code == 200
            body = resp.get_json()
            match = next(
                (e for e in body["elements"] if e["name"] == "Unconnected Role"), None
            )
            assert match is not None
            assert match["rel_count"] == 0
