"""
Manual Intervention Manager

Provides comprehensive manual intervention capabilities for workflow executions.
"""

import logging
import json  # dead-code-ok
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from flask import current_app  # dead-code-ok
from app import db
from app.monitoring.alerting_service import alerting_service, AlertSeverity

logger = logging.getLogger(__name__)

class InterventionType(Enum):
    """Manual intervention types."""
    APPROVAL_REQUIRED = "approval_required"
    ERROR_HANDLING = "error_handling"
    DECISION_POINT = "decision_point"
    RESOURCE_ALLOCATION = "resource_allocation"
    POLICY_VIOLATION = "policy_violation"
    EXCEPTION_REQUEST = "exception_request"

class InterventionStatus(Enum):
    """Intervention status."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class InterventionPriority(Enum):
    """Intervention priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class InterventionRequest:
    """Represents a manual intervention request."""
    id: str
    workflow_id: str
    step_id: Optional[str]
    intervention_type: InterventionType
    priority: InterventionPriority
    title: str
    description: str
    requested_by: str
    assigned_to: Optional[str]
    status: InterventionStatus
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    context: Dict[str, Any]
    actions: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intervention request to dictionary."""
        data = asdict(self)
        data['intervention_type'] = self.intervention_type.value
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

@dataclass
class InterventionAction:
    """Represents an intervention action."""
    id: str
    intervention_id: str
    action_type: str
    description: str
    performed_by: str
    performed_at: datetime
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intervention action to dictionary."""
        data = asdict(self)
        data['performed_at'] = self.performed_at.isoformat()
        return data

