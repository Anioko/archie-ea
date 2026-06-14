"""
Governance v2 utility helpers.

Shared helpers for the governance v2 module routes.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def severity_badge(severity: str) -> Dict[str, str]:
    """Return display label and CSS class for a policy severity.

    Args:
        severity: Raw severity string (info, warning, critical).

    Returns:
        Dict with 'label' and 'css_class' keys.
    """
    mapping = {
        "info": {"label": "Info", "css_class": "bg-blue-100 text-blue-800"},
        "warning": {"label": "Warning", "css_class": "bg-yellow-100 text-yellow-800"},
        "critical": {"label": "Critical", "css_class": "bg-red-100 text-red-800"},
    }
    return mapping.get(severity, {"label": severity.title(), "css_class": "bg-gray-100 text-gray-800"})


def compliance_score(violations: int, total_checks: int) -> float:
    """Calculate a compliance score as a percentage.

    Args:
        violations: Number of policy violations found.
        total_checks: Total number of checks performed.

    Returns:
        Compliance percentage (0.0-100.0). Returns 100.0 if no checks.
    """
    if total_checks <= 0:
        return 100.0
    return round(((total_checks - violations) / total_checks) * 100, 1)


def priority_sort_key(priority: str) -> int:
    """Return a numeric sort key for consolidation priority.

    Lower number = higher priority (for ascending sort).

    Args:
        priority: Priority string (critical, high, medium, low).

    Returns:
        Integer sort key.
    """
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(priority, 99)


def maturity_label(level: int) -> str:
    """Convert a numeric maturity level to a human-readable label.

    Args:
        level: Maturity level (1-5).

    Returns:
        Label string.
    """
    labels = {
        1: "Initial",
        2: "Managed",
        3: "Defined",
        4: "Quantitatively Managed",
        5: "Optimizing",
    }
    return labels.get(level, f"Level {level}")


def safe_page_params(page: Any, per_page: Any, max_per_page: int = 100) -> tuple:
    """Safely parse pagination parameters.

    Args:
        page: Raw page value.
        per_page: Raw per_page value.
        max_per_page: Maximum allowed per_page.

    Returns:
        Tuple of (page, per_page) as clamped integers.
    """
    try:
        p = max(1, int(page))
    except (TypeError, ValueError):
        p = 1
    try:
        pp = min(max(1, int(per_page)), max_per_page)
    except (TypeError, ValueError):
        pp = 20
    return p, pp
