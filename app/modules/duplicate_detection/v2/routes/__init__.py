"""Duplicate Detection v2 route blueprints."""

from .unified_duplicate_routes import unified_duplicate_bp_v2
from .ai_dedupe_routes import ai_dedupe_bp_v2

__all__ = ["unified_duplicate_bp_v2", "ai_dedupe_bp_v2"]
