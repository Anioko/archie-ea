"""
Abacus Scheduled Sync Task

Background task for daily incremental synchronization with Avolution Abacus.
Runs at 2 AM by default (configurable via ExternalSystem.sync_interval_minutes).

Uses APScheduler for reliable scheduling with:
- Cron-style scheduling (daily at specified hour)
- Async task execution
- Error handling and retry logic
- Job persistence across app restarts

Named platform job, not a per-tenant one: ``ExternalSystem`` (the Abacus
connection record this reads) carries no ``organization_id`` -- there is one
Abacus connection for the whole platform, not one per tenant. It is listed as
deliberately unfenced in ``scripts/unfenced_tables.txt``. ``run_abacus_sync_job``
is therefore guarded by ``job_lock`` (a cross-process advisory lock, the same
mechanism ``app/jobs/capability_projection_job.py`` uses for the same reason),
not by ``tenant_scope`` -- there is no organisation to scope it by.

The job is NOT registered by the worker process (``app/jobs/worker.py``) because
the sync writes tenant-owned rows (ApplicationComponent, BusinessCapability,
ArchiMateElement, ArchiMateRelationship) and the method it calls
(``async_run_incremental_sync``) is not ``run_incremental_sync``.  The job will
be re-registered once it has a tenant context and the correct method name.
"""

import asyncio
import logging
from datetime import datetime

from app.services.abacus_sync_service import get_sync_service

logger = logging.getLogger(__name__)


def run_abacus_sync_job(app=None):
    """
    Background job to run Abacus incremental sync.

    Called by APScheduler on schedule. Wraps async sync call in event loop.

    ``app`` is the Flask application the caller is running under. Reading
    ``ExternalSystem``/config through the ORM requires an application
    context, which APScheduler's background thread does not push on its own
    -- ``init_abacus_scheduler`` always passes ``app`` through a closure, so
    the ``app is None`` branch only matters for a direct unit-test call.
    """
    logger.info("Abacus scheduled sync job started")

    from app.jobs.tenant_safe_job import job_lock

    def _run_sync():
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

    def _run_locked():
        with job_lock("abacus_incremental_sync", required=False) as acquired:
            if not acquired:
                logger.info(
                    "Abacus sync job skipped -- advisory lock held by another process"
                )
                return
            _run_sync()

    if app is not None:
        with app.app_context():
            _run_locked()
    else:
        _run_locked()


def init_abacus_scheduler(app, scheduler=None):
    """
    Initialize the Abacus sync job on an APScheduler instance.

    Args:
        app: Flask application instance
        scheduler: Existing APScheduler instance to register the job on.
                   When None (backward-compatible path for direct tests), a
                   BackgroundScheduler is created, started and stored.

    Note: called by the dedicated jobs worker (app/jobs/worker.py), which
    passes the ``ea_workflow_scheduler`` from ``app.extensions`` so there is
    never a second scheduler instance. Previously each call created its own.
    """
    try:
        from apscheduler.triggers.cron import CronTrigger

        # Check if APScheduler is available
        logger.info("Initializing Abacus sync scheduler...")

        own_scheduler = False
        if scheduler is None:
            from apscheduler.schedulers.background import BackgroundScheduler

            scheduler = BackgroundScheduler()
            own_scheduler = True

        # Get sync schedule from configuration
        # Default: Daily at 2 AM
        sync_hour = app.config.get("ABACUS_SYNC_HOUR", 2)
        sync_minute = app.config.get("ABACUS_SYNC_MINUTE", 0)

        # Add job with cron trigger
        scheduler.add_job(
            func=lambda: run_abacus_sync_job(app),
            trigger=CronTrigger(hour=sync_hour, minute=sync_minute),
            id="abacus_incremental_sync",
            name="Abacus Incremental Sync (Daily)",
            replace_existing=True,
        )

        # Start scheduler only when this call owns it
        if own_scheduler:
            scheduler.start()

        # Remove any undeclared job ids — this job itself must be declared
        # in PLATFORM_JOBS or TENANT_JOBS in app/jobs/tenant_safe_job.py.
        try:
            from app.jobs.tenant_safe_job import _remove_undeclared_jobs

            _remove_undeclared_jobs(scheduler)
        except Exception as exc:
            logger.exception(
                "init_abacus_scheduler: _remove_undeclared_jobs failed — "
                "enforcement skipped: %s",
                exc,
            )

        logger.info(f"Abacus sync scheduler: Daily at {sync_hour:02d}:{sync_minute:02d}")

        # Store scheduler in app context for shutdown (backward compat)
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
