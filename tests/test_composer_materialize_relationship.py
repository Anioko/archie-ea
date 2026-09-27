"""F-05(c), Capgemini walkthrough: connecting two Composer template elements
(client-only ids like "__builtin__sh1", never written to the database) sent
the fake id straight to valid-relationship-types (400) and then to
POST /api/relationships (500 — a string into an Integer FK). The fix exposes
_materialize_canvas_items() (already used by the full-diagram save path) as
an on-demand endpoint the Composer's connect-mode calls first. These tests
pin the endpoint and the full chain a materialized pair then unlocks.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_materialize_creates_real_rows_for_template_ids(app, db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement
    from app.models.user import User

    org = make_org("materialize")
    with tenant_ctx(org.id):
        user = User(email=f"mz-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post("/archimate/api/elements/materialize", json={
                "elements": [
                    {"element_id": "__builtin__sh1", "name": "MuleSoft Integration Layer",
                     "el_type": "ApplicationComponent", "layer": "application"},
                    {"element_id": "__builtin__sh2", "name": "SCADE Plant Control",
                     "el_type": "ApplicationComponent", "layer": "application"},
                ]
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            id_map = resp.get_json()["element_id_map"]
            assert set(id_map.keys()) == {"__builtin__sh1", "__builtin__sh2"}

            # Read back independently — real rows exist, not just an echoed id.
            src = db_session.get(ArchiMateElement, id_map["__builtin__sh1"])
            tgt = db_session.get(ArchiMateElement, id_map["__builtin__sh2"])
            assert src is not None and src.name == "MuleSoft Integration Layer"
            assert tgt is not None and tgt.name == "SCADE Plant Control"


@pytest.mark.usefixtures("db_session")
def test_materialize_then_connect_chain_round_trips(app, db_session, make_org, tenant_ctx):
    """The exact sequence the fixed Composer now drives: materialize the two
    template elements, fetch valid relationship types for the REAL ids
    (previously a 400 on the fake ones), then create the relationship
    (previously a 500) — and read it back."""
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.user import User

    org = make_org("materialize-chain")
    with tenant_ctx(org.id):
        user = User(email=f"mzc-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)

            mat = c.post("/archimate/api/elements/materialize", json={
                "elements": [
                    {"element_id": "__builtin__dr1", "name": "Cost Pressure Driver",
                     "el_type": "Driver", "layer": "motivation"},
                    {"element_id": "__builtin__gl1", "name": "Reduce Run Cost Goal",
                     "el_type": "Goal", "layer": "motivation"},
                ]
            })
            assert mat.status_code == 200
            id_map = mat.get_json()["element_id_map"]
            src_id = id_map["__builtin__dr1"]
            tgt_id = id_map["__builtin__gl1"]

            types = c.get(f"/archimate/api/valid-relationship-types?source_id={src_id}&target_id={tgt_id}")
            assert types.status_code == 200, types.get_data(as_text=True)
            valid_types = types.get_json()["valid_types"]
            assert len(valid_types) > 0

            create = c.post("/archimate/api/relationships", json={
                "source_element_id": src_id,
                "target_element_id": tgt_id,
                "relationship_type": valid_types[0],
            })
            assert create.status_code == 201, create.get_data(as_text=True)

            rel = db_session.query(ArchiMateRelationship).filter_by(
                source_id=src_id, target_id=tgt_id
            ).first()
            assert rel is not None
            assert rel.type == valid_types[0]
