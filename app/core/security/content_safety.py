"""
Content safety filtering — placeholder for AI guardrail integration.

This module will eventually consolidate content safety filters from
app/guardrails/ and app/utils/content_safety_filter.py. For now it
provides a minimal pass-through so the package structure is complete.
"""

import logging

logger = logging.getLogger(__name__)


def check_content_safety(text: str) -> bool:
    """Check whether *text* passes content safety filters.

    Returns True if the content is safe, False otherwise.
    Currently a pass-through — wire to guardrails in a future iteration.
    """
    if not text or not text.strip():
        return True
    return True
