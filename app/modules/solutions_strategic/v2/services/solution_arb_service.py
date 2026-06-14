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
        # Check if already submitted
        existing = db.session.query(SolutionARBReview).filter(
            SolutionARBReview.solution_id == solution_id,
            SolutionARBReview.arb_decision.in_(['pending', 'conditional'])
        ).first()
        
        if existing:
            raise ValueError(f"Solution {solution_id} already has pending ARB review")
        
        review = SolutionARBReview(
            solution_id=solution_id,
            version_id=version_id,
            submitted_by_id=submitted_by_id,
            submitted_at=datetime.utcnow(),
            arb_decision='pending'
        )
        
        if submission_notes:
            review.arb_decision_reason = submission_notes
        
        db.session.add(review)
        db.session.commit()
        
        return review
    
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
        review = db.session.query(SolutionARBReview).get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        review.arb_attendees = attendees
        
        db.session.commit()
        
        return review
    
    def record_arb_decision(
        self,
        review_id: int,
        decision: str,  # approved, rejected, conditional
        decided_by_id: int,
        decision_reason: str,
        conditions: Optional[List[Dict]] = None,
        compliance_notes: Optional[Dict] = None
    ) -> SolutionARBReview:
        """
        Record ARB decision.
        
        Args:
            review_id: ARB review
            decision: approved/rejected/conditional
            decided_by_id: Lead ARB member making decision
            decision_reason: Why this decision
            conditions: Conditions for approval (if conditional)
            compliance_notes: Compliance assessment per area
        
        Returns:
            SolutionARBReview: Updated review
        """
        review = db.session.query(SolutionARBReview).get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        if decision not in ['approved', 'rejected', 'conditional']:
            raise ValueError(f"Invalid decision: {decision}")
        
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
            version = db.session.query(SolutionVersion).get(review.version_id)
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
        review = db.session.query(SolutionARBReview).get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
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
        review = db.session.query(SolutionARBReview).get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
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
        review = db.session.query(SolutionARBReview).get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
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
