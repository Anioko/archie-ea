"""
Detection Strategies Module

Implements the Strategy Pattern for duplicate detection algorithms.
Each strategy implements a common interface but uses different detection approaches.
"""

from .base import DetectionStrategy
from .enhanced_strategy import EnhancedDetectionStrategy
from .fast_strategy import FastDetectionStrategy
from .hybrid_strategy import HybridDetectionStrategy

__all__ = [
    "DetectionStrategy",
    "FastDetectionStrategy",
    "HybridDetectionStrategy",
    "EnhancedDetectionStrategy",
]
