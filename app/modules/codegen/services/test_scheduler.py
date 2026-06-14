"""Test scheduler -- trigger acceptance tests after deployment, on-demand, or nightly.

Stores results per version for trend tracking across releases.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VALID_TRIGGER_TYPES = frozenset({"post_deploy", "on_demand", "nightly", "manual"})


class TestScheduler:
    """Schedule and manage test execution for deployed solutions."""

    def trigger(self, solution_id: int, trigger_type: str, version: int | None = None) -> dict:
        """Trigger a test run for a specific solution.

        Args:
            solution_id: The solution to test.
            trigger_type: What triggered the run (post_deploy, on_demand, nightly, manual).
            version: Optional version number being tested.

        Returns dict with: solution_id, trigger, timestamp, report.
        """
        if trigger_type not in VALID_TRIGGER_TYPES:
            raise ValueError(f"Invalid trigger type '{trigger_type}'. Valid: {sorted(VALID_TRIGGER_TYPES)}")

        report = self._run_acceptance(solution_id, trigger_type, version)

        return {
            "solution_id": solution_id,
            "trigger": trigger_type,
            "version": version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report": report,
        }

    def trigger_nightly(self) -> list[dict]:
        """Run tests for all active deployed solutions.

        Returns list of trigger results, one per solution.
        """
        solution_ids = self._get_active_solutions()
        results = []

        for sid in solution_ids:
            try:
                result = self.trigger(solution_id=sid, trigger_type="nightly")
                results.append(result)
            except Exception as e:
                logger.warning("Nightly test failed for solution %s: %s", sid, e)
                results.append({
                    "solution_id": sid,
                    "trigger": "nightly",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                })

        return results

    def get_run_history(self, solution_id: int, limit: int = 20) -> list[dict]:
        """Get test run history for a solution, most recent first.

        Returns list of {id, trigger, status, version, summary, created_at}.
        """
        try:
            from app.modules.codegen.models import TestRun

            runs = (
                TestRun.query.filter_by(solution_id=solution_id)
                .order_by(TestRun.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": r.id,
                    "trigger": r.trigger,
                    "status": r.status,
                    "version": r.version,
                    "summary": r.summary or {},
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ]
        except Exception as e:
            logger.warning("Failed to get run history for solution %s: %s", solution_id, e)
            return []

    def get_version_trend(self, solution_id: int) -> list[dict]:
        """Get test results grouped by version for trend analysis.

        Returns list of {version, status, summary, tested_at} ordered by version.
        """
        try:
            from app.modules.codegen.models import TestRun

            runs = (
                TestRun.query.filter_by(solution_id=solution_id)
                .filter(TestRun.version.isnot(None))
                .order_by(TestRun.version.asc())
                .all()
            )

            return [
                {
                    "version": r.version,
                    "status": r.status,
                    "summary": r.summary or {},
                    "tested_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ]
        except Exception as e:
            logger.warning("Failed to get version trend for solution %s: %s", solution_id, e)
            return []

    def _run_acceptance(
        self, solution_id: int, trigger_type: str, version: int | None = None
    ) -> dict:
        """Run acceptance tests and persist results."""
        from app.modules.codegen.services.acceptance_test_runner import AcceptanceTestRunner

        runner = AcceptanceTestRunner()
        report = runner.run_all(
            solution_id=solution_id,
            persist=True,
            trigger=trigger_type,
        )

        # Update the persisted TestRun with version info
        if version is not None:
            try:
                from app.modules.codegen.models import TestRun
                from app.extensions import db

                latest_run = (
                    TestRun.query.filter_by(solution_id=solution_id)
                    .order_by(TestRun.created_at.desc())
                    .first()
                )
                if latest_run:
                    latest_run.version = version
                    db.session.commit()
            except Exception as e:
                logger.debug("Could not set version on test run: %s", e)

        return report

    def _get_active_solutions(self) -> list[int]:
        """Get IDs of all solutions with active (healthy) deployments."""
        try:
            from app.modules.codegen.models import SolutionInstance

            instances = SolutionInstance.query.filter_by(health_status="healthy").all()
            return [i.solution_id for i in instances]
        except Exception as e:
            logger.warning("Failed to query active solutions: %s", e)
            return []
