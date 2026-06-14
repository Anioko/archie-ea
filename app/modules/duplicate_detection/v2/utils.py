"""
Duplicate Detection v2 utility helpers.

Shared helpers for the duplicate detection v2 module routes.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def confidence_level(score: float) -> str:
    """Classify a similarity score into a confidence level.

    Args:
        score: Similarity score between 0.0 and 1.0.

    Returns:
        One of "high", "medium", or "low".
    """
    if score >= 0.8:
        return "high"
    elif score >= 0.6:
        return "medium"
    return "low"


def risk_level(dependency_count: int, user_count: int) -> str:
    """Classify consolidation risk based on dependencies and user count.

    Args:
        dependency_count: Total number of dependencies (processes + capabilities + integrations).
        user_count: Number of users of the application.

    Returns:
        One of "high", "medium", or "low".
    """
    if dependency_count > 10 or user_count > 500:
        return "high"
    elif dependency_count > 5 or user_count > 100:
        return "medium"
    return "low"


def safe_threshold(value: Any, default: float = 0.5) -> float:
    """Safely parse a threshold value, clamping to [0.0, 1.0].

    Args:
        value: Raw threshold value (string, int, float, or None).
        default: Default value if parsing fails.

    Returns:
        Clamped float between 0.0 and 1.0.
    """
    try:
        t = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(t, 0.0), 1.0)


def truncate_description(text: Optional[str], max_len: int = 100) -> Optional[str]:
    """Truncate a description string to a maximum length with ellipsis.

    Args:
        text: Input string, may be None.
        max_len: Maximum character length.

    Returns:
        Truncated string or None.
    """
    if not text:
        return text
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def aggregate_scores(scores: List[float]) -> Dict[str, Any]:
    """Compute aggregate statistics over a list of similarity scores.

    Args:
        scores: List of float scores.

    Returns:
        Dict with avg, min, max, and distribution counts.
    """
    if not scores:
        return {
            "avg_confidence": 0,
            "min_confidence": 0,
            "max_confidence": 0,
            "distribution": {"high": 0, "medium": 0, "low": 0},
        }
    return {
        "avg_confidence": round(sum(scores) / len(scores), 4),
        "min_confidence": round(min(scores), 4),
        "max_confidence": round(max(scores), 4),
        "distribution": {
            "high": len([s for s in scores if s >= 0.8]),
            "medium": len([s for s in scores if 0.6 <= s < 0.8]),
            "low": len([s for s in scores if s < 0.6]),
        },
    }
