"""
Unified Seed Data Orchestrator

Orchestrates the seeding of all curated seed data in the correct dependency order.
Implements comprehensive seeding with rollback capabilities and progress tracking.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.services.business_capability_seeder import BusinessCapabilitySeeder
from app.services.technical_capability_seeder import TechnicalCapabilitySeeder
from app.services.vendor_organization_seeder import VendorOrganizationSeeder
from app.services.vendor_product_seeder import VendorProductSeeder

logger = logging.getLogger(__name__)


class UnifiedSeedOrchestrator:
    """
    Orchestrates comprehensive seed data operations.

    Handles:
    - Dependency-aware seeding order
    - Progress tracking and error handling
    - Rollback capabilities
    - Comprehensive reporting
    """

    def __init__(self):
        self.seeders = {
            "vendor_organizations": VendorOrganizationSeeder(),
            "business_capabilities": BusinessCapabilitySeeder(),
            "technical_capabilities": TechnicalCapabilitySeeder(),
            "vendor_products": VendorProductSeeder(),  # Depends on vendor_organizations
        }

        # Define seeding order based on dependencies
        self.seeding_order = [
            "vendor_organizations",  # No dependencies
            "business_capabilities",  # No dependencies
            "technical_capabilities",  # No dependencies
            "vendor_products",  # Depends on vendor_organizations
        ]

    def seed_all(self, skip_errors: bool = False) -> Dict[str, Any]:
        """
        Execute all seeders in dependency order.

        Args:
            skip_errors: Continue with remaining seeders if one fails
        """
        logger.info("Starting unified seed data orchestration...")

        start_time = datetime.utcnow()
        results = {}
        overall_success = True

        for seeder_name in self.seeding_order:
            logger.info(f"Executing seeder: {seeder_name}")

            try:
                seeder = self.seeders[seeder_name]
                result = seeder.seed()

                results[seeder_name] = result

                if not result.get("success", False):
                    overall_success = False
                    if not skip_errors:
                        logger.error(f"Seeder {seeder_name} failed, stopping orchestration")
                        break
                    else:
                        logger.warning(f"Seeder {seeder_name} failed, continuing with others")

            except Exception as e:
                logger.error(f"Unexpected error in seeder {seeder_name}: {e}")
                results[seeder_name] = {
                    "success": False,
                    "message": f"Unexpected error: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }

                overall_success = False
                if not skip_errors:
                    break

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Compile summary
        summary = self._compile_summary(results, duration)

        if overall_success:
            logger.info("Unified seed orchestration completed successfully")
        else:
            logger.error("Unified seed orchestration completed with errors")

        return {
            "success": overall_success,
            "message": "Unified seed orchestration completed"
            if overall_success
            else "Unified seed orchestration completed with errors",
            "data": {
                "results": results,
                "summary": summary,
                "duration_seconds": duration,
                "timestamp": end_time.isoformat(),
            },
        }

    def rollback_all(self) -> Dict[str, Any]:
        """Rollback all seeders in reverse dependency order."""
        logger.info("Starting unified seed rollback...")

        # Reverse the seeding order for rollback
        rollback_order = list(reversed(self.seeding_order))

        start_time = datetime.utcnow()
        results = {}
        overall_success = True

        for seeder_name in rollback_order:
            logger.info(f"Rolling back seeder: {seeder_name}")

            try:
                seeder = self.seeders[seeder_name]
                result = seeder.rollback()

                results[seeder_name] = result

                if not result.get("success", False):
                    overall_success = False
                    logger.warning(f"Rollback failed for {seeder_name}, continuing with others")

            except Exception as e:
                logger.error(f"Unexpected error in rollback for {seeder_name}: {e}")
                results[seeder_name] = {
                    "success": False,
                    "message": f"Unexpected error: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                overall_success = False

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        if overall_success:
            logger.info("Unified seed rollback completed successfully")
        else:
            logger.warning("Unified seed rollback completed with some errors")

        return {
            "success": overall_success,
            "message": "Unified seed rollback completed"
            if overall_success
            else "Unified seed rollback completed with errors",
            "data": {
                "results": results,
                "duration_seconds": duration,
                "timestamp": end_time.isoformat(),
            },
        }

    def seed_specific(self, seeder_names: List[str]) -> Dict[str, Any]:
        """Seed only specific seeders."""
        logger.info(f"Starting specific seed orchestration for: {seeder_names}")

        results = {}
        overall_success = True

        for seeder_name in seeder_names:
            if seeder_name not in self.seeders:
                logger.error(f"Unknown seeder: {seeder_name}")
                results[seeder_name] = {
                    "success": False,
                    "message": f"Unknown seeder: {seeder_name}",
                }
                overall_success = False
                continue

            try:
                seeder = self.seeders[seeder_name]
                result = seeder.seed()
                results[seeder_name] = result

                if not result.get("success", False):
                    overall_success = False

            except Exception as e:
                logger.error(f"Error in seeder {seeder_name}: {e}")
                results[seeder_name] = {"success": False, "message": f"Error: {str(e)}"}
                overall_success = False

        return {
            "success": overall_success,
            "message": "Specific seed orchestration completed",
            "data": {"results": results, "timestamp": datetime.utcnow().isoformat()},
        }

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of all seeders."""
        status = {}

        for seeder_name, seeder in self.seeders.items():
            try:
                # This would typically check if the seeder has been run
                # For now, we'll just return basic info
                status[seeder_name] = {
                    "available": True,
                    "model_class": seeder.model_class.__name__
                    if hasattr(seeder, "model_class")
                    else "Unknown",
                }
            except Exception as e:
                status[seeder_name] = {"available": False, "error": str(e)}

        return {
            "success": True,
            "message": "Seeder status retrieved",
            "data": {
                "seeders": status,
                "seeding_order": self.seeding_order,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def _compile_summary(self, results: Dict[str, Any], duration: float) -> Dict[str, Any]:
        """Compile a summary of seeding results."""
        total_created = 0
        total_updated = 0
        total_failed = 0
        successful_seeders = []

        for seeder_name, result in results.items():
            if result.get("success", False):
                successful_seeders.append(seeder_name)
                data = result.get("data", {})
                total_created += data.get("created", 0)
                total_updated += data.get("updated", 0)
            else:
                total_failed += 1

        return {
            "total_seeders": len(self.seeders),
            "successful_seeders": len(successful_seeders),
            "failed_seeders": total_failed,
            "total_records_created": total_created,
            "total_records_updated": total_updated,
            "duration_seconds": duration,
            "successful_seeder_names": successful_seeders,
        }
