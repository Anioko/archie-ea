"""Regression: as-is/to-be plateau tagging must be readable back, not write-only.

A Capgemini delivery-team dry-run (2 Sep 2026) found that tagging an ArchiMate
element Baseline/Target/Transition through the create/edit form (which writes
ArchiMateElement.togaf_plateau, a real column) silently could not be found again:
GET /api/layer/<layer>/elements never serialized a "plateau" key at all, and the
client-side filter (dashboard.js) additionally read the WRONG key
(properties.plateau, a JSON blob the form never wrote to) with a mismatched
vocabulary (current/transitional/target vs. the real Baseline/Target/Transition).
Tagging worked; finding what you tagged did not. Both the API and the client
filter are fixed; this pins the API half, which is what the client-side fix
depends on.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_api_layer_elements_serializes_plateau_for_native_element(app, db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement
    from app.models.user import User

    org = make_org("plateau")
    with tenant_ctx(org.id):
        ae = ArchiMateElement(name="S/4HANA landscape", type="Node", layer="Technology",
                              organization_id=org.id, togaf_plateau="Target")
        db_session.add(ae)
        user = User(email=f"pu-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/api/layer/technology/elements")
            assert resp.status_code == 200
            body = resp.get_json()
            match = next((e for e in body["elements"] if e["name"] == "S/4HANA landscape"), None)
            assert match is not None, "element not found in API response"
            assert match["plateau"] == "Target", \
                f"API must serialize the real togaf_plateau value; got {match.get('plateau')!r}"


@pytest.mark.usefixtures("db_session")
def test_api_layer_elements_serializes_plateau_for_domain_model(app, db_session, make_org, tenant_ctx):
    """A domain model (e.g. BusinessRole) reaches its plateau through its linked
    ArchiMateElement (archimate_element_id) — the portfolio branch of the API."""
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_layer import BusinessRole
    from app.models.user import User

    org = make_org("plateau")
    with tenant_ctx(org.id):
        role = BusinessRole(name="Revenue Operations Lead", organization_id=org.id)
        db_session.add(role)
        db_session.commit()  # before_insert listener creates the linked element
        ae = db_session.get(ArchiMateElement, role.archimate_element_id)
        ae.togaf_plateau = "Baseline"
        user = User(email=f"pu2-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/api/layer/business/elements")
            assert resp.status_code == 200
            body = resp.get_json()
            match = next((e for e in body["elements"] if e["name"] == "Revenue Operations Lead"), None)
            assert match is not None
            assert match["plateau"] == "Baseline"


@pytest.mark.usefixtures("db_session")
def test_mirrored_element_appears_exactly_once_not_twice(app, db_session, make_org, tenant_ctx):
    """Capgemini walkthrough F-04: a domain-model row that has been mirrored
    into ArchiMateElement (BusinessRole -> archimate_element_id) was appearing
    TWICE in api_layer_elements — once tagged source=portfolio (keyed by the
    role's own id) and once source=architecture (keyed by the mirror's id) —
    because the dedup check compared the wrong id pair, so the mirror was
    never recognised as "already seen". One create must produce one listed
    element, not two different ids for the same real-world thing."""
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_layer import BusinessRole
    from app.models.user import User

    org = make_org("mirror-dedup")
    with tenant_ctx(org.id):
        role = BusinessRole(name="Plant Control Operator", organization_id=org.id)
        db_session.add(role)
        db_session.commit()  # before_insert listener creates the linked ArchiMateElement
        assert role.archimate_element_id is not None, "fixture assumption: BusinessRole auto-mirrors"
        user = User(email=f"pu3-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/architecture/api/layer/business/elements")
            assert resp.status_code == 200
            body = resp.get_json()
            matches = [e for e in body["elements"] if e["name"] == "Plant Control Operator"]
            assert len(matches) == 1, (
                f"expected exactly one listed element for the mirrored role, got "
                f"{len(matches)}: {matches}"
            )
            # Once mirrored, the dedicated-table (portfolio) row is excluded here —
            # same convention _count_layer_elements already uses — and the single
            # surviving entry is the archimate_elements (architecture) side.
            assert matches[0]["id"] == role.archimate_element_id
            assert matches[0]["source"] == "architecture"
