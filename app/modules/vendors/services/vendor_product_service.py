"""
-> app.modules.vendors.services.vendor_service

Vendor Product Catalog & Intelligent Matching Service

Provides three-level vendor hierarchy management and AI-powered vendor product matching
for enterprise architecture applications.

Features:
- Three-level vendor hierarchy (Organization → Product Family → Product)
- AI product extraction from application names
- Vendor alias database for name variations
- Product-level mapping with version tracking
- License and contract management
- Vendor risk scoring and analysis
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db

logger = logging.getLogger(__name__)


@dataclass
class VendorExtractionResult:
    """Result of AI vendor product extraction."""

    vendor_id: Optional[int]
    vendor_name: str
    vendor_confidence: float

    family_id: Optional[int]
    family_name: str
    family_confidence: float

    product_id: Optional[int]
    product_name: str
    product_confidence: float

    version: Optional[str]
    edition: Optional[str]

    extraction_method: str
    rationale: List[str]
    alternative_matches: List[Dict[str, Any]]


class VendorProductService:
    """
    Enhanced vendor product catalog service with intelligent matching.

    Provides three-level vendor hierarchy management, AI-powered product extraction,
    and comprehensive vendor analysis for enterprise architecture.
    """

    def __init__(self):
        """Initialize the vendor product service."""
        self._init_vendor_patterns()
        self._init_product_patterns()
        self._init_alias_patterns()

    def _init_vendor_patterns(self):
        """Initialize known vendor patterns for AI extraction."""
        self.vendor_patterns = {
            # Major enterprise vendors with multiple patterns
            "sap": {
                "names": ["sap", "sap se", "sap ag", "sap america", "sap emea"],
                "confidence_boost": 0.3,
                "known_products": [
                    "s/4hana",
                    "business one",
                    "successfactors",
                    "hybris",
                    "ariba",
                    "concur",
                    "fieldglass",
                ],
            },
            "microsoft": {
                "names": ["microsoft", "msft", "ms", "microsoft corporation"],
                "confidence_boost": 0.3,
                "known_products": [
                    "office 365",
                    "azure",
                    "dynamics 365",
                    "sharepoint",
                    "teams",
                    "power bi",
                    "sql server",
                ],
            },
            "oracle": {
                "names": ["oracle", "oracle corporation", "oracle america"],
                "confidence_boost": 0.3,
                "known_products": [
                    "oracle ebs",
                    "oracle fusion",
                    "oracle cloud",
                    "net suite",
                    "peoplesoft",
                    "jd edwards",
                ],
            },
            "salesforce": {
                "names": ["salesforce", "salesforce.com", "sfdc"],
                "confidence_boost": 0.3,
                "known_products": [
                    "sales cloud",
                    "service cloud",
                    "marketing cloud",
                    "commerce cloud",
                    "platform",
                    "tableau",
                ],
            },
            "workday": {
                "names": ["workday", "workday inc"],
                "confidence_boost": 0.25,
                "known_products": [
                    "workday hcm",
                    "workday financials",
                    "workday student",
                    "workday adaptive planning",
                ],
            },
            "servicenow": {
                "names": ["servicenow", "service-now", "servicenow inc"],
                "confidence_boost": 0.25,
                "known_products": [
                    "itom",
                    "hrsd",
                    "csom",
                    "fsm",
                    "governance",
                    "risk",
                    "security operations",
                ],
            },
            "adobe": {
                "names": ["adobe", "adobe systems", "adobe inc"],
                "confidence_boost": 0.25,
                "known_products": [
                    "creative cloud",
                    "document cloud",
                    "experience cloud",
                    "marketing cloud",
                    "analytics cloud",
                ],
            },
            "aws": {
                "names": ["amazon web services", "aws", "amazon"],
                "confidence_boost": 0.25,
                "known_products": ["ec2", "s3", "lambda", "rds", "dynamodb", "cloudfront", "iam"],
            },
            "google": {
                "names": ["google", "alphabet", "google cloud", "gcp"],
                "confidence_boost": 0.25,
                "known_products": [
                    "google workspace",
                    "g suite",
                    "google cloud platform",
                    "bigquery",
                    "kubernetes engine",
                ],
            },
        }

    def _init_product_patterns(self):
        """Initialize product family and product patterns."""
        self.product_families = {
            "sap": {
                "s/4hana": {
                    "name": "S/4HANA",
                    "category": "ERP",
                    "known_versions": ["2020", "2021", "2022", "2023", "2023 fps1", "2023 fps2"],
                    "editions": ["on-premise", "cloud", "private cloud", "public cloud"],
                },
                "business one": {
                    "name": "Business One",
                    "category": "ERP",
                    "known_versions": ["9.3", "10.0"],
                    "editions": ["on-premise", "cloud"],
                },
                "successfactors": {
                    "name": "SuccessFactors",
                    "category": "HCM",
                    "known_versions": ["2.0", "2.5"],
                    "editions": ["on-premise", "cloud"],
                },
            },
            "microsoft": {
                "office 365": {
                    "name": "Office 365",
                    "category": "Productivity",
                    "known_versions": ["2013", "2016", "2019", "2021", "2023"],
                    "editions": ["business", "enterprise", "home", "education"],
                },
                "azure": {
                    "name": "Azure",
                    "category": "Cloud Platform",
                    "known_versions": ["classic", "modern", "hybrid"],
                    "editions": ["public", "private", "government", "china"],
                },
                "dynamics 365": {
                    "name": "Dynamics 365",
                    "category": "ERP/CRM",
                    "known_versions": ["2016", "2018", "2020", "2022"],
                    "editions": [
                        "business central",
                        "sales",
                        "customer service",
                        "field service",
                        "finance",
                        "supply chain",
                    ],
                },
            },
            "salesforce": {
                "sales cloud": {
                    "name": "Sales Cloud",
                    "category": "CRM",
                    "known_versions": ["classic", "lightning", "unlimited"],
                    "editions": ["professional", "enterprise", "unlimited", "developer"],
                },
                "service cloud": {
                    "name": "Service Cloud",
                    "category": "CRM",
                    "known_versions": ["classic", "lightning"],
                    "editions": ["professional", "enterprise", "unlimited", "developer"],
                },
                "marketing cloud": {
                    "name": "Marketing Cloud",
                    "category": "Marketing",
                    "known_versions": ["classic", "lightning"],
                    "editions": ["growth", "enterprise", "unlimited", "developer"],
                },
            },
        }

    def _init_alias_patterns(self):
        """Initialize common alias patterns for vendors and products."""
        self.alias_patterns = {
            "microsoft": ["msft", "ms"],
            "oracle": ["oracle corp", "oracle america"],
            "sap": ["sap se", "sap ag", "sap america"],
            "salesforce": ["sfdc", "salesforce.com"],
            "office 365": ["o365", "microsoft 365", "ms365"],
            "dynamics 365": ["d365", "ms dynamics"],
            "s/4hana": ["s4hana", "s4 hana"],
            "business one": ["b1", "sap b1"],
            "successfactors": ["sf", "success factors"],
            "azure": ["microsoft azure", "ms azure"],
            "aws": ["amazon web services", "amazon cloud"],
            "gcp": ["google cloud platform", "google cloud"],
        }

    def extract_vendor_product(
        self, application_name: str, description: str = ""
    ) -> VendorExtractionResult:
        """
        Extract vendor, product family, and specific product from application name using AI patterns.

        Args:
            application_name: Application name to analyze
            description: Optional description for additional context

        Returns:
            VendorExtractionResult with detailed extraction results
        """
        # Combine name and description for better analysis
        full_text = f"{application_name} {description}".lower()

        # Initialize result
        result = VendorExtractionResult(
            vendor_id=None,
            vendor_name="",
            vendor_confidence=0.0,
            family_id=None,
            family_name="",
            family_confidence=0.0,
            product_id=None,
            product_name="",
            product_confidence=0.0,
            version=None,
            edition=None,
            extraction_method="pattern_matching",
            rationale=[],
            alternative_matches=[],
        )

        # Step 1: Vendor extraction
        vendor_match = self._extract_vendor(full_text)
        if vendor_match:
            result.vendor_id = vendor_match["id"]
            result.vendor_name = vendor_match["name"]
            result.vendor_confidence = vendor_match["confidence"]
            result.rationale.append(f"Vendor pattern matched: {vendor_match['pattern']}")

        # Step 2: Product family extraction
        if result.vendor_confidence > 0.3:
            family_match = self._extract_product_family(full_text, result.vendor_name)
            if family_match:
                result.family_id = family_match["id"]
                result.family_name = family_match["name"]
                result.family_confidence = family_match["confidence"]
                result.rationale.append(
                    f"Product family pattern matched: {family_match['pattern']}"
                )

        # Step 3: Specific product extraction
        if result.family_confidence > 0.3:
            product_match = self._extract_specific_product(
                full_text, result.vendor_name, result.family_name
            )
            if product_match:
                result.product_id = product_match["id"]
                result.product_name = product_match["name"]
                result.product_confidence = product_match["confidence"]
                result.version = product_match.get("version")
                result.edition = product_match.get("edition")
                result.rationale.append(f"Product pattern matched: {product_match['pattern']}")

        # Step 4: Generate alternative matches if confidence is low
        if result.product_confidence < 0.7 or result.family_confidence < 0.7:
            alternatives = self._generate_alternative_matches(full_text)
            result.alternative_matches = alternatives

        return result

    def _extract_vendor(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract vendor from text using pattern matching."""
        for vendor_name, config in self.vendor_patterns.items():
            for pattern in config["names"]:
                if pattern in text:
                    # Find vendor in database
                    vendor = self._find_vendor_by_name(vendor_name)
                    if vendor:
                        return {
                            "id": vendor.id,
                            "name": vendor.name,
                            "confidence": min(0.9, 0.5 + config["confidence_boost"]),
                            "pattern": pattern,
                        }
        return None

    def _extract_product_family(self, text: str, vendor_name: str) -> Optional[Dict[str, Any]]:
        """Extract product family from text."""
        if vendor_name not in self.product_families:
            return None

        families = self.product_families[vendor_name]
        for family_name, config in families.items():
            for pattern in [family_name] + config.get("aliases", []):
                if pattern in text:
                    # Find product family in database
                    family = self._find_product_family_by_name(family_name, vendor_name)
                    if family:
                        return {
                            "id": family.id,
                            "name": family.family_name,
                            "confidence": min(0.9, 0.6 + 0.2),
                            "pattern": pattern,
                        }
        return None

    def _extract_specific_product(
        self, text: str, vendor_name: str, family_name: str
    ) -> Optional[Dict[str, Any]]:
        """Extract specific product with version and edition."""
        if (
            vendor_name not in self.product_families
            or family_name not in self.product_families[vendor_name]
        ):
            return None

        family_config = self.product_families[vendor_name][family_name]

        # Look for exact product name match
        for pattern in [family_name] + family_config.get("aliases", []):
            if pattern in text:
                # Try to extract version and edition
                version, edition = self._extract_version_edition(text, pattern)

                # Find specific product in database
                product = self._find_product_by_name(family_name, vendor_name, version, edition)
                if product:
                    return {
                        "id": product.id,
                        "name": product.product_name,
                        "confidence": 0.8,
                        "pattern": pattern,
                        "version": version,
                        "edition": edition,
                    }

        return None

    def _extract_version_edition(
        self, text: str, product_pattern: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract version and edition from text."""
        version = None
        edition = None

        # Common version patterns
        version_patterns = [
            r"(\d{4})",  # 2023, 2022, etc.
            r"(\d{4})\s*fps\d",  # 2023 fps1, 2023 fps2
            r"v(\d+)",  # v15, v2, etc.
            r"version\s*(\d+)",
            r"(\d+\.\d+)",  # 15.0, 2.5, etc.
        ]

        for pattern in version_patterns:
            import re

            match = re.search(pattern, text)
            if match:
                version = match.group(1)
                break

        # Common edition patterns
        edition_patterns = [
            r"(on-premise|cloud|private cloud|public cloud|hybrid)",
            r"(professional|enterprise|unlimited|developer|business|home|education)",
            r"(classic|lightning|modern)",
            r"(fps\d+|fps\d+)",  # fps1, fps2
        ]

        for pattern in edition_patterns:
            import re

            match = re.search(pattern, text)
            if match:
                edition = match.group(1)
                break

        return version, edition

    def _generate_alternative_matches(self, text: str) -> List[Dict[str, Any]]:
        """Generate alternative vendor-product matches for low-confidence results."""
        alternatives = []

        # Try different vendor patterns
        for vendor_name, config in self.vendor_patterns.items():
            for pattern in config["names"]:
                if pattern in text:
                    vendor = self._find_vendor_by_name(vendor_name)
                    if vendor:
                        # Get all product families for this vendor
                        families = self._get_vendor_product_families(vendor.id)
                        for family in families:
                            alternatives.append(
                                {
                                    "vendor_id": vendor.id,
                                    "vendor_name": vendor.name,
                                    "vendor_confidence": 0.4,
                                    "family_id": family.id,
                                    "family_name": family.family_name,
                                    "family_confidence": 0.3,
                                    "product_id": None,
                                    "product_name": "",
                                    "product_confidence": 0.2,
                                    "reason": f"Alternative vendor pattern match: {pattern}",
                                }
                            )

        # Sort by confidence and limit results
        alternatives.sort(key=lambda x: x["vendor_confidence"], reverse=True)
        return alternatives[:5]

    def find_vendor_product_match(
        self, application_name: str, description: str = ""
    ) -> Dict[str, Any]:
        """
        Find the best vendor product match for an application.

        Args:
            application_name: Application name
            description: Optional description

        Returns:
            Dictionary with match results and confidence scores
        """
        extraction_result = self.extract_vendor_product(application_name, description)

        # Calculate overall confidence
        if extraction_result.product_confidence > 0:
            overall_confidence = (
                extraction_result.vendor_confidence * 0.3
                + extraction_result.family_confidence * 0.3
                + extraction_result.product_confidence * 0.4
            )
        else:
            overall_confidence = 0.0

        return {
            "success": extraction_result.product_id is not None,
            "vendor": {
                "id": extraction_result.vendor_id,
                "name": extraction_result.vendor_name,
                "confidence": extraction_result.vendor_confidence,
            },
            "product_family": {
                "id": extraction_result.family_id,
                "name": extraction_result.family_name,
                "confidence": extraction_result.family_confidence,
            },
            "product": {
                "id": extraction_result.product_id,
                "name": extraction_result.product_name,
                "confidence": extraction_result.product_confidence,
                "version": extraction_result.version,
                "edition": extraction_result.edition,
            },
            "overall_confidence": overall_confidence,
            "extraction_method": extraction_result.extraction_method,
            "rationale": extraction_result.rationale,
            "alternative_matches": extraction_result.alternative_matches,
        }

    def create_vendor_product_mapping(
        self,
        application_id: int,
        vendor_product_id: int,
        confidence_score: float,
        mapping_method: str = "ai_extracted",
        deployment_type: str = "Production",
        version_deployed: str = None,
        license_type: str = "unknown",
        user_id: int = None,
    ) -> Dict[str, Any]:
        """
        Create an application-vendor product mapping.

        Args:
            application_id: Application ID
            vendor_product_id: Vendor product ID
            confidence_score: Confidence score (0.0 - 1.0)
            mapping_method: How the mapping was determined
            deployment_type: Deployment type
            version_deployed: Version deployed
            license_type: License type
            user_id: User ID who created the mapping

        Returns:
            Dictionary with creation result
        """
        try:
            from app.models.vendor.vendor_product import ApplicationVendorProductMapping

            # Check if mapping already exists
            existing = ApplicationVendorProductMapping.query.filter_by(
                application_id=application_id, vendor_product_id=vendor_product_id
            ).first()

            if existing:
                return {
                    "success": False,
                    "error": "Mapping already exists",
                    "existing_id": existing.id,
                }

            # Create new mapping
            mapping = ApplicationVendorProductMapping(
                application_id=application_id,
                vendor_product_id=vendor_product_id,
                confidence_score=confidence_score,
                mapping_method=mapping_method,
                deployment_type=deployment_type,
                version_deployed=version_deployed,
                license_type=license_type,
                ai_extraction_rationale=f"AI extracted vendor-product mapping with confidence {confidence_score}",
                created_by_id=user_id,
            )

            db.session.add(mapping)
            db.session.commit()

            return {"success": True, "mapping_id": mapping.id, "confidence_score": confidence_score}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating vendor product mapping: {e}")
            return {"success": False, "error": str(e)}

    def get_vendor_hierarchy(self, vendor_id: int) -> Dict[str, Any]:
        """
        Get complete vendor hierarchy including product families and products.

        Args:
            vendor_id: Vendor organization ID

        Returns:
            Dictionary with vendor hierarchy structure
        """
        try:
            from app.models.vendor.vendor_organization import VendorOrganization

            try:
                from app.models.vendor.vendor_organization import VendorProduct
                from app.models.vendor.vendor_product import VendorProductFamily
            except Exception:
                from app.models.vendor.vendor_organization import VendorProduct  # type: ignore
                from app.models.vendor.vendor_product import VendorProductFamily

            vendor = VendorOrganization.query.get(vendor_id)
            if not vendor:
                return {"error": "Vendor not found"}

            # Get product families
            families = VendorProductFamily.query.filter_by(vendor_id=vendor_id).all()
            hierarchy = {"vendor": vendor.to_dict(), "product_families": []}

            for family in families:
                family_dict = family.to_dict()

                # Get products for this family
                products = VendorProduct.query.filter_by(family_id=family.id).all()
                family_dict["products"] = [p.to_dict() for p in products]

                hierarchy["product_families"].append(family_dict)

            return hierarchy

        except Exception as e:
            logger.error(f"Error getting vendor hierarchy: {e}")
            return {"error": str(e)}

    def get_vendor_risk_analysis(self, vendor_id: int) -> Dict[str, Any]:
        """
        Calculate vendor risk analysis scores.

        Args:
            vendor_id: Vendor organization ID

        Returns:
            Dictionary with risk analysis results
        """
        try:
            from app.models.vendor.vendor_organization import VendorOrganization

            vendor = VendorOrganization.query.get(vendor_id)
            if not vendor:
                return {"error": "Vendor not found"}

            # Calculate risk scores
            risk_scores = {
                "financial_health": vendor.financial_health_score or 50,
                "vendor_lock_in": vendor.vendor_lock_in_risk or 5,
                "acquisition_risk": self._calculate_acquisition_risk(vendor),
                "technology_maturity": self._calculate_technology_maturity(vendor),
                "strategic_tier": self._calculate_strategic_tier_risk(vendor),
                "enterprise_readiness": vendor.enterprise_readiness_score or 50,
            }

            # Calculate overall risk score
            overall_risk = (
                risk_scores["financial_health"] * 0.25
                + risk_scores["vendor_lock_in"] * 0.20
                + risk_scores["acquisition_risk"] * 0.20
                + risk_scores["technology_maturity"] * 0.15
                + risk_scores["strategic_tier"] * 0.10
                + risk_scores["enterprise_readiness"] * 0.10
            )

            # Determine risk level
            if overall_risk >= 80:
                risk_level = "low"
            elif overall_risk >= 60:
                risk_level = "medium"
            elif overall_risk >= 40:
                risk_level = "high"
            else:
                risk_level = "critical"

            return {
                "vendor_id": vendor_id,
                "vendor_name": vendor.name,
                "risk_scores": risk_scores,
                "overall_risk_score": overall_risk,
                "risk_level": risk_level,
                "recommendations": self._generate_risk_recommendations(vendor, risk_scores),
            }

        except Exception as e:
            logger.error(f"Error calculating vendor risk analysis: {e}")
            return {"error": str(e)}

    def _calculate_acquisition_risk(self, vendor) -> int:
        """Calculate acquisition risk score (1 - 10 scale)."""
        if vendor.acquisition_risk == "low":
            return 2
        elif vendor.acquisition_risk == "medium":
            return 5
        elif vendor.acquisition_risk == "high":
            return 8
        else:
            return 10

    def _calculate_technology_maturity(self, vendor) -> int:
        """Calculate technology maturity score (1 - 10 scale)."""
        if vendor.technology_maturity == "mature":
            return 2
        elif vendor.technology_maturity == "established":
            return 4
        elif vendor.technology_maturity == "emerging":
            return 7
        elif vendor.technology_maturity == "legacy":
            return 9
        else:
            return 5

    def _calculate_strategic_tier_risk(self, vendor) -> int:
        """Calculate strategic tier risk score (1 - 10 scale, lower is better)."""
        if vendor.strategic_tier == "tier_1_strategic":
            return 2
        elif vendor.strategic_tier == "tier_2_preferred":
            return 4
        elif vendor.strategic_tier == "tier_3_approved":
            return 6
        elif vendor.strategic_tier == "tier_4_restricted":
            return 9
        else:
            return 7

    def _generate_risk_recommendations(self, vendor, risk_scores: Dict[str, int]) -> List[str]:
        """Generate risk mitigation recommendations."""
        recommendations = []

        if risk_scores["financial_health"] < 60:
            recommendations.append(
                "Review vendor financial stability and consider financial guarantees"
            )

        if risk_scores["vendor_lock_in"] > 7:
            recommendations.append("Develop exit strategy and evaluate alternative vendors")

        if risk_scores["technology_maturity"] > 7:
            recommendations.append("Plan technology migration path and assess upgrade requirements")

        if risk_scores["acquisition_risk"] > 6:
            recommendations.append("Monitor acquisition activity and prepare contingency plans")

        if risk_scores["enterprise_readiness"] < 60:
            recommendations.append(
                "Evaluate vendor's enterprise capabilities and support structure"
            )

        return recommendations

    # Database helper methods
    def _find_vendor_by_name(self, vendor_name: str):
        """Find vendor by name (case-insensitive)."""
        from app.models.vendor.vendor_organization import VendorOrganization

        return VendorOrganization.query.filter(
            func.lower(VendorOrganization.name) == func.lower(vendor_name)
        ).first()

    def _find_product_family_by_name(self, family_name: str, vendor_name: str):
        """Find product family by name and vendor."""
        from app.models.vendor.vendor_organization import VendorProduct
        from app.models.vendor.vendor_product import VendorProductFamily

        return (
            VendorProductFamily.query.join(VendorOrganization)
            .filter(
                VendorProductFamily.family_name.ilike(f"%{family_name}%"),
                VendorOrganization.name.ilike(f"%{vendor_name}%"),
            )
            .first()
        )

    def _find_product_by_name(
        self, product_name: str, vendor_name: str, version: str = None, edition: str = None
    ):
        """Find specific product by name, vendor, version, and edition."""
        from app.models.vendor.vendor_organization import VendorProduct
        from app.models.vendor.vendor_product import VendorProductFamily

        query = (
            VendorProduct.query.join(VendorProductFamily)
            .join(VendorOrganization)
            .filter(
                VendorProduct.product_name.ilike(f"%{product_name}%"),
                VendorOrganization.name.ilike(f"%{vendor_name}%"),
            )
        )

        if version:
            query = query.filter(VendorProduct.current_version == version)

        if edition:
            query = query.filter(VendorProduct.deployment_model.ilike(f"%{edition}%"))

        return query.first()

    def _get_vendor_product_families(self, vendor_id: int):
        """Get all product families for a vendor."""
        from app.models.vendor.vendor_organization import VendorProduct
        from app.models.vendor.vendor_product import VendorProductFamily

        return VendorProductFamily.query.filter_by(vendor_id=vendor_id).all()

    def search_vendor_products(
        self,
        query: str,
        vendor_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search vendor products with intelligent matching.

        Args:
            query: Search query
            vendor_id: Optional vendor ID filter
            category: Optional product category filter
            limit: Maximum results

        Returns:
            List of matching products with hierarchy information
        """
        try:
            # Use VendorProduct from vendor_organization (table: vendor_products) —
            # this is the model used by link-vendor-product, so IDs are consistent.
            from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

            base_query = (
                VendorProduct.query
                .join(VendorOrganization, VendorProduct.vendor_organization_id == VendorOrganization.id)
            )

            # Apply filters
            if vendor_id:
                base_query = base_query.filter(VendorOrganization.id == vendor_id)

            if category:
                base_query = base_query.filter(VendorProduct.product_family_name == category)

            # Text search: product name and vendor org name
            search_filter = or_(
                VendorProduct.name.ilike(f"%{query}%"),
                VendorProduct.product_family_name.ilike(f"%{query}%"),
                VendorOrganization.name.ilike(f"%{query}%"),
            )
            base_query = base_query.filter(search_filter)

            products = base_query.limit(limit).all()

            results = []
            for product in products:
                vendor_org = product.vendor_organization
                result = {
                    "id": product.id,
                    "product_id": product.id,  # legacy alias
                    "name": product.name,
                    "product_name": product.name,  # legacy alias
                    "product_code": product.product_code,
                    "version": product.version,
                    "deployment_model": product.deployment_model,
                    "product_family": product.product_family_name,
                    "vendor": {
                        "id": vendor_org.id if vendor_org else None,
                        "name": vendor_org.name if vendor_org else None,
                    },
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error searching vendor products: {e}")
            return []

    def get_vendor_statistics(self, vendor_id: int) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a vendor.

        Args:
            vendor_id: Vendor ID

        Returns:
            Dictionary with vendor statistics
        """
        try:
            from app.models.vendor.vendor_organization import VendorOrganization

            try:
                from app.models.vendor.vendor_organization import VendorProduct
                from app.models.vendor.vendor_product import VendorProductFamily
            except Exception:
                from app.models.vendor.vendor_organization import VendorProduct  # type: ignore
                from app.models.vendor.vendor_product import VendorProductFamily

            vendor = VendorOrganization.query.get(vendor_id)
            if not vendor:
                return {"error": "Vendor not found"}

            # Get statistics
            family_count = VendorProductFamily.query.filter_by(vendor_id=vendor_id).count()
            product_count = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).count()

            # Category breakdown (from families, which have the vendor FK)
            category_stats = (
                db.session.query(
                    VendorProductFamily.category, func.count(VendorProductFamily.id).label("count")
                )
                .filter_by(vendor_id=vendor_id)
                .group_by(VendorProductFamily.category)
                .all()
            )

            # Status breakdown — filter directly by vendor_organization_id (no join needed)
            status_stats = (
                db.session.query(VendorProduct.status, func.count(VendorProduct.id).label("count"))
                .filter(VendorProduct.vendor_organization_id == vendor_id)
                .group_by(VendorProduct.status)
                .all()
            )

            return {
                "vendor": vendor.to_dict(),
                "statistics": {
                    "product_families": family_count,
                    "total_products": product_count,
                    "category_breakdown": {cat.category: cat.count for cat in category_stats},
                    "status_breakdown": {status.status: status.count for status in status_stats},
                },
            }

        except Exception as e:
            logger.error(f"Error getting vendor statistics: {e}")
            return {"error": str(e)}

    def get_all_vendors_with_stats(self, tier=None, category=None, search=None):
        """Get all vendors with comprehensive statistics, with optional filtering."""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily

            query = VendorOrganization.query

            if tier:
                query = query.filter(VendorOrganization.strategic_tier == tier)
            if category:
                query = query.filter(VendorOrganization.vendor_type == category)
            if search:
                query = query.filter(
                    db.or_(
                        VendorOrganization.name.ilike(f"%{search}%"),
                        VendorOrganization.description.ilike(f"%{search}%"),
                    )
                )

            vendors = query.all()
            vendor_stats = []

            for vendor in vendors:
                try:
                    # Get product counts
                    family_count = VendorProductFamily.query.filter_by(vendor_id=vendor.id).count()
                    product_count = VendorProduct.query.filter_by(vendor_organization_id=vendor.id).count()

                    # Calculate average TCO (simplified calculation)
                    avg_tco = self._calculate_avg_tco(vendor)

                    # Calculate risk score
                    risk_score = self._calculate_risk_score(vendor)

                    # Get active contracts count (placeholder)
                    active_contracts = 0  # Would be calculated from contracts table

                    stats = {
                        "id": vendor.id,
                        "name": vendor.name,
                        "description": vendor.description,
                        "market_position": vendor.vendor_type,
                        "revenue_tier": vendor.strategic_tier,
                        "employee_count": vendor.employee_count,
                        "headquarters_location": vendor.headquarters_location,
                        "founded_year": vendor.year_founded,
                        "website_url": vendor.website,
                        "is_active": vendor.status == "active",
                        "risk_score": risk_score,
                        "statistics": {
                            "product_family_count": family_count,
                            "product_count": product_count,
                            "average_tco": avg_tco,
                            "active_contracts": active_contracts,
                            "market_position": vendor.vendor_type,
                            "revenue_tier": vendor.strategic_tier,
                        },
                    }
                    vendor_stats.append(stats)

                except Exception as e:
                    logger.error(f"Error processing vendor {vendor.id}: {e}")
                    # Add minimal stats for this vendor
                    vendor_stats.append(
                        {
                            "id": vendor.id,
                            "name": vendor.name,
                            "description": vendor.description,
                            "market_position": vendor.vendor_type,
                            "is_active": vendor.status == "active",
                            "risk_score": 50,  # Default risk score
                            "statistics": {
                                "product_family_count": 0,
                                "product_count": 0,
                                "average_tco": 0,
                                "active_contracts": 0,
                                "market_position": vendor.vendor_type,
                                "revenue_tier": vendor.strategic_tier,
                            },
                        }
                    )

            return vendor_stats

        except Exception as e:
            logger.error(f"Error getting all vendor stats: {e}")
            return []

    def _calculate_avg_tco(self, vendor):
        """Calculate average TCO for vendor products"""
        try:
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily

            # Get all products for this vendor directly by vendor_organization_id
            products = VendorProduct.query.filter_by(vendor_organization_id=vendor.id).all()

            if not products:
                return 0

            # Calculate average based on pricing tiers (simplified)
            total_tco = 0
            valid_products = 0

            for product in products:
                # Use pricing tier to estimate TCO
                if hasattr(product, "pricing_tier") and product.pricing_tier:
                    tco_mapping = {
                        "basic": 1000,
                        "standard": 5000,
                        "premium": 15000,
                        "enterprise": 50000,
                    }
                    tco = tco_mapping.get(product.pricing_tier.lower(), 5000)
                    total_tco += tco
                    valid_products += 1
                else:
                    # Default TCO estimation
                    total_tco += 5000
                    valid_products += 1

            return total_tco / valid_products if valid_products > 0 else 0

        except Exception as e:
            logger.error(f"Error calculating avg TCO for vendor {vendor.id}: {e}")
            return 0

    def _calculate_risk_score(self, vendor):
        """Calculate risk score for vendor"""
        try:
            risk_score = 50  # Base risk score

            # Adjust based on market position
            if vendor.vendor_type:
                position_scores = {
                    "leader": -10,
                    "challenger": -5,
                    "visionary": 5,
                    "niche_player": 10,
                }
                risk_score += position_scores.get(vendor.vendor_type.lower(), 0)

            # Adjust based on revenue tier
            if vendor.strategic_tier:
                revenue_scores = {"large": -10, "medium": 0, "small": 10, "startup": 20}
                risk_score += revenue_scores.get(vendor.strategic_tier.lower(), 0)

            # Adjust based on company age
            if vendor.year_founded:
                company_age = datetime.now().year - vendor.year_founded
                if company_age < 5:
                    risk_score += 10  # New companies are riskier
                elif company_age > 20:
                    risk_score -= 5  # Established companies are less risky

            # Ensure risk score is within bounds
            return max(0, min(100, risk_score))

        except Exception as e:
            logger.error(f"Error calculating risk score for vendor {vendor.id}: {e}")
            return 50  # Default risk score

    def search_products(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search vendor products with comprehensive filtering.

        Args:
            query: Search query string
            filters: Dictionary of filters (category, tier, price_range, etc.)

        Returns:
            List of product dictionaries with search results
        """
        try:
            from sqlalchemy import and_, distinct, or_

            from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

            # Base query
            products_query = VendorProduct.query.join(VendorOrganization)

            # Text search
            if query:
                search_filter = or_(
                    VendorProduct.name.ilike(f"%{query}%"),
                    VendorProduct.description.ilike(f"%{query}%"),
                    VendorProduct.category.ilike(f"%{query}%"),
                    VendorOrganization.name.ilike(f"%{query}%"),
                )
                products_query = products_query.filter(search_filter)

            # Apply filters
            if filters:
                if "category" in filters:
                    products_query = products_query.filter(
                        VendorProduct.category == filters["category"]
                    )

                if "tier" in filters:
                    products_query = products_query.filter(VendorProduct.tier == filters["tier"])

                if "min_price" in filters:
                    products_query = products_query.filter(
                        VendorProduct.base_price >= filters["min_price"]
                    )

                if "max_price" in filters:
                    products_query = products_query.filter(
                        VendorProduct.base_price <= filters["max_price"]
                    )

                if "vendor_id" in filters:
                    products_query = products_query.filter(
                        VendorProduct.vendor_id == filters["vendor_id"]
                    )

            # Execute query
            products = products_query.limit(50).all()

            # Format results
            results = []
            for product in products:
                results.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "category": product.category,
                        "tier": product.tier,
                        "base_price": float(product.base_price) if product.base_price else 0.0,
                        "vendor": {
                            "id": product.vendor.id,
                            "name": product.vendor.name,
                            "market_position": product.vendor.vendor_type,
                            "revenue_tier": product.vendor.strategic_tier,
                        },
                        "features": product.features or [],
                        "compliance": product.compliance_standards or [],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    def get_vendor_categories(self) -> List[str]:
        """Get all unique product categories"""
        try:
            from sqlalchemy import distinct

            from app.models.vendor.vendor_organization import VendorProduct

            categories = db.session.query(distinct(VendorProduct.category)).all()
            return [cat[0] for cat in categories if cat[0]]

        except Exception as e:
            logger.error(f"Error getting vendor categories: {e}")
            return []

    def get_products_by_tier(self, tier: str) -> List[Dict[str, Any]]:
        """Get all products in a specific tier"""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

            products = VendorProduct.query.filter_by(tier=tier).join(VendorOrganization).all()

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "vendor": p.vendor.name,
                    "base_price": float(p.base_price) if p.base_price else 0.0,
                    "category": p.category,
                    "description": p.description,
                }
                for p in products
            ]

        except Exception as e:
            logger.error(f"Error getting products by tier {tier}: {e}")
            return []

    def get_products_by_vendor(self, vendor_id: int) -> List[Dict[str, Any]]:
        """Get all products for a specific vendor"""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

            products = (
                VendorProduct.query.filter_by(vendor_id=vendor_id).join(VendorOrganization).all()
            )

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "category": p.category,
                    "tier": p.tier,
                    "base_price": float(p.base_price) if p.base_price else 0.0,
                    "features": p.features or [],
                    "compliance_standards": p.compliance_standards or [],
                }
                for p in products
            ]

        except Exception as e:
            logger.error(f"Error getting products by vendor {vendor_id}: {e}")
            return []

    def get_product_details(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific product"""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

            product = VendorProduct.query.filter_by(id=product_id).join(VendorOrganization).first()

            if not product:
                return None

            return {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "tier": product.tier,
                "base_price": float(product.base_price) if product.base_price else 0.0,
                "vendor": {
                    "id": product.vendor.id,
                    "name": product.vendor.name,
                    "description": product.vendor.description,
                    "market_position": product.vendor.vendor_type,
                    "revenue_tier": product.vendor.strategic_tier,
                    "website_url": product.vendor.website,
                    "contact_email": product.vendor.contact_email,
                },
                "features": product.features or [],
                "compliance_standards": product.compliance_standards or [],
                "created_at": product.created_at.isoformat() if product.created_at else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            }

        except Exception as e:
            logger.error(f"Error getting product details {product_id}: {e}")
            return None

    def get_complete_catalog(self, tier=None, category=None, search=None) -> Dict[str, Any]:
        """Get complete vendor catalog with three-level hierarchy."""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily

            query = VendorOrganization.query
            if tier:
                query = query.filter(VendorOrganization.strategic_tier == tier)
            if search:
                query = query.filter(
                    db.or_(
                        VendorOrganization.name.ilike(f"%{search}%"),
                        VendorOrganization.description.ilike(f"%{search}%"),
                    )
                )
            vendors = query.order_by(VendorOrganization.name).all()

            total_families = 0
            total_products = 0
            vendor_list = []

            for vendor in vendors:
                families = VendorProductFamily.query.filter_by(vendor_id=vendor.id).all()
                if category:
                    families = [f for f in families if f.category == category]
                family_list = []
                for family in families:
                    products = VendorProduct.query.filter_by(family_id=family.id).all()
                    family_list.append({
                        "id": family.id,
                        "name": family.family_name,
                        "category": family.category,
                        "product_count": len(products),
                    })
                    total_products += len(products)
                total_families += len(family_list)
                vendor_list.append({
                    "id": vendor.id,
                    "name": vendor.name,
                    "market_position": vendor.vendor_type,
                    "revenue_tier": vendor.strategic_tier,
                    "product_families": family_list,
                    "family_count": len(family_list),
                })

            return {
                "vendors": vendor_list,
                "total_vendors": len(vendor_list),
                "total_families": total_families,
                "total_products": total_products,
            }
        except Exception as e:
            logger.error(f"Error getting complete catalog: {e}")
            return {"vendors": [], "total_vendors": 0, "total_families": 0, "total_products": 0}

    def get_catalog_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics for the vendor catalog."""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily

            total_vendors = VendorOrganization.query.count()
            total_families = VendorProductFamily.query.count()
            total_products = VendorProduct.query.count()

            tier_breakdown = (
                db.session.query(VendorOrganization.strategic_tier, func.count(VendorOrganization.id))
                .group_by(VendorOrganization.strategic_tier)
                .all()
            )
            category_breakdown = (
                db.session.query(VendorProductFamily.category, func.count(VendorProductFamily.id))
                .group_by(VendorProductFamily.category)
                .all()
            )

            return {
                "total_vendors": total_vendors,
                "total_product_families": total_families,
                "total_products": total_products,
                "tier_breakdown": {t: c for t, c in tier_breakdown if t},
                "category_breakdown": {cat: cnt for cat, cnt in category_breakdown if cat},
            }
        except Exception as e:
            logger.error(f"Error getting catalog statistics: {e}")
            return {"total_vendors": 0, "total_product_families": 0, "total_products": 0}

    def get_all_categories(self) -> List[str]:
        """Get all unique product family categories."""
        try:
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily
            rows = db.session.query(VendorProductFamily.category).distinct().all()
            return sorted([r[0] for r in rows if r[0]])
        except Exception as e:
            logger.error(f"Error getting all categories: {e}")
            return []

    def get_all_tiers(self) -> List[str]:
        """Get all unique vendor revenue tiers."""
        try:
            from app.models.vendor.vendor_organization import VendorOrganization
            rows = db.session.query(VendorOrganization.strategic_tier).distinct().all()
            return sorted([r[0] for r in rows if r[0]])
        except Exception as e:
            logger.error(f"Error getting all tiers: {e}")
            return []

    def get_vendor_products(self, vendor_id: int) -> List[Dict[str, Any]]:
        """Get all products for a vendor (flat list across all families)."""
        try:
            from app.models.vendor.vendor_organization import VendorProduct
            # VendorProduct links to the vendor directly via vendor_organization_id;
            # it has no FK to VendorProductFamily (only a denormalized
            # product_family_name string), so filter on the org FK without a join.
            products = (
                VendorProduct.query.filter(
                    VendorProduct.vendor_organization_id == vendor_id
                ).all()
            )
            # VendorProduct has no to_dict(); serialise explicitly (mirrors the
            # architecture vendor-products endpoint) so a real product list is
            # not silently dropped to [] by the broad except below.
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "product_code": p.product_code,
                    "version": p.version,
                    "product_family": p.product_family_name,
                    "deployment_model": p.deployment_model,
                    "licensing_model": p.licensing_model,
                    "product_type": p.product_type,
                    "target_market": p.target_market,
                    "primary_technology": p.primary_technology,
                    "api_availability": p.api_availability,
                    "functional_scope": p.functional_scope,
                    "market_position": p.market_position,
                    "product_maturity": p.product_maturity,
                    "status": getattr(p, "status", None),
                    "description": p.description,
                    "vendor_organization_id": p.vendor_organization_id,
                }
                for p in products
            ]
        except Exception as e:
            logger.error(f"Error getting vendor products for {vendor_id}: {e}")
            return []

    def get_vendor_product_families(self, vendor_id: int) -> List[Dict[str, Any]]:
        """Get all product families for a vendor."""
        try:
            from app.models.vendor.vendor_organization import VendorProduct
            from app.models.vendor.vendor_product import VendorProductFamily
            families = VendorProductFamily.query.filter_by(vendor_id=vendor_id).all()
            return [f.to_dict() for f in families] if families else []
        except Exception as e:
            logger.error(f"Error getting vendor product families for {vendor_id}: {e}")
            return []

    def get_family_products(self, family_id: int) -> List[Dict[str, Any]]:
        """Get all products in a product family."""
        try:
            from app.models.vendor.vendor_organization import VendorProduct
            products = VendorProduct.query.filter_by(family_id=family_id).all()
            return [p.to_dict() for p in products] if products else []
        except Exception as e:
            logger.error(f"Error getting family products for {family_id}: {e}")
            return []

    def get_product_applications(self, product_id: int) -> List[Dict[str, Any]]:
        """Get all applications mapped to a product via application_vendor_product_mappings."""
        try:
            rows = db.session.execute(
                db.text("""
                    SELECT ac.id, ac.name, m.role_type
                    FROM application_vendor_product_mappings m
                    JOIN application_components ac ON ac.id = m.application_component_id
                    WHERE m.vendor_product_id = :pid
                    ORDER BY ac.name
                """),
                {"pid": product_id},
            ).fetchall()
            return [{"id": r[0], "name": r[1], "role_type": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Error getting product applications for {product_id}: {e}")
            return []
