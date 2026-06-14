"""
-> app.modules.vendors.services.discovery_service

Vendor Data Population Service - LLM-PRD - 02 Implementation

Comprehensive vendor data population service with:
- 150+ vendors with complete market intelligence
- 500+ products with capability coverage
- Gartner Magic Quadrant positioning
- G2 ratings and market share data
- Pricing models and deployment options
- Industry-specific capability mapping

Key Features:
- Bulk vendor and product creation
- Capability coverage matrix population
- Market intelligence integration
- Pricing model management
- Industry focus mapping
- Real-time progress tracking
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
    VendorProductPricing,
)

logger = logging.getLogger(__name__)


@dataclass
class PopulationStats:
    """Statistics for vendor data population."""

    vendors_created: int = 0
    vendors_updated: int = 0
    products_created: int = 0
    products_updated: int = 0
    capabilities_mapped: int = 0
    pricing_models_created: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class VendorDataPopulationService:
    """
    Comprehensive vendor data population service for loading
    and managing vendor data with market intelligence.
    """

    def __init__(self):
        """Initialize the vendor data population service."""
        self.logger = logging.getLogger(__name__)
        self.stats = PopulationStats()

        # Load comprehensive vendor dataset
        try:
            from scripts.vendor_seeds.comprehensive_vendor_dataset import get_vendor_data

            self.vendor_data = get_vendor_data()
            self.logger.info(
                f"Loaded vendor dataset: {self.vendor_data['metadata']['total_vendors']} vendors"
            )
        except Exception as e:
            self.logger.error(f"Failed to load vendor dataset: {e}")
            self.vendor_data = None

    def populate_all_vendors(self, force_update: bool = False) -> Dict[str, Any]:
        """
        Populate all vendors from the comprehensive dataset.

        Args:
            force_update: Whether to update existing vendors

        Returns:
            Population statistics and results
        """
        if not self.vendor_data:
            return {"error": "Vendor dataset not available"}

        self.logger.info("Starting comprehensive vendor data population")
        start_time = datetime.now()

        try:
            # Process each vendor
            for vendor_data in self.vendor_data["vendors"]:
                try:
                    self._populate_vendor(vendor_data, force_update)
                except Exception as e:
                    error_msg = (
                        f"Failed to populate vendor {vendor_data.get('name', 'Unknown')}: {str(e)}"
                    )
                    self.logger.error(error_msg)
                    self.stats.errors.append(error_msg)

            # Commit all changes
            db.session.commit()

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            result = {
                "success": True,
                "stats": {
                    "vendors_created": self.stats.vendors_created,
                    "vendors_updated": self.stats.vendors_updated,
                    "products_created": self.stats.products_created,
                    "products_updated": self.stats.products_updated,
                    "capabilities_mapped": self.stats.capabilities_mapped,
                    "pricing_models_created": self.stats.pricing_models_created,
                    "errors_count": len(self.stats.errors),
                    "processing_time_seconds": round(processing_time, 2),
                },
                "dataset_metadata": self.vendor_data["metadata"],
                "errors": self.stats.errors[:10],  # Limit to first 10 errors
            }

            self.logger.info(f"Vendor population completed: {result['stats']}")
            return result

        except Exception as e:
            db.session.rollback()
            error_msg = f"Vendor population failed: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "stats": self.stats.__dict__}

    def _populate_vendor(self, vendor_data: Dict[str, Any], force_update: bool = False):
        """Populate a single vendor and its products."""
        vendor_name = vendor_data["name"]

        # Check if vendor exists
        existing_vendor = VendorOrganization.query.filter_by(name=vendor_name).first()

        if existing_vendor and not force_update:
            self.logger.debug(f"Vendor {vendor_name} already exists, skipping")
            return

        # Create or update vendor
        if existing_vendor:
            vendor = existing_vendor
            self.stats.vendors_updated += 1
        else:
            vendor = VendorOrganization(name=vendor_name)
            db.session.add(vendor)
            db.session.flush()  # Get ID
            self.stats.vendors_created += 1

        # Populate vendor fields
        self._populate_vendor_fields(vendor, vendor_data)

        # Populate products
        for product_data in vendor_data.get("products", []):
            self._populate_product(vendor, product_data, force_update)

    def _populate_vendor_fields(self, vendor: VendorOrganization, vendor_data: Dict[str, Any]):
        """Populate vendor organization fields."""
        # Basic information
        vendor.website = vendor_data.get("website")
        vendor.headquarters = vendor_data.get("headquarters")
        vendor.year_founded = vendor_data.get("year_founded")
        vendor.employees = vendor_data.get("employees")
        vendor.revenue = vendor_data.get("revenue")
        vendor.category = vendor_data.get("category")
        vendor.description = vendor_data.get("description")

        # Strategic information
        vendor.strategic_tier = vendor_data.get("strategic_tier")
        vendor.partnership_level = vendor_data.get("partnership_level")
        vendor.industry_focus = vendor_data.get("industry_focus", [])

        # Market intelligence
        vendor.gartner_magic_quadrant = vendor_data.get("gartner_magic_quadrant")
        vendor.g2_rating = vendor_data.get("g2_rating")
        vendor.g2_reviews = vendor_data.get("g2_reviews")
        vendor.market_share = vendor_data.get("market_share")

        # Additional metadata
        vendor.data_source = vendor_data.get("data_source", "comprehensive_dataset")
        vendor.last_updated = datetime.utcnow()

    def _populate_product(
        self, vendor: VendorOrganization, product_data: Dict[str, Any], force_update: bool = False
    ):
        """Populate a vendor product with capabilities and pricing."""
        product_name = product_data["name"]

        # Check if product exists
        existing_product = VendorProduct.query.filter_by(
            vendor_organization_id=vendor.id, name=product_name
        ).first()

        if existing_product and not force_update:
            self.logger.debug(f"Product {product_name} already exists, skipping")
            return

        # Create or update product
        if existing_product:
            product = existing_product
            self.stats.products_updated += 1
        else:
            product = VendorProduct(vendor_organization_id=vendor.id, name=product_name)
            db.session.add(product)
            db.session.flush()  # Get ID
            self.stats.products_created += 1

        # Populate product fields
        self._populate_product_fields(product, product_data)

        # Populate capabilities
        for capability_data in product_data.get("capabilities", []):
            self._populate_product_capability(product, capability_data)

        # Populate pricing
        for pricing_data in product_data.get("pricing", {}).get("tiers", []):
            self._populate_product_pricing(product, pricing_data)

    def _populate_product_fields(self, product: VendorProduct, product_data: Dict[str, Any]):
        """Populate product fields."""
        # Basic information
        product.description = product_data.get("description")
        product.product_type = product_data.get("product_type", "software")
        product.product_lifecycle = product_data.get("product_lifecycle", "mature")
        product.deployment_models = product_data.get("deployment_models", [])
        product.target_industries = product_data.get("target_industries", [])

        # Technical specifications
        product.programming_languages = product_data.get("programming_languages", [])
        product.frameworks = product_data.get("frameworks", [])
        product.databases = product_data.get("databases", [])
        product.cloud_platforms = product_data.get("cloud_platforms", [])

        # Market information
        product.g2_rating = product_data.get("g2_rating")
        product.g2_reviews = product_data.get("g2_reviews")
        product.market_position = product_data.get("market_position")

        # Additional metadata
        product.data_source = product_data.get("data_source", "comprehensive_dataset")
        product.last_updated = datetime.utcnow()

    def _populate_product_capability(self, product: VendorProduct, capability_data: Dict[str, Any]):
        """Populate product capability mapping."""
        capability_id = capability_data.get("capability_id")

        if not capability_id:
            self.logger.warning(f"Missing capability_id for product {product.name}")
            return

        # Check if capability exists
        capability = BusinessCapability.query.get(capability_id)
        if not capability:
            self.logger.warning(f"Capability {capability_id} not found for product {product.name}")
            return

        # Check if mapping exists
        existing_mapping = VendorProductCapability.query.filter_by(
            vendor_product_id=product.id, business_capability_id=capability_id
        ).first()

        if existing_mapping:
            # Update existing mapping
            mapping = existing_mapping
        else:
            # Create new mapping
            mapping = VendorProductCapability(
                vendor_product_id=product.id, business_capability_id=capability_id
            )
            db.session.add(mapping)
            self.stats.capabilities_mapped += 1

        # Populate mapping fields
        mapping.coverage_percentage = capability_data.get("coverage", 0)
        mapping.maturity_level = capability_data.get("maturity", 1)
        mapping.gaps = capability_data.get("gaps", [])
        mapping.strengths = capability_data.get("strengths", [])
        mapping.implementation_complexity = capability_data.get(
            "implementation_complexity", "medium"
        )
        mapping.quality_rating = capability_data.get("quality_rating", 4.0)
        mapping.last_assessed = datetime.utcnow()

    def _populate_product_pricing(self, product: VendorProduct, pricing_data: Dict[str, Any]):
        """Populate product pricing model."""
        tier_name = pricing_data.get("name")

        if not tier_name:
            self.logger.warning(f"Missing pricing tier name for product {product.name}")
            return

        # Check if pricing exists
        existing_pricing = VendorProductPricing.query.filter_by(
            vendor_product_id=product.id, tier_name=tier_name
        ).first()

        if existing_pricing:
            # Update existing pricing
            pricing = existing_pricing
        else:
            # Create new pricing
            pricing = VendorProductPricing(vendor_product_id=product.id, tier_name=tier_name)
            db.session.add(pricing)
            self.stats.pricing_models_created += 1

        # Populate pricing fields
        pricing.per_user_pricing = pricing_data.get("per_user")
        pricing.min_users = pricing_data.get("min_users")
        pricing.max_users = pricing_data.get("max_users")
        pricing.billing_cycle = pricing_data.get("billing", "annual")
        pricing.setup_fee = pricing_data.get("setup_fee")
        pricing.features = pricing_data.get("features", [])
        pricing.support_level = pricing_data.get("support_level", "standard")
        pricing.sla_guarantee = pricing_data.get("sla_guarantee")
        pricing.currency = pricing_data.get("currency", "USD")
        pricing.last_updated = datetime.utcnow()

    def get_population_status(self) -> Dict[str, Any]:
        """Get current vendor data population status."""
        try:
            # Count vendors and products
            vendor_count = VendorOrganization.query.count()
            product_count = VendorProduct.query.count()
            capability_mapping_count = VendorProductCapability.query.count()
            pricing_count = VendorProductPricing.query.count()

            # Count by category
            vendor_categories = (
                db.session.query(VendorOrganization.category, func.count(VendorOrganization.id))
                .group_by(VendorOrganization.category)
                .all()
            )

            # Get dataset info
            dataset_info = {}
            if self.vendor_data:
                dataset_info = {
                    "total_vendors_in_dataset": self.vendor_data["metadata"]["total_vendors"],
                    "total_products_in_dataset": self.vendor_data["metadata"]["total_products"],
                    "categories_in_dataset": self.vendor_data["metadata"]["categories"],
                    "last_updated": self.vendor_data["metadata"]["last_updated"],
                }

            # Calculate coverage percentages
            vendor_coverage = (vendor_count / dataset_info.get("total_vendors_in_dataset", 1)) * 100
            product_coverage = (
                product_count / dataset_info.get("total_products_in_dataset", 1)
            ) * 100

            return {
                "database_status": {
                    "vendors_in_db": vendor_count,
                    "products_in_db": product_count,
                    "capability_mappings": capability_mapping_count,
                    "pricing_models": pricing_count,
                },
                "dataset_info": dataset_info,
                "coverage_percentages": {
                    "vendor_coverage": round(vendor_coverage, 2),
                    "product_coverage": round(product_coverage, 2),
                },
                "vendor_categories": dict(vendor_categories),
                "last_population_check": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get population status: {e}")
            return {"error": str(e)}

    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate the integrity of populated vendor data."""
        validation_results = {
            "total_issues": 0,
            "issues": [],
            "warnings": [],
            "validation_time": datetime.utcnow().isoformat(),
        }

        try:
            # Check for vendors without products
            vendors_without_products = (
                db.session.query(VendorOrganization)
                .filter(~VendorOrganization.products.any())
                .count()
            )

            if vendors_without_products > 0:
                validation_results["issues"].append(
                    {
                        "type": "missing_products",
                        "count": vendors_without_products,
                        "message": f"{vendors_without_products} vendors have no products",
                    }
                )
                validation_results["total_issues"] += vendors_without_products

            # Check for products without capabilities
            products_without_capabilities = (
                db.session.query(VendorProduct).filter(~VendorProduct.capabilities.any()).count()
            )

            if products_without_capabilities > 0:
                validation_results["issues"].append(
                    {
                        "type": "missing_capabilities",
                        "count": products_without_capabilities,
                        "message": f"{products_without_capabilities} products have no capability mappings",
                    }
                )
                validation_results["total_issues"] += products_without_capabilities

            # Check for products without pricing
            products_without_pricing = (
                db.session.query(VendorProduct).filter(~VendorProduct.pricing_models.any()).count()
            )

            if products_without_pricing > 0:
                validation_results["warnings"].append(
                    {
                        "type": "missing_pricing",
                        "count": products_without_pricing,
                        "message": f"{products_without_pricing} products have no pricing models",
                    }
                )

            # Check for invalid capability coverage values
            invalid_coverage = (
                db.session.query(VendorProductCapability)
                .filter(
                    or_(
                        VendorProductCapability.coverage_percentage < 0,
                        VendorProductCapability.coverage_percentage > 100,
                    )
                )
                .count()
            )

            if invalid_coverage > 0:
                validation_results["issues"].append(
                    {
                        "type": "invalid_coverage",
                        "count": invalid_coverage,
                        "message": f"{invalid_coverage} capability mappings have invalid coverage values",
                    }
                )
                validation_results["total_issues"] += invalid_coverage

            # Check for duplicate vendor names
            duplicate_vendors = (
                db.session.query(VendorOrganization.name, func.count(VendorOrganization.id))
                .group_by(VendorOrganization.name)
                .having(func.count(VendorOrganization.id) > 1)
                .count()
            )

            if duplicate_vendors > 0:
                validation_results["issues"].append(
                    {
                        "type": "duplicate_vendors",
                        "count": duplicate_vendors,
                        "message": f"{duplicate_vendors} vendor names have duplicates",
                    }
                )
                validation_results["total_issues"] += duplicate_vendors

            validation_results["status"] = (
                "passed" if validation_results["total_issues"] == 0 else "failed"
            )

        except Exception as e:
            validation_results["status"] = "error"
            validation_results["error"] = str(e)

        return validation_results

    def get_vendors_by_category(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get vendors filtered by category with detailed information."""
        try:
            query = VendorOrganization.query

            if category:
                query = query.filter(VendorOrganization.category == category)

            vendors = query.options(
                joinedload(VendorOrganization.products),
                joinedload(VendorOrganization.products, VendorProduct.capabilities),
            ).all()

            result = {"category": category, "vendors": [], "total_vendors": len(vendors)}

            for vendor in vendors:
                vendor_info = {
                    "id": vendor.id,
                    "name": vendor.name,
                    "website": vendor.website,
                    "category": vendor.category,
                    "strategic_tier": vendor.strategic_tier,
                    "gartner_magic_quadrant": vendor.gartner_magic_quadrant,
                    "g2_rating": vendor.g2_rating,
                    "market_share": vendor.market_share,
                    "products_count": len(vendor.products),
                    "products": [],
                }

                # Add product information
                for product in vendor.products:
                    product_info = {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "product_type": product.product_type,
                        "deployment_models": product.deployment_models,
                        "capabilities_count": len(product.capabilities),
                        "g2_rating": product.g2_rating,
                    }
                    vendor_info["products"].append(product_info)

                result["vendors"].append(vendor_info)

            return result

        except Exception as e:
            self.logger.error(f"Failed to get vendors by category: {e}")
            return {"error": str(e)}


# Global service instance
_vendor_population_service = None


def get_vendor_population_service() -> VendorDataPopulationService:
    """Get the global vendor population service instance."""
    global _vendor_population_service
    if _vendor_population_service is None:
        _vendor_population_service = VendorDataPopulationService()
    return _vendor_population_service
