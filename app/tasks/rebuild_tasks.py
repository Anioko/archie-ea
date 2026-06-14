"""
Module-level worker functions for multiprocessing.spawn.

MUST remain at module level — functions defined inside other functions (closures,
nested defs) are not picklable by multiprocessing.spawn and will raise:
  PicklingError: Can't pickle <function _worker at ...>: attribute lookup failed

This module is the fix for Fix 2, 4, and 5. All three use multiprocessing.spawn
to avoid Gunicorn worker thread lifecycle issues. See background_sync.py for the
reference pattern this follows.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def rebuild_relationships_worker(app_root: str, solution_id: int) -> None:
    """Spawned by confirm_domain to asynchronously rebuild ARM relationships.

    Creates its own Flask app context and SQLAlchemy session — fully independent
    of the Gunicorn worker that spawned it.
    """
    sys.path.insert(0, app_root)
    os.chdir(app_root)
    from app import create_app  # noqa: PLC0415
    app = create_app()
    with app.app_context():
        try:
            from app.modules.architecture_assistant.journey_orchestrator import JourneyOrchestrator  # noqa: PLC0415
            JourneyOrchestrator(solution_id).rebuild_relationships()
            logger.info("rebuild_relationships_worker completed sol=%d", solution_id)
        except Exception as exc:
            logger.warning(
                "rebuild_relationships_worker failed sol=%d: %s", solution_id, exc
            )


def promote_domains_worker(app_root: str, solution_id: int, domain_codes: list) -> None:
    """Spawned by batch_accept_proposals to asynchronously promote all domains.

    Confirms each domain in sequence (each is idempotent), then rebuilds ARM
    relationships. Per-domain failures are logged and skipped; promotion is
    recoverable by re-running batch_accept for the same solution.
    """
    sys.path.insert(0, app_root)
    os.chdir(app_root)
    from app import create_app  # noqa: PLC0415
    app = create_app()
    with app.app_context():
        from app.modules.architecture_assistant.journey_orchestrator import JourneyOrchestrator  # noqa: PLC0415
        orch = JourneyOrchestrator(solution_id)
        for domain_code in domain_codes:
            try:
                orch.confirm_domain(domain_code)
            except Exception as exc:
                logger.warning(
                    "promote_domains_worker domain=%s sol=%d: %s",
                    domain_code, solution_id, exc,
                )
        try:
            orch.rebuild_relationships()
            logger.info(
                "promote_domains_worker completed sol=%d domains=%s",
                solution_id, domain_codes,
            )
        except Exception as exc:
            logger.warning(
                "promote_domains_worker rebuild_relationships sol=%d: %s",
                solution_id, exc,
            )


def generate_decision_rationale_worker(app_root: str, solution_id: int) -> None:
    """Spawned by generate_decision_rationale route to run LLM calls asynchronously.

    Processes proposals in batches of 20 to stay within LLM token budgets.
    Uses row-level locks on acm_properties writes to prevent race conditions.
    Skips proposals that already have a clean build_or_buy and non-null rationale.
    """
    sys.path.insert(0, app_root)
    os.chdir(app_root)
    from app import create_app  # noqa: PLC0415
    app = create_app()
    with app.app_context():
        try:
            from app.modules.architecture_assistant.journey_orchestrator import JourneyOrchestrator  # noqa: PLC0415
            JourneyOrchestrator(solution_id).generate_decision_rationale()
            logger.info(
                "generate_decision_rationale_worker completed sol=%d", solution_id
            )
        except Exception as exc:
            logger.warning(
                "generate_decision_rationale_worker failed sol=%d: %s",
                solution_id, exc,
            )
