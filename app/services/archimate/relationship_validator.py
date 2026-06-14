"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.relationship_validator
Backward-compat re-export. Canonical: app/modules/architecture/services/relationship_validator.py
"""
from app.modules.architecture.services.relationship_validator import (  # noqa: F401
    ValidationResult,
    BatchValidationResult,
    RelationshipValidator,
    get_relationship_validator,
)
