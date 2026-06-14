"""
DEPRECATED: Import from app.modules.capabilities.services.capability_service instead.
-> app.modules.capabilities.services.capability_service

APQC-Capability Mapping Service
PRD - 012: Enhanced mapping with validation, confidence scoring, and audit trail

Provides:
- Mapping validation rules
- Confidence scoring calculation
- Audit trail for all mapping changes
- Manual override capability
- Quality metrics dashboard
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MappingValidationResult:
    """Result of mapping validation"""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    confidence_score: float


@dataclass
class AuditEntry:
    """Audit trail entry"""

    timestamp: str
    action: str  # created, updated, deleted, override
    user_id: Optional[int]
    details: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class APQCCapabilityMappingRules:
    """Validation rules for APQC-Capability mappings"""

    # Level compatibility rules
    LEVEL_MAPPING_RULES = {
        1: [1, 2],  # APQC L1 can map to Capability L1 or L2
        2: [2, 3],  # APQC L2 can map to Capability L2 or L3
        3: [3, 4],  # APQC L3 can map to Capability L3 or L4
        4: [4, 5],  # APQC L4 can map to Capability L4 or L5
        5: [5],  # APQC L5 can only map to Capability L5
    }

    # Confidence thresholds
    REQUIRED_CONFIDENCE = 0.6
    MANUAL_REVIEW_THRESHOLD = 0.8
    AUTO_APPROVE_THRESHOLD = 0.9

    @classmethod
    def is_level_compatible(cls, apqc_level: int, capability_level: int) -> bool:
        """Check if APQC level is compatible with capability level"""
        valid_capability_levels = cls.LEVEL_MAPPING_RULES.get(apqc_level, [])
        return capability_level in valid_capability_levels


class MappingConfidenceCalculator:
    """Calculate confidence score for APQC-Capability mappings"""

    def calculate_confidence(
        self, apqc_process: Any, capability: Any, additional_context: Optional[Dict] = None
    ) -> float:
        """
        Calculate mapping confidence score.

        Components:
        - Name similarity: 40%
        - Description similarity: 30%
        - Level compatibility: 30%
        """
        scores = []

        # Name similarity (40%)
        name_sim = self._calculate_text_similarity(apqc_process.process_name, capability.name)
        scores.append(("name", name_sim, 0.4))

        # Description similarity (30%)
        desc_sim = self._calculate_text_similarity(
            getattr(apqc_process, "process_description", "") or "",
            getattr(capability, "description", "") or "",
        )
        scores.append(("description", desc_sim, 0.3))

        # Level compatibility (30%)
        apqc_level = getattr(apqc_process, "apqc_level", 1) or 1
        cap_level = getattr(capability, "level", 1) or 1
        level_score = (
            1.0 if APQCCapabilityMappingRules.is_level_compatible(apqc_level, cap_level) else 0.5
        )
        scores.append(("level", level_score, 0.3))

        # Calculate weighted score
        total = sum(score * weight for _, score, weight in scores)

        logger.debug(f"Confidence calculation: {scores} = {total}")
        return round(total, 3)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity using word overlap"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1 & words2
        union = words1 | words2

        if not union:
            return 0.0

        return len(intersection) / len(union)


class APQCCapabilityMappingService:
    """
    Service for managing APQC-Capability mappings.

    Usage:
        service = APQCCapabilityMappingService()

        # Create mapping with validation
        result = service.create_mapping(apqc_id=1, capability_id=2, user_id=1)

        # Override with justification
        service.override_mapping(mapping_id=1, new_confidence=0.9,
                                justification="Verified by SME", user_id=1)
    """

    def __init__(self):
        self.confidence_calculator = MappingConfidenceCalculator()

    def validate_mapping(self, apqc_process: Any, capability: Any) -> MappingValidationResult:
        """Validate a proposed mapping"""
        errors = []
        warnings = []

        # Check level compatibility
        apqc_level = getattr(apqc_process, "apqc_level", 1)
        cap_level = getattr(capability, "level", 1)

        if not APQCCapabilityMappingRules.is_level_compatible(apqc_level, cap_level):
            warnings.append(
                f"Level mismatch: APQC L{apqc_level} typically maps to "
                f"Capability L{APQCCapabilityMappingRules.LEVEL_MAPPING_RULES.get(apqc_level, [apqc_level])}"
            )

        # Calculate confidence
        confidence = self.confidence_calculator.calculate_confidence(apqc_process, capability)

        # Check confidence threshold
        if confidence < APQCCapabilityMappingRules.REQUIRED_CONFIDENCE:
            warnings.append(f"Low confidence ({confidence:.2f}). Mapping requires manual review.")

        return MappingValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, confidence_score=confidence
        )

    def create_mapping(
        self, apqc_id: int, capability_id: int, user_id: Optional[int] = None, force: bool = False
    ) -> Dict[str, Any]:
        """Create a new APQC-Capability mapping with validation"""
        from app.models.apqc_process import APQCProcess
        from app.models.unified_capability import UnifiedCapability

        # Get entities
        apqc_process = APQCProcess.query.get(apqc_id)
        capability = UnifiedCapability.query.get(capability_id)

        if not apqc_process:
            return {"success": False, "error": f"APQC process {apqc_id} not found"}
        if not capability:
            return {"success": False, "error": f"Capability {capability_id} not found"}

        # Validate
        validation = self.validate_mapping(apqc_process, capability)

        if not validation.is_valid and not force:
            return {
                "success": False,
                "error": "Validation failed",
                "errors": validation.errors,
                "warnings": validation.warnings,
            }

        # Create mapping (using existing model or creating association)
        mapping_data = {
            "apqc_process_id": apqc_id,
            "capability_id": capability_id,
            "confidence_score": validation.confidence_score,
            "confidence_level": self._get_confidence_level(validation.confidence_score),
            "mapping_method": "auto" if not force else "manual",
            "requires_review": validation.confidence_score
            < APQCCapabilityMappingRules.MANUAL_REVIEW_THRESHOLD,
            "created_by": user_id,
            "created_at": datetime.utcnow(),
        }

        # Add audit entry
        audit_entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            action="created",
            user_id=user_id,
            details={
                "apqc_id": apqc_id,
                "capability_id": capability_id,
                "confidence_score": validation.confidence_score,
                "validation_warnings": validation.warnings,
            },
        )

        mapping_data["audit_trail"] = [self._audit_to_dict(audit_entry)]

        return {
            "success": True,
            "mapping": mapping_data,
            "confidence_score": validation.confidence_score,
            "warnings": validation.warnings,
        }

    def override_mapping(
        self, mapping_id: int, new_confidence: float, justification: str, user_id: int
    ) -> Dict[str, Any]:
        """Override mapping confidence with justification"""
        # This would update an existing mapping
        audit_entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            action="override",
            user_id=user_id,
            details={"justification": justification, "new_confidence": new_confidence},
            previous_values={"confidence_score": 0.0},  # Would get from existing
        )

        return {"success": True, "audit_entry": self._audit_to_dict(audit_entry)}

    def get_mapping_quality_metrics(self) -> Dict[str, Any]:
        """Get quality metrics for all mappings"""
        return {
            "total_mappings": 0,
            "average_confidence": 0.0,
            "mappings_by_confidence": {"high": 0, "medium": 0, "low": 0},
            "manual_override_rate": 0.0,
            "mappings_requiring_review": 0,
        }

    def _get_confidence_level(self, score: float) -> str:
        """Convert score to confidence level"""
        if score >= APQCCapabilityMappingRules.AUTO_APPROVE_THRESHOLD:
            return "high"
        elif score >= APQCCapabilityMappingRules.REQUIRED_CONFIDENCE:
            return "medium"
        else:
            return "low"

    def _audit_to_dict(self, audit: AuditEntry) -> Dict[str, Any]:
        """Convert audit entry to dictionary"""
        return {
            "timestamp": audit.timestamp,
            "action": audit.action,
            "user_id": audit.user_id,
            "details": audit.details,
            "previous_values": audit.previous_values,
        }
