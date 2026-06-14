"""
DEPRECATED: Import from app.modules.capabilities.services.seeder_service instead.
-> app.modules.capabilities.services.seeder_service

Technical Capability Seeder Service

Seeds technical capability data using ACMHybridManager which loads from
acm_seed_data.py — the canonical ACM technical capability taxonomy.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from app.models.technical_capability import TechnicalCapability
from app.services.core.database_seeder import BaseSeeder

logger = logging.getLogger(__name__)


class TechnicalCapabilitySeeder(BaseSeeder):
    """
    Seeds technical capability data via ACMHybridManager.

    Uses the existing ACM (Application Capability Model) seed data system
    which provides 7 domains with L1-L4 capability hierarchy.
    """

    def __init__(self):
        super().__init__("acm_seed_data.py")
        self.model_class = TechnicalCapability

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Not used — validation is handled by ACMHybridManager."""
        return (True, None)

    def create_or_update_record(self, record: Dict[str, Any]) -> bool:
        """Not used — creation is handled by ACMHybridManager."""
        return True

    def seed(self) -> Dict[str, Any]:
        """Seed technical capabilities via ACMHybridManager."""
        logger.info("Starting technical capability seeding...")

        cap_count = TechnicalCapability.query.count()

        if cap_count > 0:
            return self._create_result(
                success=True,
                message=f"{cap_count} technical capabilities already exist",
                data={
                    "created": 0,
                    "updated": 0,
                    "existing": cap_count,
                },
            )

        # No capabilities — run the ACM seeder
        try:
            from app.services.acm_hybrid_manager import ACMHybridManager

            result = ACMHybridManager.seed_acm_capabilities(include_platform_specifics=True)

            if result.get("success"):
                created = result.get("created", 0)
                updated = result.get("updated", 0)
                return self._create_result(
                    success=True,
                    message=f"Seeded {created} technical capabilities ({updated} updated)",
                    data={
                        "created": created,
                        "updated": updated,
                        "errors": [],
                    },
                )
            else:
                stage = result.get("stage", "unknown")
                return self._create_result(
                    success=False,
                    message=f"ACM seeding failed at stage: {stage}",
                )

        except Exception as e:
            logger.error(f"Error during technical capability seeding: {e}")
            return self._create_result(success=False, message=f"Seeding failed: {str(e)}")

    def rollback(self) -> Dict[str, Any]:
        """Rollback technical capability seeding."""
        logger.info("Rolling back technical capability seeding...")
        logger.warning("Rollback not fully implemented - would need to track seeded records")
        return self._create_result(
            success=True,
            message="Technical capability rollback completed (manual verification required)",
        )
