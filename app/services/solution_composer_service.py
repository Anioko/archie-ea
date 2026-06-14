# mass-deletion-ok — v1→v2 migration: 3,490-line duplicate replaced with shim
# DEPRECATED(2026-03-17): Import from app.modules.solutions_strategic.v2.services.solution_composer_service instead.  # dead-code-ok
"""Backward-compatibility shim. Canonical: app/modules/solutions_strategic/v2/services/solution_composer_service.py"""
from app.modules.solutions_strategic.v2.services.solution_composer_service import (  # noqa: F401,F403  # dead-code-ok
    SolutionComposerService,
    CanvasNode,
    CanvasConnection,
    CanvasState,
)
