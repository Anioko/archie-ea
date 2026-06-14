"""
DEPRECATED: Import from app.modules.capabilities.services.seeder_service instead.
-> app.modules.capabilities.services.seeder_service

Business Capability Seeder Service

Reports business capability status. Capabilities are created by VendorCatalogueImporter
when vendor organizations are seeded — this seeder verifies capability state.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from app.models.business_capabilities import BusinessCapability
from app.services.core.database_seeder import BaseSeeder

logger = logging.getLogger(__name__)


class BusinessCapabilitySeeder(BaseSeeder):
    """
    Business capability status reporter and seeder.

    Capabilities are created automatically by VendorCatalogueImporter when
    vendor_organizations seeder runs. This seeder re-runs the import
    if no capabilities exist, otherwise reports current status.
    """

    def __init__(self):
        super().__init__("vendor_catalogue.py")
        self.model_class = BusinessCapability

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Not used — validation is handled by VendorCatalogueImporter."""
        return (True, None)

    def create_or_update_record(self, record: Dict[str, Any]) -> bool:
        """Not used — creation is handled by VendorCatalogueImporter."""
        return True

    def seed(self) -> Dict[str, Any]:
        """Seed business capabilities via VendorCatalogueImporter."""
        logger.info("Starting business capability seeding...")

        cap_count = BusinessCapability.query.count()

        if cap_count > 0:
            return self._create_result(
                success=True,
                message=f"{cap_count} business capabilities already exist",
                data={
                    "created": 0,
                    "updated": 0,
                    "existing": cap_count,
                },
            )

        # No capabilities — run the importer
        try:
            from app.seed_data.catalogue_importer import VendorCatalogueImporter

            importer = VendorCatalogueImporter()
            summary = importer.run(commit=True)
            report = summary.to_dict()

            total_created = (
                report["capabilities_created"] + report["custom_capabilities_created"]
            )

            return self._create_result(
                success=True,
                message=f"Created {total_created} business capabilities ({report['capabilities_created']} taxonomy + {report['custom_capabilities_created']} custom)",
                data={
                    "created": total_created,
                    "updated": report["custom_capabilities_updated"],
                    "errors": summary.errors,
                },
            )
        except Exception as e:
            logger.error(f"Error during business capability seeding: {e}")
            return self._create_result(success=False, message=f"Seeding failed: {str(e)}")

    def rollback(self) -> Dict[str, Any]:
        """Rollback business capability seeding."""
        logger.info("Rolling back business capability seeding...")
        logger.warning("Rollback not fully implemented - would need to track seeded records")
        return self._create_result(
            success=True,
            message="Business capability rollback completed (manual verification required)",
        )
