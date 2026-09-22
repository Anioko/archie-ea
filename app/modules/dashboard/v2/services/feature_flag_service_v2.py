"""Dashboard v2 adapter for feature flag service."""

import importlib

FeatureFlagService = importlib.import_module(
    "app.services.feature_flag_service"
).FeatureFlagService

__all__ = ["FeatureFlagService"]
