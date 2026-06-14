"""
Abacus Scheduled Sync Task

Background task for daily incremental synchronization with Avolution Abacus.
Runs at 2 AM by default (configurable via ExternalSystem.sync_interval_minutes).

Uses APScheduler for reliable scheduling with:
- Cron-style scheduling (daily at specified hour)
- Async task execution
- Error handling and retry logic
- Job persistence across app restarts
"""

import asyncio
import logging
from datetime import datetime

from app.services.abacus_sync_service import get_sync_service

logger = logging.getLogger(__name__)


def run_abacus_sync_job():
    """
    Background job to run Abacus incremental sync.

    Called by APScheduler on schedule.
    Wraps async sync call in event loop.
    """
    logger.info("Abacus scheduled sync job started")

    try:
        # Get sync service
        sync_service = get_sync_service()

        # Run incremental sync in async context
        # Create new event loop for background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(sync_service.run_incremental_sync())
            logger.info(f"Scheduled sync completed: {result.get('status')}")

            if result.get("status") == "error":
                logger.error(f"Sync error: {result.get('message')}")

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Abacus sync job failed: {e}", exc_info=True)


def init_abacus_scheduler(app):
    """
    Initialize APScheduler for Abacus sync.

    Args:
        app: Flask application instance

    Note: This function should be called during Flask app initialization.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        # Check if APScheduler is available
        logger.info("Initializing Abacus sync scheduler...")

        # Create scheduler
        scheduler = BackgroundScheduler()

        # Get sync schedule from configuration
        # Default: Daily at 2 AM
        sync_hour = app.config.get("ABACUS_SYNC_HOUR", 2)
        sync_minute = app.config.get("ABACUS_SYNC_MINUTE", 0)

        # Add job with cron trigger
        scheduler.add_job(
            func=run_abacus_sync_job,
            trigger=CronTrigger(hour=sync_hour, minute=sync_minute),
            id="abacus_incremental_sync",
            name="Abacus Incremental Sync (Daily)",
            replace_existing=True,
        )

        # Start scheduler
        scheduler.start()

        logger.info(f"Abacus sync scheduler started: Daily at {sync_hour:02d}:{sync_minute:02d}")

        # Store scheduler in app context for shutdown
        app.abacus_scheduler = scheduler

        return scheduler

    except ImportError:
        logger.warning(
            "APScheduler not installed - Abacus scheduled sync disabled. "
            "Install with: pip install APScheduler"
        )
        return None

    except Exception as e:
        logger.error(f"Failed to initialize Abacus scheduler: {e}", exc_info=True)
        return None


def shutdown_abacus_scheduler(app):
    """
    Shutdown Abacus sync scheduler gracefully.

    Args:
        app: Flask application instance
    """
    if hasattr(app, "abacus_scheduler") and app.abacus_scheduler:
        logger.info("Shutting down Abacus sync scheduler...")
        app.abacus_scheduler.shutdown(wait=False)
        logger.info("Abacus sync scheduler stopped")


def trigger_manual_sync():
    """
    Trigger manual Abacus sync (used by admin panel).

    Returns:
        Dictionary with sync result
    """
    logger.info("Manual Abacus sync triggered")

    try:
        # Get sync service
        sync_service = get_sync_service()

        # Run FULL sync for manual triggers to get all data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(sync_service.run_full_sync())
            return result

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Manual sync failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Manual sync failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }
