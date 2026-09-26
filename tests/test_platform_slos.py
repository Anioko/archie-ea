"""TB-0165: platform SLO attainment for answers, API and approval services.

Uses a fresh, isolated CollectorRegistry (monkeypatched in place of
``get_http_metrics_registry``) for every attainment/burn assertion, so these
tests never depend on -- or pollute -- the shared process-global
``HTTP_REQUESTS_TOTAL``/``HTTP_REQUEST_DURATION`` counters that real request
traffic also writes to.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram

from app.services import platform_slo_service as slo


def _fresh_registry():
    """A private registry declaring the same metric names/labels as
    ``app.services.prometheus_metrics``, so the module's aggregation code
    exercises the real code path against controlled, synthetic data.
    """
    registry = CollectorRegistry()
    requests_total = Counter(
        "app_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status_code"],
        registry=registry,
    )
    request_duration = Histogram(
        "app_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        registry=registry,
    )
    return registry, requests_total, request_duration


def _patched_status(monkeypatch, registry):
    monkeypatch.setattr(slo, "get_http_metrics_registry", lambda: (registry, False))
    return slo.get_platform_slo_status()


def test_attainment_from_synthetic_counter_values(monkeypatch):
    """A route with real, healthy traffic reports a real availability and a
    real bucket-edge p95, computed from the counters -- never a literal."""
    registry, requests_total, duration = _fresh_registry()

    for _ in range(999):
        requests_total.labels(
            method="GET", endpoint="/api/v1/intelligence/cross-layer-impact", status_code="200"
        ).inc()
        duration.labels(
            method="GET", endpoint="/api/v1/intelligence/cross-layer-impact"
        ).observe(0.4)
    requests_total.labels(
        method="GET", endpoint="/api/v1/intelligence/cross-layer-impact", status_code="500"
    ).inc()

    status = _patched_status(monkeypatch, registry)
    answers = status["objectives"]["answers"]

    assert answers["measured"] is True
    assert answers["requests_observed"] == 1000
    assert answers["availability"] == 0.999
    assert answers["meets_availability_target"] is True
    assert answers["latency_p95_seconds"] == 0.5
    assert answers["meets_latency_target"] is True


def test_availability_is_null_reason_not_measured_when_unobserved(monkeypatch):
    """An objective with zero observed requests is `measured: false`, never a
    fabricated 100% (CLAUDE.md "never invent data")."""
    registry, _requests_total, _duration = _fresh_registry()

    status = _patched_status(monkeypatch, registry)

    for objective_name in ("answers", "api", "approvals"):
        objective = status["objectives"][objective_name]
        assert objective["measured"] is False
        assert objective["reason"] == "not measured"
        assert objective["availability"] is None
        assert objective["latency_p95_seconds"] is None
        assert objective["burn_rate"] is None
        assert objective["burn_alert"] is None
        # Never a fabricated 100 (or 100%) standing in for "unmeasured".
        assert objective["availability"] != 100
        assert objective["availability"] != 1.0


def test_unmeasured_traffic_on_other_prefixes_does_not_leak_into_api(monkeypatch):
    """Requests outside every declared prefix are simply not counted --
    the `api` objective stays unmeasured rather than reporting on them."""
    registry, requests_total, _duration = _fresh_registry()
    requests_total.labels(method="GET", endpoint="/health", status_code="200").inc()

    status = _patched_status(monkeypatch, registry)

    assert status["objectives"]["api"]["measured"] is False
    assert status["objectives"]["approvals"]["measured"] is False


def test_burn_alert_true_when_both_windows_exceed_threshold():
    assert slo.compute_burn_alert(20.0, 15.0) is True


def test_burn_alert_false_when_either_window_is_below_threshold():
    assert slo.compute_burn_alert(20.0, 5.0) is False
    assert slo.compute_burn_alert(1.0, 1.0) is False


def test_burn_alert_is_null_not_false_when_unmeasured():
    assert slo.compute_burn_alert(None, 20.0) is None
    assert slo.compute_burn_alert(20.0, None) is None
    assert slo.compute_burn_alert(None, None) is None


def test_burn_alert_true_end_to_end_on_heavy_error_rate(monkeypatch):
    """A route burning its 30-day error budget fast enough to exhaust it
    within the hour trips the alert; end-to-end through
    ``get_platform_slo_status``."""
    registry, requests_total, duration = _fresh_registry()

    for _ in range(95):
        requests_total.labels(
            method="POST", endpoint="/ai-chat/approvals/1/approve", status_code="200"
        ).inc()
        duration.labels(method="POST", endpoint="/ai-chat/approvals/1/approve").observe(0.1)
    for _ in range(5):
        requests_total.labels(
            method="POST", endpoint="/ai-chat/approvals/1/approve", status_code="500"
        ).inc()

    status = _patched_status(monkeypatch, registry)
    approvals = status["objectives"]["approvals"]

    assert approvals["measured"] is True
    assert approvals["availability"] == 0.95
    assert approvals["meets_availability_target"] is False
    assert approvals["burn_alert"] is True


def test_burn_alert_false_end_to_end_on_healthy_traffic(monkeypatch):
    registry, requests_total, duration = _fresh_registry()

    for _ in range(10000):
        requests_total.labels(
            method="GET", endpoint="/api/v1/dashboard/metrics", status_code="200"
        ).inc()
        duration.labels(method="GET", endpoint="/api/v1/dashboard/metrics").observe(0.05)
    requests_total.labels(
        method="GET", endpoint="/api/v1/dashboard/metrics", status_code="500"
    ).inc()

    status = _patched_status(monkeypatch, registry)
    api = status["objectives"]["api"]

    assert api["measured"] is True
    assert api["meets_availability_target"] is True
    assert api["burn_alert"] is False


def test_health_slo_endpoint_shape(app):
    """`/health/slo` is reachable unauthenticated and returns the three
    declared objectives with the fields the brief specifies."""
    with app.test_client() as client:
        response = client.get("/health/slo")

    assert response.status_code == 200
    body = response.get_json()

    assert "objectives" in body
    assert set(body["objectives"].keys()) == {"answers", "api", "approvals"}
    for objective in body["objectives"].values():
        assert "measured" in objective
        assert "availability" in objective
        assert "availability_target" in objective
        assert "latency_p95_seconds" in objective
        assert "latency_target_seconds" in objective
        assert "burn_alert" in objective


def test_health_slo_endpoint_leaks_no_organisation_or_user_data(app):
    """REQ-NFR-005: aggregate numbers only -- no organisation names, user
    data or request paths beyond the three fixed objective identifiers."""
    with app.test_client() as client:
        response = client.get("/health/slo")

    body = response.get_json()
    serialized = str(body).lower()

    for forbidden in ("organization_id", "org_id", "user_id", "email", "@"):
        assert forbidden not in serialized

    # The only strings identifying "what" are the three fixed objective
    # names -- not a per-tenant or per-user value.
    assert set(body["objectives"].keys()) == {"answers", "api", "approvals"}
