"""
Value Stream models for enterprise architecture value delivery mapping.

This module imports the canonical ValueStream models from strategy_layer.py
to avoid duplication and ensure consistency across the application.
"""

# Import the canonical ArchiMate ValueStream models
from .strategy_layer import ValueStream, ValueStreamStage
