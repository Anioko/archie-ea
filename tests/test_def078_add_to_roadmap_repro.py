"""DEF-078 live click-through follow-up: "Add to Roadmap" submit failed
with a raw 400 (production server log confirmed) and a plain "Error adding
to roadmap" toast with no detail. Reproduce with the exact payload shape
the real JS (app/static/js/capability_map/index.js:submitAddToRoadmap)
sends, to see the real validation failure.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_add_to_roadmap_from_real_capability_row(app, db_session, make_org, tenant_ctx):
    from app.models.business_capability import BusinessCapability
    from app.models.user import User

    org = make_org("def078-add-to-roadmap")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="ZZ-VERIFY Add To Roadmap Cap", level=2,
                                  organization_id=org.id)
        db_session.add(cap)
        user = User(email=f"def078-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()
        cap_id = cap.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.post(
                "/capability-map/api/roadmap/gaps/add-from-capability",
                json={
                    "capability_id": cap_id,
                    "capability_type": "business",
                    "capability_name": "ZZ-VERIFY Add To Roadmap Cap",
                    "level": 2,
                    "gap_type": "quality",
                    "priority": "high",
                    "start_date": "2026-09-03",
                    "end_date": "2026-10-03",
                    "color": "#6B7280",
                    "create_work_packages": False,
                },
            )
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["success"] is True


@pytest.mark.usefixtures("db_session")
def test_add_to_roadmap_twice_gives_specific_conflict_message(app, db_session, make_org, tenant_ctx):
    """The client's catch block used to discard this message for a generic
    'Error adding to roadmap' -- confirm the server itself still names the
    real reason, which app/static/js/capability_map/index.js now surfaces
    via error.message instead of swallowing it."""
    from app.models.business_capability import BusinessCapability
    from app.models.user import User

    org = make_org("def078-add-to-roadmap-dup")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="ZZ-VERIFY Dup Cap", level=2, organization_id=org.id)
        db_session.add(cap)
        user = User(email=f"def078dup-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()
        cap_id = cap.id

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            payload = {
                "capability_id": cap_id,
                "capability_type": "business",
                "capability_name": "ZZ-VERIFY Dup Cap",
                "level": 2,
                "gap_type": "quality",
                "priority": "high",
                "start_date": "2026-09-03",
                "end_date": "2026-10-03",
                "color": "#6B7280",
                "create_work_packages": False,
            }
            first = c.post("/capability-map/api/roadmap/gaps/add-from-capability", json=payload)
            assert first.status_code == 200, first.get_data(as_text=True)

            second = c.post("/capability-map/api/roadmap/gaps/add-from-capability", json=payload)
            assert second.status_code == 400
            assert "already on the roadmap" in second.get_json()["error"]
