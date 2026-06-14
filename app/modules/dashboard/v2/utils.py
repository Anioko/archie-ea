"""
Dashboard v2 utility helpers.

Shared helpers for the dashboard v2 module routes.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def format_currency(value: Any, symbol: str = "£") -> str:
    """Format a numeric value as currency.

    Args:
        value: Numeric value to format.
        symbol: Currency symbol (default: £).

    Returns:
        Formatted currency string like "£1,234,567".
    """
    try:
        num = float(value)
        if num >= 1_000_000:
            return f"{symbol}{num / 1_000_000:,.1f}M"
        elif num >= 1_000:
            return f"{symbol}{num / 1_000:,.0f}K"
        return f"{symbol}{num:,.0f}"
    except (TypeError, ValueError):
        return f"{symbol}0"


def clamp_depth(depth: Any, min_val: int = 1, max_val: int = 5, default: int = 3) -> int:
    """Safely parse and clamp a depth parameter.

    Args:
        depth: Raw depth value.
        min_val: Minimum allowed depth.
        max_val: Maximum allowed depth.
        default: Default if parsing fails.

    Returns:
        Clamped integer.
    """
    try:
        d = int(depth)
    except (TypeError, ValueError):
        return default
    return min(max(d, min_val), max_val)


def safe_percentage(numerator: int, denominator: int, decimals: int = 1) -> float:
    """Calculate percentage safely, returning 0.0 on division by zero.

    Args:
        numerator: Top value.
        denominator: Bottom value.
        decimals: Decimal places to round to.

    Returns:
        Rounded percentage float.
    """
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, decimals)


def build_tier_result(tier: Dict, count: int, total: int) -> Dict:
    """Build a formatted tier result dict with percentage.

    Args:
        tier: Tier definition dict (name, min, max, color, description).
        count: Number of applications in this tier.
        total: Total applications across all tiers.

    Returns:
        Tier dict enriched with application_count and percentage.
    """
    return {
        **tier,
        "application_count": count,
        "percentage": safe_percentage(count, total),
    }
