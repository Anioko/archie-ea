"""
Abacus Sync Service

Orchestrates daily incremental synchronization with Avolution Abacus.
Fetches only modified records (last 24h) for performance optimization.
Updates existing A.R.C.I.E records based on Abacus ID match.

Key Features:
- Incremental sync (modified records only, not full batch)
- Scheduled execution (daily at 2 AM, configurable)
- Manual trigger from admin panel
- Rollback on error (transaction safety)
- Sync history tracking via ExternalSystem.last_sync_at
- Error logging and admin notification
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.connectors.abacus import AbacusConnector
from app.models.models import ExternalSystem
from app.services.abacus_import_service import AbacusImportService

logger = logging.getLogger(__name__)


class AbacusSyncService:
    """
    Service for orchestrating scheduled Abacus synchronization.

    Uses AbacusImportService for actual import logic.
    Adds scheduling, error handling, and transaction management.
    """

    SYSTEM_NAME = "abacus"  # Must match ExternalSystem.system_name

    def __init__(self):
        """Initialize sync service."""
        self.external_system = None
        self.connector = None
        self.import_service = None

    def _initialize_connector(self) -> bool:
        """
        Initialize Abacus connector from ExternalSystem configuration or .env fallback.

        Returns:
            True if successful, False if configuration missing
        """
        try:
            # Get Abacus configuration from database
            self.external_system = ExternalSystem.query.filter_by(
                system_name=self.SYSTEM_NAME
            ).first()

            # Try .env fallback if no database config
            if not self.external_system:
                import os

                env_base_url = os.getenv("ABACUS_BASE_URL")
                env_client_id = os.getenv("ABACUS_CLIENT_ID")
                env_client_secret = os.getenv("ABACUS_CLIENT_SECRET")

                if all([env_base_url, env_client_id, env_client_secret]):
                    logger.info("Using Abacus credentials from .env file")

                    # Create a temporary config object that mimics ConnectorConfig
                    # ConnectorConfig expects config.config to be a dict with credentials
                    class TempConfig:
                        def __init__(self):
                            self.config = {
                                "base_url": env_base_url,
                                "client_id": env_client_id,
                                "client_secret": env_client_secret,
                            }

                    config = TempConfig()

                    # Initialize connector and import service
                    self.connector = AbacusConnector(config)
                    self.import_service = AbacusImportService(self.connector)

                    return True
                else:
                    logger.error(
                        f"ExternalSystem '{self.SYSTEM_NAME}' not found in database and .env variables incomplete"
                    )
                    return False

            if not self.external_system.enabled:
                logger.info("Abacus sync disabled in configuration")
                return False

            # Parse credentials from database
            import json

            try:
                credentials = json.loads(self.external_system.credentials)
            except (json.JSONDecodeError, TypeError):
                logger.error("Invalid Abacus credentials format")
                return False

            # Create connector config from database
            # ConnectorConfig expects config.config to be a dict with credentials
            # Also include filter settings from config_json
            config_dict = {}
            if self.external_system.config_json:
                try:
                    config_dict = json.loads(self.external_system.config_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            class TempConfig:
                def __init__(self, external_system, credentials, config_dict):
                    self.config = {
                        "base_url": external_system.base_url,
                        "client_id": credentials.get("client_id"),
                        "client_secret": credentials.get("client_secret"),
                        "filter_uk_only": config_dict.get("filter_uk_only", False),
                        "filter_countries": config_dict.get("filter_countries", ""),
                    }

            config = TempConfig(self.external_system, credentials, config_dict)

            # Initialize connector and import service
            self.connector = AbacusConnector(config)
            self.import_service = AbacusImportService(self.connector)

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Abacus connector: {e}", exc_info=True)
            return False

    async def async_run_incremental_sync(self) -> Dict[str, any]:
        """
        Run incremental sync: fetch and import modified records only.

        Returns:
            Dictionary with sync statistics and status
        """
        logger.info("Starting Abacus incremental sync...")

        # Initialize connector
        if not self._initialize_connector():
            return {
                "status": "error",
                "message": "Failed to initialize Abacus connector",
                "timestamp": datetime.utcnow().isoformat(),
            }

        try:
            # Determine sync window (modified since last sync, or last 24h)
            since = self._get_sync_window()
            logger.info(f"Fetching Abacus records modified since {since}")

            # Fetch modified records from Abacus
            batch_result = await self.connector.batch_sync(since=since)

            applications = batch_result.get("applications", [])
            capabilities = batch_result.get("capabilities", [])
            relationships = batch_result.get("relationships", [])

            logger.info(
                f"Fetched from Abacus: {len(applications)} apps, "
                f"{len(capabilities)} caps, {len(relationships)} rels (modified since {since})"
            )

            # Import using existing import service
            # This will create new or update existing records
            await self.import_service.import_capabilities(capabilities)
            await self.import_service.import_applications(applications)
            await self.import_service.import_relationships(relationships)

            # Update sync metadata (only if using database config)
            if self.external_system:
                self.external_system.last_sync_at = datetime.utcnow()
                self.external_system.connection_status = "connected"
                self.external_system.last_error = None
                db.session.commit()

            # Prepare success response
            stats = self.import_service.stats
            result = {
                "status": "success",
                "sync_window_start": since.isoformat() if since else None,
                "sync_window_end": datetime.utcnow().isoformat(),
                "records_fetched": {
                    "applications": len(applications),
                    "capabilities": len(capabilities),
                    "relationships": len(relationships),
                },
                "import_statistics": stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(f"Abacus incremental sync completed successfully: {result}")
            return result

        except SQLAlchemyError as e:
            # Database error - rollback transaction
            db.session.rollback()
            error_msg = f"Database error during sync: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Update error status
            if self.external_system:
                self.external_system.connection_status = "error"
                self.external_system.last_error = error_msg
                db.session.commit()

            return {
                "status": "error",
                "message": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # General error
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Update error status
            if self.external_system:
                try:
                    self.external_system.connection_status = "error"
                    self.external_system.last_error = error_msg
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            return {
                "status": "error",
                "message": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _get_sync_window(self) -> Optional[datetime]:
        """
        Determine sync window start time.

        Returns:
            Datetime to fetch records modified since, or None for full sync
        """
        if self.external_system and self.external_system.last_sync_at:
            # Incremental: fetch since last sync
            return self.external_system.last_sync_at
        else:
            # First sync: fetch last 24 hours (or None for all historical data)
            # Using 24h window to avoid overwhelming initial sync
            return datetime.utcnow() - timedelta(days=1)

    async def async_run_full_sync(self) -> Dict[str, any]:
        """
        Run full batch sync (all records, not just modified).

        Use this for:
        - Initial setup
        - Manual data refresh
        - Disaster recovery

        Returns:
            Dictionary with sync statistics and status
        """
        logger.info("Starting Abacus FULL sync (all records)...")

        # Initialize connector
        if not self._initialize_connector():
            return {
                "status": "error",
                "message": "Failed to initialize Abacus connector",
                "timestamp": datetime.utcnow().isoformat(),
            }

        try:
            # Fetch ALL records (since=None)
            batch_result = await self.connector.batch_sync(since=None)

            applications = batch_result.get("applications", [])
            capabilities = batch_result.get("capabilities", [])
            relationships = batch_result.get("relationships", [])

            logger.info(
                f"Fetched ALL records from Abacus: {len(applications)} apps, "
                f"{len(capabilities)} caps, {len(relationships)} rels"
            )

            # Import using existing import service
            await self.import_service.import_capabilities(capabilities)
            await self.import_service.import_applications(applications)
            await self.import_service.import_relationships(relationships)

            # Update sync metadata (only if using database config)
            if self.external_system:
                self.external_system.last_sync_at = datetime.utcnow()
                self.external_system.connection_status = "connected"
                self.external_system.last_error = None
                db.session.commit()

            # Prepare success response
            stats = self.import_service.stats
            result = {
                "status": "success",
                "sync_type": "full",
                "records_fetched": {
                    "applications": len(applications),
                    "capabilities": len(capabilities),
                    "relationships": len(relationships),
                },
                "import_statistics": stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(f"Abacus full sync completed successfully: {result}")
            return result

        except Exception as e:
            # Rollback on error
            db.session.rollback()
            error_msg = f"Full sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Update error status
            if self.external_system:
                try:
                    self.external_system.connection_status = "error"
                    self.external_system.last_error = error_msg
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            return {
                "status": "error",
                "message": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_sync_status(self) -> Dict[str, any]:
        """
        Get current sync status and metadata.

        Falls back to .env configuration if no ExternalSystem database record exists.

        Returns:
            Dictionary with sync status information
        """
        import os

        try:
            external_system = ExternalSystem.query.filter_by(system_name=self.SYSTEM_NAME).first()

            if not external_system:
                # Fall back to .env configuration
                env_base_url = os.getenv("ABACUS_BASE_URL")
                env_enabled = os.getenv("ABACUS_ENABLED", "false").lower() == "true"
                env_countries = os.getenv("ABACUS_FILTER_COUNTRIES", "")

                if env_base_url and env_enabled:
                    return {
                        "status": "unknown",
                        "enabled": True,
                        "sync_enabled": False,
                        "last_sync_at": None,
                        "last_error": None,
                        "sync_interval_minutes": None,
                        "base_url": env_base_url,
                        "filter_countries": env_countries,
                        "config_source": "env",
                    }

                return {
                    "status": "not_configured",
                    "message": "Abacus integration not configured",
                }

            return {
                "status": external_system.connection_status or "unknown",
                "enabled": external_system.enabled,
                "sync_enabled": external_system.sync_enabled,
                "last_sync_at": (
                    external_system.last_sync_at.isoformat()
                    if external_system.last_sync_at
                    else None
                ),
                "last_error": external_system.last_error,
                "sync_interval_minutes": external_system.sync_interval_minutes,
                "base_url": external_system.base_url,
            }

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}


# Global service instance
_sync_service = None


def get_sync_service() -> AbacusSyncService:
    """
    Get the global AbacusSyncService instance.

    Returns:
        AbacusSyncService singleton instance
    """
    global _sync_service
    if _sync_service is None:
        _sync_service = AbacusSyncService()
    return _sync_service
