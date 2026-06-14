"""
Architecture Review Board (ARB) Governance Service

Implements comprehensive ARB governance aligned with TOGAF ADM and ArchiMate 3.2.
Integrates with existing platform capabilities:
- Solution Design workflow
- Capability-based planning
- Architecture Decision Records (ADRs)
- Gap Analysis
- EA Workflow Engine

TOGAF ADM Integration:
- Phase A: Architecture Vision reviews
- Phase B-D: Domain architecture reviews
- Phase E-F: Opportunity and migration reviews
- Phase G: Implementation governance
- Phase H: Change management reviews
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.architecture_review_board import (
    DEFAULT_GOVERNANCE_STANDARDS,
    ARBBoardMember,
    ARBCapabilityImpact,
    ARBGovernanceStandard,
    ARBReviewComment,
    ARBReviewItem,
    ARBReviewStatus,
    ArchitectureReviewBoard,
    ReviewType,
    TOGAFPhase,
)

logger = logging.getLogger(__name__)


class ARBGovernanceService:
    """
    Service for managing Architecture Review Board governance processes.

    Provides comprehensive governance capabilities:
    - ARB session management
    - Review item lifecycle management
    - Governance scoring and assessment
    - Integration with capabilities and solutions
    - TOGAF ADM alignment
    - ArchiMate viewpoint validation
    """

    # Governance scoring weights
    SCORING_WEIGHTS = {"compliance": 0.35, "risk": 0.30, "quality": 0.35}

    # TOGAF ADM phase to ArchiMate layer mapping
    TOGAF_ARCHIMATE_MAPPING = {
        "phase_a_vision": ["motivation", "strategy"],
        "phase_b_business": ["business"],
        "phase_c_information_systems": ["application"],
        "phase_d_technology": ["technology"],
        "phase_e_opportunities": ["implementation"],
        "phase_f_migration": ["implementation"],
        "phase_g_implementation": ["implementation", "technology"],
        "phase_h_change_management": ["all"],
    }

    # =========================================================================
    # ARB SESSION MANAGEMENT
    # =========================================================================

    def create_arb_session(
        self,
        name: str,
        scheduled_date: datetime,
        chair_id: int,
        description: str = None,
        duration_minutes: int = 120,
        location: str = None,
        meeting_link: str = None,
        secretary_id: int = None,
    ) -> ArchitectureReviewBoard:
        """
        Create a new ARB session.

        Args:
            name: Session name/title
            scheduled_date: When the session is scheduled
            chair_id: User ID of the ARB chair
            description: Optional description
            duration_minutes: Expected duration
            location: Physical location
            meeting_link: Video conference URL
            secretary_id: User ID of secretary

        Returns:
            Created ArchitectureReviewBoard instance
        """
        board_number = ArchitectureReviewBoard.generate_board_number()

        arb = ArchitectureReviewBoard(
            board_number=board_number,
            name=name,
            description=description,
            scheduled_date=scheduled_date,
            duration_minutes=duration_minutes,
            location=location,
            meeting_link=meeting_link,
            chair_id=chair_id,
            secretary_id=secretary_id,
            status="scheduled",
        )

        db.session.add(arb)
        db.session.commit()

        logger.info(f"Created ARB session {board_number}: {name}")
        return arb

    def add_board_member(
        self, arb_session_id: int, user_id: int, role: str, voting_member: bool = True
    ) -> ARBBoardMember:
        """Add a member to an ARB session."""
        member = ARBBoardMember(
            arb_session_id=arb_session_id,
            user_id=user_id,
            role=role,
            voting_member=voting_member,
            attendance_status="pending",
        )

        db.session.add(member)
        db.session.commit()
        return member

    def get_upcoming_sessions(self, days: int = 30) -> List[ArchitectureReviewBoard]:
        """Get upcoming ARB sessions."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        return (
            ArchitectureReviewBoard.query.filter(
                ArchitectureReviewBoard.scheduled_date >= datetime.utcnow(),
                ArchitectureReviewBoard.scheduled_date <= cutoff,
                ArchitectureReviewBoard.status == "scheduled",
            )
            .order_by(ArchitectureReviewBoard.scheduled_date)
            .all()
        )

    def complete_session(self, arb_session_id: int, minutes: str = None) -> ArchitectureReviewBoard:
        """Complete an ARB session and finalize metrics."""
        arb = db.session.get(ArchitectureReviewBoard, arb_session_id)
        if not arb:
            raise ValueError(f"ARB session {arb_session_id} not found")

        # Calculate metrics
        review_items = arb.review_items
        arb.items_reviewed = len(review_items)
        arb.items_approved = len(
            [i for i in review_items if i.decision in ["approved", "approved_with_conditions"]]
        )
        arb.items_rejected = len([i for i in review_items if i.decision == "rejected"])
        arb.items_deferred = len([i for i in review_items if i.decision == "deferred"])

        # Generate decisions summary
        arb.decisions_summary = {
            "total_items": arb.items_reviewed,
            "approved": arb.items_approved,
            "rejected": arb.items_rejected,
            "deferred": arb.items_deferred,
            "decisions": [
                {
                    "review_number": item.review_number,
                    "title": item.title,
                    "decision": item.decision,
                    "conditions": item.conditions,
                }
                for item in review_items
            ],
        }

        if minutes:
            arb.minutes = minutes

        arb.status = "completed"
        arb.completed_at = datetime.utcnow()

        db.session.commit()
        return arb

    # =========================================================================
    # REVIEW ITEM MANAGEMENT
    # =========================================================================

    def submit_for_review(
        self,
        title: str,
        description: str,
        review_type: str,
        submitter_id: int,
        togaf_phase: str = None,
        archimate_layer: str = None,
        solution_id: int = None,
        adr_id: int = None,
        architecture_model_id: int = None,
        priority: str = "medium",
        business_impact: str = "medium",
        estimated_effort: str = "medium",
        capability_ids: List[int] = None,
    ) -> ARBReviewItem:
        """
        Submit an item for ARB review.

        Automatically integrates with:
        - Solutions (if solution_id provided)
        - ADRs (if adr_id provided)
        - Capabilities (if capability_ids provided)

        Args:
            title: Review item title
            description: Detailed description
            review_type: Type from ReviewType enum
            submitter_id: User ID of submitter
            togaf_phase: TOGAF ADM phase
            archimate_layer: Primary ArchiMate layer
            solution_id: Optional linked solution
            adr_id: Optional linked ADR
            architecture_model_id: Optional linked architecture model
            priority: Priority level
            business_impact: Business impact level
            estimated_effort: Estimated effort
            capability_ids: List of impacted capability IDs

        Returns:
            Created ARBReviewItem
        """
        review_number = ARBReviewItem.generate_review_number()

        # Auto-determine ArchiMate layer from TOGAF phase if not provided
        if togaf_phase and not archimate_layer:
            layers = self.TOGAF_ARCHIMATE_MAPPING.get(togaf_phase, ["application"])
            archimate_layer = layers[0] if layers else "application"

        item = ARBReviewItem(
            review_number=review_number,
            title=title,
            description=description,
            review_type=review_type,
            togaf_phase=togaf_phase,
            archimate_layer=archimate_layer,
            priority=priority,
            business_impact=business_impact,
            estimated_effort=estimated_effort,
            solution_id=solution_id,
            adr_id=adr_id,
            architecture_model_id=architecture_model_id,
            submitter_id=submitter_id,
            status="draft",
        )

        db.session.add(item)
        db.session.flush()  # Get ID for capability links

        # Link capabilities
        if capability_ids:
            for cap_id in capability_ids:
                impact = ARBCapabilityImpact(
                    review_item_id=item.id,
                    capability_id=cap_id,
                    impact_type="modifies",
                    impact_level="medium",
                )
                db.session.add(impact)

        # Initialize governance checklist based on review type
        item.governance_checklist = self._get_governance_checklist(review_type, togaf_phase)

        db.session.commit()

        logger.info(f"Submitted review item {review_number}: {title}")
        return item

    def submit_item(self, review_item_id: int) -> ARBReviewItem:
        """Submit a draft review item for ARB consideration."""
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        if item.status != "draft":
            raise ValueError(f"Item must be in draft status to submit")

        item.status = "submitted"
        item.submitted_at = datetime.utcnow()

        db.session.commit()
        return item

    def assign_to_session(self, review_item_id: int, arb_session_id: int) -> ARBReviewItem:
        """Assign a review item to an ARB session."""
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        item.arb_session_id = arb_session_id
        item.status = "under_review"
        item.review_started_at = datetime.utcnow()

        db.session.commit()
        return item

    def record_decision(
        self,
        review_item_id: int,
        decision: str,
        rationale: str,
        decided_by_id: int,
        conditions: List[Dict] = None,
    ) -> ARBReviewItem:
        """
        Record the ARB decision for a review item.

        Args:
            review_item_id: ID of the review item
            decision: Decision outcome (approved, approved_with_conditions, rejected, deferred)
            rationale: Explanation for the decision
            decided_by_id: User ID who recorded the decision
            conditions: Optional conditions for approval

        Returns:
            Updated ARBReviewItem
        """
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        item.decision = decision
        item.decision_rationale = rationale
        item.decided_by_id = decided_by_id
        item.decision_date = datetime.utcnow()
        item.review_completed_at = datetime.utcnow()

        if conditions:
            item.conditions = conditions
            item.follow_up_required = True

        # Update status based on decision
        if decision == "approved":
            item.status = "approved"
        elif decision == "approved_with_conditions":
            item.status = "approved_with_conditions"
        elif decision == "rejected":
            item.status = "rejected"
        elif decision == "deferred":
            item.status = "deferred"

        db.session.commit()
        return item

    # =========================================================================
    # GOVERNANCE ASSESSMENT
    # =========================================================================

    def assess_compliance(self, review_item_id: int) -> float:
        """
        Assess compliance score for a review item.

        Returns:
            Compliance score (0 - 100)
        """
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        # Get applicable governance standards
        standards = self._get_applicable_standards(item.review_type, item.togaf_phase)

        if not standards:
            return 100.0  # No applicable standards = full compliance

        # Calculate compliance based on checklist completion
        checklist = item.governance_checklist or {}
        completed_items = 0
        total_items = 0

        for standard in standards:
            for checklist_item in standard.checklist_items:
                total_items += 1
                if checklist_item.get("required", False):
                    item_key = f"std_{standard.code}_{checklist_item['item']}"
                    if checklist.get(item_key, False):
                        completed_items += 1

        compliance_score = (completed_items / total_items * 100) if total_items > 0 else 100
        item.compliance_score = compliance_score

        db.session.commit()
        return compliance_score

    def assess_risk(self, review_item_id: int) -> float:
        """
        Assess risk score for a review item.

        Factors:
        - Business impact
        - Priority
        - Number of impacted capabilities
        - Technology complexity

        Returns:
            Risk score (0 - 100, higher = riskier)
        """
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        # Base risk factors
        risk_factors = {
            "business_impact": {"critical": 25, "high": 20, "medium": 10, "low": 5},
            "priority": {"critical": 20, "high": 15, "medium": 10, "low": 5},
            "estimated_effort": {"xl": 15, "large": 10, "medium": 5, "small": 2},
        }

        total_risk = 0

        # Business impact risk
        if item.business_impact:
            total_risk += risk_factors["business_impact"].get(item.business_impact, 10)

        # Priority risk
        if item.priority:
            total_risk += risk_factors["priority"].get(item.priority, 10)

        # Effort risk
        if item.estimated_effort:
            total_risk += risk_factors["estimated_effort"].get(item.estimated_effort, 5)

        # Capability impact risk
        capability_count = len(item.capability_links)
        if capability_count > 5:
            total_risk += 15
        elif capability_count > 2:
            total_risk += 10
        elif capability_count > 0:
            total_risk += 5

        # Cap at 100
        risk_score = min(total_risk, 100)
        item.risk_score = risk_score

        db.session.commit()
        return risk_score

    def assess_quality(self, review_item_id: int) -> float:
        """
        Assess quality score for a review item.

        Factors:
        - Documentation completeness
        - ArchiMate model quality
        - ADR coverage
        - Requirements traceability

        Returns:
            Quality score (0 - 100)
        """
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        quality_score = 0
        max_score = 0

        # Description quality (20 points)
        max_score += 20
        if item.description and len(item.description) > 100:
            quality_score += 20
        elif item.description:
            quality_score += 10

        # Linked entities (30 points)
        max_score += 30
        linked_entities = 0
        if item.solution_id:
            linked_entities += 10
        if item.adr_id:
            linked_entities += 10
        if item.architecture_model_id:
            linked_entities += 10
        quality_score += linked_entities

        # Capability mapping (20 points)
        max_score += 20
        if item.capability_links:
            quality_score += 20

        # ArchiMate layer specification (10 points)
        max_score += 10
        if item.archimate_layer:
            quality_score += 10

        # TOGAF phase specification (10 points)
        max_score += 10
        if item.togaf_phase:
            quality_score += 10

        # Attachments (10 points)
        max_score += 10
        if item.attachments and len(item.attachments) > 0:
            quality_score += 10

        # Normalize to 0 - 100
        final_score = (quality_score / max_score * 100) if max_score > 0 else 0
        item.quality_score = final_score

        db.session.commit()
        return final_score

    def calculate_overall_score(self, review_item_id: int) -> float:
        """
        Calculate weighted overall governance score.

        Returns:
            Overall score (0 - 100)
        """
        item = db.session.get(ARBReviewItem, review_item_id)
        if not item:
            raise ValueError(f"Review item {review_item_id} not found")

        # Ensure individual scores are calculated
        if item.compliance_score is None:
            self.assess_compliance(review_item_id)
        if item.risk_score is None:
            self.assess_risk(review_item_id)
        if item.quality_score is None:
            self.assess_quality(review_item_id)

        # Calculate weighted average
        scores = []
        weights = []

        if item.compliance_score is not None:
            scores.append(item.compliance_score)
            weights.append(self.SCORING_WEIGHTS["compliance"])

        if item.risk_score is not None:
            # Risk is inverted - lower risk = higher score
            scores.append(100 - item.risk_score)
            weights.append(self.SCORING_WEIGHTS["risk"])

        if item.quality_score is not None:
            scores.append(item.quality_score)
            weights.append(self.SCORING_WEIGHTS["quality"])

        if scores and weights:
            overall_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            overall_score = 0

        item.overall_score = overall_score
        db.session.commit()

        return overall_score

    # =========================================================================
    # INTEGRATION WITH EXISTING WORKFLOWS
    # =========================================================================

    def auto_submit_solution_for_review(self, solution_id: int, submitter_id: int) -> ARBReviewItem:
        """
        Automatically submit a solution for ARB review when it reaches certain criteria.

        Triggered when:
        - Solution status changes to 'ready_for_review'
        - Solution has required documentation
        - Solution has capability mappings

        Args:
            solution_id: Solution ID
            submitter_id: User ID of the submitter

        Returns:
            Created ARBReviewItem
        """
        from app.models.truly_missing_models import Solution

        solution = db.session.get(Solution, solution_id)
        if not solution:
            raise ValueError(f"Solution {solution_id} not found")

        # Determine review type based on solution characteristics
        review_type = "solution_design"
        togaf_phase = "phase_e_opportunities"  # Solutions typically align with Phase E

        # Get capability mappings
        capability_ids = []
        if hasattr(solution, "capability_mappings"):
            capability_ids = [cm.capability_id for cm in solution.capability_mappings]

        return self.submit_for_review(
            title=f"Solution Review: {solution.name}",
            description=f"Architecture review for solution: {solution.description or 'No description'}",
            review_type=review_type,
            submitter_id=submitter_id,
            togaf_phase=togaf_phase,
            solution_id=solution_id,
            capability_ids=capability_ids,
            priority=self._determine_priority_from_solution(solution),
        )

    def auto_submit_adr_for_review(self, adr_id: int, submitter_id: int) -> ARBReviewItem:
        """
        Automatically submit an ADR for ARB review when significant.

        Triggered when:
        - ADR has high business value
        - ADR affects multiple systems
        - ADR introduces new technology

        Args:
            adr_id: ADR ID
            submitter_id: User ID of the submitter

        Returns:
            Created ARBReviewItem
        """
        from app.models.adr import ArchitectureDecisionRecord

        adr = db.session.get(ArchitectureDecisionRecord, adr_id)
        if not adr:
            raise ValueError(f"ADR {adr_id} not found")

        # Determine if ADR needs ARB review
        if not self._adr_needs_arb_review(adr):
            return None

        # Get linked capabilities
        capability_ids = []
        from app.models.unified_capability import UnifiedCapability

        if adr.linked_capabilities:
            capability_ids = [cap.id for cap in adr.linked_capabilities]

        return self.submit_for_review(
            title=f"ADR Review: {adr.title}",
            description=f"Architecture Decision Record review: {adr.context}",
            review_type="architecture_change",
            submitter_id=submitter_id,
            togaf_phase=self._map_adr_to_togaf_phase(adr),
            adr_id=adr_id,
            capability_ids=capability_ids,
            priority=self._determine_priority_from_adr(adr),
        )

    def get_pending_reviews_by_capability(self, capability_id: int) -> List[ARBReviewItem]:
        """
        Get all pending review items that impact a specific capability.

        Useful for capability owners to track governance activities.

        Args:
            capability_id: Capability ID

        Returns:
            List of ARBReviewItem
        """
        return (
            ARBReviewItem.query.join(ARBCapabilityImpact)
            .filter(
                ARBCapabilityImpact.capability_id == capability_id,
                ARBReviewItem.status.in_(["submitted", "under_review", "pending_info"]),
            )
            .order_by(ARBReviewItem.priority.desc(), ARBReviewItem.created_at)
            .all()
        )

    def get_governance_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive governance dashboard data.

        Returns:
            Dashboard metrics and data
        """
        # Overall metrics
        total_items = ARBReviewItem.query.count()
        pending_items = ARBReviewItem.query.filter(
            ARBReviewItem.status.in_(["submitted", "under_review", "pending_info"])
        ).count()
        approved_items = ARBReviewItem.query.filter(ARBReviewItem.status == "approved").count()
        rejected_items = ARBReviewItem.query.filter(ARBReviewItem.status == "rejected").count()

        # Recent activity
        recent_reviews = (
            ARBReviewItem.query.order_by(ARBReviewItem.created_at.desc()).limit(10).all()
        )

        # Upcoming ARB sessions
        upcoming_sessions = self.get_upcoming_sessions(days=30)

        # Review type distribution
        review_types = (
            db.session.query(ARBReviewItem.review_type, func.count(ARBReviewItem.id))
            .group_by(ARBReviewItem.review_type)
            .all()
        )

        # TOGAF phase distribution
        togaf_phases = (
            db.session.query(ARBReviewItem.togaf_phase, func.count(ARBReviewItem.id))
            .filter(ARBReviewItem.togaf_phase.isnot(None))
            .group_by(ARBReviewItem.togaf_phase)
            .all()
        )

        return {
            "metrics": {
                "total_items": total_items,
                "pending_items": pending_items,
                "approved_items": approved_items,
                "rejected_items": rejected_items,
                "approval_rate": (approved_items / total_items * 100) if total_items > 0 else 0,
            },
            "recent_reviews": [item.to_dict(include_details=False) for item in recent_reviews],
            "upcoming_sessions": [session.to_dict() for session in upcoming_sessions],
            "review_types": [{"type": rt[0], "count": rt[1]} for rt in review_types],
            "togaf_phases": [{"phase": tp[0], "count": tp[1]} for tp in togaf_phases],
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_governance_checklist(self, review_type: str, togaf_phase: str = None) -> Dict:
        """Get governance checklist for a review type."""
        standards = self._get_applicable_standards(review_type, togaf_phase)
        checklist = {}

        for standard in standards:
            for item in standard.checklist_items:
                key = f"std_{standard.code}_{item['item']}"
                checklist[key] = False  # Default to not completed

        return checklist

    def _get_applicable_standards(
        self, review_type: str, togaf_phase: str = None
    ) -> List[ARBGovernanceStandard]:
        """Get governance standards applicable to a review type."""
        query = ARBGovernanceStandard.query.filter(
            ARBGovernanceStandard.status == "active",
            ARBGovernanceStandard.applies_to_review_types.contains([review_type]),
        )

        if togaf_phase:
            query = query.filter(
                or_(
                    ARBGovernanceStandard.togaf_phase == togaf_phase,
                    ARBGovernanceStandard.togaf_phase.is_(None),
                )
            )

        return query.all()

    def _determine_priority_from_solution(self, solution) -> str:
        """Determine review priority from solution characteristics."""
        # This would analyze solution attributes to determine priority
        # For now, return medium as default
        return "medium"

    def _determine_priority_from_adr(self, adr) -> str:
        """Determine review priority from ADR characteristics."""
        if adr.business_value == "critical":
            return "critical"
        elif adr.business_value == "high":
            return "high"
        elif adr.estimated_effort in ["large", "xl"]:
            return "high"
        return "medium"

    def _adr_needs_arb_review(self, adr) -> bool:
        """Determine if an ADR needs ARB review."""
        # High business value decisions need review
        if adr.business_value in ["critical", "high"]:
            return True

        # Decisions affecting multiple systems need review
        if adr.affected_systems and len(adr.affected_systems.split(",")) > 1:
            return True

        # Technology stack changes need review
        if adr.technology_stack_id:
            return True

        return False

    def _map_adr_to_togaf_phase(self, adr) -> str:
        """Map ADR to appropriate TOGAF phase."""
        if adr.archimate_layer == "motivation":
            return "phase_a_vision"
        elif adr.archimate_layer == "strategy":
            return "phase_a_vision"
        elif adr.archimate_layer == "business":
            return "phase_b_business"
        elif adr.archimate_layer == "application":
            return "phase_c_information_systems"
        elif adr.archimate_layer == "technology":
            return "phase_d_technology"
        else:
            return "phase_e_opportunities"

    # =========================================================================
    # GOVERNANCE STANDARDS MANAGEMENT
    # =========================================================================

    def initialize_governance_standards(self):
        """Initialize default governance standards."""
        for std_data in DEFAULT_GOVERNANCE_STANDARDS:
            existing = ARBGovernanceStandard.query.filter_by(code=std_data["code"]).first()
            if not existing:
                standard = ARBGovernanceStandard(
                    code=std_data["code"],
                    name=std_data["name"],
                    description=std_data["description"],
                    category=std_data["category"],
                    requirements=std_data["requirements"],
                    checklist_items=std_data["checklist_items"],
                    mandatory=std_data["mandatory"],
                    status="active",
                    effective_date=datetime.utcnow().date(),
                )
                db.session.add(standard)

        db.session.commit()
        logger.info("Initialized ARB governance standards")

    def get_governance_standards(self, category: str = None) -> List[ARBGovernanceStandard]:
        """Get governance standards, optionally filtered by category."""
        query = ARBGovernanceStandard.query.filter_by(status="active")

        if category:
            query = query.filter_by(category=category)

        return query.order_by(ARBGovernanceStandard.code).all()
