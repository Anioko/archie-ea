"""Architecture monitoring (baselines, alerts, snapshots, drift) is per organisation.

Before this fix ``monitoring_baselines``/``monitoring_alerts`` carried no
``organization_id`` at all, the service cached every baseline and alert in a
single process-wide dict shared by every tenant's instance, and its capability
and vendor snapshots read the whole catalogue with ``.query.all()``. This file
proves two organisations cannot see, mutate or be deactivated by each other's
monitoring data, that the per-tenant cache is actually per-tenant, and that the
capability and vendor snapshots carry an explicit predicate (so a call with no
Flask request on the stack is scoped too).

Follows the ``db_session`` / ``make_org`` / ``tenant_ctx`` fixtures in
``tests/conftest.py`` -- see ``tests/test_arb_ea_tenant_isolation.py`` for the
pattern this repo standardizes on.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _reset_monitoring_state():
    """Clear the module-level per-tenant cache before and after every test.

    ArchitectureMonitoringService._STATE lives for the life of the process,
    not the life of a request, so one test's cached baselines/alerts must not
    leak into the next test's fresh service instances.
    """
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    ArchitectureMonitoringService.reset_state()
    yield
    ArchitectureMonitoringService.reset_state()


def _make_user(db_session, org_id, label):
    """Same three-line construction tests/test_arb_ea_tenant_isolation.py uses.

    There is no shared user-factory fixture on this branch's base; each module
    that needs one still builds its own inline.
    """
    from app.models.user import User

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="Test",
        last_name=label,
        organization_id=org_id,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# --------------------------------------------------------------- (1) baselines


def test_baseline_captured_for_one_org_is_invisible_to_the_other(
    db_session, make_org, tenant_ctx
):
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-bl-a"), make_org("dr3-bl-b")

    # CapabilityHealthService withholds average_health as None (not a
    # fabricated 0) when nothing is assessable, and the drift maths this
    # brief does not touch subtracts baseline from current unconditionally --
    # so a capability whose maturity is set (making it assessable) is needed
    # here for analyze_drift below to have a real number on both sides rather
    # than None - None.
    element_a = ArchiMateElement(
        name="Health-bearing capability", type="Capability", layer="Strategy",
        organization_id=org_a.id,
    )
    db_session.add(element_a)
    db_session.flush()
    db_session.add(
        BusinessCapability(
            name="Health-bearing capability",
            organization_id=org_a.id,
            level=1,
            archimate_element_id=element_a.id,
            current_maturity_level=3,
        )
    )
    db_session.flush()

    with tenant_ctx(org_a.id):
        service_a = ArchitectureMonitoringService(org_a.id)
        result = service_a.capture_baseline(name="A baseline", created_by="tester-a")
        assert result["success"] is True, result
        baseline_id = result["baseline"]["id"]

        listed = service_a.list_baselines()
        assert baseline_id in {b["id"] for b in listed["baselines"]}

        fetched = service_a.get_baseline(baseline_id)
        assert fetched["success"] is True

        drift = service_a.analyze_drift(baseline_id)
        assert drift["success"] is True

    ArchitectureMonitoringService.reset_state()

    with tenant_ctx(org_b.id):
        service_b = ArchitectureMonitoringService(org_b.id)

        listed_b = service_b.list_baselines()
        assert listed_b["baselines"] == []
        assert baseline_id not in {b["id"] for b in listed_b["baselines"]}

        fetched_b = service_b.get_baseline(baseline_id)
        assert fetched_b == {"success": False, "error": "Baseline not found"}


# ------------------------------------------------------------------- (2) alerts


def test_alert_raised_for_one_org_is_invisible_to_the_other_and_foreign_ack_is_a_noop(
    db_session, make_org, tenant_ctx
):
    from app.models.policy_monitoring import MonitoringAlert
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-al-a"), make_org("dr3-al-b")

    row = MonitoringAlert(
        alert_id=f"alert-{uuid.uuid4().hex[:10]}",
        organization_id=org_a.id,
        alert_type="new_gap",
        severity="warning",
        title="Org A alert",
    )
    db_session.add(row)
    db_session.flush()
    alert_id = row.alert_id

    with tenant_ctx(org_a.id):
        service_a = ArchitectureMonitoringService(org_a.id)
        seen_a = service_a.get_alert(alert_id)
        assert seen_a["success"] is True

    ArchitectureMonitoringService.reset_state()

    with tenant_ctx(org_b.id):
        service_b = ArchitectureMonitoringService(org_b.id)

        seen_b = service_b.get_alert(alert_id)
        assert seen_b == {"success": False, "error": "Alert not found"}

        ack_result = service_b.acknowledge_alert(alert_id, acknowledged_by="user-b")
        assert ack_result == {"success": False, "error": "Alert not found"}

    # Raw SQL, deliberately outside any tenant_ctx block: a plain ORM refresh
    # here would still be caught by g.current_org_id left over from the block
    # above (Flask reuses the outer app context's g across nested
    # test_request_context blocks), which would filter it to org B and hide
    # org A's own row. The row's real database state is the assertion.
    row_state = db_session.execute(
        text("SELECT acknowledged, acknowledged_by FROM monitoring_alerts WHERE id = :id"),
        {"id": row.id},
    ).one()
    assert row_state.acknowledged is False
    assert row_state.acknowledged_by is None


# ------------------------------------------------------------- (3) activation


def test_activating_a_baseline_in_one_org_does_not_touch_the_others_active_baseline(
    db_session, make_org, tenant_ctx
):
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-act-a"), make_org("dr3-act-b")

    with tenant_ctx(org_b.id):
        service_b = ArchitectureMonitoringService(org_b.id)
        result_b = service_b.capture_baseline(
            name="B baseline", created_by="tester-b", set_as_active=True
        )
        assert result_b["success"] is True, result_b
        baseline_b_id = result_b["baseline"]["id"]
        assert result_b["baseline"]["is_active"] is True

    ArchitectureMonitoringService.reset_state(org_b.id)

    with tenant_ctx(org_a.id):
        service_a = ArchitectureMonitoringService(org_a.id)
        first = service_a.capture_baseline(
            name="A baseline 1", created_by="tester-a", set_as_active=True
        )
        assert first["success"] is True, first
        # A second activation in A used to run MBModel.query.update(...) with
        # no organisation predicate, deactivating every tenant's active
        # baseline, including B's, captured above.
        second = service_a.capture_baseline(
            name="A baseline 2", created_by="tester-a", set_as_active=True
        )
        assert second["success"] is True, second
        assert second["baseline"]["is_active"] is True

    ArchitectureMonitoringService.reset_state(org_a.id)

    with tenant_ctx(org_b.id):
        fresh_b = ArchitectureMonitoringService(org_b.id)
        still_active = fresh_b.get_baseline(baseline_b_id)
        assert still_active["success"] is True
        assert still_active["baseline"]["is_active"] is True


# ---------------------------------------------------------------- (4) cache


def test_per_tenant_cache_is_isolated_and_state_holds_one_entry_per_org(
    db_session, make_org, tenant_ctx
):
    from app.models.policy_monitoring import MonitoringBaseline
    from app.modules.architecture.services.architecture_monitoring_service import (
        _STATE,
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-cache-a"), make_org("dr3-cache-b")

    row_a = MonitoringBaseline(
        baseline_id=f"bl-{uuid.uuid4().hex[:10]}",
        organization_id=org_a.id,
        name="A cached baseline",
        snapshot_data="{}",
        checksum="deadbeef",
    )
    db_session.add(row_a)
    db_session.flush()

    with tenant_ctx(org_a.id):
        service_a = ArchitectureMonitoringService(org_a.id)
        assert row_a.baseline_id in service_a._state.baselines

    with tenant_ctx(org_b.id):
        service_b = ArchitectureMonitoringService(org_b.id)
        # A fresh org B instance must see none of org A's rows: no shared
        # class-level cache, only this org's entry in _STATE.
        assert service_b._state.baselines == {}

    assert set(_STATE.keys()) == {org_a.id, org_b.id}
    assert _STATE[org_a.id] is not _STATE[org_b.id]


# ------------------------------------------------------- (5) capability snapshot


def test_capability_snapshot_includes_own_and_reference_rows_excludes_other_org(
    db_session, make_org
):
    """No tenant_ctx here: the point is that the explicit predicate in the
    service, not the request-scoped do_orm_execute listener, is what scopes
    this read -- so a call with no Flask request on the stack is safe too.
    """
    from app.models.unified_capability import UnifiedCapability
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-cap-a"), make_org("dr3-cap-b")
    suffix = uuid.uuid4().hex[:10]

    reference = UnifiedCapability(
        name=f"Reference {suffix}", code=f"REF-{suffix}", organization_id=None
    )
    own = UnifiedCapability(
        name=f"Own A {suffix}", code=f"A-{suffix}", organization_id=org_a.id
    )
    foreign = UnifiedCapability(
        name=f"Own B {suffix}", code=f"B-{suffix}", organization_id=org_b.id
    )
    db_session.add_all([reference, own, foreign])
    db_session.flush()

    service_a = ArchitectureMonitoringService(org_a.id)
    snapshot = service_a._capture_capabilities_snapshot()
    ids = {row["id"] for row in snapshot}

    assert reference.id in ids
    assert own.id in ids
    assert foreign.id not in ids


# ----------------------------------------------------------- (6) vendor snapshot


def test_vendor_snapshot_only_includes_products_mapped_by_this_org(
    db_session, make_org
):
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability
    from app.models.vendor.vendor_organization import (
        VendorOrganization,
        VendorProduct,
        VendorProductCapability,
    )
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )

    org_a, org_b = make_org("dr3-vend-a"), make_org("dr3-vend-b")
    suffix = uuid.uuid4().hex[:10]

    vendor = VendorOrganization(name=f"Vendor {suffix}")
    db_session.add(vendor)
    db_session.flush()

    product_a = VendorProduct(vendor_organization_id=vendor.id, name=f"Product A {suffix}")
    product_b = VendorProduct(vendor_organization_id=vendor.id, name=f"Product B {suffix}")
    product_unmapped = VendorProduct(vendor_organization_id=vendor.id, name=f"Product None {suffix}")
    db_session.add_all([product_a, product_b, product_unmapped])
    db_session.flush()

    # BusinessCapability's before_insert hook auto-creates an ArchiMateElement
    # via a raw connection.execute() that does not set organization_id, so it
    # violates that column's NOT NULL constraint unless archimate_element_id
    # is already populated. Pre-create the element through the ORM (which
    # does set organization_id) to sidestep that unrelated, pre-existing gap
    # -- the same workaround tests/test_tenant_scoping_leaks.py uses.
    element_a = ArchiMateElement(
        name=f"Cap A {suffix}", type="Capability", layer="Strategy", organization_id=org_a.id
    )
    db_session.add(element_a)
    db_session.flush()
    capability_a = BusinessCapability(
        name=f"Cap A {suffix}", organization_id=org_a.id, level=1, archimate_element_id=element_a.id
    )
    db_session.add(capability_a)
    db_session.flush()

    element_b = ArchiMateElement(
        name=f"Cap B {suffix}", type="Capability", layer="Strategy", organization_id=org_b.id
    )
    db_session.add(element_b)
    db_session.flush()
    capability_b = BusinessCapability(
        name=f"Cap B {suffix}", organization_id=org_b.id, level=1, archimate_element_id=element_b.id
    )
    db_session.add(capability_b)
    db_session.flush()

    mapping_a = VendorProductCapability(
        vendor_product_id=product_a.id,
        business_capability_id=capability_a.id,
        organization_id=org_a.id,
        coverage_percentage=80.0,
    )
    mapping_b = VendorProductCapability(
        vendor_product_id=product_b.id,
        business_capability_id=capability_b.id,
        organization_id=org_b.id,
        coverage_percentage=60.0,
    )
    db_session.add_all([mapping_a, mapping_b])
    db_session.flush()

    service_a = ArchitectureMonitoringService(org_a.id)
    vendor_ids = {row["id"] for row in service_a._capture_vendor_snapshot()}

    assert product_a.id in vendor_ids
    assert product_b.id not in vendor_ids
    assert product_unmapped.id not in vendor_ids

    # A tenant with no vendor mappings at all gets an honest empty snapshot,
    # not the shared VendorProduct catalogue.
    org_c = make_org("dr3-vend-c")
    service_c = ArchitectureMonitoringService(org_c.id)
    assert service_c._capture_vendor_snapshot() == []


# --------------------------------------------------------------- (7) mixin stamp


def test_mixin_stamps_organization_id_on_insert_without_explicit_value(
    db_session, make_org, tenant_ctx
):
    from app.models.policy_monitoring import MonitoringBaseline

    org_a, org_b = make_org("dr3-stamp-a"), make_org("dr3-stamp-b")

    with tenant_ctx(org_a.id):
        implicit = MonitoringBaseline(
            baseline_id=f"bl-{uuid.uuid4().hex[:10]}",
            name="Implicit stamp",
            snapshot_data="{}",
            checksum="cafebabe",
        )
        db_session.add(implicit)
        db_session.flush()
        assert implicit.organization_id == org_a.id

    explicit = MonitoringBaseline(
        baseline_id=f"bl-{uuid.uuid4().hex[:10]}",
        organization_id=org_b.id,
        name="Explicit stamp",
        snapshot_data="{}",
        checksum="cafebabe",
    )
    db_session.add(explicit)
    db_session.flush()

    assert explicit.organization_id == org_b.id
    assert implicit.organization_id == org_a.id  # unaffected by the second insert


# -------------------------------------------------------- (9) no-tenant refusal


def test_service_requires_organization_id_and_route_answers_404_without_tenant(
    db_session, make_org, client, login_as, monkeypatch
):
    from app.modules.architecture.services.architecture_monitoring_service import (
        ArchitectureMonitoringService,
    )
    import app.modules.architecture.routes.architecture_monitoring_routes as routes_module

    with pytest.raises(ValueError):
        ArchitectureMonitoringService(None)

    org = make_org("dr3-no-tenant")
    user = _make_user(db_session, org.id, "NoTenant")

    login_as(client, user)
    # The middleware always resolves a real, non-None organisation for a
    # logged-in user (users.organization_id is NOT NULL); simulate the "no
    # tenant on the request" case the routes must still refuse -- a CLI/job
    # call, or a request the tenant middleware has not run for -- by patching
    # the routes module's own current_org_id reference.
    monkeypatch.setattr(routes_module, "current_org_id", lambda: None)

    response = client.get("/api/architecture-monitoring/status")

    assert response.status_code == 404
    assert response.get_json()["success"] is False
