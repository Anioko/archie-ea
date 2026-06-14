# mass-deletion-ok
"""
-> app.modules.import_batch.services.import_service

Import Audit Service

Comprehensive audit trail for all import operations.
Tracks user actions, data changes, and system events.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from flask import request
from app import db
from app.models.audit_log import AuditLog
from app.models.batch_import import ImportAuditLog

logger = logging.getLogger(__name__)


class ImportAuditService:
    """
    Comprehensive audit service for import operations.
    
    Provides unified audit trail across all import systems:
    - Unified applications import
    - Batch import
    - Conflict resolution
    - Data changes
    - System events
    """
    
    # NOTE (PROG-002): the four convenience wrappers below this class have
    # always called log_import_operation / log_batch_operation — neither
    # method existed, so every call site crashed (masked until the batch
    # state-machine fix made approve reachable). Implemented against the
    # ImportAuditLog model.

    @classmethod
    def log_import_operation(
        cls,
        operation: str,
        import_type: str,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Optional["ImportAuditLog"]:
        """Write an import-operation audit row. Never raises — audit failure
        must not break the operation being audited."""
        try:
            from flask_login import current_user

            entry = ImportAuditLog(
                user_id=getattr(current_user, "id", None) or 0,
                user_email=getattr(current_user, "email", None),
                import_type=import_type or "unknown",
                filename=(details or {}).get("filename"),
                changes=[{"operation": operation, "details": details or {}}],
                errors=[error_message] if error_message else None,
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception as e:
            logger.error(f"Audit logging failed for {operation}: {e}")
            db.session.rollback()
            return None

    @classmethod
    def log_batch_operation(
        cls,
        operation: str,
        batch_id: int,
        job_id: int,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Optional["ImportAuditLog"]:
        """Write a batch-operation audit row (approval/commit/reject)."""
        payload = dict(details or {})
        payload.update({"batch_id": batch_id, "job_id": job_id})
        return cls.log_import_operation(
            operation=operation,
            import_type="batch",
            details=payload,
            success=success,
            error_message=error_message,
        )

    @classmethod
    def get_import_statistics(
        cls,
        import_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get import operation statistics.
        
        Args:
            import_type: Filter by import type
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            Import statistics dictionary
        """
        try:
            # Query ImportAuditLog
            query = ImportAuditLog.query
            
            # Apply filters
            if import_type:
                query = query.filter(ImportAuditLog.import_type == import_type)
            if start_date:
                query = query.filter(ImportAuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(ImportAuditLog.timestamp <= end_date)
            
            # Get all records for statistics
            records = query.all()
            
            # Calculate statistics
            stats = {
                'total_operations': len(records),
                'successful_operations': len([r for r in records if r.status == 'success']),
                'failed_operations': len([r for r in records if r.status == 'error']),
                'operations_by_type': {},
                'operations_by_status': {},
                'unique_users': len(set(r.user_id for r in records if r.user_id)),
                'date_range': {
                    'start': min(r.timestamp for r in records if r.timestamp).isoformat() if records else None,
                    'end': max(r.timestamp for r in records if r.timestamp).isoformat() if records else None
                }
            }
            
            # Group by operation type
            for record in records:
                op_type = record.operation or 'unknown'
                stats['operations_by_type'][op_type] = stats['operations_by_type'].get(op_type, 0) + 1
            
            # Group by status
            for record in records:
                status = record.status or 'unknown'
                stats['operations_by_status'][status] = stats['operations_by_status'].get(status, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get import statistics: {e}", exc_info=True)
            return {}


# Convenience functions for common audit operations
def log_file_upload(
    filename: str,
    file_size: int,
    import_type: str,
    success: bool = True,
    error_message: Optional[str] = None
) -> AuditLog:
    """Log file upload operation."""
    return ImportAuditService.log_import_operation(
        operation='file_upload',
        import_type=import_type,
        details={
            'filename': filename,
            'file_size': file_size,
            'ip_address': request.remote_addr if request else None
        },
        success=success,
        error_message=error_message
    )


def log_import_analysis(
    import_type: str,
    analysis_results: Dict[str, Any],
    success: bool = True,
    error_message: Optional[str] = None
) -> AuditLog:
    """Log import analysis operation."""
    return ImportAuditService.log_import_operation(
        operation='import_analysis',
        import_type=import_type,
        details=analysis_results,
        success=success,
        error_message=error_message
    )


def log_import_commit(
    import_type: str,
    commit_results: Dict[str, Any],
    success: bool = True,
    error_message: Optional[str] = None
) -> AuditLog:
    """Log import commit operation."""
    return ImportAuditService.log_import_operation(
        operation='import_commit',
        import_type=import_type,
        details=commit_results,
        success=success,
        error_message=error_message
    )


def log_batch_approval(
    batch_id: int,
    job_id: int,
    approval_results: Dict[str, Any],
    success: bool = True,
    error_message: Optional[str] = None
) -> ImportAuditLog:
    """Log batch approval operation."""
    return ImportAuditService.log_batch_operation(
        operation='batch_approval',
        batch_id=batch_id,
        job_id=job_id,
        details=approval_results,
        success=success,
        error_message=error_message
    )
