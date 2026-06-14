"""Dashboard v2 adapter for rationalization scoring service."""

import importlib

RationalizationScoringService = importlib.import_module(
    "app.services.rationalization_scoring_service"
).RationalizationScoringService

__all__ = ["RationalizationScoringService"]
