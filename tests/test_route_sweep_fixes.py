"""Regression test for the FE-QA route sweep's 22 authenticated 500s.

An authenticated sweep (admin user, empty-ish org, non-existent ids) found these
routes returning HTTP 500 instead of a clean 404 (entity-id routes) or 200 with an
empty result (list/aggregate routes). Root causes were all in the "broad except
Exception swallows the deliberate 404" family, one aggregate KeyError on empty
data, and two external-enrichment routes that should answer 503 rather than 500
when the upstream provider is unreachable. See the fixes referenced inline below.

Uses the shared fixtures from tests/conftest.py (db_session/make_org), following
tests/test_tenant_isolation.py's style.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


@pytest.fixture
def admin_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("route_sweep")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"route-sweep-admin-{suffix}@example.com",
        first_name="Sweep",
        last_name="Admin",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


# (path, min_expected_status) - all must be < 500. Entity-id routes with a
# non-existent id (999999) expect 404; the two no-param aggregate routes and
# the coverage matrix expect 200 with an empty/zeroed result; the two external
# enrichment routes expect 503 because the upstream provider is unreachable in
# this environment (app/api/api_pipeline_routes.py::enrich_vendor/enrich_product).
ROUTES = [
    # app/api/application_routes.py - get_or_404() was inside a bare
    # `except Exception`, so the deliberate NotFound was caught and turned into
    # a 500. Fixed by re-raising HTTPException before the generic handler.
    "/api/applications/999999/process-links",
    "/api/applications/999999/solutions",
    "/api/applications/999999/work-packages",
    "/api/applications/999999/architecture/elements",
    "/api/applications/999999/architecture/export-csv",
    "/api/applications/999999/details",
    # no-param aggregate routes - already tolerant of empty data once the
    # get_or_404 issue elsewhere was ruled out; kept here as a regression guard.
    "/api/applications/duplicates",
    "/api/applications/table-data",
    # app/services/interactive_coverage_matrix.py::_calculate_matrix_statistics
    # - the empty-cells branch omitted "coverage_distribution", which the route
    # unconditionally indexes.
    "/api/coverage-matrix/matrix-data",
    # app/api/api_pipeline_routes.py - external enrichment providers
    # unreachable; now answers 503 instead of 500.
    "/api/pipeline/enrich/product/nonexistent-product",
    "/api/pipeline/enrich/vendor/nonexistent-vendor",
    # already returned 404 correctly; kept as a regression guard.
    "/applications/api/v1/applications/999999/architectural-analysis",
    "/applications/api/vendor-analysis/999999/export",
    "/applications/api/vendor-analysis/999999/results",
    # app/modules/governance/routes/capability_governance_routes.py -
    # service returned {"success": False, "error": "Capability not found"} but
    # the route always answered 500 for any success=False result.
    "/capability-governance/api/health-check/999999",
    # app/modules/governance/routes/capability_management_routes.py - same
    # get_or_404-inside-broad-except pattern as application_routes.py.
    "/capability-management/api/capability-details/999999",
    # app/modules/applications/routes/capability_tagging_routes.py - same
    # pattern.
    "/dashboard/api/applications/999999/tags",
    # app/application_mgmt/implementation_layer_routes.py - same pattern.
    "/dashboard/api/applications/999999/work-packages",
    # app/api/application_merging_routes.py - same pattern.
    "/dashboard/api/applications/merging/analyze/999999",
    # app/modules/solutions_strategic/v2/routes/solution_design_routes.py -
    # same pattern, plus it leaked str(e) into the response body.
    "/solutions/999999/traceability/chain",
    # app/modules/vendors/routes/vendor_analysis_routes.py -
    # OptionsAnalysisService.get_comparison_data() raises ValueError for a
    # missing analysis; the route caught it with a bare `except Exception`
    # and returned 500.
    "/vendor-analysis/999999/comparison",
    "/vendor-analysis/999999/results",
]


# The two enrichment routes legitimately answer 503 (upstream provider
# unreachable) rather than 2xx/404; every other route must be < 500.
ALLOWED_5XX = {
    "/api/pipeline/enrich/product/nonexistent-product": 503,
    "/api/pipeline/enrich/vendor/nonexistent-vendor": 503,
}


@pytest.mark.parametrize("path", ROUTES)
def test_route_does_not_500(admin_client, path):
    resp = admin_client.get(path)
    allowed = ALLOWED_5XX.get(path)
    ok = resp.status_code < 500 or resp.status_code == allowed
    assert ok, (
        f"{path} returned {resp.status_code}: {resp.get_data(as_text=True)[:500]}"
    )
