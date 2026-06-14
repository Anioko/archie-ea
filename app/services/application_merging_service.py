# DEPRECATED: Import from app.modules.applications.services.application_merging_service instead.
"""Backward-compatibility shim. Canonical: app/modules/applications/services/application_merging_service.py"""
from app.modules.applications.services.application_merging_service import (  # noqa: F401,F403
    MergeCandidate,
    MergeConfig,
    ApplicationMatchingService,
    ApplicationMergeService,
)
