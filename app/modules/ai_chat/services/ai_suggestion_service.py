"""
-> app.modules.ai_chat.services.ai_analysis_service

AI Suggestion Service

Manages the creation, retrieval, and processing of AI-generated suggestions.
Supports the hybrid manual/automated workflow pattern where users can choose
between manual entry, AI-assisted entry, or fully automated processing.

Usage:
    service = AISuggestionService()

    # Create a suggestion
    suggestion = service.create_suggestion(
        entity_type='application',
        entity_id=123,
        suggestion_type='field_value',
        field_name='vendor_id',
        suggested_value={'id': 456, 'name': 'SAP SE'},
        confidence=0.92,
        source='document_analysis',
        reasoning='Matched vendor name in uploaded specification document'
    )

    # Get pending suggestions for review
    pending = service.get_pending_suggestions(entity_type='application')

    # Accept/reject suggestions
    service.accept_suggestion(suggestion_id, user_id)
    service.reject_suggestion(suggestion_id, user_id, notes='Incorrect match')
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import and_, func, or_

from app import db
from app.models.ai_suggestion import AISuggestion, SuggestionFeedback, UserPreference


class AISuggestionService:
    """
    Service for managing AI suggestions in hybrid workflows.

    Provides methods for creating suggestions, reviewing them,
    and tracking feedback for continuous improvement.
    """

    # Suggestion sources
    SOURCE_DOCUMENT_ANALYSIS = "document_analysis"
    SOURCE_RELATIONSHIP_DERIVATION = "relationship_derivation"
    SOURCE_PATTERN_MATCHING = "pattern_matching"
    SOURCE_APQC_MAPPING = "apqc_mapping"
    SOURCE_CAPABILITY_DISCOVERY = "capability_discovery"
    SOURCE_GAP_DETECTION = "gap_detection"
    SOURCE_VENDOR_MATCHING = "vendor_matching"
    SOURCE_DUPLICATE_DETECTION = "duplicate_detection"

    # Suggestion types
    TYPE_FIELD_VALUE = "field_value"
    TYPE_RELATIONSHIP = "relationship"
    TYPE_NEW_ENTITY = "new_entity"
    TYPE_MAPPING = "mapping"
    TYPE_CLASSIFICATION = "classification"
    TYPE_MERGE = "merge"

    # Entity types
    ENTITY_APPLICATION = "application"
    ENTITY_CAPABILITY = "capability"
    ENTITY_VENDOR = "vendor"
    ENTITY_PROCESS = "process"
    ENTITY_RELATIONSHIP = "relationship"
    ENTITY_GAP = "gap"
    ENTITY_ROADMAP_ITEM = "roadmap_item"

    def __init__(self):
        """Initialize the AI suggestion service."""
        self.app = current_app._get_current_object() if current_app else None

    def create_suggestion(
        self,
        entity_type: str,
        suggestion_type: str,
        suggested_value: Any,
        confidence: float,
        source: str,
        entity_id: Optional[int] = None,
        field_name: Optional[str] = None,
        current_value: Any = None,
        reasoning: Optional[str] = None,
        confidence_factors: Optional[Dict] = None,
        source_reference: Optional[Dict] = None,
        workflow_name: Optional[str] = None,
        workflow_step: Optional[str] = None,
        batch_id: Optional[str] = None,
        priority: str = "normal",
        category: Optional[str] = None,
        expires_in_hours: Optional[int] = None,
    ) -> AISuggestion:
        """
        Create a new AI suggestion.

        Args:
            entity_type: Type of entity (application, capability, etc.)
            suggestion_type: Type of suggestion (field_value, relationship, etc.)
            suggested_value: The AI's suggested value
            confidence: Confidence score 0 - 1
            source: Source of suggestion (document_analysis, pattern_matching, etc.)
            entity_id: ID of existing entity (None for new entity suggestions)
            field_name: Specific field being suggested
            current_value: Current value for comparison
            reasoning: Human-readable explanation
            confidence_factors: Breakdown of confidence score
            source_reference: Reference to source (document, rule, etc.)
            workflow_name: Name of workflow this suggestion is part of
            workflow_step: Step in workflow
            batch_id: Group related suggestions
            priority: Priority level (critical, high, normal, low)
            category: Additional categorization
            expires_in_hours: Hours until suggestion expires

        Returns:
            Created AISuggestion object
        """
        suggestion = AISuggestion(
            entity_type=entity_type,
            entity_id=entity_id,
            suggestion_type=suggestion_type,
            field_name=field_name,
            suggested_value=suggested_value,
            current_value=current_value,
            confidence=confidence,
            confidence_factors=confidence_factors,
            reasoning=reasoning,
            source=source,
            source_reference=source_reference,
            workflow_name=workflow_name,
            workflow_step=workflow_step,
            batch_id=batch_id,
            priority=priority,
            category=category,
            status="pending",
        )

        if expires_in_hours:
            suggestion.expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        db.session.add(suggestion)
        db.session.commit()

        return suggestion

    def create_batch_suggestions(
        self,
        suggestions_data: List[Dict],
        workflow_name: Optional[str] = None,
        workflow_step: Optional[str] = None,
    ) -> Tuple[str, List[AISuggestion]]:
        """
        Create multiple suggestions as a batch.

        Args:
            suggestions_data: List of suggestion dictionaries
            workflow_name: Common workflow name
            workflow_step: Common workflow step

        Returns:
            Tuple of (batch_id, list of created suggestions)
        """
        batch_id = str(uuid.uuid4())[:8]
        created = []

        for data in suggestions_data:
            data["batch_id"] = batch_id
            if workflow_name:
                data["workflow_name"] = workflow_name
            if workflow_step:
                data["workflow_step"] = workflow_step

            suggestion = AISuggestion(**data)
            db.session.add(suggestion)
            created.append(suggestion)

        db.session.commit()
        return batch_id, created

    def get_pending_suggestions(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        source: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        priority: Optional[str] = None,
        workflow_name: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "priority_confidence",
    ) -> List[AISuggestion]:
        """
        Get pending suggestions with filters.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by specific entity
            source: Filter by suggestion source
            min_confidence: Minimum confidence threshold
            max_confidence: Maximum confidence threshold
            priority: Filter by priority
            workflow_name: Filter by workflow
            batch_id: Filter by batch
            limit: Maximum results
            offset: Pagination offset
            order_by: Sort order (priority_confidence, confidence, created_at)

        Returns:
            List of matching suggestions
        """
        query = AISuggestion.query.filter(AISuggestion.status == "pending")

        # Apply filters
        if entity_type:
            query = query.filter(AISuggestion.entity_type == entity_type)
        if entity_id is not None:
            query = query.filter(AISuggestion.entity_id == entity_id)
        if source:
            query = query.filter(AISuggestion.source == source)
        if min_confidence is not None:
            query = query.filter(AISuggestion.confidence >= min_confidence)
        if max_confidence is not None:
            query = query.filter(AISuggestion.confidence <= max_confidence)
        if priority:
            query = query.filter(AISuggestion.priority == priority)
        if workflow_name:
            query = query.filter(AISuggestion.workflow_name == workflow_name)
        if batch_id:
            query = query.filter(AISuggestion.batch_id == batch_id)

        # Exclude expired suggestions
        query = query.filter(
            or_(AISuggestion.expires_at.is_(None), AISuggestion.expires_at > datetime.utcnow())
        )

        # Apply ordering
        if order_by == "priority_confidence":
            # Custom priority order: critical > high > normal > low
            priority_order = db.case(
                (AISuggestion.priority == "critical", 1),
                (AISuggestion.priority == "high", 2),
                (AISuggestion.priority == "normal", 3),
                (AISuggestion.priority == "low", 4),
                else_=5,
            )
            query = query.order_by(priority_order, AISuggestion.confidence.desc())
        elif order_by == "confidence":
            query = query.order_by(AISuggestion.confidence.desc())
        elif order_by == "created_at":
            query = query.order_by(AISuggestion.created_at.desc())

        return query.offset(offset).limit(limit).all()

    def get_suggestions_for_entity(
        self, entity_type: str, entity_id: int, include_reviewed: bool = False
    ) -> List[AISuggestion]:
        """
        Get all suggestions for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            include_reviewed: Include already reviewed suggestions

        Returns:
            List of suggestions
        """
        query = AISuggestion.query.filter(
            AISuggestion.entity_type == entity_type, AISuggestion.entity_id == entity_id
        )

        if not include_reviewed:
            query = query.filter(AISuggestion.status == "pending")

        return query.order_by(AISuggestion.confidence.desc()).all()

    def accept_suggestion(
        self,
        suggestion_id: int,
        user_id: int,
        final_value: Any = None,
        notes: Optional[str] = None,
        apply_to_entity: bool = True,
    ) -> Dict:
        """
        Accept an AI suggestion.

        Args:
            suggestion_id: ID of suggestion to accept
            user_id: ID of reviewing user
            final_value: Value to use (defaults to suggested_value)
            notes: Optional review notes
            apply_to_entity: Whether to apply the value to the entity

        Returns:
            Result dictionary with applied changes
        """
        suggestion = db.session.get(AISuggestion, suggestion_id)
        if not suggestion:
            return {"success": False, "error": "Suggestion not found"}

        if suggestion.status != "pending":
            return {"success": False, "error": f"Suggestion already {suggestion.status}"}

        # Mark as accepted
        suggestion.accept(user_id, final_value, notes)

        result = {
            "success": True,
            "suggestion_id": suggestion_id,
            "status": "accepted",
            "applied_value": suggestion.final_value,
            "applied_to_entity": False,
        }

        # Apply to entity if requested
        if apply_to_entity and suggestion.entity_id and suggestion.field_name:
            applied = self._apply_suggestion_to_entity(suggestion)
            result["applied_to_entity"] = applied

        db.session.commit()
        return result

    def reject_suggestion(
        self, suggestion_id: int, user_id: int, notes: Optional[str] = None
    ) -> Dict:
        """
        Reject an AI suggestion.

        Args:
            suggestion_id: ID of suggestion to reject
            user_id: ID of reviewing user
            notes: Optional reason for rejection

        Returns:
            Result dictionary
        """
        suggestion = db.session.get(AISuggestion, suggestion_id)
        if not suggestion:
            return {"success": False, "error": "Suggestion not found"}

        if suggestion.status != "pending":
            return {"success": False, "error": f"Suggestion already {suggestion.status}"}

        suggestion.reject(user_id, notes)
        db.session.commit()

        return {"success": True, "suggestion_id": suggestion_id, "status": "rejected"}

    def modify_and_accept(
        self,
        suggestion_id: int,
        user_id: int,
        modified_value: Any,
        notes: Optional[str] = None,
        apply_to_entity: bool = True,
    ) -> Dict:
        """
        Accept a suggestion with modifications.

        Args:
            suggestion_id: ID of suggestion
            user_id: ID of reviewing user
            modified_value: User's modified value
            notes: Optional notes
            apply_to_entity: Whether to apply the value

        Returns:
            Result dictionary
        """
        suggestion = db.session.get(AISuggestion, suggestion_id)
        if not suggestion:
            return {"success": False, "error": "Suggestion not found"}

        if suggestion.status != "pending":
            return {"success": False, "error": f"Suggestion already {suggestion.status}"}

        suggestion.modify(user_id, modified_value, notes)

        result = {
            "success": True,
            "suggestion_id": suggestion_id,
            "status": "modified",
            "original_value": suggestion.suggested_value,
            "applied_value": modified_value,
            "applied_to_entity": False,
        }

        if apply_to_entity and suggestion.entity_id and suggestion.field_name:
            applied = self._apply_suggestion_to_entity(suggestion)
            result["applied_to_entity"] = applied

        db.session.commit()
        return result

    def bulk_accept_by_confidence(
        self,
        user_id: int,
        threshold: float = 0.85,
        entity_type: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Dict:
        """
        Auto-accept all suggestions above confidence threshold.

        Args:
            user_id: ID of user approving
            threshold: Minimum confidence to auto-accept
            entity_type: Optional filter by entity type
            batch_id: Optional filter by batch

        Returns:
            Result with count of accepted suggestions
        """
        query = AISuggestion.query.filter(
            AISuggestion.status == "pending", AISuggestion.confidence >= threshold
        )

        if entity_type:
            query = query.filter(AISuggestion.entity_type == entity_type)
        if batch_id:
            query = query.filter(AISuggestion.batch_id == batch_id)

        suggestions = query.all()
        count = 0

        for suggestion in suggestions:
            suggestion.status = "auto_accepted"
            suggestion.reviewed_by_id = user_id
            suggestion.reviewed_at = datetime.utcnow()
            suggestion.final_value = suggestion.suggested_value
            suggestion.review_notes = f"Auto-accepted (confidence >= {threshold:.0%})"
            count += 1

        db.session.commit()

        return {"success": True, "accepted_count": count, "threshold": threshold}

    def bulk_reject_by_confidence(
        self,
        user_id: int,
        threshold: float = 0.5,
        entity_type: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Dict:
        """
        Reject all suggestions below confidence threshold.

        Args:
            user_id: ID of user rejecting
            threshold: Maximum confidence to reject
            entity_type: Optional filter
            batch_id: Optional filter

        Returns:
            Result with count
        """
        query = AISuggestion.query.filter(
            AISuggestion.status == "pending", AISuggestion.confidence < threshold
        )

        if entity_type:
            query = query.filter(AISuggestion.entity_type == entity_type)
        if batch_id:
            query = query.filter(AISuggestion.batch_id == batch_id)

        suggestions = query.all()
        count = 0

        for suggestion in suggestions:
            suggestion.status = "rejected"
            suggestion.reviewed_by_id = user_id
            suggestion.reviewed_at = datetime.utcnow()
            suggestion.review_notes = f"Bulk rejected (confidence < {threshold:.0%})"
            count += 1

        db.session.commit()

        return {"success": True, "rejected_count": count, "threshold": threshold}

    def mark_helpful(self, suggestion_id: int, helpful: bool) -> Dict:
        """
        Record user feedback on suggestion quality.

        Args:
            suggestion_id: ID of suggestion
            helpful: Whether suggestion was helpful

        Returns:
            Result dictionary
        """
        suggestion = db.session.get(AISuggestion, suggestion_id)
        if not suggestion:
            return {"success": False, "error": "Suggestion not found"}

        suggestion.mark_helpful(helpful)
        db.session.commit()

        return {"success": True, "suggestion_id": suggestion_id, "was_helpful": helpful}

    def get_statistics(self, days: int = 30) -> Dict:
        """
        Get suggestion statistics for dashboard.

        Args:
            days: Number of days to include

        Returns:
            Statistics dictionary
        """
        since = datetime.utcnow() - timedelta(days=days)

        base_query = AISuggestion.query.filter(AISuggestion.created_at >= since)

        total = base_query.count()
        pending = base_query.filter(AISuggestion.status == "pending").count()
        accepted = base_query.filter(AISuggestion.status == "accepted").count()
        auto_accepted = base_query.filter(AISuggestion.status == "auto_accepted").count()
        rejected = base_query.filter(AISuggestion.status == "rejected").count()
        modified = base_query.filter(AISuggestion.status == "modified").count()

        reviewed = accepted + rejected + modified + auto_accepted
        acceptance_rate = (accepted + modified + auto_accepted) / reviewed if reviewed > 0 else 0

        # By entity type
        by_entity = (
            db.session.query(AISuggestion.entity_type, func.count(AISuggestion.id))
            .filter(AISuggestion.created_at >= since, AISuggestion.status == "pending")
            .group_by(AISuggestion.entity_type)
            .all()
        )

        # By source
        by_source = (
            db.session.query(AISuggestion.source, func.count(AISuggestion.id))
            .filter(AISuggestion.created_at >= since, AISuggestion.status == "pending")
            .group_by(AISuggestion.source)
            .all()
        )

        # Average confidence
        avg_confidence = (
            db.session.query(func.avg(AISuggestion.confidence))
            .filter(AISuggestion.created_at >= since)
            .scalar()
        ) or 0

        # Helpfulness
        helpful = base_query.filter(AISuggestion.was_helpful == True).count()
        unhelpful = base_query.filter(AISuggestion.was_helpful == False).count()
        feedback_total = helpful + unhelpful
        helpfulness_rate = helpful / feedback_total if feedback_total > 0 else None

        return {
            "period_days": days,
            "total": total,
            "pending": pending,
            "accepted": accepted,
            "auto_accepted": auto_accepted,
            "rejected": rejected,
            "modified": modified,
            "reviewed": reviewed,
            "acceptance_rate": round(acceptance_rate * 100, 1),
            "average_confidence": round(avg_confidence * 100, 1),
            "pending_by_entity_type": dict(by_entity),
            "pending_by_source": dict(by_source),
            "helpfulness_rate": round(helpfulness_rate * 100, 1) if helpfulness_rate else None,
            "feedback_count": feedback_total,
        }

    def expire_old_suggestions(self, hours: int = 168) -> int:
        """
        Expire suggestions older than specified hours.

        Args:
            hours: Age threshold (default 7 days)

        Returns:
            Count of expired suggestions
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        expired = AISuggestion.query.filter(
            AISuggestion.status == "pending",
            or_(AISuggestion.expires_at <= datetime.utcnow(), AISuggestion.created_at <= cutoff),
        ).all()

        count = 0
        for suggestion in expired:
            suggestion.status = "expired"
            count += 1

        db.session.commit()
        return count

    def _apply_suggestion_to_entity(self, suggestion: AISuggestion) -> bool:
        """
        Apply accepted suggestion value to the target entity.

        Args:
            suggestion: The accepted suggestion

        Returns:
            True if applied successfully
        """
        try:
            # Get the entity model based on type
            entity = self._get_entity(suggestion.entity_type, suggestion.entity_id)
            if not entity:
                return False

            # Apply the value
            value = (
                suggestion.final_value
                if suggestion.final_value is not None
                else suggestion.suggested_value
            )

            # Handle different value types
            if suggestion.field_name and hasattr(entity, suggestion.field_name):
                setattr(entity, suggestion.field_name, value)
                return True

            return False

        except Exception as e:
            current_app.logger.error(f"Failed to apply suggestion {suggestion.id}: {e}")
            return False

    def _get_entity(self, entity_type: str, entity_id: int) -> Optional[Any]:
        """
        Get entity by type and ID.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Entity object or None
        """
        from app.models.application_layer import ApplicationComponent
        from app.models.apqc_process import APQCProcess
        from app.models.vendor import VendorProduct

        model_map = {
            "application": ApplicationComponent,
            "vendor": VendorProduct,
            "process": APQCProcess,
        }

        model = model_map.get(entity_type)
        if model:
            return db.session.get(model, entity_id)

        return None

    # User preference methods

    def get_user_preferences(self, user_id: int) -> UserPreference:
        """
        Get or create user preferences.

        Args:
            user_id: User ID

        Returns:
            UserPreference object
        """
        return UserPreference.get_or_create(user_id)

    def update_user_preferences(self, user_id: int, **kwargs) -> UserPreference:
        """
        Update user preferences.

        Args:
            user_id: User ID
            **kwargs: Preference fields to update

        Returns:
            Updated UserPreference object
        """
        pref = UserPreference.get_or_create(user_id)

        allowed_fields = [
            "default_entry_mode",
            "show_ai_suggestions",
            "auto_derive_relationships",
            "auto_map_apqc_processes",
            "auto_link_capabilities",
            "require_approval_for_ai",
            "auto_accept_high_confidence",
            "high_confidence_threshold",
            "notify_on_suggestions",
            "notify_on_gaps_detected",
            "notify_on_policy_violations",
            "workflow_mode_overrides",
        ]

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(pref, key, value)

        db.session.commit()
        return pref

    def should_auto_suggest(self, user_id: int, workflow_name: Optional[str] = None) -> bool:
        """
        Check if AI suggestions should be shown for a user/workflow.

        Args:
            user_id: User ID
            workflow_name: Optional workflow name

        Returns:
            True if suggestions should be shown
        """
        pref = self.get_user_preferences(user_id)

        if not pref.show_ai_suggestions:
            return False

        if workflow_name:
            mode = pref.get_mode_for_workflow(workflow_name)
            return mode in ["assisted", "automated", "hybrid"]

        return pref.default_entry_mode != "manual"

    def should_auto_accept(
        self, user_id: int, confidence: float, workflow_name: Optional[str] = None
    ) -> bool:
        """
        Check if a suggestion should be auto-accepted based on user preferences.

        Args:
            user_id: User ID
            confidence: Suggestion confidence
            workflow_name: Optional workflow name

        Returns:
            True if should auto-accept
        """
        pref = self.get_user_preferences(user_id)

        if not pref.auto_accept_high_confidence:
            return False

        if workflow_name:
            mode = pref.get_mode_for_workflow(workflow_name)
            if mode == "manual":
                return False

        return confidence >= pref.high_confidence_threshold


# Singleton instance
ai_suggestion_service = AISuggestionService()
