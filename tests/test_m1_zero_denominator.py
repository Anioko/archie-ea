"""
M1: zero-denominator metrics must render as unmeasured (None -> em dash),
never as a fabricated percentage (0% or 100%) that looks like a real reading.

Covers the fixes in:
  - app/services/product_roadmap_service.py (on_track_pct)
  - app/utils/policy_tool_wrapper.py (compliance_rate)
  - app/services/policy_monitoring_service.py (calculate_enterprise_compliance)
"""

from app.utils.policy_tool_wrapper import get_policy_compliance_report, policy_tool_wrapper


def test_product_roadmap_on_track_pct_none_when_no_now_epics(app, db_session, make_org, tenant_ctx):
    from app.services.product_roadmap_service import get_outcome_roadmap

    org = make_org("m1-roadmap")
    with tenant_ctx(org.id):
        result = get_outcome_roadmap()
        # No epics scheduled anywhere -- on_track_pct must be unmeasured, not
        # the old vacuous 100.0.
        assert result["on_track_pct"] is None
        assert result["total_epics"] == 0


def test_policy_compliance_rate_none_when_no_operations():
    # Reset shared module-level history so this test is independent of
    # ordering (policy_tool_wrapper keeps process-lifetime lists).
    policy_tool_wrapper.operation_history.clear()
    policy_tool_wrapper.violation_history.clear()

    report = get_policy_compliance_report()

    assert report["enforcement_status"]["total_operations_checked"] == 0
    assert report["enforcement_status"]["compliance_rate"] is None


def test_enterprise_compliance_none_when_no_application_statuses(app, db_session, make_org, tenant_ctx):
    from app.services.policy_monitoring_service import PolicyMonitoringService

    org = make_org("m1-compliance")
    with tenant_ctx(org.id):
        result = PolicyMonitoringService.calculate_enterprise_compliance()

        assert result["success"] is True
        assert result["compliance_percentage"] is None
        assert result["risk_score"] is None
