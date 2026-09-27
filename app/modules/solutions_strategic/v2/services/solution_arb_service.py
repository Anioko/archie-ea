"""
SolutionARBService: Track Architecture Review Board approval for solutions.
Separate from the capability ARB tracking - this is for solution governance.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from app import db
from app.models.solution_governance import SolutionARBReview, SolutionVersion


class SolutionARBService:
    """Manage ARB submission and decision tracking for solutions."""

    @staticmethod
    def _session_actor() -> tuple:
        """Return ``(user_id, organization_id)`` from the authenticated session.

        Governance actors are never taken from a request body.  Raises
        ``PermissionError`` when there is no tenant-bound authenticated user.
        """
        from flask import g
        from flask_login import current_user

        if not getattr(current_user, "is_authenticated", False):
            raise PermissionError("actor_not_authorized")
        user_id = getattr(current_user, "id", None)
        org_id = getattr(g, "current_org_id", None)
        if not isinstance(org_id, int) or org_id <= 0:
            org_id = getattr(current_user, "organization_id", None)
        if not isinstance(user_id, int) or not isinstance(org_id, int) or org_id <= 0:
            raise PermissionError("actor_not_authorized")
        return user_id, org_id


    def submit_for_arb_review(
        self,
        solution_id: int,
        version_id: Optional[int] = None,
        submitted_by_id: int = None,
        submission_notes: Optional[str] = None
    ) -> SolutionARBReview:
        """
        Submit solution to ARB for review.
        
        Args:
            solution_id: Solution to submit
            version_id: Specific version to review
            submitted_by_id: Who is submitting
            submission_notes: Submission notes for ARB
        
        Returns:
            SolutionARBReview: New review record
        """
        raise ValueError(
            "Legacy solution ARB writes are disabled; use the canonical evidence-gated submission service"
        )
    
    def record_arb_attendance(
        self,
        review_id: int,
        attendees: List[Dict]  # [{user_id, name, vote}]
    ) -> SolutionARBReview:
        """
        Record who attended ARB and how they voted.
        
        Args:
            review_id: ARB review
            attendees: List of attendees with votes
        
        Returns:
            SolutionARBReview: Updated review
        """
        _, organization_id = self._session_actor()
        review = db.session.execute(
            db.select(SolutionARBReview).where(
                SolutionARBReview.id == review_id,
                SolutionARBReview.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not review:
            raise LookupError("arb_review_not_found")
        
        review.arb_attendees = attendees
        
        db.session.commit()
        
        return review
    
    def record_arb_decision(
        self,
        review_id: int,
        decision: str,  # approved, rejected, conditional
        decision_reason: str,
        solution_id: Optional[int] = None,
        conditions: Optional[List[Dict]] = None,
        compliance_notes: Optional[Dict] = None
    ) -> SolutionARBReview:
        """
        Record ARB decision.

        The deciding actor is resolved from the authenticated session only — a
        caller-supplied ``decided_by_id`` is not accepted, because it let a
        browser attribute a governance decision to another user.

        Args:
            review_id: ARB review
            decision: approved/rejected/conditional
            decision_reason: Why this decision
            solution_id: Solution the review must belong to (membership proof)
            conditions: Conditions for approval (if conditional)
            compliance_notes: Compliance assessment per area

        Returns:
            SolutionARBReview: Updated review

        Raises:
            PermissionError: no authenticated tenant-bound actor
            LookupError: review missing, foreign, or not on this solution
            ValueError: invalid decision value
        """
        decided_by_id, organization_id = self._session_actor()

        predicates = [
            SolutionARBReview.id == review_id,
            SolutionARBReview.organization_id == organization_id,
        ]
        if solution_id is not None:
            predicates.append(SolutionARBReview.solution_id == solution_id)
        review = db.session.execute(
            db.select(SolutionARBReview).where(*predicates)
        ).scalar_one_or_none()
        if not review:
            # Same outcome for missing and foreign: never confirm existence.
            raise LookupError("arb_review_not_found")

        if decision not in ['approved', 'rejected', 'conditional']:
            raise ValueError("invalid_decision")

        review.arb_decision = decision
        review.decided_by_id = decided_by_id
        review.decided_at = datetime.utcnow()
        review.arb_decision_reason = decision_reason
        
        if conditions:
            review.conditions = conditions
        
        if compliance_notes:
            review.compliance_notes = compliance_notes
        
        db.session.commit()
        
        # If approved, update related version
        if review.version_id and decision == 'approved':
            version = db.session.execute(
                db.select(SolutionVersion).where(
                    SolutionVersion.id == review.version_id,
                    SolutionVersion.organization_id == organization_id,
                )
            ).scalar_one_or_none()
            if version:
                version.approval_status = 'approved'
                version.approved_at = datetime.utcnow()
                version.approved_by_id = decided_by_id
                db.session.commit()
        
        return review
    
    def add_compliance_review(
        self,
        review_id: int,
        compliance_areas: List[str],  # [security, finance, ops, legal, etc.]
        compliance_notes: Dict[str, str]
    ) -> SolutionARBReview:
        """
        Add compliance review assessment.
        
        Args:
            review_id: ARB review
            compliance_areas: Areas reviewed
            compliance_notes: Assessment per area
        
        Returns:
            SolutionARBReview: Updated review
        """
        _, organization_id = self._session_actor()
        review = db.session.execute(
            db.select(SolutionARBReview).where(
                SolutionARBReview.id == review_id,
                SolutionARBReview.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not review:
            raise LookupError("arb_review_not_found")
        
        review.compliance_areas_reviewed = compliance_areas
        review.compliance_notes = compliance_notes
        
        db.session.commit()
        
        return review
    
    def schedule_next_review(
        self,
        review_id: int,
        next_review_date: datetime,
        next_steps: str
    ) -> SolutionARBReview:
        """
        Schedule next ARB review.
        
        Args:
            review_id: Current ARB review
            next_review_date: When to review next
            next_steps: What happens next
        
        Returns:
            SolutionARBReview: Updated review
        """
        _, organization_id = self._session_actor()
        review = db.session.execute(
            db.select(SolutionARBReview).where(
                SolutionARBReview.id == review_id,
                SolutionARBReview.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not review:
            raise LookupError("arb_review_not_found")
        
        review.next_review_date = next_review_date
        review.next_steps = next_steps
        
        db.session.commit()
        
        return review
    
    def get_compliance_trail(self, solution_id: int) -> List[Dict]:
        """
        Get full compliance/governance trail for solution.
        
        Args:
            solution_id: Solution to trace
        
        Returns:
            List of all ARB reviews and decisions
        """
        reviews = db.session.query(SolutionARBReview).filter(
            SolutionARBReview.solution_id == solution_id
        ).order_by(SolutionARBReview.submitted_at).all()
        
        trail = []
        for review in reviews:
            trail.append({
                'review_id': review.id,
                'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None,
                'submitted_by_id': review.submitted_by_id,
                'submission_version': review.submission_version,
                'arb_decision': review.arb_decision,
                'decided_at': review.decided_at.isoformat() if review.decided_at else None,
                'decided_by_id': review.decided_by_id,
                'decision_reason': review.arb_decision_reason,
                'attendees': review.arb_attendees,
                'compliance_areas': review.compliance_areas_reviewed,
                'conditions': review.conditions,
                'next_steps': review.next_steps
            })
        
        return trail
    
    def get_arb_status(self, solution_id: int) -> Dict[str, Any]:
        """
        Get current ARB status for solution.
        
        Args:
            solution_id: Solution to check
        
        Returns:
            Dict with current ARB status
        """
        latest_review = db.session.query(SolutionARBReview).filter(
            SolutionARBReview.solution_id == solution_id
        ).order_by(SolutionARBReview.submitted_at.desc()).first()
        
        if not latest_review:
            return {
                'solution_id': solution_id,
                'status': 'not_submitted',
                'message': 'Solution has not been submitted to ARB'
            }
        
        result = {
            'solution_id': solution_id,
            'status': latest_review.arb_decision,
            'submitted_at': latest_review.submitted_at.isoformat() if latest_review.submitted_at else None,
            'decided_at': latest_review.decided_at.isoformat() if latest_review.decided_at else None,
            'decision_reason': latest_review.arb_decision_reason,
            'attendees': latest_review.arb_attendees,
            'compliance_areas_reviewed': latest_review.compliance_areas_reviewed,
        }
        
        if latest_review.arb_decision == 'conditional':
            result['conditions'] = latest_review.conditions
            result['conditions_count'] = len(latest_review.conditions) if latest_review.conditions else 0
        
        if latest_review.next_review_date:
            result['next_review_date'] = latest_review.next_review_date.isoformat()
            result['next_steps'] = latest_review.next_steps
        
        return result
    
    def check_approval_conditions(self, review_id: int) -> Dict[str, Any]:
        """
        Check status of approval conditions.
        
        Args:
            review_id: ARB review with conditions
        
        Returns:
            Dict showing which conditions are satisfied
        """
        _, organization_id = self._session_actor()
        review = db.session.execute(
            db.select(SolutionARBReview).where(
                SolutionARBReview.id == review_id,
                SolutionARBReview.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not review:
            raise LookupError("arb_review_not_found")
        
        if review.arb_decision != 'conditional':
            return {'error': 'Review is not conditional approval'}
        
        conditions_status = []
        for condition in (review.conditions or []):
            conditions_status.append({
                'condition': condition.get('condition'),
                'owner_id': condition.get('owner_id'),
                'target_date': condition.get('target_date'),
                'status': condition.get('status', 'pending')  # pending, satisfied, waived
            })
        
        all_satisfied = all(c.get('status') == 'satisfied' for c in conditions_status)
        
        return {
            'review_id': review_id,
            'total_conditions': len(conditions_status),
            'conditions': conditions_status,
            'all_satisfied': all_satisfied,
            'ready_for_final_approval': all_satisfied
        }
