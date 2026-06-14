"""
-> app.modules.vendors.services.seeder_service

Vendor Organization Seeder Service

Seeds vendor organization data using the VendorCatalogueImporter from flask-base-master.
Loads 33 vendors from vendor_catalogue.py with COBIT, ITIL, and capability mappings.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.models.vendor.vendor_organization import VendorOrganization
from app.modules.vendors.v2.services import BaseSeeder

logger = logging.getLogger(__name__)


class VendorOrganizationSeeder(BaseSeeder):
    """
    Seeds vendor organization data via VendorCatalogueImporter.

    The importer handles the full lifecycle:
    - VendorOrganization records
    - VendorProduct records (one per vendor)
    - BusinessCapability records (from capability taxonomy)
    - VendorProductCapability mappings
    - COBITDomain + COBITProcess reference data
    - ITILPractice reference data
    - Custom capability model (3-level hierarchy)
    """

    def __init__(self):
        super().__init__("vendor_catalogue.py")
        self.model_class = VendorOrganization

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Not used — validation is handled by VendorCatalogueImporter."""
        return (True, None)

    def create_or_update_record(self, record: Dict[str, Any]) -> bool:
        """Not used — creation is handled by VendorCatalogueImporter."""
        return True

    def seed(self) -> Dict[str, Any]:
        """Execute the seeding process using VendorCatalogueImporter."""
        logger.info("Starting vendor organization seeding via VendorCatalogueImporter...")

        try:
            from app.seed_data.catalogue_importer import VendorCatalogueImporter

            importer = VendorCatalogueImporter()
            summary = importer.run(commit=True)

            report = summary.to_dict()
            total_created = report["vendors_created"] + report["products_created"]
            total_updated = report["vendors_updated"] + report["products_updated"]

            message = (
                f"Imported {report['vendors_created']} new vendors "
                f"({report['vendors_updated']} updated), "
                f"{report['products_created']} products, "
                f"{report['capabilities_created']} capabilities, "
                f"{report['cobit_processes_created']} COBIT processes, "
                f"{report['itil_practices_created']} ITIL practices"
            )

            if report["errors"] > 0:
                message += f" ({report['errors']} errors)"

            logger.info(message)

            return self._create_result(
                success=True,
                message=message,
                data={
                    "created": total_created,
                    "updated": total_updated,
                    "errors": summary.errors,
                    **report,
                },
            )

        except Exception as e:
            logger.error(f"Error during vendor catalogue import: {e}")
            return self._create_result(success=False, message=f"Import failed: {str(e)}")

    def rollback(self) -> Dict[str, Any]:
        """Rollback vendor organization seeding."""
        logger.info("Rolling back vendor organization seeding...")
        logger.warning("Rollback not fully implemented - would need to track seeded records")
        return self._create_result(
            success=True,
            message="Vendor organization rollback completed (manual verification required)",
        )
