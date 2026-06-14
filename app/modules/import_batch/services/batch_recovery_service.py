# mass-deletion-ok
"""
-> app.modules.import_batch.services.batch_service

Batch Import Recovery Service

Handles recovery of stuck batch import operations and cleanup of orphaned records.
"""

import logging

logger = logging.getLogger(__name__)


class BatchImportRecoveryService:
    """
    Recovery service for batch import operations.
    
    Handles:
    - Stuck PROCESSING applications
    - Orphaned batch states
    - Inconsistent job progress
    - Cleanup of failed operations
    """
    
    # Recovery thresholds (configurable)
    PROCESSING_TIMEOUT_MINUTES = 30  # Max time for app to be in PROCESSING
    STUCK_JOB_TIMEOUT_HOURS = 24     # Max time for job to be stuck
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)


# Global recovery service instance
_recovery_service = BatchImportRecoveryService()
