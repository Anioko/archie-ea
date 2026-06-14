"""
Capability-Based Vendor Selection Engine

Enterprise-grade vendor selection based on business capability requirements,
L1/L2/L3 filtering, coverage scoring, and intelligent recommendations.

Replaces manual checkbox selection with algorithmic vendor matching.
"""

import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import joinedload

from app import create_app, db
from app.models import BusinessCapability
from app.models.vendor import VendorProduct, VendorProductCapability
from config import config as Config


class CapabilityBasedVendorSelector:
    """Enterprise-grade vendor selection based on capability requirements"""

    def __init__(self):
        self.app = create_app(Config)

    def find_vendors_for_capability(
        self,
        capability_id: int,
        level: Optional[int] = None,
        domain: Optional[str] = None,
        min_coverage: int = 70,
    ) -> List[Dict]:
        """
        Find vendors that support specific capability with L1/L2/L3 filtering

        Args:
            capability_id: Business capability ID
            level: Capability level (1=Strategic, 2=Tactical, 3=Operational)
            domain: Capability domain filter
            min_coverage: Minimum coverage percentage (default 70%)

        Returns:
            List of ranked vendors with coverage scores and implementation details
        """

        with self.app.app_context():
            # Get capability details
            capability = BusinessCapability.query.get(capability_id)
            if not capability:
                raise ValueError(f"Capability {capability_id} not found")

            # Apply level and domain filters
            if level and capability.level != level:
                return []
            if domain and capability.business_domain != domain:
                return []

            # Find vendor capability mappings
            mappings = (
                db.session.query(VendorProductCapability)
                .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
                .filter(
                    VendorProductCapability.business_capability_id == capability_id,
                    VendorProductCapability.coverage_percentage >= min_coverage,
                )
                .all()
            )

            # Rank and format results
            ranked_vendors = []
            for mapping in mappings:
                # Get vendor product details
                vendor_product = VendorProduct.query.get(mapping.vendor_product_id)
                if not vendor_product:
                    continue

                vendor_data = {
                    "vendor_product_id": mapping.vendor_product_id,
                    "vendor_name": vendor_product.name,
                    "vendor_organization": vendor_product.vendor_organization.name
                    if vendor_product.vendor_organization
                    else "Unknown",
                    "coverage_percentage": mapping.coverage_percentage,
                    "maturity_level": mapping.maturity_level,
                    "fit_score": mapping.fit_score or mapping.coverage_percentage,
                    "implementation_complexity": mapping.implementation_complexity,
                    "estimated_weeks": mapping.estimated_implementation_weeks,
                    "customization_required": mapping.customization_required,
                    "integration_complexity": mapping.integration_complexity,
                    "gaps": mapping.get_gaps(),
                    "workarounds": mapping.get_workarounds(),
                    "notes": mapping.notes,
                    "capability_level": capability.level,
                    "capability_domain": capability.business_domain,
                    "capability_name": capability.name,
                }

                # Calculate overall score (weighted)
                vendor_data["overall_score"] = self._calculate_overall_score(vendor_data)
                ranked_vendors.append(vendor_data)

            # Sort by overall score (highest first)
            ranked_vendors.sort(key=lambda x: x["overall_score"], reverse=True)

            return ranked_vendors

    def get_capability_coverage_matrix(self, capability_ids: List[int]) -> Dict:
        """
        Generate vendor vs capability coverage matrix for multiple capabilities

        Args:
            capability_ids: List of capability IDs to analyze

        Returns:
            Matrix with vendors as rows and capabilities as columns
        """

        with self.app.app_context():
            # Get all capabilities
            capabilities = BusinessCapability.query.filter(
                BusinessCapability.id.in_(capability_ids)
            ).all()

            # Build matrix
            matrix = {"capabilities": [], "vendors": {}, "coverage_summary": {}}

            # Add capability details
            for cap in capabilities:
                matrix["capabilities"].append(
                    {
                        "id": cap.id,
                        "name": cap.name,
                        "level": cap.level,
                        "domain": cap.business_domain,
                    }
                )

            # Get all vendor mappings for these capabilities
            mappings = (
                db.session.query(VendorProductCapability)
                .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
                .filter(VendorProductCapability.business_capability_id.in_(capability_ids))
                .all()
            )

            # Group by vendor
            vendor_data = {}
            for mapping in mappings:
                vendor_id = mapping.vendor_product_id
                vendor_product = VendorProduct.query.get(vendor_id)
                if not vendor_product:
                    continue

                vendor_name = vendor_product.name

                if vendor_id not in vendor_data:
                    vendor_data[vendor_id] = {
                        "name": vendor_name,
                        "organization": vendor_product.vendor_organization.name
                        if vendor_product.vendor_organization
                        else "Unknown",
                        "capabilities": {},
                        "total_coverage": 0,
                        "capability_count": 0,
                    }

                vendor_data[vendor_id]["capabilities"][mapping.business_capability_id] = {
                    "coverage": mapping.coverage_percentage,
                    "maturity": mapping.maturity_level,
                    "fit_score": mapping.fit_score or mapping.coverage_percentage,
                    "complexity": mapping.implementation_complexity,
                }

                vendor_data[vendor_id]["total_coverage"] += mapping.coverage_percentage
                vendor_data[vendor_id]["capability_count"] += 1

            # Calculate average coverage and add to matrix
            for vendor_id, data in vendor_data.items():
                if data["capability_count"] > 0:
                    data["average_coverage"] = data["total_coverage"] / data["capability_count"]
                else:
                    data["average_coverage"] = 0

                matrix["vendors"][vendor_id] = data

            # Generate coverage summary
            matrix["coverage_summary"] = {
                "total_vendors": len(vendor_data),
                "capabilities_analyzed": len(capabilities),
                "best_coverage_vendor": max(
                    vendor_data.items(), key=lambda x: x[1]["average_coverage"]
                )
                if vendor_data
                else None,
                "vendors_with_full_coverage": len(
                    [v for v in vendor_data.values() if v["capability_count"] == len(capabilities)]
                ),
            }

            return matrix

    def recommend_vendors(
        self, requirements: Dict, constraints: Optional[Dict] = None
    ) -> List[Dict]:
        """
        AI-powered vendor recommendations based on requirements and constraints

        Args:
            requirements: Dict with capability requirements
                {
                    'primary_capability_id': int,
                    'secondary_capabilities': [int],
                    'min_coverage': int (default 70),
                    'max_complexity': int (default 8),
                    'max_implementation_weeks': int (default 52)
                }
            constraints: Optional constraints like budget, organization size, etc.

        Returns:
            List of recommended vendors with scoring and rationale
        """

        with self.app.app_context():
            recommendations = []

            # Get primary capability vendors
            primary_vendors = self.find_vendors_for_capability(
                requirements["primary_capability_id"],
                min_coverage=requirements.get("min_coverage", 70),
            )

            # Score each vendor against all requirements
            for vendor in primary_vendors:
                score = 0
                max_score = 100

                # Coverage score (40% weight)
                coverage_score = vendor["coverage_percentage"] * 0.4
                score += coverage_score

                # Maturity score (20% weight)
                maturity_score = (vendor["maturity_level"] / 5) * 20
                score += maturity_score

                # Implementation complexity score (20% weight, lower is better)
                complexity_penalty = (vendor["implementation_complexity"] / 10) * 20
                score += 20 - complexity_penalty

                # Multi-capability support (20% weight)
                multi_cap_score = 0
                secondary_caps = requirements.get("secondary_capabilities", [])
                if secondary_caps:
                    supported_secondary = 0
                    for cap_id in secondary_caps:
                        secondary_mappings = (
                            db.session.query(VendorProductCapability)
                            .filter(
                                VendorProductCapability.vendor_product_id
                                == vendor["vendor_product_id"],
                                VendorProductCapability.business_capability_id == cap_id,
                            )
                            .first()
                        )
                        if secondary_mappings:
                            supported_secondary += 1

                    multi_cap_score = (supported_secondary / len(secondary_caps)) * 20
                score += multi_cap_score

                # Apply constraints
                if constraints:
                    # Budget constraint (if provided)
                    if "max_implementation_weeks" in constraints:
                        if vendor["estimated_weeks"] > constraints["max_implementation_weeks"]:
                            score -= 20  # Penalty for exceeding timeline

                    if "max_complexity" in constraints:
                        if vendor["implementation_complexity"] > constraints["max_complexity"]:
                            score -= 15  # Penalty for high complexity

                # Add recommendation details
                recommendation = vendor.copy()
                recommendation["recommendation_score"] = min(score, max_score)
                recommendation["rationale"] = self._generate_rationale(vendor, requirements)
                recommendation["strengths"] = self._identify_strengths(vendor)
                recommendation["considerations"] = self._identify_considerations(vendor)

                recommendations.append(recommendation)

            # Sort by recommendation score
            recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)

            return recommendations[:10]  # Return top 10 recommendations

    def _calculate_overall_score(self, vendor_data: Dict) -> float:
        """Calculate overall vendor score using weighted criteria"""

        weights = {"coverage": 0.4, "maturity": 0.2, "implementation": 0.2, "fit": 0.2}

        # Coverage score (0 - 100)
        coverage_score = vendor_data["coverage_percentage"]

        # Maturity score (0 - 100, based on level 1 - 5)
        maturity_score = (vendor_data["maturity_level"] or 3) * 20

        # Implementation score (0 - 100, lower complexity is better)
        impl_complexity = vendor_data["implementation_complexity"] or 5
        impl_score = max(0, 100 - (impl_complexity * 10))

        # Fit score (0 - 100)
        fit_score = vendor_data["fit_score"] or vendor_data["coverage_percentage"]

        overall_score = (
            coverage_score * weights["coverage"]
            + maturity_score * weights["maturity"]
            + impl_score * weights["implementation"]
            + fit_score * weights["fit"]
        )

        return round(overall_score, 1)

    def _generate_rationale(self, vendor: Dict, requirements: Dict) -> str:
        """Generate recommendation rationale"""

        rationale_parts = []

        # Coverage rationale
        if vendor["coverage_percentage"] >= 90:
            rationale_parts.append(
                f"Excellent {vendor['coverage_percentage']}% coverage of primary requirement"
            )
        elif vendor["coverage_percentage"] >= 80:
            rationale_parts.append(
                f"Strong {vendor['coverage_percentage']}% coverage of primary requirement"
            )
        else:
            rationale_parts.append(
                f"Adequate {vendor['coverage_percentage']}% coverage of primary requirement"
            )

        # Maturity rationale
        if vendor["maturity_level"] >= 4:
            rationale_parts.append("Production-ready with proven track record")
        elif vendor["maturity_level"] >= 3:
            rationale_parts.append("Mature solution with stable implementation")
        else:
            rationale_parts.append("Emerging solution requiring careful consideration")

        # Implementation rationale
        if vendor["implementation_complexity"] <= 4:
            rationale_parts.append("Relatively straightforward implementation")
        elif vendor["implementation_complexity"] <= 7:
            rationale_parts.append("Moderate implementation complexity")
        else:
            rationale_parts.append("Complex implementation requiring expertise")

        return ". ".join(rationale_parts) + "."

    def _identify_strengths(self, vendor: Dict) -> List[str]:
        """Identify vendor strengths"""
        strengths = []

        if vendor["coverage_percentage"] >= 90:
            strengths.append("High capability coverage")

        if vendor["maturity_level"] >= 4:
            strengths.append("Production-ready maturity")

        if vendor["implementation_complexity"] <= 5:
            strengths.append("Manageable implementation complexity")

        if vendor["estimated_weeks"] and vendor["estimated_weeks"] <= 12:
            strengths.append("Quick implementation timeline")

        if not vendor["gaps"]:
            strengths.append("No identified capability gaps")

        return strengths

    def _identify_considerations(self, vendor: Dict) -> List[str]:
        """Identify vendor considerations/risk factors"""
        considerations = []

        if vendor["coverage_percentage"] < 80:
            considerations.append("Lower capability coverage may require workarounds")

        if vendor["maturity_level"] < 3:
            considerations.append("Emerging solution with potential risks")

        if vendor["implementation_complexity"] >= 8:
            considerations.append("High implementation complexity")

        if vendor["estimated_weeks"] and vendor["estimated_weeks"] > 24:
            considerations.append("Extended implementation timeline")

        if vendor["customization_required"]:
            considerations.append("Customization required increases complexity")

        if vendor["gaps"]:
            considerations.append(f"Identified gaps: {', '.join(vendor['gaps'][:2])}")

        return considerations


# Export the class for use in other modules
if __name__ == "__main__":
    # Test the vendor selector when run directly
    selector = CapabilityBasedVendorSelector()
    print("Capability-Based Vendor Selector ready for use!")
