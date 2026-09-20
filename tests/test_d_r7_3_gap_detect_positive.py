"""D-R7-3: mutation-coverage hole in the /api/roadmap/gaps/detect tests.

Every existing test for this endpoint (test_d_r5_1_gap_detect_divergence.py,
test_c1_gap_tile_reconciliation.py) only asserts `created == 0` in various
skip scenarios. Nothing asserted the endpoint ever successfully creates a Gap
element when it should -- a mutation that makes the endpoint always skip
everything (e.g. inverting the `no_maturity_recorded` check, or an
unconditional `continue`/early `return`) would leave every existing test
green while gap detection silently does nothing in production.

This test seeds a capability with a FRESH, correctly-projected authority row
carrying a real maturity delta (target > current, both non-None) and asserts
a Gap element IS created, with the correct magnitude reflected in its
priority/severity classification and in the persisted description.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_detect_gaps_creates_gap_for_capability_with_real_projected_delta(
    app, db_session, make_org, tenant_ctx
):
    from app.models.business_capabilities import BusinessCapability
    from app.models.unified_capability import UnifiedCapability
    from app.models.user import User

    org = make_org("d-r7-3-positive-gap-detect")
    with tenant_ctx(org.id):
        user = User(
            email=f"d-r7-3-{org.id}@example.com",
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        # A capability with a real, non-None maturity delta: current=2,
        # target=5 -> gap of 3 ("critical" priority per the endpoint's own
        # thresholding).
        cap = BusinessCapability(
            name="D-R7-3 real-delta capability",
            code=f"CAP-DR73-{org.id}",
            organization_id=org.id,
            level=1,
            current_maturity_level=2,
            target_maturity_level=5,
        )
        db_session.add(cap)
        db_session.commit()

        # The write-time ORM sync listener projects the UnifiedCapability row
        # automatically on insert -- confirm it actually landed with the same
        # non-None current/target values (i.e. the authority is FRESH and
        # correctly projected, not stale), so this test exercises the
        # success path rather than accidentally re-testing the skip path.
        authority_row = UnifiedCapability.query.filter(
            UnifiedCapability.source_table == "business_capability",
            UnifiedCapability.source_id == str(cap.id),
        ).one()
        assert authority_row.current_maturity_level == 2
        assert authority_row.target_maturity_level == 5

        from tests.test_ba_tenant_and_authz import _login

        c = app.test_client()
        _login(c, user_id)

        resp = c.post("/capability-map/api/roadmap/gaps/detect")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["success"] is True

        assert body["created"] == 1, (
            "a capability with a real, non-None, correctly-projected "
            "maturity delta (current=2, target=5) must produce a created "
            "Gap element -- if this is 0, gap detection is silently "
            "skipping everything"
        )

        # GapArchiMateService._create_gap_from_data prefixes "Gap: " onto
        # whatever `name` it's handed -- and the endpoint already passes
        # `f"Gap: {cap.name}"`, so the persisted name is double-prefixed.
        expected_gap_name = f"Gap: Gap: {cap.name}"
        matching_gaps = [g for g in body["gaps"] if g["name"] == expected_gap_name]
        assert len(matching_gaps) == 1
        gap = matching_gaps[0]
        assert gap["auto_generated"] is True
        assert gap["generation_source"] == "maturity_delta"
        # gap of 3 (target 5 - current 2) crosses the endpoint's own
        # ">= 3 -> critical" threshold.
        assert gap["priority"] == "critical"

        from app.models.implementation_migration import Gap

        persisted_gap = Gap.query.filter_by(name=expected_gap_name).one()
        assert persisted_gap.priority == "critical"
        assert persisted_gap.severity in ("critical", "high")
        assert persisted_gap.resolution_status == "identified"
