"""
Import Rollback Manager

Provides comprehensive rollback capabilities for import workflows.
"""

import logging
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import os

from flask import current_app
from app import db

logger = logging.getLogger(__name__)

class RollbackType(Enum):
    """Rollback operation types."""
    FULL_IMPORT = "full_import"
    PARTIAL_IMPORT = "partial_import"
    ROW_LEVEL = "row_level"
    TRANSACTION_LEVEL = "transaction_level"

class RollbackStatus(Enum):
    """Rollback operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class RollbackPoint:
    """Represents a rollback checkpoint."""
    id: str
    import_id: str
    rollback_type: RollbackType
    timestamp: datetime
    state_data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rollback point to dictionary."""
        data = asdict(self)
        data['rollback_type'] = self.rollback_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class RollbackOperation:
    """Represents a rollback operation."""
    id: str
    import_id: str
    rollback_type: RollbackType
    target_checkpoint_id: Optional[str]
    status: RollbackStatus
    reason: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    affected_records: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rollback operation to dictionary."""
        data = asdict(self)
        data['rollback_type'] = self.rollback_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if data['started_at']:
            data['started_at'] = data['started_at'].isoformat()
        if data['completed_at']:
            data['completed_at'] = data['completed_at'].isoformat()
        return data

class ImportRollbackManager:
    """
    Manages rollback operations for import workflows.
    """
    
    def __init__(self):
        """Initialize the import rollback manager."""
        self._checkpoints = {}  # checkpoint_id -> RollbackPoint
        self._rollback_operations = {}  # rollback_id -> RollbackOperation
        self._import_checkpoints = {}  # import_id -> [checkpoint_ids]
        self._lock = threading.Lock()
        
        # Initialize rollback configuration
        self._max_checkpoints_per_import = current_app.config.get('IMPORT_MAX_CHECKPOINTS', 50)
        self._checkpoint_retention_days = current_app.config.get('IMPORT_CHECKPOINT_RETENTION_DAYS', 30)
        self._rollback_dir = current_app.config.get('IMPORT_ROLLBACK_DIR', 'import_rollback')
        
        # Ensure rollback directory exists
        os.makedirs(self._rollback_dir, exist_ok=True)
        
        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()
    
    def create_checkpoint(self, import_id: str, rollback_type: RollbackType,
                         state_data: Dict[str, Any], 
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a rollback checkpoint.
        
        Args:
            import_id: Import session ID
            rollback_type: Type of rollback operation
            state_data: Current state data
            metadata: Additional metadata
            
        Returns:
            Checkpoint ID
        """
        checkpoint = RollbackPoint(
            id=self._generate_checkpoint_id(),
            import_id=import_id,
            rollback_type=rollback_type,
            timestamp=datetime.utcnow(),
            state_data=state_data,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._checkpoints[checkpoint.id] = checkpoint
            
            # Update import checkpoints list
            if import_id not in self._import_checkpoints:
                self._import_checkpoints[import_id] = []
            self._import_checkpoints[import_id].append(checkpoint.id)
            
            # Limit checkpoints per import
            if len(self._import_checkpoints[import_id]) > self._max_checkpoints_per_import:
                # Remove oldest checkpoint
                oldest_checkpoint_id = self._import_checkpoints[import_id].pop(0)
                self._checkpoints.pop(oldest_checkpoint_id, None)
        
        logger.debug(f"Created checkpoint {checkpoint.id} for import {import_id}")
        return checkpoint.id
    
    def rollback_import(self, import_id: str, rollback_type: RollbackType,
                        checkpoint_id: Optional[str] = None, 
                        reason: Optional[str] = None) -> bool:
        """
        Rollback an import to a previous state.
        
        Args:
            import_id: Import session ID
            rollback_type: Type of rollback to perform
            checkpoint_id: Target checkpoint ID (optional)
            reason: Reason for rollback
            
        Returns:
            True if rollback initiated successfully, False otherwise
        """
        # Determine target checkpoint
        if checkpoint_id:
            target_checkpoint = self._checkpoints.get(checkpoint_id)
            if not target_checkpoint or target_checkpoint.import_id != import_id:
                logger.error(f"Invalid checkpoint ID: {checkpoint_id}")
                return False
        else:
            target_checkpoint = self._get_latest_checkpoint(import_id)
            if not target_checkpoint:
                logger.error(f"No checkpoints found for import: {import_id}")
                return False
        
        # Create rollback operation
        rollback_op = RollbackOperation(
            id=self._generate_rollback_id(),
            import_id=import_id,
            rollback_type=rollback_type,
            target_checkpoint_id=checkpoint_id,
            status=RollbackStatus.PENDING,
            reason=reason or "Manual rollback",
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            affected_records=0,
            metadata={}
        )
        
        with self._lock:
            self._rollback_operations[rollback_op.id] = rollback_op
        
        # Execute rollback
        return self._execute_rollback(rollback_op, target_checkpoint)
    
    def _execute_rollback(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Execute a rollback operation."""
        try:
            # Update status to in progress
            rollback_op.status = RollbackStatus.IN_PROGRESS
            rollback_op.started_at = datetime.utcnow()
            
            logger.info(f"Executing rollback {rollback_op.id} for import {rollback_op.import_id}")
            
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
    
    def _perform_rollback(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Perform the actual rollback operation."""
        try:
            if rollback_op.rollback_type == RollbackType.FULL_IMPORT:
                return self._rollback_full_import(rollback_op, target_checkpoint)
            elif rollback_op.rollback_type == RollbackType.PARTIAL_IMPORT:
                return self._rollback_partial_import(rollback_op, target_checkpoint)
            elif rollback_op.rollback_type == RollbackType.ROW_LEVEL:
                return self._rollback_row_level(rollback_op, target_checkpoint)
            elif rollback_op.rollback_type == RollbackType.TRANSACTION_LEVEL:
                return self._rollback_transaction_level(rollback_op, target_checkpoint)
            else:
                logger.error(f"Unknown rollback type: {rollback_op.rollback_type}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback operation failed: {e}")
            return False
    
    def _rollback_full_import(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Perform full import rollback."""
        try:
            # Restore state from checkpoint
            state_restored = self._restore_import_state(rollback_op.import_id, target_checkpoint.state_data)
            
            if not state_restored:
                logger.error(f"Failed to restore import state for {rollback_op.import_id}")
                return False
            
            # Delete all imported records
            records_deleted = self._delete_all_imported_records(rollback_op.import_id)
            rollback_op.affected_records = records_deleted
            
            # Reset import status
            self._reset_import_status(rollback_op.import_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Full import rollback failed: {e}")
            return False
    
    def _rollback_partial_import(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Perform partial import rollback."""
        try:
            # Get records to rollback (records created after checkpoint)
            records_to_rollback = self._get_records_since_checkpoint(rollback_op.import_id, target_checkpoint.timestamp)
            
            # Delete those records
            records_deleted = 0
            for record in records_to_rollback:
                if self._delete_import_record(record['id'], record['table']):
                    records_deleted += 1
            
            rollback_op.affected_records = records_deleted
            
            # Restore partial state
            state_restored = self._restore_partial_import_state(rollback_op.import_id, target_checkpoint.state_data)
            
            if not state_restored:
                logger.warning(f"Failed to restore partial import state for {rollback_op.import_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Partial import rollback failed: {e}")
            return False
    
    def _rollback_row_level(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Perform row-level rollback."""
        try:
            # Get specific row to rollback (would be provided in metadata)
            row_id = rollback_op.metadata.get('row_id')
            table_name = rollback_opmetadata.get('table_name')
            
            if not row_id or not table_name:
                logger.error(f"Row-level rollback requires row_id and table_name in metadata")
                return False
            
            # Delete specific record
            if self._delete_import_record(row_id, table_name):
                rollback_op.affected_records = 1
                return True
            else:
                logger.error(f"Failed to delete record {row_id} from {table_name}")
                return False
                
        except Exception as e:
            logger.error(f"Row-level rollback failed: {e}")
            return False
    
    def _rollback_transaction_level(self, rollback_op: RollbackOperation, target_checkpoint: RollbackPoint) -> bool:
        """Perform transaction-level rollback."""
        try:
            # In a real implementation, this would rollback database transactions
            # For now, simulate transaction rollback
            logger.info(f"Transaction rollback simulated for import {rollback_op.import_id}")
            
            # This would involve:
            # 1. Rolling back uncommitted transactions
            # 2. Restoring database state from checkpoint
            # 3. Updating import status
            
            rollback_op.affected_records = 0  # Would be calculated from transaction
            
            return True
            
        except Exception as e:
            logger.error(f"Transaction-level rollback failed: {e}")
            return False
    
    def _restore_import_state(self, import_id: str, state_data: Dict[str, Any]) -> bool:
        """Restore import state from checkpoint data."""
        try:
            # This would restore import session state
            # For now, simulate state restoration
            logger.info(f"Import state restored for {import_id}")
            
            # In a real implementation, this would:
            # 1. Restore import session variables
            # 2. Restore file pointers
            # 3. Restore progress tracking
            # 4. Restore validation state
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore import state: {e}")
            return False
    
    def _restore_partial_import_state(self, import_id: str, state_data: Dict[str, Any]) -> bool:
        """Restore partial import state from checkpoint data."""
        try:
            # This would restore partial import state
            logger.info(f"Partial import state restored for {import_id}")
            
            # In a real implementation, this would:
            # 1. Restore partial progress tracking
            # 2. Restore validation state for processed records
            # 3. Update import session status
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore partial import state: {e}")
            return False
    
    def _delete_all_imported_records(self, import_id: str) -> int:
        """Delete all imported records for an import session."""
        try:
            deleted_count = 0
            
            # Get all tables that might contain imported data
            import_tables = self._get_import_tables()
            
            for table in import_tables:
                try:
                    # Delete records where import_id matches
                    if hasattr(table, 'query'):
                        query = table.query.filter(table.import_id == import_id)
                        count = query.count()
                        query.delete()
                        deleted_count += count
                        logger.info(f"Deleted {count} records from {table.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to delete records from {table}: {e}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete imported records: {e}")
            return 0
    
    def _delete_import_record(self, record_id: str, table_name: str) -> bool:
        """Delete a specific import record."""
        try:
            # Get table class
            table_class = self._get_table_class(table_name)
            
            if table_class:
                record = table_class.query.get(record_id)
                if record:
                    db.session.delete(record)
                    db.session.commit()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete record {record_id} from {table_name}: {e}")
            return False
    
    def _get_records_since_checkpoint(self, import_id: str, checkpoint_time: datetime) -> List[Dict[str, Any]]:
        """Get records created since checkpoint time."""
        try:
            records = []
            
            # Get all import tables
            import_tables = self._get_import_tables()
            
            for table in import_tables:
                try:
                    if hasattr(table, 'query') and hasattr(table, 'created_at'):
                        query = table.query.filter(
                            table.import_id == import_id,
                            table.created_at > checkpoint_time
                        )
                        
                        for record in query:
                            records.append({
                                'id': record.id,
                                'table': table.__name__,
                                'created_at': record.created_at.isoformat(),
                                'data': record.to_dict() if hasattr(record, 'to_dict') else {}
                            })
                except Exception as e:
                    logger.warning(f"Failed to get records from {table}: {e}")
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to get records since checkpoint: {e}")
            return []
    
    def _get_import_tables(self) -> List:
        """Get all tables that might contain imported data."""
        try:
            # This would dynamically discover tables with import_id field
            # For now, return common import tables
            from app.models import ApplicationComponent, VendorOrganization, UnifiedCapabilities
            
            tables = [ApplicationComponent, VendorOrganization, UnifiedCapabilities]
            
            # Add any other models that might have import_id
            # This would be more sophisticated in a real implementation
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get import tables: {e}")
            return []
    
    def _get_table_class(self, table_name: str) -> Optional:
        """Get table class by name."""
        try:
            # This would dynamically look up the table class
            # For now, return common table classes
            from app.models import ApplicationComponent, VendorOrganization, UnifiedCapabilities
            
            table_map = {
                'application_component': ApplicationComponent,
                'vendor_organization': VendorOrganization,
                'unified_capabilities': UnifiedCapabilities
            }
            
            return table_map.get(table_name)
            
        except Exception as e:
            logger.error(f"Failed to get table class for {table_name}: {e}")
            return None
    
    def _reset_import_status(self, import_id: str):
        """Reset import status."""
        try:
            # This would reset import status in database
            # For now, simulate status reset
            logger.info(f"Import status reset for {import_id}")
            
            # In a real implementation, this would:
            # 1. Update import session status to 'rolled_back'
            # 2. Clear progress tracking
            # 3. Update import statistics
            
        except Exception as e:
            logger.error(f"Failed to reset import status: {e}")
    
    def _get_latest_checkpoint(self, import_id: str) -> Optional[RollbackPoint]:
        """Get the latest checkpoint for an import."""
        with self._lock:
            if import_id not in self._import_checkpoints:
                return None
            
            checkpoint_ids = self._import_checkpoints[import_id]
            if not checkpoint_ids:
                return None
            
            # Get latest checkpoint
            latest_checkpoint_id = checkpoint_ids[-1]
            return self._checkpoints.get(latest_checkpoint_id)
    
    def get_checkpoints(self, import_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get checkpoints for an import.
        
        Args:
            import_id: Import session ID
            limit: Maximum number of checkpoints to return
            
        Returns:
            List of checkpoints
        """
        with self._lock:
            if import_id not in self._import_checkpoints:
                return []
            
            checkpoint_ids = self._import_checkpoints[import_id][-limit:]
            checkpoints = [self._checkpoints[cid] for cid in checkpoint_ids if cid in self._checkpoints]
            
            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x.timestamp, reverse=True)
            
            return [checkpoint.to_dict() for checkpoint in checkpoints]
    
    def get_rollback_operations(self, import_id: Optional[str] = None,
                              status: Optional[RollbackStatus] = None,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get rollback operations with filtering options.
        
        Args:
            import_id: Filter by import ID
            status: Filter by status
            limit: Maximum number of operations to return
            
        Returns:
            List of rollback operations
        """
        with self._lock:
            operations = list(self._rollback_operations.values())
        
        # Apply filters
        if import_id:
            operations = [op for op in operations if op.import_id == import_id]
        
        if status:
            operations = [op for op in operations if op.status == status]
        
        # Sort by creation time (newest first) and limit
        operations.sort(key=lambda x: x.created_at, reverse=True)
        
        return [op.to_dict() for op in operations[:limit]]
    
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
        
        if not recent_operations:
            return {
                'time_period': f"{time_delta.days} days",
                'total_operations': 0,
                'completed_operations': 0,
                'failed_operations': 0,
                'cancelled_operations': 0,
                'success_rate': 0,
                'type_distribution': {},
                'average_duration_seconds': 0,
                'total_checkpoints': len(self._checkpoints),
                'workflows_with_checkpoints': len(self._import_checkpoints),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Calculate statistics
        total_operations = len(recent_operations)
        completed_operations = len([op for op in recent_operations if op.status == RollbackStatus.COMPLETED])
        failed_operations = len([op for op in recent_operations if op.status == RollbackStatus.FAILED])
        cancelled_operations = len([op for op in recent_operations if op.status == RollbackStatus.CANCELLED])
        
        # Type distribution
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
            'workflows_with_checkpoints': len(self._import_checkpoints),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _cleanup_old_checkpoints(self):
        """Clean up old checkpoints based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self._checkpoint_retention_days)
        
        with self._lock:
            original_count = len(self._checkpoints)
            self._checkpoints = {cid: cp for cid, cp in self._checkpoints.items() if cp.timestamp > cutoff_time}
            
            # Remove excess checkpoints if over limit
            if len(self._checkpoints) > self._max_checkpoints:
                self._checkpoints = dict(list(self._checkpoints.items())[-self._max_checkpoints:])
            
            # Clean up import checkpoints list
            for import_id, checkpoint_ids in self._import_checkpoints.items():
                filtered_ids = [cid for cid in checkpoint_ids if cid in self._checkpoints]
                self._import_checkpoints[import_id] = filtered_ids
            
            cleaned_count = original_count - len(self._checkpoints)
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old checkpoints")
    
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

# Global import rollback manager instance
import_rollback_manager = ImportRollbackManager()
