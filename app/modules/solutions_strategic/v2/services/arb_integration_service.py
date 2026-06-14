"""
ARB Integration Service

Provides seamless integration between Strategic Planning and ARB governance.
Maps investment recommendations to ARB review submissions and syncs decisions
back to capabilities.

Integration Points:
- Investment Matrix → ARB Submission
- ARB Decision → Capability Status Update
- Business Case Auto-population
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_  # dead-code-ok
from sqlalchemy.orm import joinedload

from app import db
from app.models.architecture_review_board import ARBReviewItem, ARBReviewStatus, ReviewType
from app.models.business_capability import BusinessCapability
from app.modules.solutions_strategic.v2.services.arb_governance_service import (
    ARBGovernanceService,
)

logger = logging.getLogger(__name__)


class ARBIntegrationService:
    """
    Service for integrating Strategic Planning with ARB governance.
    
    Provides:
    - Capability → ARB review submission with pre-populated business case
    - ARB decision → Capability status synchronization
    - Bulk submission for multiple capabilities
    - ARB status tracking and reporting
    """
    
    def __init__(self):
        self.arb_service = ARBGovernanceService()
    
    # =========================================================================
    # CAPABILITY → ARB SUBMISSION
    # =========================================================================
    
    def submit_capability_for_review(
        self,
        capability_id: int,
        submitted_by_id: int,
        justification: str = None,
        priority_override: str = None,
        estimated_timeline: str = None,
        additional_context: Dict[str, Any] = None
    ) -> ARBReviewItem:
        """
        Submit a capability for ARB review with auto-populated business case.
        
        Args:
            capability_id: ID of the capability to submit
            submitted_by_id: User ID of submitter
            justification: Additional justification text (optional)
            priority_override: Override capability priority (optional)
            estimated_timeline: Override timeline estimate (optional)
            additional_context: Extra metadata (optional)
        
        Returns:
            Created ARBReviewItem
        
        Raises:
            ValueError: If capability not found or already has pending review
        """
        # Fetch capability with relationships
        capability = db.session.query(BusinessCapability).options(
            joinedload(BusinessCapability.domain),
            joinedload(BusinessCapability.applications)
        ).filter_by(id=capability_id).first()
        
        if not capability:
            raise ValueError(f"Capability {capability_id} not found")
        
        # Check if already has pending ARB review
        if capability.arb_status == 'pending_review':
            raise ValueError(
                f"Capability '{capability.name}' already has a pending ARB review "
                f"(Review ID: {capability.arb_review_id})"
            )
        
        # Build business case from capability data
        business_case = self._build_business_case(
            capability, justification, additional_context
        )
        
        # Map priority
        priority = priority_override or self._map_priority(capability)
        
        # Map business impact
        business_impact = self._calculate_business_impact(capability)
        
        # Map TOGAF phase and ArchiMate layer
        togaf_phase = capability.togaf_phase or 'phase_b_business'
        archimate_layer = capability.archimate_layer or 'business'
        
        # Create ARB review item
        review_item = ARBReviewItem(
            title=f"Strategic Investment: {capability.name}",
            description=business_case['summary'],
            item_type=ReviewType.CAPABILITY.value,
            review_type='capability',
            priority=priority,
            status=ARBReviewStatus.SUBMITTED.value,
            business_impact=business_impact,
            submitted_by_id=submitted_by_id,
            created_by_id=submitted_by_id,
            togaf_phase=togaf_phase,
            archimate_layer=archimate_layer,
            business_justification=business_case['justification'],
            technical_requirements=business_case['technical_requirements'],
            risk_assessment=business_case['risk_assessment'],
            estimated_cost=business_case['estimated_cost'],
            estimated_timeline=estimated_timeline or business_case['timeline'],
            metadata_json={
                'source': 'strategic_planning_investment_matrix',
                'capability_id': capability_id,
                'capability_name': capability.name,
                'capability_domain': capability.domain.name if capability.domain else None,
                'strategic_score': getattr(capability, 'strategic_importance', None),
                'application_count': len(capability.applications) if capability.applications else 0,
                **(additional_context or {})
            }
        )
        
        db.session.add(review_item)
        db.session.flush()  # Get review_item.id
        
        # Update capability ARB tracking
        capability.arb_status = 'pending_review'
        capability.arb_review_id = review_item.id
        capability.arb_submission_date = datetime.utcnow()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(
                "Failed to commit ARB submission capability_id=%s submitted_by_id=%s: %s",
                capability_id,
                submitted_by_id,
                e,
                exc_info=True,
            )
            raise
        
        logger.info(
            f"Submitted capability '{capability.name}' (ID: {capability_id}) "
            f"for ARB review (Review #: {review_item.review_number})"
        )
        
        return review_item
    
    def _build_business_case(
        self,
        capability: BusinessCapability,
        additional_justification: str = None,
        context: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """Build comprehensive business case from capability data."""
        context = context or {}
        
        # Summary
        app_count = len(capability.applications) if capability.applications else 0
        summary = (
            f"Request for ARB approval to invest in the '{capability.name}' capability. "
            f"This capability currently supports {app_count} application{'' if app_count == 1 else 's'} "
            f"in the {capability.domain.name if capability.domain else 'undefined'} domain."
        )
        
        # Business Justification
        justification_parts = []
        
        if hasattr(capability, 'strategic_importance') and capability.strategic_importance:
            justification_parts.append(
                f"Strategic Importance: {capability.strategic_importance}/10 - "
                f"This capability is critical to achieving business objectives."
            )
        
        if hasattr(capability, 'maturity_level'):
            justification_parts.append(
                f"Current Maturity: {capability.maturity_level} - "
                f"Investment required to reach target state."
            )
        
        if additional_justification:
            justification_parts.append(f"Additional Context: {additional_justification}")
        
        if context.get('recommendation'):
            justification_parts.append(f"Investment Recommendation: {context['recommendation']}")
        
        justification = " ".join(justification_parts) if justification_parts else (
            "Investment required to maintain and enhance this strategic capability."
        )
        
        # Technical Requirements
        technical_requirements = (
            f"Capability: {capability.name}\n"
            f"Domain: {capability.domain.name if capability.domain else 'N/A'}\n"
            f"Current Applications: {app_count}\n"
        )
        
        if hasattr(capability, 'technology_stack'):
            technical_requirements += f"Technology Stack: {capability.technology_stack}\n"
        
        # Risk Assessment
        risk_parts = []
        
        if hasattr(capability, 'risk_score') and capability.risk_score:
            risk_level = "High" if capability.risk_score > 7 else "Medium" if capability.risk_score > 4 else "Low"
            risk_parts.append(f"Risk Score: {capability.risk_score}/10 ({risk_level})")
        
        if app_count == 0:
            risk_parts.append("Risk: Capability gap - no supporting applications identified.")
        elif app_count > 10:
            risk_parts.append(f"Risk: High complexity - {app_count} applications to coordinate.")
        
        risk_assessment = " ".join(risk_parts) if risk_parts else (
            "Standard implementation risks apply. Mitigation plan required."
        )
        
        # Cost Estimate
        estimated_cost = context.get('estimated_investment') or getattr(
            capability, 'estimated_investment', 0
        )
        
        # Timeline
        timeline = context.get('timeframe') or getattr(
            capability, 'implementation_timeframe', '12-18 months'
        )
        
        return {
            'summary': summary,
            'justification': justification,
            'technical_requirements': technical_requirements,
            'risk_assessment': risk_assessment,
            'estimated_cost': estimated_cost,
            'timeline': timeline
        }
    
    def _map_priority(self, capability: BusinessCapability) -> str:
        """Map capability priority to ARB priority."""
        priority_mapping = {
            'CRITICAL': 'critical',
            'HIGH': 'high',
            'MEDIUM': 'medium',
            'LOW': 'low'
        }
        
        cap_priority = getattr(capability, 'priority_level', None)
        if cap_priority and cap_priority in priority_mapping:
            return priority_mapping[cap_priority]
        
        # Fallback: use strategic importance
        if hasattr(capability, 'strategic_importance'):
            score = capability.strategic_importance
            if score >= 8:
                return 'critical'
            elif score >= 6:
                return 'high'
            elif score >= 4:
                return 'medium'
        
        return 'medium'  # Default
    
    def _calculate_business_impact(self, capability: BusinessCapability) -> str:
        """Calculate business impact level."""
        # Use strategic importance if available
        if hasattr(capability, 'strategic_importance') and capability.strategic_importance:
            score = capability.strategic_importance
            if score >= 8:
                return 'transformational'
            elif score >= 6:
                return 'significant'
            elif score >= 4:
                return 'moderate'
            else:
                return 'minimal'
        
        # Fallback: use application count
        app_count = len(capability.applications) if capability.applications else 0
        if app_count >= 10:
            return 'significant'
        elif app_count >= 5:
            return 'moderate'
        elif app_count >= 1:
            return 'minimal'
        
        return 'moderate'  # Default
    
    # =========================================================================
    # ARB DECISION → CAPABILITY SYNC
    # =========================================================================
    
    def sync_arb_decision_to_capability(self, review_id: int) -> Optional[BusinessCapability]:
        """
        Sync ARB decision back to capability.
        
        Called when ARB makes a decision on a capability review.
        Updates capability ARB status and decision metadata.
        
        Args:
            review_id: ARB review item ID
        
        Returns:
            Updated BusinessCapability or None if not a capability review
        """
        review = db.session.query(ARBReviewItem).filter_by(id=review_id).first()
        
        if not review:
            logger.warning(f"ARB review {review_id} not found")
            return None
        
        # Only process capability reviews
        if review.review_type != 'capability':
            logger.debug(f"Review {review_id} is not a capability review, skipping sync")
            return None
        
        # Find linked capability
        capability_id = review.metadata_json.get('capability_id') if review.metadata_json else None
        if not capability_id:
            logger.error(f"Review {review_id} has no capability_id in metadata")
            return None
        
        capability = db.session.get(BusinessCapability, capability_id)
        if not capability:
            logger.error(f"Capability {capability_id} not found")
            return None
        
        # Map ARB decision to capability status
        decision = review.decision
        if decision == 'approved':
            capability.arb_status = 'approved'
        elif decision == 'approved_with_conditions':
            capability.arb_status = 'approved_with_conditions'
        elif decision == 'rejected':
            capability.arb_status = 'rejected'
        elif decision == 'deferred':
            capability.arb_status = 'deferred'
        else:
            # Review in progress or other status
            capability.arb_status = 'under_review'
        
        capability.arb_decision_date = review.decision_date or datetime.utcnow()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(
                "Failed to commit ARB decision sync review_id=%s capability_id=%s decision=%s: %s",
                review_id,
                capability_id,
                decision,
                e,
                exc_info=True,
            )
            raise
        
        logger.info(
            f"Synced ARB decision '{decision}' to capability '{capability.name}' "
            f"(ID: {capability_id})"
        )
        
        return capability
    
    # =========================================================================
    # STATUS AND REPORTING
    # =========================================================================
    
    def get_capability_arb_status(self, capability_id: int) -> Dict[str, Any]:
        """
        Get ARB status for a capability.
        
        Returns:
            Dictionary with ARB status, review details, and links
        """
        capability = db.session.get(BusinessCapability, capability_id)
        if not capability:
            raise ValueError(f"Capability {capability_id} not found")
        
        result = {
            'capability_id': capability_id,
            'capability_name': capability.name,
            'arb_status': capability.arb_status or 'not_submitted',
            'arb_submission_date': capability.arb_submission_date.isoformat() if capability.arb_submission_date else None,
            'arb_decision_date': capability.arb_decision_date.isoformat() if capability.arb_decision_date else None,
            'review_details': None
        }
        
        if capability.arb_review_id:
            review = db.session.get(ARBReviewItem, capability.arb_review_id)
            if review:
                result['review_details'] = {
                    'review_id': review.id,
                    'review_number': review.review_number,
                    'status': review.status,
                    'decision': review.decision,
                    'decision_rationale': review.decision_rationale,
                    'conditions': review.conditions,
                    'review_url': f"/arb/review/{review.id}"
                }
        
        return result
    
    def bulk_submit_capabilities(
        self,
        capability_ids: List[int],
        submitted_by_id: int,
        bulk_justification: str = None
    ) -> List[Dict[str, Any]]:
        """
        Submit multiple capabilities for ARB review in bulk.
        
        Args:
            capability_ids: List of capability IDs
            submitted_by_id: User ID of submitter
            bulk_justification: Common justification text
        
        Returns:
            List of submission results (success/error for each)
        """
        results = []
        
        for cap_id in capability_ids:
            try:
                review = self.submit_capability_for_review(
                    capability_id=cap_id,
                    submitted_by_id=submitted_by_id,
                    justification=bulk_justification
                )
                results.append({
                    'capability_id': cap_id,
                    'success': True,
                    'review_id': review.id,
                    'review_number': review.review_number
                })
            except Exception as e:
                logger.error(f"Failed to submit capability {cap_id}: {e}")
                results.append({
                    'capability_id': cap_id,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def get_arb_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio-wide ARB submission summary.
        
        Returns:
            Statistics on ARB submissions across all capabilities
        """
        capabilities = db.session.query(BusinessCapability).all()
        
        # BusinessCapability has no arb_status column; read defensively so the
        # summary returns a valid (zeroed) shape instead of 500ing. getattr keeps
        # this correct if ARB status tracking is added to the model later.
        total = len(capabilities)
        _status = lambda c: getattr(c, "arb_status", None)
        with_arb_status = len([c for c in capabilities if _status(c)])
        pending = len([c for c in capabilities if _status(c) == 'pending_review'])
        approved = len([c for c in capabilities if _status(c) == 'approved'])
        approved_with_conditions = len([c for c in capabilities if _status(c) == 'approved_with_conditions'])
        rejected = len([c for c in capabilities if _status(c) == 'rejected'])
        
        return {
            'total_capabilities': total,
            'with_arb_tracking': with_arb_status,
            'not_submitted': total - with_arb_status,
            'pending_review': pending,
            'approved': approved,
            'approved_with_conditions': approved_with_conditions,
            'rejected': rejected,
            'approval_rate': round((approved + approved_with_conditions) / with_arb_status * 100, 1) if with_arb_status > 0 else 0
        }