class ManualInterventionManager:
    """
    Manages manual intervention requests and workflows.
    """
    
    def __init__(self):
        """Initialize the manual intervention manager."""
        self._interventions = {}  # intervention_id -> InterventionRequest
        self._actions = {}  # intervention_id -> [InterventionAction]
        self._escalation_rules = {}
        self._lock = threading.Lock()
        
        # Initialize escalation rules
        self._initialize_escalation_rules()
        
        # Start background task for overdue interventions
        self._start_overdue_checker()
    
    def _initialize_escalation_rules(self):
        """Initialize escalation rules for interventions."""
        self._escalation_rules = {
            'critical_overdue': {
                'priority': InterventionPriority.CRITICAL,
                'overdue_hours': 2,
                'escalation_action': 'alert_management'
            },
            'high_overdue': {
                'priority': InterventionPriority.HIGH,
                'overdue_hours': 8,
                'escalation_action': 'notify_supervisor'
            },
            'medium_overdue': {
                'priority': InterventionPriority.MEDIUM,
                'overdue_hours': 24,
                'escalation_action': 'send_reminder'
            },
            'low_overdue': {
                'priority': InterventionPriority.LOW,
                'overdue_hours': 72,
                'escalation_action': 'log_warning'
            }
        }
    
    def create_intervention_request(self, workflow_id: str, step_id: Optional[str] = None,
                                 intervention_type: InterventionType = InterventionType.ERROR_HANDLING,
                                 priority: InterventionPriority = InterventionPriority.MEDIUM,
                                 title: str = "", description: str = "",
                                 requested_by: str = "", assigned_to: Optional[str] = None,
                                 due_date: Optional[datetime] = None,
                                 context: Optional[Dict[str, Any]] = None,
                                 error: Optional[Any] = None) -> str:
        """
        Create a manual intervention request.
        
        Args:
            workflow_id: Workflow instance ID
            step_id: Optional step ID
            intervention_type: Type of intervention
            priority: Priority level
            title: Intervention title
            description: Intervention description
            requested_by: User who requested intervention
            assigned_to: User assigned to handle intervention
            due_date: Optional due date
            context: Additional context
            error: Optional error information
            
        Returns:
            Intervention request ID
        """
        # Generate default title and description if not provided
        if not title:
            title = f"Manual Intervention Required for {workflow_id}"
        
        if not description:
            description = f"Manual intervention required for workflow {workflow_id}"
            if step_id:
                description += f" at step {step_id}"
            if error:
                description += f" due to error: {error}"
        
        # Set default due date based on priority
        if not due_date:
            due_hours = {
                InterventionPriority.CRITICAL: 2,
                InterventionPriority.HIGH: 8,
                InterventionPriority.MEDIUM: 24,
                InterventionPriority.LOW: 72
            }.get(priority, 24)
            due_date = datetime.utcnow() + timedelta(hours=due_hours)
        
        # Create intervention request
        intervention = InterventionRequest(
            id=self._generate_intervention_id(),
            workflow_id=workflow_id,
            step_id=step_id,
            intervention_type=intervention_type,
            priority=priority,
            title=title,
            description=description,
            requested_by=requested_by,
            assigned_to=assigned_to,
            status=InterventionStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            due_date=due_date,
            completed_at=None,
            context=context or {},
            actions=[],
            metadata={}
        )
        
        # Add error information if provided
        if error:
            intervention.context['error'] = {
                'type': type(error).__name__,
                'message': str(error)
            }
        
        with self._lock:
            self._interventions[intervention.id] = intervention
            self._actions[intervention.id] = []
        
        # Log intervention creation
        logger.info(f"Created intervention request: {intervention.id} - {title}")
        
        # Send notification
        self._send_intervention_notification(intervention)
        
        # Create alert for high priority interventions
        if priority in [InterventionPriority.HIGH, InterventionPriority.CRITICAL]:
            alerting_service.create_manual_alert(
                name=f"workflow_intervention_{intervention.id}",
                severity=AlertSeverity.CRITICAL if priority == InterventionPriority.CRITICAL else AlertSeverity.WARNING,
                message=f"Manual intervention required: {title}",
                source='workflow_manual_intervention',
                metadata={
                    'intervention_id': intervention.id,
                    'workflow_id': workflow_id,
                    'priority': priority.value,
                    'intervention_type': intervention_type.value
                }
            )
        
        return intervention.id
    
    def update_intervention_status(self, intervention_id: str, status: InterventionStatus,
                                 performed_by: str, notes: Optional[str] = None) -> bool:
        """
        Update intervention status.
        
        Args:
            intervention_id: Intervention request ID
            status: New status
            performed_by: User performing the update
            notes: Optional notes
            
        Returns:
            True if updated successfully, False otherwise
        """
        with self._lock:
            intervention = self._interventions.get(intervention_id)
            
            if not intervention:
                logger.warning(f"Intervention not found: {intervention_id}")
                return False
            
            old_status = intervention.status
            intervention.status = status
            intervention.updated_at = datetime.utcnow()
            
            if status in [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]:
                intervention.completed_at = datetime.utcnow()
            
            # Add action record
            action = InterventionAction(
                id=self._generate_action_id(),
                intervention_id=intervention_id,
                action_type='status_change',
                description=f"Status changed from {old_status.value} to {status.value}",
                performed_by=performed_by,
                performed_at=datetime.utcnow(),
                details={
                    'old_status': old_status.value,
                    'new_status': status.value,
                    'notes': notes
                }
            )
            
            self._actions[intervention_id].append(action)
            intervention.actions.append(action.to_dict())

        # Keep workflow state machine in sync with intervention lifecycle.
        if status in [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]:
            try:
                from app.models.workflow_models import EAWorkflowInstance

                instance = EAWorkflowInstance.query.filter_by(
                    instance_code=intervention.workflow_id
                ).first()
                if instance:
                    if status == InterventionStatus.COMPLETED and instance.status == "waiting_approval":
                        instance.status = "running"
                    elif status == InterventionStatus.CANCELLED:
                        instance.status = "failed"
                    db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.warning(
                    "Failed to sync workflow status for intervention %s: %s",
                    intervention_id,
                    exc,
                )

        logger.info(f"Updated intervention {intervention_id} status to {status.value}")
        
        # Send notification for status changes
        self._send_status_change_notification(intervention, old_status, status, performed_by)
        
        return True
    
    def add_intervention_action(self, intervention_id: str, action_type: str,
                              description: str, performed_by: str,
                              details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an action to an intervention.
        
        Args:
            intervention_id: Intervention request ID
            action_type: Type of action
            description: Action description
            performed_by: User performing the action
            details: Additional action details
            
        Returns:
            True if action added successfully, False otherwise
        """
        with self._lock:
            intervention = self._interventions.get(intervention_id)
            
            if not intervention:
                logger.warning(f"Intervention not found: {intervention_id}")
                return False
            
            action = InterventionAction(
                id=self._generate_action_id(),
                intervention_id=intervention_id,
                action_type=action_type,
                description=description,
                performed_by=performed_by,
                performed_at=datetime.utcnow(),
                details=details or {}
            )
            
            self._actions[intervention_id].append(action)
            intervention.actions.append(action.to_dict())
            intervention.updated_at = datetime.utcnow()
        
        logger.info(f"Added action to intervention {intervention_id}: {action_type}")
        
        return True
    
    def get_intervention(self, intervention_id: str) -> Optional[Dict[str, Any]]:
        """
        Get intervention request details.
        
        Args:
            intervention_id: Intervention request ID
            
        Returns:
            Intervention request details or None if not found
        """
        with self._lock:
            intervention = self._interventions.get(intervention_id)
            
            if not intervention:
                return None
            
            return intervention.to_dict()
    
    def get_interventions(self, workflow_id: Optional[str] = None,
                         status: Optional[InterventionStatus] = None,
                         priority: Optional[InterventionPriority] = None,
                         assigned_to: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get intervention requests with filtering options.
        
        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status
            priority: Filter by priority
            assigned_to: Filter by assigned user
            limit: Maximum number of results to return
            
        Returns:
            List of intervention requests
        """
        with self._lock:
            interventions = list(self._interventions.values())
        
        # Apply filters
        if workflow_id:
            interventions = [i for i in interventions if i.workflow_id == workflow_id]
        
        if status:
            interventions = [i for i in interventions if i.status == status]
        
        if priority:
            interventions = [i for i in interventions if i.priority == priority]
        
        if assigned_to:
            interventions = [i for i in interventions if i.assigned_to == assigned_to]
        
        # Sort by priority and creation time
        priority_order = {
            InterventionPriority.CRITICAL: 0,
            InterventionPriority.HIGH: 1,
            InterventionPriority.MEDIUM: 2,
            InterventionPriority.LOW: 3
        }
        
        interventions.sort(key=lambda x: (priority_order.get(x.priority, 4), x.created_at), reverse=False)
        
        return [intervention.to_dict() for intervention in interventions[:limit]]
    
    def get_my_interventions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get interventions assigned to a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of results to return
            
        Returns:
            List of intervention requests
        """
        return self.get_interventions(assigned_to=user_id, limit=limit)
    
    def get_overdue_interventions(self) -> List[Dict[str, Any]]:
        """
        Get overdue intervention requests.
        
        Returns:
            List of overdue intervention requests
        """
        now = datetime.utcnow()
        
        with self._lock:
            interventions = list(self._interventions.values())
        
        overdue = [
            i for i in interventions
            if i.due_date and i.due_date < now and i.status not in [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]
        ]
        
        # Sort by overdue duration
        overdue.sort(key=lambda x: x.due_date, reverse=True)
        
        return [intervention.to_dict() for intervention in overdue]
    
    def escalate_overdue_interventions(self):
        """Escalate overdue interventions based on rules."""
        overdue_interventions = self.get_overdue_interventions()
        
        for intervention_dict in overdue_interventions:
            intervention_id = intervention_dict['id']
            priority = InterventionPriority(intervention_dict['priority'])
            due_date = datetime.fromisoformat(intervention_dict['due_date'].replace('Z', '+00:00'))
            
            # Check escalation rules
            for rule_name, rule in self._escalation_rules.items():
                if rule['priority'] == priority:
                    overdue_hours = (datetime.utcnow() - due_date).total_seconds() / 3600
                    
                    if overdue_hours >= rule['overdue_hours']:
                        self._perform_escalation(intervention_id, rule)
                        break
    
    def _perform_escalation(self, intervention_id: str, rule: Dict[str, Any]):
        """Perform escalation action for an intervention."""
        escalation_action = rule['escalation_action']
        
        with self._lock:
            intervention = self._interventions.get(intervention_id)
            
            if not intervention:
                return
        
        if escalation_action == 'alert_management':
            alerting_service.create_manual_alert(
                name=f"intervention_escalation_{intervention_id}",
                severity=AlertSeverity.CRITICAL,
                message=f"Critical intervention overdue: {intervention.title}",
                source='workflow_intervention_escalation',
                metadata={
                    'intervention_id': intervention_id,
                    'workflow_id': intervention.workflow_id,
                    'overdue_hours': (datetime.utcnow() - intervention.due_date).total_seconds() / 3600
                }
            )
        
        elif escalation_action == 'notify_supervisor':
            # In a real implementation, this would notify the supervisor
            logger.warning(f"Supervisor notification for overdue intervention: {intervention_id}")
        
        elif escalation_action == 'send_reminder':
            # In a real implementation, this would send a reminder
            logger.info(f"Reminder sent for overdue intervention: {intervention_id}")
        
        elif escalation_action == 'log_warning':
            logger.warning(f"Intervention overdue: {intervention_id}")
        
        # Add escalation action record
        self.add_intervention_action(
            intervention_id=intervention_id,
            action_type='escalation',
            description=f"Escalated due to being overdue: {escalation_action}",
            performed_by='system',
            details={'rule': rule}
        )
    
    def _send_intervention_notification(self, intervention: InterventionRequest):
        """Send notification for new intervention request."""
        try:
            # In a real implementation, this would send email/Slack notifications
            logger.info(f"Intervention notification sent: {intervention.id} - {intervention.title}")
            
            # Log to workflow audit
            try:
                from .workflow_audit import workflow_audit
                workflow_audit.log_intervention_event(
                    workflow_id=intervention.workflow_id,
                    intervention_id=intervention.id,
                    action='created',
                    details={
                        'intervention_type': intervention.intervention_type.value,
                        'priority': intervention.priority.value,
                        'assigned_to': intervention.assigned_to
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log intervention to audit: {e}")
                
        except Exception as e:
            logger.error(f"Failed to send intervention notification: {e}")
    
    def _send_status_change_notification(self, intervention: InterventionRequest,
                                       old_status: InterventionStatus, new_status: InterventionStatus,
                                       performed_by: str):
        """Send notification for status change."""
        try:
            # In a real implementation, this would send email/Slack notifications
            logger.info(f"Intervention status change notification: {intervention.id} - {old_status.value} -> {new_status.value}")
            
            # Log to workflow audit
            try:
                from .workflow_audit import workflow_audit
                workflow_audit.log_intervention_event(
                    workflow_id=intervention.workflow_id,
                    intervention_id=intervention.id,
                    action='status_changed',
                    details={
                        'old_status': old_status.value,
                        'new_status': new_status.value,
                        'performed_by': performed_by
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log status change to audit: {e}")
                
        except Exception as e:
            logger.error(f"Failed to send status change notification: {e}")
    
    def _start_overdue_checker(self):
        """Start background task to check for overdue interventions."""
        # In a real implementation, this would use a proper background task scheduler
        # For now, we'll just log that this would be started
        logger.info("Overdue intervention checker started")
    
    def get_intervention_statistics(self, time_delta: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """
        Get intervention statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Intervention statistics
        """
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_interventions = [
                i for i in self._interventions.values()
                if i.created_at > cutoff_time
            ]
        
        # Calculate statistics
        total_interventions = len(recent_interventions)
        
        status_distribution = {}
        for intervention in recent_interventions:
            status = intervention.status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        priority_distribution = {}
        for intervention in recent_interventions:
            priority = intervention.priority.value
            priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
        
        type_distribution = {}
        for intervention in recent_interventions:
            intervention_type = intervention.intervention_type.value
            type_distribution[intervention_type] = type_distribution.get(intervention_type, 0) + 1
        
        # Calculate average resolution time
        completed_interventions = [
            i for i in recent_interventions
            if i.status == InterventionStatus.COMPLETED and i.completed_at
        ]
        
        avg_resolution_time = 0
        if completed_interventions:
            total_resolution_time = sum(
                (i.completed_at - i.created_at).total_seconds()
                for i in completed_interventions
            )
            avg_resolution_time = total_resolution_time / len(completed_interventions)
        
        # Get overdue count
        overdue_count = len(self.get_overdue_interventions())
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_interventions': total_interventions,
            'status_distribution': status_distribution,
            'priority_distribution': priority_distribution,
            'type_distribution': type_distribution,
            'completed_interventions': len(completed_interventions),
            'completion_rate': len(completed_interventions) / total_interventions if total_interventions > 0 else 0,
            'average_resolution_time_hours': avg_resolution_time / 3600,
            'overdue_interventions': overdue_count,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_intervention_id(self) -> str:
        """Generate unique intervention ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"intervention_{timestamp}_{threading.get_ident()}"
        return data
    
    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"action_{timestamp}_{threading.get_ident()}"
        return data

# Global manual intervention manager instance
manual_intervention_manager = ManualInterventionManager()
