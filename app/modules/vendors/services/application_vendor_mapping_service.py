"""
-> app.modules.vendors.services.integration_service

Application Vendor Product Mapping Service

Service for managing ApplicationComponent to VendorProduct mappings.
Implements Option B+ - direct FK for primary vendor product plus M:M junction table.

Features:
- Auto-match applications to vendor products based on vendor_name
- Bulk populate mappings for existing applications
- Manual mapping management
- Fuzzy matching for vendor names
"""

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.relationship_tables import application_component_vendor_products
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct


class ApplicationVendorMappingService:
    """Service for mapping applications to vendor products."""

    # Common vendor name variations for fuzzy matching
    VENDOR_NAME_ALIASES = {
        "sap": ["sap", "sap se", "sap ag", "sap america"],
        "oracle": ["oracle", "oracle corporation", "oracle corp"],
        "microsoft": ["microsoft", "microsoft corporation", "ms", "msft"],
        "salesforce": ["salesforce", "salesforce.com", "sfdc"],
        "servicenow": ["servicenow", "service now", "service-now"],
        "workday": ["workday", "workday inc"],
        "ibm": ["ibm", "international business machines"],
        "aws": ["aws", "amazon web services", "amazon"],
        "google": ["google", "google cloud", "gcp", "alphabet"],
        "adobe": ["adobe", "adobe systems", "adobe inc"],
    }

    def __init__(self):
        self._vendor_cache = None
        self._product_cache = None

    def _build_vendor_cache(self) -> Dict[str, VendorOrganization]:
        """Build a cache of vendor names to VendorOrganization objects."""
        if self._vendor_cache is not None:
            return self._vendor_cache

        self._vendor_cache = {}
        vendors = VendorOrganization.query.all()

        for vendor in vendors:
            # Add exact name (lowercase)
            self._vendor_cache[vendor.name.lower()] = vendor

            # Add display name if different
            if vendor.display_name:
                self._vendor_cache[vendor.display_name.lower()] = vendor

            # Add aliases
            for base_name, aliases in self.VENDOR_NAME_ALIASES.items():
                if base_name in vendor.name.lower():
                    for alias in aliases:
                        self._vendor_cache[alias] = vendor

        return self._vendor_cache

    def _build_product_cache(self) -> Dict[int, List[VendorProduct]]:
        """Build a cache of vendor_id to VendorProduct list."""
        if self._product_cache is not None:
            return self._product_cache

        self._product_cache = {}
        products = VendorProduct.query.all()

        for product in products:
            if product.vendor_organization_id not in self._product_cache:
                self._product_cache[product.vendor_organization_id] = []
            self._product_cache[product.vendor_organization_id].append(product)

        return self._product_cache

    def find_vendor_by_name(self, vendor_name: str) -> Optional[VendorOrganization]:
        """
        Find a VendorOrganization by name using fuzzy matching.

        Args:
            vendor_name: The vendor name to search for

        Returns:
            VendorOrganization if found, None otherwise
        """
        if not vendor_name:
            return None

        cache = self._build_vendor_cache()
        normalized = vendor_name.lower().strip()

        # Exact match
        if normalized in cache:
            return cache[normalized]

        # Fuzzy match - find best match with similarity > 0.8
        best_match = None
        best_score = 0.0

        for cached_name, vendor in cache.items():
            score = SequenceMatcher(None, normalized, cached_name).ratio()
            if score > best_score and score > 0.8:
                best_score = score
                best_match = vendor

        return best_match

    def find_products_for_vendor(self, vendor: VendorOrganization) -> List[VendorProduct]:
        """Get all products for a vendor."""
        cache = self._build_product_cache()
        return cache.get(vendor.id, [])

    def find_best_product_match(
        self, vendor: VendorOrganization, app_name: str, app_category: Optional[str] = None
    ) -> Optional[VendorProduct]:
        """
        Find the best matching product for an application.

        Uses application name and category to find the most relevant product.

        Args:
            vendor: The VendorOrganization to search within
            app_name: The application name
            app_category: Optional application category (erp, crm, hcm, etc.)

        Returns:
            Best matching VendorProduct or None
        """
        products = self.find_products_for_vendor(vendor)
        if not products:
            return None

        if len(products) == 1:
            return products[0]

        # Score each product
        scored_products = []
        app_name_lower = app_name.lower()

        for product in products:
            score = 0.0

            # Name similarity
            name_sim = SequenceMatcher(None, app_name_lower, product.name.lower()).ratio()
            score += name_sim * 50

            # Category match
            if app_category and product.product_family:
                if app_category.lower() in (product.product_family.family_name or "").lower():
                    score += 30
                elif (product.product_family.family_name or "").lower() in app_category.lower():
                    score += 20

            # Product code in app name
            if product.product_code and product.product_code.lower() in app_name_lower:
                score += 25

            # Keywords in app name
            product_keywords = re.findall(r"\w+", product.name.lower())
            for keyword in product_keywords:
                if len(keyword) > 3 and keyword in app_name_lower:
                    score += 10

            scored_products.append((product, score))

        # Return best match if score is reasonable
        scored_products.sort(key=lambda x: x[1], reverse=True)
        if scored_products and scored_products[0][1] > 20:
            return scored_products[0][0]

        # Default to first product if no good match
        return products[0]

    def map_application_to_vendor_product(
        self,
        application: ApplicationComponent,
        vendor_product: VendorProduct,
        is_primary: bool = True,
        relationship_type: str = "uses",
        deployment_type: Optional[str] = "production",
        criticality: Optional[str] = None,
        usage_percentage: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Map an application to a vendor product.

        Args:
            application: The ApplicationComponent to map
            vendor_product: The VendorProduct to map to
            is_primary: If True, also set as primary vendor product
            relationship_type: Type of relationship ('primary', 'integration', 'data_source', 'reporting', 'uses')
            deployment_type: Deployment type ('production', 'staging', 'development', 'disaster_recovery')
            criticality: Criticality level ('mission_critical', 'business_critical', 'important', 'supporting')
            usage_percentage: How much of the product's capabilities are used (0 - 100)
            notes: Optional notes

        Returns:
            True if successful, False otherwise
        """
        try:
            # Set primary vendor product if requested
            if is_primary:
                application.vendor_product_id = vendor_product.id
                # Also update vendor_name for consistency
                if vendor_product.vendor_organization:
                    application.vendor_name = vendor_product.vendor_organization.name

            # Add to M:M junction table if not already present
            existing = db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                db.select(application_component_vendor_products).where(
                    application_component_vendor_products.c.application_component_id
                    == application.id,
                    application_component_vendor_products.c.vendor_product_id == vendor_product.id,
                )
            ).first()

            if not existing:
                db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                    application_component_vendor_products.insert().values(
                        application_component_id=application.id,
                        vendor_product_id=vendor_product.id,
                        relationship_type=relationship_type,
                        deployment_type=deployment_type,
                        criticality=criticality or application.criticality,
                        usage_percentage=usage_percentage,
                        implementation_date=application.implementation_date,
                        notes=notes,
                        created_at=datetime.utcnow(),
                    )
                )

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            print(
                f"Error mapping application {application.name} to vendor product {vendor_product.name}: {e}"
            )
            return False

    def auto_map_application(self, application: ApplicationComponent) -> Tuple[bool, Optional[str]]:
        """
        Automatically map an application to a vendor product based on vendor_name.

        Args:
            application: The ApplicationComponent to map

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not application.vendor_name:
            return False, "No vendor_name set on application"

        # Skip if already mapped
        if application.vendor_product_id:
            return True, f"Already mapped to vendor product {application.vendor_product_id}"

        # Find vendor
        vendor = self.find_vendor_by_name(application.vendor_name)
        if not vendor:
            return False, f"No vendor found matching '{application.vendor_name}'"

        # Find best product match
        product = self.find_best_product_match(
            vendor, application.name, application.application_category
        )

        if not product:
            return False, f"Vendor '{vendor.name}' has no products"

        # Create mapping
        success = self.map_application_to_vendor_product(
            application, product, is_primary=True, relationship_type="primary"
        )

        if success:
            return True, f"Mapped to {vendor.name} - {product.name}"
        else:
            return False, "Failed to create mapping"

    def bulk_auto_map_applications(self, limit: Optional[int] = None) -> Dict:
        """
        Bulk auto-map all unmapped applications to vendor products.

        Args:
            limit: Optional limit on number of applications to process

        Returns:
            Dict with statistics: {
                'total_processed': int,
                'mapped': int,
                'skipped': int,
                'failed': int,
                'details': List[dict]
            }
        """
        # Clear caches to ensure fresh data
        self._vendor_cache = None
        self._product_cache = None

        # Get unmapped applications with vendor_name set
        query = ApplicationComponent.query.filter(
            ApplicationComponent.vendor_name.isnot(None),
            ApplicationComponent.vendor_name != "",
            ApplicationComponent.vendor_product_id.is_(None),
        )

        if limit:
            query = query.limit(limit)

        applications = query.all()

        results = {
            "total_processed": len(applications),
            "mapped": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for app in applications:
            success, message = self.auto_map_application(app)

            detail = {
                "application_id": app.id,
                "application_name": app.name,
                "vendor_name": app.vendor_name,
                "success": success,
                "message": message,
            }
            results["details"].append(detail)

            if success:
                if "Already mapped" in message:
                    results["skipped"] += 1
                else:
                    results["mapped"] += 1
            else:
                results["failed"] += 1

        return results

    def get_unmapped_applications(self) -> List[ApplicationComponent]:
        """Get all applications that have vendor_name but no vendor_product_id."""
        return ApplicationComponent.query.filter(
            ApplicationComponent.vendor_name.isnot(None),
            ApplicationComponent.vendor_name != "",
            ApplicationComponent.vendor_product_id.is_(None),
        ).all()

    def get_application_vendor_products(self, application_id: int) -> List[Dict]:
        """
        Get all vendor products for an application.

        Returns list of dicts with vendor product info and relationship metadata.
        """
        results = db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id)
            db.select(
                VendorProduct,
                application_component_vendor_products.c.relationship_type,
                application_component_vendor_products.c.deployment_type,
                application_component_vendor_products.c.criticality,
                application_component_vendor_products.c.usage_percentage,
                application_component_vendor_products.c.notes,
            )
            .select_from(application_component_vendor_products)
            .join(
                VendorProduct,
                VendorProduct.id == application_component_vendor_products.c.vendor_product_id,
            )
            .where(
                application_component_vendor_products.c.application_component_id == application_id
            )
        ).all()

        return [
            {
                "vendor_product": {
                    "id": row[0].id,
                    "name": row[0].name,
                    "vendor_name": row[0].vendor_organization.name
                    if row[0].vendor_organization
                    else None,
                    "product_family": row[0].product_family.family_name
                    if row[0].product_family
                    else None,
                    "deployment_model": row[0].deployment_model,
                },
                "relationship_type": row[1],
                "deployment_type": row[2],
                "criticality": row[3],
                "usage_percentage": row[4],
                "notes": row[5],
            }
            for row in results
        ]

    def get_vendor_product_applications(self, vendor_product_id: int) -> List[Dict]:
        """
        Get all applications using a vendor product.

        Returns list of dicts with application info and relationship metadata.
        """
        results = db.session.execute(  # tenant-filtered: scoped via parent FK (vendor_product_id)
            db.select(
                ApplicationComponent,
                application_component_vendor_products.c.relationship_type,
                application_component_vendor_products.c.deployment_type,
                application_component_vendor_products.c.criticality,
                application_component_vendor_products.c.usage_percentage,
            )
            .select_from(application_component_vendor_products)
            .join(
                ApplicationComponent,
                ApplicationComponent.id
                == application_component_vendor_products.c.application_component_id,
            )
            .where(application_component_vendor_products.c.vendor_product_id == vendor_product_id)
        ).all()

        return [
            {
                "application": {
                    "id": row[0].id,
                    "name": row[0].name,
                    "application_code": row[0].application_code,
                    "application_category": row[0].application_category,
                    "lifecycle_status": row[0].lifecycle_status,
                },
                "relationship_type": row[1],
                "deployment_type": row[2],
                "criticality": row[3],
                "usage_percentage": row[4],
            }
            for row in results
        ]

    def remove_application_vendor_mapping(
        self, application_id: int, vendor_product_id: int, remove_primary: bool = False
    ) -> bool:
        """
        Remove a vendor product mapping from an application.

        Args:
            application_id: The application ID
            vendor_product_id: The vendor product ID
            remove_primary: If True, also remove as primary vendor product

        Returns:
            True if successful
        """
        try:
            # Remove from junction table
            db.session.execute(  # tenant-filtered: scoped via parent FK (application_component_id, vendor_product_id)
                application_component_vendor_products.delete().where(
                    application_component_vendor_products.c.application_component_id
                    == application_id,
                    application_component_vendor_products.c.vendor_product_id == vendor_product_id,
                )
            )

            # Remove as primary if requested
            if remove_primary:
                app = ApplicationComponent.query.get(application_id)
                if app and app.vendor_product_id == vendor_product_id:
                    app.vendor_product_id = None

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Error removing mapping: {e}")
            return False


# Singleton instance
_service_instance = None


def get_application_vendor_mapping_service() -> ApplicationVendorMappingService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ApplicationVendorMappingService()
    return _service_instance
