"""
Metrics Routes v2 — guardrail-enabled.

Uses the new architecture:
- @guarded_route for auth-gated debug endpoints
- @timed_route for automatic metrics collection
- api_success for JSON endpoints
- Observability integration

URLs preserved: /metrics, /debug/metrics, /debug/metrics/json
Blueprint name: metrics_v2 (distinct from v1)
"""

import re

from flask import Blueprint, Response, render_template

from app.core.api import api_success
from app.core.compat import mark_blueprint_guardrailed
from app.core.decorators import guarded_route, timed_route
from app.services.prometheus_metrics import get_metrics_response

metrics_bp_v2 = Blueprint("metrics_v2", __name__)
mark_blueprint_guardrailed(metrics_bp_v2)


@metrics_bp_v2.route("/metrics")
@timed_route
def metrics():
    """Prometheus metrics endpoint. No auth required for scraping."""
    return get_metrics_response()


@metrics_bp_v2.route("/debug/metrics")
@guarded_route(auth="login")
def debug_metrics():
    """Human-readable metrics viewer. Requires authentication."""
    metrics_data = _parse_prometheus_metrics()
    return render_template("admin/index.html", metrics=metrics_data)


@metrics_bp_v2.route("/debug/metrics/json")
@guarded_route(auth="login")
def debug_metrics_json():
    """JSON metrics endpoint. Requires authentication."""
    metrics_data = _parse_prometheus_metrics()
    return api_success(metrics_data)


def _parse_prometheus_metrics() -> dict:
    """Parse Prometheus exposition format into a structured dict."""
    from prometheus_client import REGISTRY, generate_latest

    metrics_text = generate_latest(REGISTRY).decode("utf-8")
    metrics_data: dict = {}

    for line in metrics_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^(\w+)(?:\{([^}]*)\})?\s+(.+)$", line)
        if match:
            name, labels, value = match.groups()
            if name not in metrics_data:
                metrics_data[name] = []

            label_dict = {}
            if labels:
                for label_match in re.finditer(r'(\w+)="([^"]*)"', labels):
                    label_dict[label_match.group(1)] = label_match.group(2)

            metrics_data[name].append(
                {
                    "labels": label_dict,
                    "value": float(value) if "." in value else int(value),
                }
            )

    return metrics_data
