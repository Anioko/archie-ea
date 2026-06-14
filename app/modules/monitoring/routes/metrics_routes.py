"""
Metrics Routes (migrated).

Thin route layer for Prometheus metrics scraping and debug views.

Migrated from: app/routes/metrics_routes.py
URLs preserved: /metrics, /debug/metrics, /debug/metrics/json
"""

import re

from flask import Blueprint, Response, jsonify, render_template
from flask_login import login_required

from app.services.prometheus_metrics import get_metrics_response

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("/metrics")
def metrics():
    """Prometheus metrics endpoint. No auth required for scraping."""
    return get_metrics_response()


@metrics_bp.route("/debug/metrics")
@login_required
def debug_metrics():
    """Human-readable metrics viewer. Requires authentication."""
    metrics_data = _parse_prometheus_metrics()
    return render_template("admin/index.html", metrics=metrics_data)


@metrics_bp.route("/debug/metrics/json")
@login_required
def debug_metrics_json():
    """JSON metrics endpoint. Requires authentication."""
    metrics_data = _parse_prometheus_metrics()
    return jsonify(metrics_data)


def _parse_prometheus_metrics() -> dict:
    """Parse Prometheus exposition format into a structured dict.

    Returns:
        Dict mapping metric names to lists of {labels, value} dicts.
    """
    from prometheus_client import generate_latest, REGISTRY

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
