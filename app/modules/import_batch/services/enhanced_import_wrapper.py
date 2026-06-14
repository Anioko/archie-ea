# mass-deletion-ok
"""
-> app.modules.import_batch.services.import_service

Enhanced Import Wrapper - Integrates recovery service with existing import routes

This wrapper provides backward-compatible integration of the new recovery system
with existing import functionality. It automatically creates sessions, handles
checkpointing, and provides recovery capabilities without breaking existing code.
"""

import logging
from typing import Any, Dict, List

from flask_login import current_user

from app.modules.import_batch.v2.services.import_recovery_service_v2 import (
    get_import_recovery_service,
)
from app.modules.import_batch.v2.services.import_staging_service_v2 import (
    get_import_staging_service,
)

logger = logging.getLogger(__name__)


class EnhancedImportWrapper:
    """
    Wrapper that adds recovery capabilities to existing import operations.

    This class provides a transparent layer that:
    - Automatically creates import sessions
    - Wraps existing import logic with checkpointing
    - Handles errors and enables recovery
    - Maintains backward compatibility
    """

    def __init__(self):
        self.staging_service = get_import_staging_service()
        self.recovery_service = get_import_recovery_service()
        self.logger = logger

    def get_import_status(self, session_id: int) -> Dict[str, Any]:
        """
        Get the status of an import session.

        Args:
            session_id: Import session ID

        Returns:
            Session status dictionary
        """
        return self.recovery_service.get_session_status(session_id)

    def resume_import(self, session_id: int) -> Dict[str, Any]:
        """
        Resume a failed or paused import.

        Args:
            session_id: Import session ID to resume

        Returns:
            Import results dictionary
        """
        return self.recovery_service.resume_import(session_id)

    def get_recoverable_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all recoverable sessions for the current user.

        Returns:
            List of session dictionaries
        """
        sessions = self.staging_service.get_recoverable_sessions(current_user.id)
        return [session.to_dict() for session in sessions]


# Singleton instance
_enhanced_import_wrapper = None
