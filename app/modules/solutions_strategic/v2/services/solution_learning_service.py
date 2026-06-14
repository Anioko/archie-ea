"""
SolutionLearningService: AI learning loop from actual project outcomes.
Tracks outcomes, enables model retraining, detects drift.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from app import db
from app.models.solution_governance import SolutionOutcomeTracking


class SolutionLearningService:
    """Manage AI learning from solution outcomes."""
    
    def record_project_completion(
        self,
        solution_id: int,
        go_live_date: datetime,
        recorded_by_id: int,
        predicted_duration_weeks: Optional[float] = None,
        actual_duration_weeks: Optional[float] = None,
        predicted_cost_usd: Optional[float] = None,
        actual_cost_usd: Optional[float] = None
    ) -> SolutionOutcomeTracking:
        """
        Record project completion with actual outcomes.
        
        Args:
            solution_id: Completed solution
            go_live_date: When it went live
            recorded_by_id: Who is recording
            predicted_duration_weeks: What we predicted
            actual_duration_weeks: What actually happened
            predicted_cost_usd: Predicted budget
            actual_cost_usd: Actual spend
        
        Returns:
            SolutionOutcomeTracking: Created outcome record
        """
        outcome = SolutionOutcomeTracking(
            solution_id=solution_id,
            project_completed_at=datetime.utcnow(),
            go_live_date=go_live_date,
            recorded_by_id=recorded_by_id,
            predicted_duration_weeks=predicted_duration_weeks,
            actual_duration_weeks=actual_duration_weeks,
            predicted_cost_usd=predicted_cost_usd,
            actual_cost_usd=actual_cost_usd
        )
        
        # Calculate accuracy
        if predicted_duration_weeks and actual_duration_weeks:
            outcome.timeline_accuracy_percentage = (actual_duration_weeks / predicted_duration_weeks) * 100
        
        if predicted_cost_usd and actual_cost_usd:
            outcome.cost_accuracy_percentage = (actual_cost_usd / predicted_cost_usd) * 100
        
        db.session.add(outcome)
        db.session.commit()
        
        return outcome
    
    def record_vendor_performance(
        self,
        outcome_id: int,
        vendor_performance: Dict[str, Any]  # {vendor_id: {rating: 4.5, comment: "..."}}
    ) -> SolutionOutcomeTracking:
        """
        Record how vendors actually performed.
        
        Args:
            outcome_id: Outcome record
            vendor_performance: Dict of vendor ratings and feedback
        
        Returns:
            SolutionOutcomeTracking: Updated outcome
        """
        outcome = db.session.query(SolutionOutcomeTracking).get(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")
        
        outcome.vendor_performance = vendor_performance
        db.session.commit()
        
        return outcome
    
    def record_risk_realization(
        self,
        outcome_id: int,
        predicted_risks: List[Dict],  # What we predicted
        realized_risks: List[Dict],  # What actually happened
        unforecast_risks: List[Dict]  # What we missed
    ) -> SolutionOutcomeTracking:
        """
        Record risk realization analysis.
        
        Args:
            outcome_id: Outcome record
            predicted_risks: List of predicted risks
            realized_risks: List of risks that materialized
            unforecast_risks: List of risks we missed
        
        Returns:
            SolutionOutcomeTracking: Updated outcome
        """
        outcome = db.session.query(SolutionOutcomeTracking).get(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")
        
        outcome.predicted_risks = predicted_risks
        outcome.realized_risks = realized_risks
        outcome.unforecast_risks = unforecast_risks
        
        # Calculate risk accuracy (predicted and realized / total actual)
        total_actual_risks = len(realized_risks) + len(unforecast_risks)
        predicted_and_realized = len([r for r in realized_risks if any(p['id'] == r['id'] for p in predicted_risks)])
        
        if total_actual_risks > 0:
            outcome.risk_accuracy_percentage = (predicted_and_realized / total_actual_risks) * 100
        
        db.session.commit()
        
        return outcome
    
    def record_lessons_learned(
        self,
        outcome_id: int,
        lessons_learned: str,
        what_went_well: str,
        what_to_improve: str
    ) -> SolutionOutcomeTracking:
        """
        Record qualitative lessons learned.
        
        Args:
            outcome_id: Outcome record
            lessons_learned: Key lessons
            what_went_well: Successes
            what_to_improve: Improvement areas
        
        Returns:
            SolutionOutcomeTracking: Updated outcome
        """
        outcome = db.session.query(SolutionOutcomeTracking).get(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")
        
        outcome.lessons_learned = lessons_learned
        outcome.what_went_well = what_went_well
        outcome.what_to_improve = what_to_improve
        
        db.session.commit()
        
        return outcome
    
    def record_business_value(
        self,
        outcome_id: int,
        business_value_realized: str,
        estimated_business_value_usd: Optional[float] = None,
        roi_percentage: Optional[float] = None
    ) -> SolutionOutcomeTracking:
        """
        Record business value realization.
        
        Args:
            outcome_id: Outcome record
            business_value_realized: What business value we got
            estimated_business_value_usd: Dollar value of benefits
            roi_percentage: Return on investment %
        
        Returns:
            SolutionOutcomeTracking: Updated outcome
        """
        outcome = db.session.query(SolutionOutcomeTracking).get(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")
        
        outcome.business_value_realized = business_value_realized
        outcome.estimated_business_value_usd = estimated_business_value_usd
        outcome.roi_percentage = roi_percentage
        
        db.session.commit()
        
        return outcome
    
    def mark_for_retraining(self, outcome_id: int, retraining_version: str = None) -> SolutionOutcomeTracking:
        """
        Mark outcome data as usable for model retraining.
        
        Args:
            outcome_id: Outcome record to use for retraining
            retraining_version: Model version this will be used for
        
        Returns:
            SolutionOutcomeTracking: Updated outcome
        """
        outcome = db.session.query(SolutionOutcomeTracking).get(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")
        
        outcome.used_for_retraining = True
        outcome.retraining_version = retraining_version or f"v{datetime.utcnow().year}.{datetime.utcnow().month}"
        
        db.session.commit()
        
        return outcome
    
    def get_outcomes_for_retraining(self, min_count: int = 10) -> List[Dict]:
        """
        Get outcomes suitable for model retraining.
        
        Args:
            min_count: Minimum completed outcomes needed
        
        Returns:
            List of outcomes ready for retraining
        """
        completed = db.session.query(SolutionOutcomeTracking).filter(
            SolutionOutcomeTracking.project_completed_at != None,
            SolutionOutcomeTracking.used_for_retraining == False
        ).order_by(SolutionOutcomeTracking.recorded_at.desc()).all()
        
        if len(completed) < min_count:
            return {'error': f"Only {len(completed)} outcomes available, need {min_count} minimum"}
        
        return [o.to_dict() for o in completed]
    
    def calculate_model_accuracy(self) -> Dict[str, Any]:
        """
        Calculate overall model accuracy from outcomes.
        
        Returns:
            Dict with accuracy metrics
        """
        outcomes = db.session.query(SolutionOutcomeTracking).filter(
            SolutionOutcomeTracking.project_completed_at != None
        ).all()
        
        if not outcomes:
            return {'error': 'No completed outcomes to analyze'}
        
        timeline_accuracies = [o.timeline_accuracy_percentage for o in outcomes if o.timeline_accuracy_percentage]
        cost_accuracies = [o.cost_accuracy_percentage for o in outcomes if o.cost_accuracy_percentage]
        risk_accuracies = [o.risk_accuracy_percentage for o in outcomes if o.risk_accuracy_percentage]
        
        avg_timeline = sum(timeline_accuracies) / len(timeline_accuracies) if timeline_accuracies else None
        avg_cost = sum(cost_accuracies) / len(cost_accuracies) if cost_accuracies else None
        avg_risk = sum(risk_accuracies) / len(risk_accuracies) if risk_accuracies else None
        
        return {
            'total_outcomes': len(outcomes),
            'timeline_accuracy_percentage': round(avg_timeline, 1) if avg_timeline else None,
            'cost_accuracy_percentage': round(avg_cost, 1) if avg_cost else None,
            'risk_accuracy_percentage': round(avg_risk, 1) if avg_risk else None,
            'needs_retraining': (avg_timeline and avg_timeline < 75) or (avg_cost and avg_cost < 80)
        }
    
    def detect_model_drift(self) -> Dict[str, Any]:
        """
        Detect if model performance is drifting (getting worse).
        
        Returns:
            Dict with drift analysis
        """
        # Get recent outcomes (last 30 days)
        from datetime import timedelta
        recent_date = datetime.utcnow() - timedelta(days=30)
        
        recent = db.session.query(SolutionOutcomeTracking).filter(
            SolutionOutcomeTracking.recorded_at >= recent_date
        ).all()
        
        # Get older outcomes (before that)
        older = db.session.query(SolutionOutcomeTracking).filter(
            SolutionOutcomeTracking.recorded_at < recent_date
        ).all()
        
        recent_timeline = sum(o.timeline_accuracy_percentage for o in recent if o.timeline_accuracy_percentage) / len([o for o in recent if o.timeline_accuracy_percentage]) if any(o.timeline_accuracy_percentage for o in recent) else None
        older_timeline = sum(o.timeline_accuracy_percentage for o in older if o.timeline_accuracy_percentage) / len([o for o in older if o.timeline_accuracy_percentage]) if any(o.timeline_accuracy_percentage for o in older) else None
        
        recent_cost = sum(o.cost_accuracy_percentage for o in recent if o.cost_accuracy_percentage) / len([o for o in recent if o.cost_accuracy_percentage]) if any(o.cost_accuracy_percentage for o in recent) else None
        older_cost = sum(o.cost_accuracy_percentage for o in older if o.cost_accuracy_percentage) / len([o for o in older if o.cost_accuracy_percentage]) if any(o.cost_accuracy_percentage for o in older) else None
        
        drift_detected = False
        drift_reason = []
        
        if recent_timeline and older_timeline and recent_timeline < (older_timeline - 10):
            drift_detected = True
            drift_reason.append(f"Timeline accuracy declining: {older_timeline:.1f}% → {recent_timeline:.1f}%")
        
        if recent_cost and older_cost and recent_cost < (older_cost - 10):
            drift_detected = True
            drift_reason.append(f"Cost accuracy declining: {older_cost:.1f}% → {recent_cost:.1f}%")
        
        return {
            'drift_detected': drift_detected,
            'recent_outcomes': len(recent),
            'older_outcomes': len(older),
            'recent_timeline_accuracy': round(recent_timeline, 1) if recent_timeline else None,
            'older_timeline_accuracy': round(older_timeline, 1) if older_timeline else None,
            'recent_cost_accuracy': round(recent_cost, 1) if recent_cost else None,
            'older_cost_accuracy': round(older_cost, 1) if older_cost else None,
            'drift_reason': drift_reason if drift_detected else None,
            'recommendation': 'RETRAIN MODEL' if drift_detected else 'MODEL PERFORMING WELL'
        }
    
    def get_learning_summary(self, solution_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get learning summary (portfolio or specific solution).
        
        Args:
            solution_id: Optional specific solution
        
        Returns:
            Dict with learning metrics
        """
        if solution_id:
            outcomes = db.session.query(SolutionOutcomeTracking).filter(
                SolutionOutcomeTracking.solution_id == solution_id
            ).all()
            summary_title = f"Solution {solution_id}"
        else:
            outcomes = db.session.query(SolutionOutcomeTracking).all()
            summary_title = "Portfolio"
        
        if not outcomes:
            return {'error': f'No outcomes for {summary_title}'}
        
        completed = [o for o in outcomes if o.project_completed_at]
        used_for_retraining = [o for o in outcomes if o.used_for_retraining]
        
        return {
            'scope': summary_title,
            'total_outcomes': len(outcomes),
            'completed_projects': len(completed),
            'used_for_retraining': len(used_for_retraining),
            'accuracy_metrics': self.calculate_model_accuracy(),
            'drift_analysis': self.detect_model_drift(),
            'ready_for_next_retraining': len([o for o in outcomes if o.project_completed_at and not o.used_for_retraining])
        }
