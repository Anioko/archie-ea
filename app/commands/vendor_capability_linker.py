"""
Vendor-Capability Linking Utility

This module provides intelligent linking between VendorStackTemplates and BusinessCapabilities.

Purpose:
- Parse capabilities_enabled JSON from vendor templates
- Match to existing BusinessCapability records
- Create VendorOrganization, VendorProduct, and VendorProductCapability records
- Provide fuzzy matching and reporting

Usage:
    from app.commands.vendor_capability_linker import VendorCapabilityLinker

    linker = VendorCapabilityLinker()
    results = linker.link_vendor_template_to_capabilities(template)
    linker.print_report(results)
"""

import json
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
)
from app.models.vendor_stack_template import VendorStackTemplate
from app.services.vendor_capability_link_service import VendorCapabilityLinkService


class VendorCapabilityLinker:
    """
    Intelligent linker for vendor templates to business capabilities.
    """

    def __init__(self, fuzzy_match_threshold: float = 0.85):
        """
        Initialize the linker.

        Args:
            fuzzy_match_threshold: Minimum similarity ratio for fuzzy matching (0.0 - 1.0)
        """
        self.fuzzy_match_threshold = fuzzy_match_threshold
        self.stats = {
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "created_capabilities": 0,
            "no_match": 0,
            "linked_capabilities": 0,
            "errors": [],
        }
        self.link_service = VendorCapabilityLinkService()

    def link_vendor_template_to_capabilities(
        self,
        template: VendorStackTemplate,
        create_missing: bool = True,
        auto_link_fuzzy: bool = False,
    ) -> Dict:
        """
        Link a vendor template to business capabilities.

        Args:
            template: VendorStackTemplate to process
            create_missing: If True, create BusinessCapability records for unmatched names
            auto_link_fuzzy: If True, automatically link fuzzy matches

        Returns:
            Dictionary with linking results and statistics
        """
        results = {
            "vendor_org": None,
            "vendor_product": None,
            "capabilities_linked": [],
            "capabilities_created": [],
            "capabilities_fuzzy_matched": [],
            "capabilities_not_matched": [],
            "stats": {},
        }

        try:
            # 1. Create or update VendorOrganization
            vendor_org = self._get_or_create_vendor_organization(template)
            results["vendor_org"] = vendor_org

            # 2. Create or update VendorProduct
            vendor_product = self._get_or_create_vendor_product(template, vendor_org)
            results["vendor_product"] = vendor_product

            # 3. Parse capabilities from template
            capabilities_data = self._parse_capabilities_from_template(template)

            if not capabilities_data:
                print(f"⚠️  No capabilities found in template for {template.vendor_name}")
                return results

            # 4. Process each capability
            for cap_data in capabilities_data:
                cap_name = cap_data.get("name")
                if not cap_name:
                    continue

                # Try exact match first
                business_cap = BusinessCapability.query.filter(
                    db.func.lower(BusinessCapability.name) == db.func.lower(cap_name)
                ).first()

                if business_cap:
                    # Exact match found
                    self._link_capability(vendor_product, business_cap, cap_data, results)
                    self.stats["exact_matches"] += 1
                    continue

                # Try fuzzy match
                fuzzy_match = self._find_fuzzy_match(cap_name)

                if fuzzy_match and auto_link_fuzzy:
                    # Fuzzy match found and auto-link enabled
                    self._link_capability(vendor_product, fuzzy_match, cap_data, results)
                    results["capabilities_fuzzy_matched"].append(
                        {
                            "vendor_name": cap_name,
                            "matched_to": fuzzy_match.name,
                            "similarity": self._calculate_similarity(cap_name, fuzzy_match.name),
                        }
                    )
                    self.stats["fuzzy_matches"] += 1
                    continue

                # No match - create if allowed
                if create_missing:
                    business_cap = self._create_business_capability(cap_data)
                    self._link_capability(vendor_product, business_cap, cap_data, results)
                    results["capabilities_created"].append(cap_name)
                    self.stats["created_capabilities"] += 1
                else:
                    results["capabilities_not_matched"].append(
                        {
                            "name": cap_name,
                            "fuzzy_candidate": fuzzy_match.name if fuzzy_match else None,
                        }
                    )
                    self.stats["no_match"] += 1

            # 5. Commit all changes
            db.session.commit()
            results["stats"] = self.stats.copy()

        except Exception as e:
            db.session.rollback()
            self.stats["errors"].append(str(e))
            raise

        return results

    def _get_or_create_vendor_organization(
        self, template: VendorStackTemplate
    ) -> VendorOrganization:
        """Get or create VendorOrganization from template."""
        vendor_org = VendorOrganization.query.filter_by(
            name=template.vendor_company_name or template.vendor_name
        ).first()

        if not vendor_org:
            vendor_org = VendorOrganization(
                name=getattr(template, "vendor_company_name", None) or template.vendor_name,
                display_name=getattr(template, "vendor_company_name", None),
                vendor_type="software_vendor",
                headquarters_location=getattr(template, "headquarters", None),
                website=getattr(template, "website", None),
                gartner_magic_quadrant_position=getattr(template, "market_position", None),
                market_share_percentage=getattr(template, "market_share_percentage", None),
                year_founded=getattr(template, "founded_year", None),
                annual_revenue_usd=getattr(template, "revenue_usd", None),
                customer_count=getattr(template, "customer_count", None),
                strategic_tier="tier_1_strategic"
                if getattr(template, "market_position", None) == "leader"
                else "tier_2_preferred",
                financial_health_score=self._map_financial_health(
                    getattr(template, "financial_health", None)
                ),
                acquisition_risk=getattr(template, "acquisition_risk", None),
                status="active",
            )
            db.session.add(vendor_org)
            db.session.flush()  # Get ID without committing

        return vendor_org

    def _get_or_create_vendor_product(
        self, template: VendorStackTemplate, vendor_org: VendorOrganization
    ) -> VendorProduct:
        """Get or create VendorProduct from template."""
        product = VendorProduct.query.filter_by(
            vendor_organization_id=vendor_org.id, name=template.name
        ).first()

        if not product:
            product = VendorProduct(
                vendor_organization_id=vendor_org.id,
                name=template.name,
                product_type="erp" if "ERP" in template.name else "platform",
                functional_scope=getattr(template, "description", None),
                version=getattr(template, "framework_version", None),
                product_family=self._infer_product_category(template),
                deployment_model=self._map_platform_to_deployment(
                    getattr(template, "platform", None)
                ),
                licensing_model="subscription",  # Default assumption
                target_market=getattr(template, "target_industry", None) or "enterprise",
                market_position="leader"
                if getattr(template, "market_position", None) == "leader"
                else "challenger",
            )
            db.session.add(product)
            db.session.flush()

        return product

    def _parse_capabilities_from_template(self, template: VendorStackTemplate) -> List[Dict]:
        """Parse capabilities_enabled JSON from template."""
        if not template.capabilities_enabled:
            return []

        try:
            capabilities = json.loads(template.capabilities_enabled)
            return capabilities if isinstance(capabilities, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _find_fuzzy_match(self, capability_name: str) -> Optional[BusinessCapability]:
        """Find fuzzy match for capability name."""
        all_capabilities = BusinessCapability.query.all()

        best_match = None
        best_ratio = 0.0

        for cap in all_capabilities:
            ratio = self._calculate_similarity(capability_name, cap.name)
            if ratio > best_ratio and ratio >= self.fuzzy_match_threshold:
                best_ratio = ratio
                best_match = cap

        return best_match

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _create_business_capability(self, cap_data: Dict) -> BusinessCapability:
        """Create a new BusinessCapability from vendor capability data."""
        capability = BusinessCapability(
            name=cap_data["name"],
            description=cap_data.get("description", ""),
            level=2,  # L2 (tactical) by default
            category="Core",  # Default category
            domain="Operations",  # Default domain
            current_maturity_level=self._map_maturity_to_cmm(cap_data.get("maturity_level")),
            target_maturity_level=5,  # Optimized
            strategic_importance="high",
        )
        db.session.add(capability)
        db.session.flush()
        return capability

    def _link_capability(
        self,
        vendor_product: VendorProduct,
        business_capability: BusinessCapability,
        cap_data: Dict,
        results: Dict,
    ):
        """Create VendorProductCapability junction record."""
        # Check if link already exists
        existing = VendorProductCapability.query.filter_by(
            vendor_product_id=vendor_product.id, business_capability_id=business_capability.id
        ).first()

        if existing:
            # Update existing record
            vpc = existing
        else:
            vpc = VendorProductCapability(
                vendor_product_id=vendor_product.id, business_capability_id=business_capability.id
            )
            db.session.add(vpc)

        # Update metrics from template data
        vpc.coverage_percentage = cap_data.get("coverage_percentage", 80.0)
        vpc.maturity_level = self._map_maturity_to_cmm(cap_data.get("maturity_level"))
        vpc.fit_score = int(cap_data.get("coverage_percentage", 80))
        vpc.out_of_box_percentage = cap_data.get(
            "out_of_box_percentage", cap_data.get("coverage_percentage", 80)
        )
        vpc.implementation_complexity = self._estimate_complexity(cap_data)
        vpc.customization_required = cap_data.get("coverage_percentage", 100) < 100

        db.session.flush()

        results["capabilities_linked"].append(
            {
                "capability_name": business_capability.name,
                "coverage": vpc.coverage_percentage,
                "maturity": vpc.maturity_level,
            }
        )

        self.stats["linked_capabilities"] += 1

        if vendor_product.vendor_organization_id:
            coverage = vpc.coverage_percentage or 0
            risk_level = self._coverage_to_risk_level(coverage)
            impact = (
                f"{vendor_product.name} covers {business_capability.name} "
                f"at {coverage:.0f}% according to vendor template."
            )
            self.link_service.ensure_link(
                vendor_product.vendor_organization_id,
                business_capability.id,
                risk_level=risk_level,
                risk_type="product_dependency",
                impact_description=impact,
                mitigation_strategy="Confirm coverage assumptions during vendor evaluation.",
                contingency_plan="Identify alternate vendors for critical functions.",
                source="vendor_capability_linker",
            )

    def _map_maturity_to_cmm(self, maturity_str: Optional[str]) -> int:
        """Map maturity string to CMM level (1 - 5)."""
        if not maturity_str:
            return 3

        maturity_map = {
            "initial": 1,
            "developing": 2,
            "managed": 3,
            "defined": 3,
            "optimized": 5,
            "optimizing": 5,
        }

        return maturity_map.get(maturity_str.lower(), 3)

    def _estimate_complexity(self, cap_data: Dict) -> int:
        """Estimate implementation complexity (1 - 10) from capability data."""
        coverage = cap_data.get("coverage_percentage", 80)

        # Higher coverage = lower complexity
        if coverage >= 95:
            return 3  # Low complexity
        elif coverage >= 85:
            return 5  # Medium complexity
        elif coverage >= 70:
            return 7  # High complexity
        else:
            return 9  # Very high complexity

    def _coverage_to_risk_level(self, coverage: float) -> str:
        """Map coverage percentage to a vendor risk level."""

        if coverage >= 90:
            return "critical"
        if coverage >= 75:
            return "high"
        if coverage >= 50:
            return "medium"
        return "low"

    def _map_financial_health(self, health_str: Optional[str]) -> int:
        """Map financial health string to score (0 - 100)."""
        if not health_str:
            return 75

        health_map = {"excellent": 95, "good": 80, "fair": 65, "poor": 40, "critical": 20}

        return health_map.get(health_str.lower(), 75)

    def _infer_product_category(self, template: VendorStackTemplate) -> str:
        """Infer product category from template data."""
        name_lower = template.name.lower()

        if "erp" in name_lower or "s/4hana" in name_lower:
            return "erp"
        elif "mes" in name_lower or "manufacturing" in name_lower:
            return "mes"
        elif "plm" in name_lower:
            return "plm"
        elif "crm" in name_lower or "salesforce" in name_lower:
            return "crm"
        elif "low-code" in name_lower or "mendix" in name_lower or "outsystems" in name_lower:
            return "low_code_platform"
        else:
            return "enterprise_platform"

    def _map_platform_to_deployment(self, platform: Optional[str]) -> str:
        """Map platform to deployment model."""
        if not platform:
            return "hybrid"

        platform_lower = platform.lower()

        if platform_lower in ["aws", "azure", "gcp", "cloud"]:
            return "cloud"
        elif platform_lower == "on-prem":
            return "on_premise"
        elif platform_lower == "hybrid":
            return "hybrid"
        elif platform_lower == "saas":
            return "saas"
        else:
            return "hybrid"

    def print_report(self, results: Dict):
        """Print a formatted report of linking results."""
        print("\n" + "=" * 80)
        print("VENDOR-CAPABILITY LINKING REPORT")
        print("=" * 80)

        if results.get("vendor_org"):
            print(f"\n📦 Vendor Organization: {results['vendor_org'].name}")

        if results.get("vendor_product"):
            print(f"📦 Product: {results['vendor_product'].name}")

        stats = results.get("stats", {})

        print(f"\n📊 Linking Statistics:")
        print(f"   ✅ Exact matches: {stats.get('exact_matches', 0)}")
        print(f"   🔍 Fuzzy matches: {stats.get('fuzzy_matches', 0)}")
        print(f"   ➕ Created capabilities: {stats.get('created_capabilities', 0)}")
        print(f"   🔗 Total linked: {stats.get('linked_capabilities', 0)}")
        print(f"   ❌ Not matched: {stats.get('no_match', 0)}")

        if results.get("capabilities_created"):
            print(f"\n➕ Created Business Capabilities:")
            for cap_name in results["capabilities_created"]:
                print(f"   - {cap_name}")

        if results.get("capabilities_fuzzy_matched"):
            print(f"\n🔍 Fuzzy Matched Capabilities:")
            for match in results["capabilities_fuzzy_matched"]:
                print(
                    f"   - '{match['vendor_name']}' → '{match['matched_to']}' "
                    f"({match['similarity']:.1%} similar)"
                )

        if results.get("capabilities_not_matched"):
            print(f"\n⚠️  Unmatched Capabilities (require manual review):")
            for item in results["capabilities_not_matched"]:
                if item.get("fuzzy_candidate"):
                    print(f"   - {item['name']} (similar to: {item['fuzzy_candidate']})")
                else:
                    print(f"   - {item['name']}")

        if results.get("capabilities_linked"):
            print(f"\n✅ Successfully Linked Capabilities:")
            for link in results["capabilities_linked"]:
                print(
                    f"   - {link['capability_name']}: "
                    f"{link['coverage']:.0f}% coverage, "
                    f"Maturity L{link['maturity']}"
                )

        print("\n" + "=" * 80)

    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "created_capabilities": 0,
            "no_match": 0,
            "linked_capabilities": 0,
            "errors": [],
        }


