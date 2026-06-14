"""
ARB Readiness Service

Provides pre-submission validation for ARB review items.
Checks required fields, document requirements, and governance standard
compliance before allowing submission to ARB.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.architecture_review_board import (
    ARBGovernanceStandard,
    ARBReadinessCheck,
    ARBReviewItem,
    ReviewType,
)
from app.services.arb_audit_service import arb_audit_service

logger = logging.getLogger(__name__)


class ARBReadinessService:
    """
    Service for pre-submission readiness validation.

    Validates review items against:
    - Required fields based on review type
    - Document/attachment requirements
    - Governance standard checklists
    """

    # Required fields by review type
    REQUIRED_FIELDS = {
        ReviewType.SOLUTION_DESIGN.value: {
            "title": "Title is required",
            "description": "Description is required",
            "togaf_phase": "TOGAF ADM phase must be specified",
            "business_impact": "Business impact level must be specified",
        },
        ReviewType.ARCHITECTURE_CHANGE.value: {
            "title": "Title is required",
            "description": "Description is required",
            "togaf_phase": "TOGAF ADM phase must be specified",
        },
        ReviewType.TECHNOLOGY_SELECTION.value: {
            "title": "Title is required",
            "description": "Description is required",
            "business_impact": "Business impact level must be specified",
            "estimated_effort": "Estimated effort must be specified",
        },
        ReviewType.CAPABILITY_IMPLEMENTATION.value: {
            "title": "Title is required",
            "description": "Description is required",
            "togaf_phase": "TOGAF ADM phase must be specified",
        },
        ReviewType.INTEGRATION_PATTERN.value: {
            "title": "Title is required",
            "description": "Description is required",
            "archimate_layer": "ArchiMate layer must be specified",
        },
        ReviewType.SECURITY_REVIEW.value: {
            "title": "Title is required",
            "description": "Description is required",
            "business_impact": "Business impact level must be specified",
        },
        ReviewType.COMPLIANCE_REVIEW.value: {
            "title": "Title is required",
            "description": "Description is required",
        },
        ReviewType.EXCEPTION_REQUEST.value: {
            "title": "Title is required",
            "description": "Description is required",
        },
        ReviewType.STANDARD_DEVIATION.value: {
            "title": "Title is required",
            "description": "Description is required",
            "business_impact": "Business impact level must be specified",
        },
        ReviewType.RETIREMENT_REVIEW.value: {
            "title": "Title is required",
            "description": "Description is required",
        },
    }

    # Recommended linked entities by review type
    RECOMMENDED_LINKS = {
        ReviewType.SOLUTION_DESIGN.value: ["solution_id", "capability_links"],
        ReviewType.ARCHITECTURE_CHANGE.value: ["adr_id"],
        ReviewType.TECHNOLOGY_SELECTION.value: ["architecture_model_id"],
        ReviewType.CAPABILITY_IMPLEMENTATION.value: ["capability_links"],
    }

    # Document requirements by review type (warn if missing)
    DOCUMENT_RECOMMENDATIONS = {
        ReviewType.SOLUTION_DESIGN.value: [
            {"key": "architecture_diagram", "description": "Architecture diagram recommended"},
            {"key": "business_case", "description": "Business case document recommended"},
        ],
        ReviewType.SECURITY_REVIEW.value: [
            {"key": "threat_model", "description": "Threat model recommended"},
            {"key": "security_controls", "description": "Security controls document recommended"},
        ],
        ReviewType.INTEGRATION_PATTERN.value: [
            {"key": "integration_diagram", "description": "Integration diagram recommended"},
            {"key": "api_specification", "description": "API specification recommended"},
        ],
    }

    def __init__(self):
        pass

    def validate_readiness(
        self,
        review_item_id: int,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """
        Run full readiness validation on a review item.

        Args:
            review_item_id: ID of the review item to validate
            user_id: ID of user running the check (for audit)

        Returns:
            Dictionary with validation results
        """
        review_item = db.session.get(ARBReviewItem, review_item_id)
        if not review_item:
            return {
                "success": False,
                "error": f"Review item {review_item_id} not found",
            }

        old_score = review_item.readiness_score

        # Clear existing readiness checks
        ARBReadinessCheck.query.filter_by(review_item_id=review_item_id).delete()

        # Run all validation checks
        required_results = self._check_required_fields(review_item)
        link_results = self._check_recommended_links(review_item)
        document_results = self._check_document_requirements(review_item)
        standard_results = self._check_governance_standards(review_item)

        # Combine all checks
        all_checks = required_results + link_results + document_results + standard_results

        # Save checks to database
        for check_data in all_checks:
            check = ARBReadinessCheck(
                review_item_id=review_item_id,
                standard_id=check_data.get("standard_id"),
                check_type=check_data["check_type"],
                check_key=check_data["check_key"],
                check_description=check_data["description"],
                is_required=check_data.get("is_required", True),
                is_satisfied=check_data["is_satisfied"],
                validation_message=check_data.get("validation_message"),
            )
            db.session.add(check)

        # Calculate readiness score
        required_checks = [c for c in all_checks if c.get("is_required", True)]
        satisfied_required = [c for c in required_checks if c["is_satisfied"]]

        if required_checks:
            score = (len(satisfied_required) / len(required_checks)) * 100
        else:
            score = 100.0

        # Update review item
        review_item.readiness_score = score
        review_item.readiness_checked_at = datetime.utcnow()
        review_item.readiness_warnings = [
            c["description"]
            for c in all_checks
            if not c["is_satisfied"] and not c.get("is_required", True)
        ]

        db.session.commit()

        # Log audit event
        if user_id:
            arb_audit_service.log_readiness_check(
                review_item=review_item,
                user_id=user_id,
                old_score=old_score or 0,
                new_score=score,
            )

        return {
            "success": True,
            "review_item_id": review_item_id,
            "review_number": review_item.review_number,
            "readiness_score": score,
            "is_ready": score >= 100.0,
            "checked_at": review_item.readiness_checked_at.isoformat(),
            "total_checks": len(all_checks),
            "required_checks": len(required_checks),
            "satisfied_required": len(satisfied_required),
            "checks": all_checks,
            "warnings": review_item.readiness_warnings,
            "blocking_issues": [
                c for c in all_checks if c.get("is_required", True) and not c["is_satisfied"]
            ],
        }

    def get_readiness_status(
        self,
        review_item_id: int,
    ) -> Dict[str, Any]:
        """
        Get current readiness status without re-running validation.

        Args:
            review_item_id: ID of the review item

        Returns:
            Current readiness status
        """
        review_item = db.session.get(ARBReviewItem, review_item_id)
        if not review_item:
            return {"success": False, "error": "Review item not found"}

        checks = ARBReadinessCheck.query.filter_by(review_item_id=review_item_id).all()

        return {
            "success": True,
            "review_item_id": review_item_id,
            "readiness_score": review_item.readiness_score,
            "readiness_checked_at": (
                review_item.readiness_checked_at.isoformat()
                if review_item.readiness_checked_at
                else None
            ),
            "is_ready": (review_item.readiness_score or 0) >= 100.0,
            "warnings": review_item.readiness_warnings or [],
            "checks": [
                {
                    "id": c.id,
                    "check_type": c.check_type,
                    "check_key": c.check_key,
                    "description": c.check_description,
                    "is_required": c.is_required,
                    "is_satisfied": c.is_satisfied,
                    "validation_message": c.validation_message,
                }
                for c in checks
            ],
        }

    def get_checklist_for_review_type(
        self,
        review_type: str,
        togaf_phase: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get the full checklist for a review type.

        Args:
            review_type: Type of review
            togaf_phase: Optional TOGAF phase for additional filtering

        Returns:
            List of checklist items
        """
        checklist = []

        # Add required fields
        required_fields = self.REQUIRED_FIELDS.get(review_type, {})
        for field, message in required_fields.items():
            checklist.append(
                {
                    "check_type": "required_field",
                    "check_key": field,
                    "description": message,
                    "is_required": True,
                }
            )

        # Add recommended links
        recommended = self.RECOMMENDED_LINKS.get(review_type, [])
        for link in recommended:
            checklist.append(
                {
                    "check_type": "recommended_link",
                    "check_key": link,
                    "description": f"Link to {link.replace('_id', '').replace('_', ' ')} recommended",
                    "is_required": False,
                }
            )

        # Add document recommendations
        docs = self.DOCUMENT_RECOMMENDATIONS.get(review_type, [])
        for doc in docs:
            checklist.append(
                {
                    "check_type": "document",
                    "check_key": doc["key"],
                    "description": doc["description"],
                    "is_required": False,
                }
            )

        # Add governance standard checklists
        standards = self._get_applicable_standards(review_type, togaf_phase)
        for standard in standards:
            if standard.checklist_items:
                for item in standard.checklist_items:
                    checklist.append(
                        {
                            "check_type": "governance_standard",
                            "check_key": f"std_{standard.code}_{item.get('item', '')}",
                            "description": item.get("item", ""),
                            "is_required": item.get("required", False) and standard.mandatory,
                            "standard_id": standard.id,
                            "standard_code": standard.code,
                        }
                    )

        return checklist

    def mark_check_satisfied(
        self,
        check_id: int,
        user_id: int,
        satisfied: bool = True,
    ) -> Dict[str, Any]:
        """
        Manually mark a readiness check as satisfied.

        Args:
            check_id: ID of the readiness check
            user_id: ID of user marking the check
            satisfied: Whether the check is satisfied

        Returns:
            Updated check status
        """
        check = db.session.get(ARBReadinessCheck, check_id)
        if not check:
            return {"success": False, "error": "Check not found"}

        check.is_satisfied = satisfied
        check.satisfied_at = datetime.utcnow() if satisfied else None
        check.satisfied_by_id = user_id if satisfied else None

        db.session.commit()

        # Recalculate readiness score
        self._recalculate_score(check.review_item_id)

        return {
            "success": True,
            "check_id": check_id,
            "is_satisfied": check.is_satisfied,
        }

    # =========================================================================
    # INTERNAL CHECK METHODS
    # =========================================================================

    def _check_required_fields(
        self,
        review_item: ARBReviewItem,
    ) -> List[Dict[str, Any]]:
        """Check required fields for the review type."""
        results = []
        required_fields = self.REQUIRED_FIELDS.get(review_item.review_type, {})

        for field, message in required_fields.items():
            value = getattr(review_item, field, None)
            is_satisfied = bool(value)

            # Special handling for description - require minimum length
            if field == "description" and value:
                is_satisfied = len(value.strip()) >= 20

            results.append(
                {
                    "check_type": "required_field",
                    "check_key": field,
                    "description": message,
                    "is_required": True,
                    "is_satisfied": is_satisfied,
                    "validation_message": None if is_satisfied else message,
                }
            )

        return results

    def _check_recommended_links(
        self,
        review_item: ARBReviewItem,
    ) -> List[Dict[str, Any]]:
        """Check recommended entity links."""
        results = []
        recommended = self.RECOMMENDED_LINKS.get(review_item.review_type, [])

        for link in recommended:
            if link == "capability_links":
                is_satisfied = len(review_item.capability_links) > 0
                description = "Capability mapping recommended"
            else:
                value = getattr(review_item, link, None)
                is_satisfied = value is not None
                description = f"Link to {link.replace('_id', '').replace('_', ' ')} recommended"

            results.append(
                {
                    "check_type": "recommended_link",
                    "check_key": link,
                    "description": description,
                    "is_required": False,
                    "is_satisfied": is_satisfied,
                    "validation_message": None if is_satisfied else description,
                }
            )

        return results

    def _check_document_requirements(
        self,
        review_item: ARBReviewItem,
    ) -> List[Dict[str, Any]]:
        """Check document/attachment requirements."""
        results = []
        docs = self.DOCUMENT_RECOMMENDATIONS.get(review_item.review_type, [])
        attachments = review_item.attachments or []

        for doc in docs:
            # Check if attachment with matching key exists
            is_satisfied = (
                any(
                    att.get("key") == doc["key"] or doc["key"] in att.get("name", "").lower()
                    for att in attachments
                )
                if attachments
                else False
            )

            results.append(
                {
                    "check_type": "document",
                    "check_key": doc["key"],
                    "description": doc["description"],
                    "is_required": False,
                    "is_satisfied": is_satisfied,
                    "validation_message": None if is_satisfied else doc["description"],
                }
            )

        return results

    def _check_governance_standards(
        self,
        review_item: ARBReviewItem,
    ) -> List[Dict[str, Any]]:
        """Check governance standard compliance."""
        results = []
        standards = self._get_applicable_standards(
            review_item.review_type,
            review_item.togaf_phase,
        )

        checklist = review_item.governance_checklist or {}

        for standard in standards:
            if not standard.checklist_items:
                continue

            for item in standard.checklist_items:
                item_text = item.get("item", "")
                check_key = f"std_{standard.code}_{item_text}"
                is_required = item.get("required", False) and standard.mandatory

                # Check if item is marked as completed in governance_checklist
                is_satisfied = checklist.get(check_key, False)

                results.append(
                    {
                        "check_type": "governance_standard",
                        "check_key": check_key,
                        "description": f"[{standard.code}] {item_text}",
                        "is_required": is_required,
                        "is_satisfied": is_satisfied,
                        "standard_id": standard.id,
                        "validation_message": None
                        if is_satisfied
                        else f"Standard {standard.code}: {item_text}",
                    }
                )

        return results

    def _get_applicable_standards(
        self,
        review_type: str,
        togaf_phase: str = None,
    ) -> List[ARBGovernanceStandard]:
        """Get governance standards applicable to a review type."""
        query = ARBGovernanceStandard.query.filter(ARBGovernanceStandard.status == "active")

        standards = query.all()

        # Filter by review type in Python to handle JSON field
        applicable = []
        for standard in standards:
            if standard.applies_to_review_types:
                types = standard.applies_to_review_types
                if isinstance(types, list) and review_type in types:
                    applicable.append(standard)
                elif isinstance(types, str) and review_type in types:
                    applicable.append(standard)
            else:
                # Standards without specific types apply to all
                applicable.append(standard)

        return applicable

    def _recalculate_score(self, review_item_id: int) -> float:
        """Recalculate readiness score for a review item."""
        review_item = db.session.get(ARBReviewItem, review_item_id)
        if not review_item:
            return 0.0

        checks = ARBReadinessCheck.query.filter_by(review_item_id=review_item_id).all()

        required_checks = [c for c in checks if c.is_required]
        satisfied_required = [c for c in required_checks if c.is_satisfied]

        if required_checks:
            score = (len(satisfied_required) / len(required_checks)) * 100
        else:
            score = 100.0

        review_item.readiness_score = score
        review_item.readiness_warnings = [
            c.check_description for c in checks if not c.is_satisfied and not c.is_required
        ]

        db.session.commit()
        return score


# Create singleton instance
arb_readiness_service = ARBReadinessService()
