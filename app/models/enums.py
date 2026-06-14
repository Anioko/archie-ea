"""Transaction mode enums for mapping operations.

This module defines transaction modes used across all mapping flows
to ensure consistent transaction semantics.
"""
from enum import Enum


class TransactionMode(Enum):
    """Transaction mode for mapping operations.
    
    ATOMIC: All operations committed in a single transaction (all-or-nothing).
    PREVIEW: Analysis only, no persistence, results returned for review.
    
    Usage:
        - Auto Map: Supports both PREVIEW (analyze) and ATOMIC (accept/commit)
        - Import: Uses ATOMIC for single-commit semantics
        - Legacy: Previously auto-commit per mapping (now deprecated)
    """
    ATOMIC = "atomic"  # All-or-nothing commit
    PREVIEW = "preview"  # Analysis only, no persistence


class MappingConfidenceLevel(Enum):
    """Confidence levels for AI-generated mappings."""
    HIGH = "high"  # >= 0.8
    MEDIUM = "medium"  # 0.6 - 0.8
    LOW = "low"  # < 0.6


class MappingOperationType(Enum):
    """Types of mapping operations."""
    CAPABILITY = "capability"
    PROCESS = "process"
    ARCHIMATE = "archimate"
    VENDOR_PRODUCT = "vendor_product"
    VENDOR_ARCHIMATE = "vendor_archimate"
