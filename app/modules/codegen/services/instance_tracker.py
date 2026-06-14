"""CRUD and monitoring for deployed SolutionInstances.

Provides:
- get_instance / list_instances: query deployed solutions
- update_health: update health status from external check
- check_quota: enforce max total instances limit
"""
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.modules.codegen.models import SolutionInstance

logger = logging.getLogger(__name__)

_DEFAULT_MAX_INSTANCES = 50


class InstanceTracker:
    """Tracks and monitors deployed solution instances."""

    def __init__(self, max_total_instances: int = _DEFAULT_MAX_INSTANCES):
        self._max_total = max_total_instances

    def get_instance(self, solution_id: int) -> SolutionInstance | None:
        return SolutionInstance.query.filter_by(solution_id=solution_id).first()

    def list_instances(self) -> list[SolutionInstance]:
        return SolutionInstance.query.order_by(SolutionInstance.created_at.desc()).all()

    def active_count(self) -> int:
        return SolutionInstance.query.filter(SolutionInstance.health_status != "stopped").count()

    def check_quota(self) -> None:
        count = self.active_count()
        if count >= self._max_total:
            raise RuntimeError(
                f"Deployment quota exceeded: {count}/{self._max_total} active instances. "
                "Stop or destroy existing deployments, or contact your admin to increase the limit."
            )

    def update_health(self, instance_id: int, status: str) -> None:
        instance = db.session.get(SolutionInstance, instance_id)
        if not instance:
            logger.warning("Cannot update health for missing instance %s", instance_id)
            return
        instance.health_status = status
        instance.last_health_check = datetime.now(timezone.utc)
        db.session.commit()
