"""
AI Chat v2 utility helpers.

Shared helpers for the AI chat v2 module routes.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 10000
MAX_CONTEXT_ITEMS = 50


def truncate_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate a chat message to a maximum length.

    Args:
        text: Input message text.
        max_len: Maximum character length.

    Returns:
        Truncated string.
    """
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def sanitize_user_input(text: str) -> str:
    """Sanitize user input for safe processing.

    Strips control characters and excessive whitespace.

    Args:
        text: Raw user input.

    Returns:
        Sanitized string.
    """
    if not text:
        return ""
    # Remove control characters except newlines and tabs
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Collapse excessive whitespace
    cleaned = re.sub(r' {3,}', '  ', cleaned)
    return cleaned.strip()


def format_ai_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an AI service response into a standard envelope.

    Args:
        response: Raw response dict from AI service.

    Returns:
        Standardized response dict with success, message, and metadata.
    """
    return {
        "success": response.get("success", False),
        "message": response.get("message") or response.get("response") or "",
        "model": response.get("model", "unknown"),
        "tokens_used": response.get("tokens_used", 0),
        "session_id": response.get("session_id"),
    }


def safe_temperature(value: Any, default: float = 0.7) -> float:
    """Safely parse a temperature parameter, clamping to [0.0, 2.0].

    Args:
        value: Raw temperature value.
        default: Default if parsing fails.

    Returns:
        Clamped float.
    """
    try:
        t = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(t, 0.0), 2.0)


def detect_intent(message: str) -> str:
    """Simple intent detection for routing AI chat messages.

    Args:
        message: User's chat message.

    Returns:
        Detected intent string.
    """
    msg_lower = message.lower().strip()

    if any(kw in msg_lower for kw in ("create", "add", "insert", "new")):
        return "create"
    if any(kw in msg_lower for kw in ("update", "modify", "change", "edit")):
        return "update"
    if any(kw in msg_lower for kw in ("delete", "remove", "drop")):
        return "delete"
    if any(kw in msg_lower for kw in ("find", "search", "list", "show", "get", "query")):
        return "query"
    if any(kw in msg_lower for kw in ("analyze", "compare", "assess", "evaluate")):
        return "analyze"
    return "general"
