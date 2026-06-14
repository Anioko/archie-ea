"""
Background Sync Runner

Runs Abacus sync in a separate subprocess that survives Flask hot-reloads.
Uses database to track sync status so the UI can poll for completion.
"""

import json
import logging
import multiprocessing
import os
import sys
from datetime import datetime

logger = logging.getLogger(__name__)


def _run_sync_process(app_root: str, sync_type: str = "full"):
    """
    Worker function that runs in a separate process.

    This process is completely independent of Flask and survives hot-reloads.
    Status is written to database for UI polling.
    """
    # Add app root to path
    sys.path.insert(0, app_root)
    os.chdir(app_root)

    # Import inside the process to avoid sharing state
    import asyncio

    from app import create_app, db
    from app.models.models import ExternalSystem
    from app.services.abacus_sync_service import get_sync_service

    app = create_app()

    with app.app_context():
        try:
            # Mark sync as in progress
            abacus_config = ExternalSystem.query.filter_by(system_name="abacus").first()
            if abacus_config:
                abacus_config.connection_status = "syncing"
                abacus_config.last_error = None
                db.session.commit()

            # Get sync service
            sync_service = get_sync_service()

            # Run sync
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if sync_type == "full":
                    result = loop.run_until_complete(sync_service.run_full_sync())
                else:
                    result = loop.run_until_complete(sync_service.run_incremental_sync())
            finally:
                loop.close()

            # Update status based on result
            if abacus_config:
                if result.get("status") == "success":
                    abacus_config.connection_status = "connected"
                    abacus_config.last_sync_at = datetime.utcnow()
                    abacus_config.last_error = None
                    # Store stats in a JSON field or separate table if needed
                    stats_summary = json.dumps(
                        {
                            "records_fetched": result.get("records_fetched", {}),
                            "import_statistics": result.get("import_statistics", {}),
                            "completed_at": datetime.utcnow().isoformat(),
                        }
                    )
                    # Use last_error temporarily to store success stats (or add a new field)
                    abacus_config.last_error = f"SUCCESS: {stats_summary}"
                else:
                    abacus_config.connection_status = "error"
                    abacus_config.last_error = result.get("message", "Unknown error")

                db.session.commit()

            print(f"Sync completed: {result.get('status')}")
            return result

        except Exception as e:
            # Update error status
            try:
                abacus_config = ExternalSystem.query.filter_by(system_name="abacus").first()
                if abacus_config:
                    abacus_config.connection_status = "error"
                    abacus_config.last_error = str(e)
                    db.session.commit()
            except Exception:
                pass

            print(f"Sync failed: {e}")
            raise


def start_background_sync(sync_type: str = "full") -> dict:
    """
    Start Abacus sync in a background subprocess.

    Returns immediately - sync continues independently of Flask.
    Check ExternalSystem.connection_status for progress:
    - "syncing": In progress
    - "connected": Completed successfully
    - "error": Failed (check last_error for details)

    Args:
        sync_type: "full" or "incremental"

    Returns:
        Dict with status and message
    """
    try:
        # Get app root directory
        app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Create subprocess
        # Using spawn to create a completely independent process
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(
            target=_run_sync_process,
            args=(app_root, sync_type),
            daemon=False,  # Non-daemon so it survives parent exit
        )
        process.start()

        logger.info(f"Background sync started (PID: {process.pid}, type: {sync_type})")

        return {
            "status": "started",
            "message": f"Sync started in background (PID: {process.pid}). Check status for progress.",
            "pid": process.pid,
            "sync_type": sync_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to start background sync: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to start sync: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }


def get_sync_status() -> dict:
    """
    Get current sync status from database.

    Returns:
        Dict with current sync status
    """
    from app.models.models import ExternalSystem

    abacus_config = ExternalSystem.query.filter_by(system_name="abacus").first()

    if not abacus_config:
        return {"status": "not_configured", "message": "Abacus not configured"}

    # Parse success stats if present
    last_error = abacus_config.last_error
    stats = None
    if last_error and last_error.startswith("SUCCESS:"):
        try:
            stats = json.loads(last_error.replace("SUCCESS: ", ""))
            last_error = None
        except json.JSONDecodeError:
            pass

    return {
        "status": abacus_config.connection_status or "unknown",
        "last_sync_at": abacus_config.last_sync_at.isoformat()
        if abacus_config.last_sync_at
        else None,
        "last_error": last_error,
        "stats": stats,
        "enabled": abacus_config.enabled,
    }
