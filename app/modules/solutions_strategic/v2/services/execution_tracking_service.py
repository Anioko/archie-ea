"""
ExecutionTrackingService: Monitor actual progress vs planned timeline.
Tracks task completion, variance, risk realization.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional
from app import db
from app.models.solution_governance import SolutionExecutionTracking


class ExecutionTrackingService:
    """Track implementation progress and variance."""
    
    def initialize_tracking(
        self,
        solution_id: int,
        workflow_task_id: Optional[int] = None,
        planned_duration_days: Optional[int] = None,
        planned_end_date: Optional[date] = None
    ) -> SolutionExecutionTracking:
        """
        Initialize execution tracking for a task.
        
        Args:
            solution_id: Solution being implemented
            workflow_task_id: Workflow task being tracked
            planned_duration_days: How long this task should take
            planned_end_date: When this task should be done
        
        Returns:
            SolutionExecutionTracking: New tracking record
        """
        tracking = SolutionExecutionTracking(
            solution_id=solution_id,
            workflow_task_id=workflow_task_id,
            percent_complete=0.0,
            status='on_track',
            planned_duration_days=planned_duration_days,
            planned_end_date=planned_end_date
        )
        
        db.session.add(tracking)
        db.session.commit()
        
        return tracking
    
    def update_progress(
        self,
        tracking_id: int,
        percent_complete: float,
        updated_by_id: int,
        status_reason: Optional[str] = None,
        actual_start_date: Optional[date] = None,
        actual_end_date: Optional[date] = None
    ) -> SolutionExecutionTracking:
        """
        Update task progress.
        
        Args:
            tracking_id: Tracking record to update
            percent_complete: 0-100
            updated_by_id: Who is updating
            status_reason: Optional status note
            actual_start_date: When task actually started
            actual_end_date: When task actually completed
        
        Returns:
            SolutionExecutionTracking: Updated record
        """
        tracking = db.session.query(SolutionExecutionTracking).get(tracking_id)
        if not tracking:
            raise ValueError(f"Tracking {tracking_id} not found")
        
        tracking.percent_complete = percent_complete
        tracking.last_updated_by_id = updated_by_id
        tracking.last_updated_at = datetime.utcnow()
        
        if status_reason:
            tracking.status_reason = status_reason
        
        if actual_start_date:
            tracking.actual_start_date = actual_start_date
        
        if actual_end_date:
            tracking.actual_end_date = actual_end_date
        
        # Calculate variance if both dates set
        if tracking.actual_end_date and tracking.planned_end_date:
            tracking.variance_days = (tracking.actual_end_date - tracking.planned_end_date).days
            if tracking.planned_duration_days and tracking.planned_duration_days > 0:
                tracking.variance_percentage = (tracking.variance_days / tracking.planned_duration_days) * 100
            
            # Update status based on variance
            if tracking.variance_days > 5:
                tracking.status = 'delayed'
            elif tracking.variance_days > 0:
                tracking.status = 'at_risk'
            elif percent_complete == 100:
                tracking.status = 'on_track'
        
        db.session.commit()
        return tracking
    
    def realize_risk(
        self,
        tracking_id: int,
        risk_id: str,
        impact_description: str,
        updated_by_id: int
    ) -> SolutionExecutionTracking:
        """
        Record that a predicted risk has materialized.
        
        Args:
            tracking_id: Task tracking record
            risk_id: Which risk was realized
            impact_description: What actually happened
            updated_by_id: Who is recording this
        
        Returns:
            SolutionExecutionTracking: Updated record
        """
        tracking = db.session.query(SolutionExecutionTracking).get(tracking_id)
        if not tracking:
            raise ValueError(f"Tracking {tracking_id} not found")
        
        realized_risk = {
            'risk_id': risk_id,
            'realized_on': datetime.utcnow().isoformat(),
            'impact': impact_description,
            'reported_by_id': updated_by_id
        }
        
        if not tracking.realized_risks:
            tracking.realized_risks = []
        
        tracking.realized_risks.append(realized_risk)
        
        # If critical risk, mark as at_risk
        if 'critical' in impact_description.lower() or 'blocker' in impact_description.lower():
            tracking.status = 'blocked'
            tracking.status_reason = f"Risk realized: {impact_description}"
        elif tracking.status == 'on_track':
            tracking.status = 'at_risk'
        
        tracking.last_updated_by_id = updated_by_id
        tracking.last_updated_at = datetime.utcnow()
        
        db.session.commit()
        return tracking
    
    def get_variance_report(self, solution_id: int) -> Dict[str, Any]:
        """
        Get variance report for entire solution.
        
        Args:
            solution_id: Solution to analyze
        
        Returns:
            Dict with variance metrics
        """
        trackings = db.session.query(SolutionExecutionTracking).filter(
            SolutionExecutionTracking.solution_id == solution_id
        ).all()
        
        on_track = sum(1 for t in trackings if t.status == 'on_track')
        at_risk = sum(1 for t in trackings if t.status == 'at_risk')
        delayed = sum(1 for t in trackings if t.status == 'delayed')
        blocked = sum(1 for t in trackings if t.status == 'blocked')
        
        avg_variance = sum(t.variance_days for t in trackings if t.variance_days) / len([t for t in trackings if t.variance_days]) if any(t.variance_days for t in trackings) else 0
        
        total_variance_days = sum(t.variance_days for t in trackings if t.variance_days)
        
        realized_risks_list = []
        for t in trackings:
            if t.realized_risks:
                realized_risks_list.extend(t.realized_risks)
        
        return {
            'solution_id': solution_id,
            'total_tasks': len(trackings),
            'on_track': on_track,
            'at_risk': at_risk,
            'delayed': delayed,
            'blocked': blocked,
            'health_score': (on_track / len(trackings) * 100) if trackings else 0,
            'average_variance_days': round(avg_variance, 1),
            'total_variance_days': total_variance_days,
            'total_realized_risks': len(realized_risks_list),
            'recent_updates': [t.to_dict() for t in sorted(trackings, key=lambda x: x.last_updated_at, reverse=True)[:5]]
        }
    
    def get_dashboard_summary(self, solution_id: int) -> Dict[str, Any]:
        """
        Get dashboard summary for project health.
        
        Args:
            solution_id: Solution to summarize
        
        Returns:
            Dict with dashboard data
        """
        trackings = db.session.query(SolutionExecutionTracking).filter(
            SolutionExecutionTracking.solution_id == solution_id
        ).all()
        
        if not trackings:
            return {'error': 'No execution data for this solution'}
        
        overall_progress = sum(t.percent_complete for t in trackings) / len(trackings) if trackings else 0
        
        # Status breakdown
        status_counts = {}
        for t in trackings:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1
        
        # Risk summary
        critical_issues = sum(1 for t in trackings if t.status == 'blocked')
        at_risk_count = sum(1 for t in trackings if t.status == 'at_risk')
        
        # Variance summary
        delayed_tasks = [t for t in trackings if t.variance_days and t.variance_days > 0]
        
        return {
            'solution_id': solution_id,
            'overall_progress_percentage': round(overall_progress, 1),
            'status_breakdown': status_counts,
            'critical_issues': critical_issues,
            'at_risk_tasks': at_risk_count,
            'delayed_tasks_count': len(delayed_tasks),
            'max_variance_days': max((t.variance_days for t in delayed_tasks), default=0),
            'project_health': self._calculate_health_score(trackings)
        }
    
    def _calculate_health_score(self, trackings) -> str:
        """Calculate project health score (Green/Yellow/Red)."""
        if not trackings:
            return 'Unknown'
        
        status_counts = {}
        for t in trackings:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1
        
        blocked_pct = status_counts.get('blocked', 0) / len(trackings) * 100
        delayed_pct = status_counts.get('delayed', 0) / len(trackings) * 100
        at_risk_pct = status_counts.get('at_risk', 0) / len(trackings) * 100
        
        if blocked_pct > 10 or delayed_pct > 20:
            return 'Red'
        elif at_risk_pct > 30 or delayed_pct > 10:
            return 'Yellow'
        else:
            return 'Green'