def link_all_vendor_templates(create_missing: bool = True, auto_link_fuzzy: bool = False) -> Dict:
    """
    Link all vendor templates to business capabilities.

    Args:
        create_missing: Create BusinessCapability records for unmatched names
        auto_link_fuzzy: Automatically link fuzzy matches

    Returns:
        Dictionary with aggregated results
    """
    linker = VendorCapabilityLinker()
    all_results = {
        "vendors_processed": 0,
        "total_capabilities_linked": 0,
        "total_capabilities_created": 0,
        "vendor_results": [],
    }

    templates = VendorStackTemplate.query.all()

    if not templates:
        print("⚠️  No vendor templates found. Run vendor seed commands first.")
        return all_results

    print(f"\n🔗 Processing {len(templates)} vendor template(s)...\n")

    for template in templates:
        print(f"\n{'='*80}")
        print(f"Processing: {template.vendor_name}")
        print(f"{'='*80}")

        results = linker.link_vendor_template_to_capabilities(
            template, create_missing=create_missing, auto_link_fuzzy=auto_link_fuzzy
        )

        linker.print_report(results)

        all_results["vendors_processed"] += 1
        all_results["total_capabilities_linked"] += results["stats"].get("linked_capabilities", 0)
        all_results["total_capabilities_created"] += results["stats"].get("created_capabilities", 0)
        all_results["vendor_results"].append(results)

        # Reset stats for next vendor
        linker.reset_stats()

    # Print summary
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Vendors processed: {all_results['vendors_processed']}")
    print(f"🔗 Total capabilities linked: {all_results['total_capabilities_linked']}")
    print(f"➕ Total capabilities created: {all_results['total_capabilities_created']}")
    print(f"{'='*80}\n")

    return all_results
