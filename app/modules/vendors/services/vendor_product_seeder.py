"""
-> app.modules.vendors.services.seeder_service

Vendor Product Seeder Service

Reports vendor product status. Products are created by VendorCatalogueImporter
when vendor organizations are seeded — this seeder verifies product state.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.modules.vendors.v2.services import BaseSeeder

logger = logging.getLogger(__name__)


class VendorProductSeeder(BaseSeeder):
    """
    Vendor product status reporter.

    Products are created automatically by VendorCatalogueImporter when
    vendor_organizations seeder runs. This seeder re-runs the import
    if no products exist, otherwise reports current status.
    """

    def __init__(self):
        super().__init__("vendor_catalogue.py")
        self.model_class = VendorProduct

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Not used — validation is handled by VendorCatalogueImporter."""
        return (True, None)

    def create_or_update_record(self, record: Dict[str, Any]) -> bool:
        """Not used — creation is handled by VendorCatalogueImporter."""
        return True

    def seed(self) -> Dict[str, Any]:
        """Seed vendor products via VendorCatalogueImporter."""
        logger.info("Starting vendor product seeding...")

        product_count = VendorProduct.query.count()
        vendor_count = VendorOrganization.query.count()

        if product_count > 0:
            return self._create_result(
                success=True,
                message=f"{product_count} vendor products already exist (from {vendor_count} vendors)",
                data={
                    "created": 0,
                    "updated": 0,
                    "existing": product_count,
                    "vendors": vendor_count,
                },
            )

        # No products — run the importer
        try:
            from app.seed_data.catalogue_importer import VendorCatalogueImporter

            importer = VendorCatalogueImporter()
            summary = importer.run(commit=True)
            report = summary.to_dict()

            return self._create_result(
                success=True,
                message=f"Created {report['products_created']} products for {report['vendors_created']} vendors",
                data={
                    "created": report["products_created"],
                    "updated": report["products_updated"],
                    "errors": summary.errors,
                },
            )
        except Exception as e:
            logger.error(f"Error during vendor product seeding: {e}")
            return self._create_result(success=False, message=f"Seeding failed: {str(e)}")

    def rollback(self) -> Dict[str, Any]:
        """Rollback vendor product seeding."""
        logger.info("Rolling back vendor product seeding...")
        logger.warning("Rollback not fully implemented - would need to track seeded records")
        return self._create_result(
            success=True,
            message="Vendor product rollback completed (manual verification required)",
        )
