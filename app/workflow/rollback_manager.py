"""
Workflow Rollback Manager

Provides comprehensive rollback capabilities for workflow executions.
"""

import logging
import json  # dead-code-ok
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from flask import current_app
from app import db

logger = logging.getLogger(__name__)

class RollbackType(Enum):
    """Rollback operation types."""
    STEP_ROLLBACK = "step_rollback"
    WORKFLOW_ROLLBACK = "workflow_rollback"
    CHECKPOINT_ROLLBACK = "checkpoint_rollback"
    PARTIAL_ROLLBACK = "partial_rollback"

class RollbackStatus(Enum):
    """Rollback operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Checkpoint:
    """Represents a workflow checkpoint."""
    id: str
    workflow_id: str
    step_id: str
    timestamp: datetime
    state_data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class RollbackOperation:
    """Represents a rollback operation."""
    id: str
    workflow_id: str
    rollback_type: RollbackType
    target_step_id: Optional[str]
    target_checkpoint_id: Optional[str]
    status: RollbackStatus
    reason: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rollback operation to dictionary."""
        data = asdict(self)
        data['rollback_type'] = self.rollback_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

class WorkflowRollbackManager:
    """
    Manages rollback operations for workflow executions.
    """
    
    def __init__(self):
        """Initialize the workflow rollback manager."""
        self._checkpoints = {}  # checkpoint_id -> Checkpoint
        self._rollback_operations = {}  # rollback_id -> RollbackOperation
        self._workflow_checkpoints = {}  # workflow_id -> [checkpoint_ids]
        self._lock = threading.Lock()
        
        # Initialize rollback configuration
        self._max_checkpoints_per_workflow = current_app.config.get('WORKFLOW_MAX_CHECKPOINTS', 50)
        self._checkpoint_retention_days = current_app.config.get('WORKFLOW_CHECKPOINT_RETENTION_DAYS', 30)
        
        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()
    
    def create_checkpoint(self, workflow_id: str, step_id: str, 
                         state_data: Dict[str, Any], 
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a workflow checkpoint.
        
        Args:
            workflow_id: Workflow instance ID
            step_id: Current step ID
            state_data: Current workflow state
            metadata: Additional metadata
            
        Returns:
            Checkpoint ID
        """
        checkpoint = Checkpoint(
            id=self._generate_checkpoint_id(),
            workflow_id=workflow_id,
            step_id=step_id,
            timestamp=datetime.utcnow(),
            state_data=state_data,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._checkpoints[checkpoint.id] = checkpoint
            
            # Update workflow checkpoints list
            if workflow_id not in self._workflow_checkpoints:
                self._workflow_checkpoints[workflow_id] = []
            self._workflow_checkpoints[workflow_id].append(checkpoint.id)
            
            # Limit checkpoints per workflow
            if len(self._workflow_checkpoints[workflow_id]) > self._max_checkpoints_per_workflow:
                # Remove oldest checkpoint
                oldest_checkpoint_id = self._workflow_checkpoints[workflow_id].pop(0)
                self._checkpoints.pop(oldest_checkpoint_id, None)
        
        logger.debug(f"Created checkpoint {checkpoint.id} for workflow {workflow_id}")
        return checkpoint.id
    
    def rollback_workflow(self, workflow_id: str, step_id: Optional[str] = None,
                         checkpoint_id: Optional[str] = None, 
                         reason: Optional[str] = None) -> bool:
        """
        Rollback a workflow to a previous state.
        
        Args:
            workflow_id: Workflow instance ID
            step_id: Target step ID (optional)
            checkpoint_id: Target checkpoint ID (optional)
            reason: Reason for rollback
            
        Returns:
            True if rollback initiated successfully, False otherwise
        """
        # Determine rollback type and target
        if checkpoint_id:
            rollback_type = RollbackType.CHECKPOINT_ROLLBACK
            target_checkpoint = self._checkpoints.get(checkpoint_id)
            if not target_checkpoint or target_checkpoint.workflow_id != workflow_id:
                logger.error(f"Invalid checkpoint ID: {checkpoint_id}")
                return False
        elif step_id:
            rollback_type = RollbackType.STEP_ROLLBACK
            target_checkpoint = self._find_checkpoint_for_step(workflow_id, step_id)
            if not target_checkpoint:
                logger.error(f"No checkpoint found for step: {step_id}")
                return False
        else:
            rollback_type = RollbackType.WORKFLOW_ROLLBACK
            target_checkpoint = self._get_latest_checkpoint(workflow_id)
            if not target_checkpoint:
                logger.error(f"No checkpoints found for workflow: {workflow_id}")
                return False
        
        # Create rollback operation
        rollback_op = RollbackOperation(
            id=self._generate_rollback_id(),
            workflow_id=workflow_id,
            rollback_type=rollback_type,
            target_step_id=step_id,
            target_checkpoint_id=target_checkpoint.id,
            status=RollbackStatus.PENDING,
            reason=reason or "Manual rollback",
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            metadata={}
        )
        
        with self._lock:
            self._rollback_operations[rollback_op.id] = rollback_op
        
        # Execute rollback
        return self._execute_rollback(rollback_op, target_checkpoint)
    
    def _execute_rollback(self, rollback_op: RollbackOperation, target_checkpoint: Checkpoint) -> bool:
        """Execute a rollback operation."""
        try:
            # Update status to in progress
            rollback_op.status = RollbackStatus.IN_PROGRESS
            rollback_op.started_at = datetime.utcnow()
            
            logger.info(f"Executing rollback {rollback_op.id} for workflow {rollback_op.workflow_id}")
            
            # Perform the actual rollback
            success = self._perform_rollback(rollback_op, target_checkpoint)
            
            if success:
                rollback_op.status = RollbackStatus.COMPLETED
                rollback_op.completed_at = datetime.utcnow()
                
                logger.info(f"Rollback {rollback_op.id} completed successfully")
                self._log_rollback_success(rollback_op, target_checkpoint)
                return True
            else:
                rollback_op.status = RollbackStatus.FAILED
                rollback_op.completed_at = datetime.utcnow()
                
                logger.error(f"Rollback {rollback_op.id} failed")
                return False
                
        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            rollback_op.status = RollbackStatus.FAILED
            rollback_op.completed_at = datetime.utcnow()
            return False
    
    def _perform_rollback(self, rollback_op: RollbackOperation, target_checkpoint: Checkpoint) -> bool:
        """Perform the actual rollback operation."""
        try:
            workflow_id = rollback_op.workflow_id
            
            # Restore workflow state from checkpoint
            state_restored = self._restore_workflow_state(workflow_id, target_checkpoint.state_data)
            
            if not state_restored:
                logger.error(f"Failed to restore workflow state for {workflow_id}")
                return False
            
            # Update workflow step position
            step_updated = self._update_workflow_position(workflow_id, target_checkpoint.step_id)
            
            if not step_updated:
                logger.error(f"Failed to update workflow position for {workflow_id}")
                return False
            
            # Execute rollback-specific actions
            if rollback_op.rollback_type == RollbackType.STEP_ROLLBACK:
                return self._rollback_step(workflow_id, target_checkpoint.step_id)
            elif rollback_op.rollback_type == RollbackType.WORKFLOW_ROLLBACK:
                return self._rollback_workflow(workflow_id, target_checkpoint)
            elif rollback_op.rollback_type == RollbackType.CHECKPOINT_ROLLBACK:
                return self._rollback_to_checkpoint(workflow_id, target_checkpoint)
            
            return True
            
        except Exception as e:
            logger.error(f"Rollback operation failed: {e}")
            return False
    
    def _restore_workflow_state(self, workflow_id: str, state_data: Dict[str, Any]) -> bool:
        """Restore workflow state from checkpoint data."""
        try:
            logger.info(f"Restoring state for workflow {workflow_id}")

            # Keep in-memory rollback usable with persisted workflow instances.
            from app.models.workflow_models import EAWorkflowInstance

            instance = EAWorkflowInstance.query.filter_by(instance_code=workflow_id).first()
            if instance:
                if isinstance(state_data.get("context"), dict):
                    instance.context = state_data.get("context", {})
                if isinstance(state_data.get("current_step_index"), int):
                    instance.current_step_index = state_data.get("current_step_index", 0)
                if isinstance(state_data.get("progress_percent"), int):
                    instance.progress_percent = state_data.get("progress_percent", 0)
                restored_status = state_data.get("status")
                if restored_status:
                    instance.status = restored_status
                db.session.commit()

            return True
        except Exception as e:
            logger.error(f"Failed to restore workflow state: {e}")
            db.session.rollback()
            return False
    
    def _update_workflow_position(self, workflow_id: str, step_id: str) -> bool:
        """Update workflow position to target step."""
        try:
            # This would integrate with the actual workflow engine
            logger.info(f"Updating workflow {workflow_id} position to step {step_id}")
            
            # In a real implementation, this would update the workflow
            # execution pointer to the target step
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update workflow position: {e}")
            return False
    
    def _rollback_step(self, workflow_id: str, step_id: str) -> bool:
        """Perform step-specific rollback actions."""
        try:
            logger.info(f"Performing step rollback for {workflow_id}:{step_id}")
            
            # In a real implementation, this would:
            # 1. Undo step-specific changes
            # 2. Clean up step resources
            # 3. Reset step state
            
            return True
            
        except Exception as e:
            logger.error(f"Step rollback failed: {e}")
            return False
    
    def _rollback_workflow(self, workflow_id: str, target_checkpoint: Checkpoint) -> bool:
        """Perform full workflow rollback."""
        try:
            logger.info(f"Performing workflow rollback for {workflow_id}")
            
            # In a real implementation, this would:
            # 1. Reset workflow to initial state
            # 2. Clean up all resources
            # 3. Reset all step states
            
            return True
            
        except Exception as e:
            logger.error(f"Workflow rollback failed: {e}")
            return False
    
    def _rollback_to_checkpoint(self, workflow_id: str, target_checkpoint: Checkpoint) -> bool:
        """Perform checkpoint-specific rollback."""
        try:
            logger.info(f"Performing checkpoint rollback for {workflow_id}")
            
            # In a real implementation, this would:
            # 1. Restore exact checkpoint state
            # 2. Validate checkpoint integrity
            # 3. Resume from checkpoint position
            
            return True
            
        except Exception as e:
            logger.error(f"Checkpoint rollback failed: {e}")
            return False
    
    def _find_checkpoint_for_step(self, workflow_id: str, step_id: str) -> Optional[Checkpoint]:
        """Find checkpoint for a specific step."""
        with self._lock:
            if workflow_id not in self._workflow_checkpoints:
                return None
            
            # Find most recent checkpoint for the step
            for checkpoint_id in reversed(self._workflow_checkpoints[workflow_id]):
                checkpoint = self._checkpoints.get(checkpoint_id)
                if checkpoint and checkpoint.step_id == step_id:
                    return checkpoint
            
            return None
    
    def _get_latest_checkpoint(self, workflow_id: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a workflow."""
        with self._lock:
            if workflow_id not in self._workflow_checkpoints:
                return None
            
            if not self._workflow_checkpoints[workflow_id]:
                return None
            
            latest_checkpoint_id = self._workflow_checkpoints[workflow_id][-1]
            return self._checkpoints.get(latest_checkpoint_id)
    
    def get_checkpoints(self, workflow_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get checkpoints for a workflow.
        
        Args:
            workflow_id: Workflow instance ID
            limit: Maximum number of checkpoints to return
            
        Returns:
            List of checkpoints
        """
        with self._lock:
            if workflow_id not in self._workflow_checkpoints:
                return []
            
            checkpoint_ids = self._workflow_checkpoints[workflow_id][-limit:]
            checkpoints = [self._checkpoints[cid] for cid in checkpoint_ids if cid in self._checkpoints]
            
            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x.timestamp, reverse=True)
            
            return [checkpoint.to_dict() for checkpoint in checkpoints]
    
    def get_rollback_operations(self, workflow_id: Optional[str] = None,
                              status: Optional[RollbackStatus] = None) -> List[Dict[str, Any]]:
        """
        Get rollback operations with filtering options.
        
        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status
            
        Returns:
            List of rollback operations
        """
        with self._lock:
            operations = list(self._rollback_operations.values())
        
        # Apply filters
        if workflow_id:
            operations = [op for op in operations if op.workflow_id == workflow_id]
        
        if status:
            operations = [op for op in operations if op.status == status]
        
        # Sort by creation time (newest first)
        operations.sort(key=lambda x: x.created_at, reverse=True)
        
        return [op.to_dict() for op in operations]
    
    def cancel_rollback(self, rollback_id: str) -> bool:
        """
        Cancel a rollback operation.
        
        Args:
            rollback_id: Rollback operation ID
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        with self._lock:
            rollback_op = self._rollback_operations.get(rollback_id)
            
            if not rollback_op:
                logger.warning(f"Rollback operation not found: {rollback_id}")
                return False
            
            if rollback_op.status in [RollbackStatus.COMPLETED, RollbackStatus.FAILED, RollbackStatus.CANCELLED]:
                logger.warning(f"Cannot cancel rollback in {rollback_op.status.value} status: {rollback_id}")
                return False
            
            rollback_op.status = RollbackStatus.CANCELLED
            rollback_op.completed_at = datetime.utcnow()
            
            logger.info(f"Cancelled rollback operation: {rollback_id}")
            return True
    
    def _cleanup_old_checkpoints(self):
        """Clean up old checkpoints based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self._checkpoint_retention_days)
        
        with self._lock:
            original_count = len(self._checkpoints)
            
            # Find old checkpoints
            old_checkpoint_ids = [
                cid for cid, checkpoint in self._checkpoints.items()
                if checkpoint.timestamp < cutoff_time
            ]
            
            # Remove old checkpoints
            for cid in old_checkpoint_ids:
                checkpoint = self._checkpoints.pop(cid, None)
                if checkpoint:
                    # Remove from workflow checkpoints list
                    if checkpoint.workflow_id in self._workflow_checkpoints:
                        if cid in self._workflow_checkpoints[checkpoint.workflow_id]:
                            self._workflow_checkpoints[checkpoint.workflow_id].remove(cid)
            
            cleaned_count = original_count - len(self._checkpoints)
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old checkpoints")
    
    def _log_rollback_success(self, rollback_op: RollbackOperation, target_checkpoint: Checkpoint):
        """Log successful rollback."""
        logger.info(f"Rollback successful: {rollback_op.id} - {rollback_op.rollback_type.value}")
        
        # Log to workflow audit
        try:
            from .workflow_audit import workflow_audit
            workflow_audit.log_rollback_event(
                workflow_id=rollback_op.workflow_id,
                rollback_id=rollback_op.id,
                rollback_type=rollback_op.rollback_type.value,
                target_checkpoint_id=target_checkpoint.id,
                details={
                    'reason': rollback_op.reason,
                    'duration': (rollback_op.completed_at - rollback_op.started_at).total_seconds() if rollback_op.completed_at and rollback_op.started_at else None,
                    'target_step_id': target_checkpoint.step_id
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log rollback to audit: {e}")
    
    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"ckpt_{timestamp}_{threading.get_ident()}"
        return data
    
    def _generate_rollback_id(self) -> str:
        """Generate unique rollback ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"rb_{timestamp}_{threading.get_ident()}"
        return data
    
    def get_rollback_statistics(self, time_delta: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """
        Get rollback statistics.
        
        Args:
            time_delta: Time period to analyze
            
        Returns:
            Rollback statistics
        """
        cutoff_time = datetime.utcnow() - time_delta
        
        with self._lock:
            recent_operations = [
                op for op in self._rollback_operations.values()
                if op.created_at > cutoff_time
            ]
        
        # Calculate statistics
        total_operations = len(recent_operations)
        completed_operations = len([op for op in recent_operations if op.status == RollbackStatus.COMPLETED])
        failed_operations = len([op for op in recent_operations if op.status == RollbackStatus.FAILED])
        cancelled_operations = len([op for op in recent_operations if op.status == RollbackStatus.CANCELLED])
        
        # Rollback type distribution
        type_distribution = {}
        for op in recent_operations:
            rollback_type = op.rollback_type.value
            type_distribution[rollback_type] = type_distribution.get(rollback_type, 0) + 1
        
        # Average duration
        completed_with_duration = [
            op for op in recent_operations
            if op.status == RollbackStatus.COMPLETED and op.started_at and op.completed_at
        ]
        
        avg_duration = 0
        if completed_with_duration:
            total_duration = sum(
                (op.completed_at - op.started_at).total_seconds()
                for op in completed_with_duration
            )
            avg_duration = total_duration / len(completed_with_duration)
        
        return {
            'time_period': f"{time_delta.days} days",
            'total_operations': total_operations,
            'completed_operations': completed_operations,
            'failed_operations': failed_operations,
            'cancelled_operations': cancelled_operations,
            'success_rate': completed_operations / total_operations if total_operations > 0 else 0,
            'type_distribution': type_distribution,
            'average_duration_seconds': avg_duration,
            'total_checkpoints': len(self._checkpoints),
            'workflows_with_checkpoints': len(self._workflow_checkpoints),
            'timestamp': datetime.utcnow().isoformat()
        }

# Global workflow rollback manager instance
workflow_rollback_manager = WorkflowRollbackManager()
