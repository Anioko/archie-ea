"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.document_comparison_service
Backward-compat re-export. Canonical: app/modules/architecture/services/document_comparison_service.py
"""
from app.modules.architecture.services.document_comparison_service import (  # noqa: F401
    ElementChange,
    ComparisonResult,
    DocumentComparisonService,
)
