"""
Data Enrichment Service

Integrates API pipeline with seeding system to enrich vendor and product data.
Provides automated data enhancement using external intelligence sources.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.services.api_clients.pipeline_orchestrator import APIPipelineOrchestrator

logger = logging.getLogger(__name__)


class DataEnrichmentService:
    """
    Service for enriching seed data with external intelligence.

    Provides automated enhancement of vendor and product data using:
    - G2 Crowd ratings and reviews
    - Crunchbase company intelligence
    - GitHub technical analysis
    """

    def __init__(self):
        """Initialize the data enrichment service."""
        self.pipeline_orchestrator = APIPipelineOrchestrator()

    def enrich_vendor_organization(self, vendor_org: VendorOrganization) -> Dict[str, Any]:
        """
        Enrich a vendor organization with external data.

        Args:
            vendor_org: VendorOrganization model instance

        Returns:
            Dict with enrichment results
        """
        logger.info(f"Enriching vendor organization: {vendor_org.name}")

        enrichment_result = {
            "vendor_id": vendor_org.id,
            "vendor_name": vendor_org.name,
            "enrichment_timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "data_sources": {},
            "updates_applied": [],
        }

        try:
            # Get enriched data from API pipeline
            api_result = self.pipeline_orchestrator.enrich_vendor_data(vendor_org.name)

            if not api_result["success"]:
                enrichment_result["error"] = "API enrichment failed"
                return enrichment_result

            enrichment_result["data_sources"] = api_result["data_sources"]
            enrichment_result["success"] = True

            # Apply updates to the vendor organization
            updates = self._apply_vendor_enrichment(vendor_org, api_result["aggregated_insights"])
            enrichment_result["updates_applied"] = updates

            logger.info(
                f"Successfully enriched vendor {vendor_org.name} with {len(updates)} updates"
            )

        except Exception as e:
            logger.error(f"Error enriching vendor {vendor_org.name}: {e}")
            enrichment_result["error"] = str(e)

        return enrichment_result

    def enrich_vendor_product(self, vendor_product: VendorProduct) -> Dict[str, Any]:
        """
        Enrich a vendor product with external data.

        Args:
            vendor_product: VendorProduct model instance

        Returns:
            Dict with enrichment results
        """
        logger.info(f"Enriching vendor product: {vendor_product.name}")

        enrichment_result = {
            "product_id": vendor_product.id,
            "product_name": vendor_product.name,
            "vendor_name": vendor_product.vendor_organization.name
            if vendor_product.vendor_organization
            else None,
            "enrichment_timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "data_sources": {},
            "updates_applied": [],
        }

        try:
            # Get enriched data from API pipeline
            vendor_name = (
                vendor_product.vendor_organization.name
                if vendor_product.vendor_organization
                else None
            )
            api_result = self.pipeline_orchestrator.enrich_product_data(
                vendor_product.name, vendor_name
            )

            if not api_result["success"]:
                enrichment_result["error"] = "API enrichment failed"
                return enrichment_result

            enrichment_result["data_sources"] = api_result["data_sources"]
            enrichment_result["success"] = True

            # Apply updates to the vendor product
            updates = self._apply_product_enrichment(
                vendor_product, api_result["aggregated_insights"]
            )
            enrichment_result["updates_applied"] = updates

            logger.info(
                f"Successfully enriched product {vendor_product.name} with {len(updates)} updates"
            )

        except Exception as e:
            logger.error(f"Error enriching product {vendor_product.name}: {e}")
            enrichment_result["error"] = str(e)

        return enrichment_result

    def enrich_all_vendors(self, skip_errors: bool = True) -> Dict[str, Any]:
        """
        Enrich all vendor organizations in the database.

        Args:
            skip_errors: Continue processing even if individual enrichments fail

        Returns:
            Dict with batch enrichment results
        """
        logger.info("Starting batch vendor enrichment")

        vendors = VendorOrganization.query.all()
        results = []
        successful = 0
        failed = 0

        for vendor in vendors:
            try:
                result = self.enrich_vendor_organization(vendor)
                results.append(result)

                if result["success"]:
                    successful += 1
                else:
                    failed += 1

                if not skip_errors and not result["success"]:
                    break

            except Exception as e:
                logger.error(f"Failed to enrich vendor {vendor.name}: {e}")
                failed += 1
                if not skip_errors:
                    break

                results.append(
                    {
                        "vendor_id": vendor.id,
                        "vendor_name": vendor.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        batch_result = {
            "total_vendors": len(vendors),
            "successful_enrichments": successful,
            "failed_enrichments": failed,
            "results": results,
            "batch_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Batch vendor enrichment completed: {successful}/{len(vendors)} successful")
        return batch_result

    def enrich_all_products(self, skip_errors: bool = True) -> Dict[str, Any]:
        """
        Enrich all vendor products in the database.

        Args:
            skip_errors: Continue processing even if individual enrichments fail

        Returns:
            Dict with batch enrichment results
        """
        logger.info("Starting batch product enrichment")

        products = VendorProduct.query.all()
        results = []
        successful = 0
        failed = 0

        for product in products:
            try:
                result = self.enrich_vendor_product(product)
                results.append(result)

                if result["success"]:
                    successful += 1
                else:
                    failed += 1

                if not skip_errors and not result["success"]:
                    break

            except Exception as e:
                logger.error(f"Failed to enrich product {product.name}: {e}")
                failed += 1
                if not skip_errors:
                    break

                results.append(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        batch_result = {
            "total_products": len(products),
            "successful_enrichments": successful,
            "failed_enrichments": failed,
            "results": results,
            "batch_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Batch product enrichment completed: {successful}/{len(products)} successful")
        return batch_result

    def _apply_vendor_enrichment(
        self, vendor_org: VendorOrganization, insights: Dict[str, Any]
    ) -> List[str]:
        """
        Apply enrichment insights to vendor organization.

        Args:
            vendor_org: VendorOrganization instance
            insights: Aggregated insights from API sources

        Returns:
            List of applied updates
        """
        updates = []

        try:
            # Apply rating summary
            rating_data = insights.get("rating_summary", {})
            if rating_data and not vendor_org.g2_rating:
                vendor_org.g2_rating = rating_data.get("average_rating")
                updates.append("g2_rating")

            # Apply company profile data
            profile_data = insights.get("company_profile", {})
            if profile_data:
                if profile_data.get("founded_year") and not vendor_org.founded_year:
                    vendor_org.founded_year = profile_data["founded_year"]
                    updates.append("founded_year")

                if profile_data.get("headquarters") and not vendor_org.headquarters:
                    hq = profile_data["headquarters"]
                    vendor_org.headquarters = (
                        f"{hq.get('city', '')}, {hq.get('country', '')}".strip(", ")
                    )
                    updates.append("headquarters")

                if profile_data.get("funding_total") and not vendor_org.funding_total:
                    vendor_org.funding_total = profile_data["funding_total"]
                    updates.append("funding_total")

                if profile_data.get("employee_count") and not vendor_org.employee_count:
                    vendor_org.employee_count = profile_data["employee_count"]
                    updates.append("employee_count")

            # Apply market positioning
            positioning = insights.get("market_positioning", {})
            if positioning and not vendor_org.market_positioning:
                vendor_org.market_positioning = positioning.get("maturity_level", "Unknown")
                updates.append("market_positioning")

            # Update enrichment metadata
            vendor_org.last_enriched_at = datetime.utcnow()
            vendor_org.enrichment_sources = list(insights.keys()) if insights else []

            # Commit changes
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error applying vendor enrichment: {e}")
            raise

        return updates

    def _apply_product_enrichment(
        self, vendor_product: VendorProduct, insights: Dict[str, Any]
    ) -> List[str]:
        """
        Apply enrichment insights to vendor product.

        Args:
            vendor_product: VendorProduct instance
            insights: Aggregated insights from API sources

        Returns:
            List of applied updates
        """
        updates = []

        try:
            # Apply rating summary
            rating_data = insights.get("rating_summary", {})
            if rating_data and not vendor_product.g2_rating:
                vendor_product.g2_rating = rating_data.get("average_rating")
                updates.append("g2_rating")

            # Apply technical stack data
            tech_stack = insights.get("technical_stack", {})
            if tech_stack and not vendor_product.technical_stack:
                vendor_product.technical_stack = tech_stack.get("primary_language")
                updates.append("technical_stack")

            # Apply community metrics
            community = insights.get("community_metrics", {})
            if community:
                if community.get("stars") and not vendor_product.github_stars:
                    vendor_product.github_stars = community["stars"]
                    updates.append("github_stars")

                if community.get("forks") and not vendor_product.github_forks:
                    vendor_product.github_forks = community["forks"]
                    updates.append("github_forks")

            # Update enrichment metadata
            vendor_product.last_enriched_at = datetime.utcnow()
            vendor_product.enrichment_sources = list(insights.keys()) if insights else []

            # Commit changes
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error applying product enrichment: {e}")
            raise

        return updates

    def get_enrichment_status(self) -> Dict[str, Any]:
        """
        Get the current enrichment status of seeded data.

        Returns:
            Dict with enrichment statistics
        """
        try:
            # Vendor enrichment stats
            total_vendors = VendorOrganization.query.count()
            enriched_vendors = VendorOrganization.query.filter(
                VendorOrganization.last_enriched_at.isnot(None)
            ).count()

            # Product enrichment stats
            total_products = VendorProduct.query.count()
            enriched_products = VendorProduct.query.filter(
                VendorProduct.last_enriched_at.isnot(None)
            ).count()

            # Recent enrichments (last 24 hours)
            yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            recent_vendors = VendorOrganization.query.filter(
                VendorOrganization.last_enriched_at >= yesterday
            ).count()

            recent_products = VendorProduct.query.filter(
                VendorProduct.last_enriched_at >= yesterday
            ).count()

            return {
                "vendors": {
                    "total": total_vendors,
                    "enriched": enriched_vendors,
                    "enrichment_rate": enriched_vendors / total_vendors if total_vendors > 0 else 0,
                    "recently_enriched": recent_vendors,
                },
                "products": {
                    "total": total_products,
                    "enriched": enriched_products,
                    "enrichment_rate": enriched_products / total_products
                    if total_products > 0
                    else 0,
                    "recently_enriched": recent_products,
                },
                "api_health": self.pipeline_orchestrator.health_check(),
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
