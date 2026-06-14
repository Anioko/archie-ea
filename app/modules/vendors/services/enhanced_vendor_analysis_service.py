"""
-> app.modules.vendors.services.analysis_service

Enhanced Vendor Analysis Service

This service extends the existing vendor analysis capabilities with
improved classifications and quality metrics from the enhanced dataset.
"""

import logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import joinedload

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor import VendorOrganization, VendorProduct

logger = logging.getLogger(__name__)


class EnhancedVendorAnalysisService:
    """
    Enhanced vendor analysis service that leverages improved dataset classifications
    and quality metrics for better vendor evaluation and selection.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_domain_coverage(self, vendor_ids: Optional[List[int]] = None) -> Dict:
        """
        Analyze domain coverage across vendor portfolio.

        Args:
            vendor_ids: Optional list of vendor IDs to analyze

        Returns:
            Dictionary with domain coverage analysis
        """
        try:
            # Build query
            query = VendorProduct.query.options(joinedload(VendorProduct.vendor_organization))

            if vendor_ids:
                query = query.filter(VendorProduct.vendor_organization_id.in_(vendor_ids))

            products = query.all()

            # Domain analysis
            domain_stats = defaultdict(
                lambda: {
                    "count": 0,
                    "vendors": set(),
                    "high_confidence": 0,
                    "avg_capabilities": 0,
                    "avg_quality_score": 0,
                }
            )

            for product in products:
                domain = product.domain or "Unknown"
                domain_stats[domain]["count"] += 1
                domain_stats[domain]["vendors"].add(product.vendor_organization_id)

                if product.classification_confidence == "high":
                    domain_stats[domain]["high_confidence"] += 1

                # Calculate capabilities count
                cap_count = len(product.capabilities) if product.capabilities else 0
                domain_stats[domain]["avg_capabilities"] += cap_count

                # Calculate quality score
                domain_stats[domain]["avg_quality_score"] += product.get_quality_score()

            # Calculate averages
            for domain, stats in domain_stats.items():
                if stats["count"] > 0:
                    stats["avg_capabilities"] = stats["avg_capabilities"] / stats["count"]
                    stats["avg_quality_score"] = stats["avg_quality_score"] / stats["count"]
                    stats["vendor_count"] = len(stats["vendors"])
                else:
                    stats["vendor_count"] = 0

                # Convert sets to lists for JSON serialization
                stats["vendors"] = list(stats["vendors"])

            # Coverage analysis
            total_products = len(products)
            domain_coverage = {
                domain: {
                    "percentage": (stats["count"] / total_products * 100)
                    if total_products > 0
                    else 0,
                    "confidence_quality": (stats["high_confidence"] / stats["count"] * 100)
                    if stats["count"] > 0
                    else 0,
                    **stats,
                }
                for domain, stats in domain_stats.items()
            }

            return {
                "total_products": total_products,
                "domain_coverage": domain_coverage,
                "domains_by_coverage": sorted(
                    domain_coverage.items(), key=lambda x: x[1]["percentage"], reverse=True
                ),
                "high_quality_domains": [
                    domain
                    for domain, stats in domain_coverage.items()
                    if stats["avg_quality_score"] >= 80
                ],
            }

        except Exception as e:
            logger.error(f"Error in domain coverage analysis: {str(e)}")
            return {"error": str(e)}

    def analyze_capability_gaps(
        self, target_capabilities: List[str], vendor_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Analyze capability gaps across vendor portfolio.

        Args:
            target_capabilities: List of required capabilities
            vendor_ids: Optional list of vendor IDs to analyze

        Returns:
            Dictionary with capability gap analysis
        """
        try:
            # Build query
            query = VendorProduct.query.options(joinedload(VendorProduct.vendor_organization))

            if vendor_ids:
                query = query.filter(VendorProduct.vendor_organization_id.in_(vendor_ids))

            products = query.all()

            # Capability analysis
            capability_coverage = defaultdict(
                lambda: {
                    "covered_by": [],
                    "vendor_count": 0,
                    "high_confidence_vendors": 0,
                    "domains": set(),
                }
            )

            for product in products:
                if not product.capabilities:
                    continue

                product_caps = set(product.capabilities)
                vendor_name = (
                    product.vendor_organization.name if product.vendor_organization else "Unknown"
                )

                for capability in target_capabilities:
                    if capability in product_caps:
                        capability_coverage[capability]["covered_by"].append(
                            {
                                "vendor": vendor_name,
                                "product": product.name,
                                "product_id": product.id,
                                "confidence": product.classification_confidence,
                                "domain": product.domain,
                                "quality_score": product.get_quality_score(),
                            }
                        )
                        capability_coverage[capability]["vendor_count"] += 1

                        if product.classification_confidence == "high":
                            capability_coverage[capability]["high_confidence_vendors"] += 1

                        if product.domain:
                            capability_coverage[capability]["domains"].add(product.domain)

            # Calculate coverage statistics
            total_vendors = len(set(p.vendor_organization_id for p in products))

            capability_analysis = {}
            for capability, coverage in capability_coverage.items():
                coverage["coverage_percentage"] = (
                    (coverage["vendor_count"] / total_vendors * 100) if total_vendors > 0 else 0
                )
                coverage["high_confidence_percentage"] = (
                    (coverage["high_confidence_vendors"] / coverage["vendor_count"] * 100)
                    if coverage["vendor_count"] > 0
                    else 0
                )
                coverage["domain_diversity"] = len(coverage["domains"])
                coverage["domains"] = list(coverage["domains"])

                # Sort vendors by quality score
                coverage["covered_by"].sort(key=lambda x: x["quality_score"], reverse=True)

                capability_analysis[capability] = coverage

            # Identify gaps and recommendations
            uncovered_capabilities = [
                cap for cap in target_capabilities if cap not in capability_analysis
            ]
            low_coverage_capabilities = [
                cap
                for cap, analysis in capability_analysis.items()
                if analysis["coverage_percentage"] < 30
            ]

            return {
                "target_capabilities": target_capabilities,
                "total_vendors": total_vendors,
                "capability_analysis": capability_analysis,
                "coverage_summary": {
                    "fully_covered": len(
                        [
                            cap
                            for cap, analysis in capability_analysis.items()
                            if analysis["coverage_percentage"] >= 80
                        ]
                    ),
                    "partially_covered": len(
                        [
                            cap
                            for cap, analysis in capability_analysis.items()
                            if 30 <= analysis["coverage_percentage"] < 80
                        ]
                    ),
                    "uncovered": len(uncovered_capabilities),
                    "low_coverage": len(low_coverage_capabilities),
                },
                "gaps": {
                    "uncovered_capabilities": uncovered_capabilities,
                    "low_coverage_capabilities": low_coverage_capabilities,
                },
                "recommendations": self._generate_capability_recommendations(
                    capability_analysis, uncovered_capabilities, low_coverage_capabilities
                ),
            }

        except Exception as e:
            logger.error(f"Error in capability gap analysis: {str(e)}")
            return {"error": str(e)}

    def analyze_quality_metrics(self, vendor_ids: Optional[List[int]] = None) -> Dict:
        """
        Analyze quality metrics across vendor portfolio.

        Args:
            vendor_ids: Optional list of vendor IDs to analyze

        Returns:
            Dictionary with quality metrics analysis
        """
        try:
            # Build query
            query = VendorProduct.query.options(joinedload(VendorProduct.vendor_organization))

            if vendor_ids:
                query = query.filter(VendorProduct.vendor_organization_id.in_(vendor_ids))

            products = query.all()

            if not products:
                return {"error": "No products found"}

            # Quality metrics
            quality_scores = [p.get_quality_score() for p in products]
            confidence_distribution = Counter(p.classification_confidence for p in products)

            # Domain quality analysis
            domain_quality = defaultdict(
                lambda: {"products": [], "avg_score": 0, "confidence_distribution": Counter()}
            )

            for product in products:
                domain = product.domain or "Unknown"
                score = product.get_quality_score()

                domain_quality[domain]["products"].append(
                    {
                        "product_name": product.name,
                        "vendor_name": product.vendor_organization.name
                        if product.vendor_organization
                        else "Unknown",
                        "quality_score": score,
                        "confidence": product.classification_confidence,
                        "capability_count": len(product.capabilities)
                        if product.capabilities
                        else 0,
                        "process_count": len(product.apqc_processes)
                        if product.apqc_processes
                        else 0,
                    }
                )

                domain_quality[domain]["avg_score"] += score
                domain_quality[domain]["confidence_distribution"][
                    product.classification_confidence
                ] += 1

            # Calculate averages
            for domain, stats in domain_quality.items():
                if stats["products"]:
                    stats["avg_score"] = stats["avg_score"] / len(stats["products"])
                    stats["product_count"] = len(stats["products"])
                else:
                    stats["product_count"] = 0

            # Overall statistics
            avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

            return {
                "overall_metrics": {
                    "total_products": len(products),
                    "average_quality_score": round(avg_quality_score, 1),
                    "confidence_distribution": dict(confidence_distribution),
                    "high_confidence_percentage": (
                        confidence_distribution.get("high", 0) / len(products) * 100
                    ),
                    "quality_distribution": {
                        "high_quality": len([s for s in quality_scores if s >= 80]),
                        "medium_quality": len([s for s in quality_scores if 60 <= s < 80]),
                        "low_quality": len([s for s in quality_scores if s < 60]),
                    },
                },
                "domain_quality": dict(domain_quality),
                "quality_recommendations": self._generate_quality_recommendations(
                    domain_quality, confidence_distribution
                ),
                "top_quality_products": sorted(
                    [
                        {
                            "product_name": p.name,
                            "vendor_name": p.vendor_organization.name
                            if p.vendor_organization
                            else "Unknown",
                            "domain": p.domain,
                            "quality_score": p.get_quality_score(),
                            "confidence": p.classification_confidence,
                        }
                        for p in products
                    ],
                    key=lambda x: x["quality_score"],
                    reverse=True,
                )[:10],
            }

        except Exception as e:
            logger.error(f"Error in quality metrics analysis: {str(e)}")
            return {"error": str(e)}

    def recommend_vendors(self, requirements: Dict, limit: int = 10) -> Dict:
        """
        Recommend vendors based on requirements using improved classifications.

        Args:
            requirements: Dictionary containing requirements
                - domains: List of preferred domains
                - capabilities: List of required capabilities
                - min_confidence: Minimum confidence level
                - max_vendors_per_domain: Maximum vendors per domain
            limit: Maximum number of recommendations

        Returns:
            Dictionary with vendor recommendations
        """
        try:
            # Extract requirements
            preferred_domains = requirements.get("domains", [])
            required_capabilities = requirements.get("capabilities", [])
            min_confidence = requirements.get("min_confidence", "medium")
            max_vendors_per_domain = requirements.get("max_vendors_per_domain", 3)

            # Build query with filters
            query = VendorProduct.query.options(joinedload(VendorProduct.vendor_organization))

            # Filter by confidence
            if min_confidence:
                query = query.filter(VendorProduct.classification_confidence >= min_confidence)

            # Filter by domains if specified
            if preferred_domains:
                query = query.filter(VendorProduct.domain.in_(preferred_domains))

            products = query.all()

            # Score products based on requirements
            scored_products = []
            for product in products:
                score = 0
                reasons = []

                # Domain matching
                if preferred_domains and product.domain in preferred_domains:
                    score += 30
                    reasons.append(f"Domain match: {product.domain}")

                # Capability matching
                if required_capabilities and product.capabilities:
                    matching_caps = set(required_capabilities) & set(product.capabilities)
                    cap_score = (len(matching_caps) / len(required_capabilities)) * 40
                    score += cap_score
                    if matching_caps:
                        reasons.append(
                            f"Capability match: {len(matching_caps)}/{len(required_capabilities)}"
                        )

                # Quality score
                quality_score = product.get_quality_score()
                score += quality_score * 0.3
                if quality_score >= 80:
                    reasons.append("High quality classification")

                # ArchiMate template availability
                if product.has_archimate_template:
                    score += 10
                    reasons.append("Has ArchiMate template")

                scored_products.append(
                    {
                        "product": product,
                        "score": score,
                        "reasons": reasons,
                        "details": {
                            "vendor_name": product.vendor_organization.name
                            if product.vendor_organization
                            else "Unknown",
                            "domain": product.domain,
                            "confidence": product.classification_confidence,
                            "quality_score": quality_score,
                            "capability_count": len(product.capabilities)
                            if product.capabilities
                            else 0,
                            "has_template": product.has_archimate_template,
                        },
                    }
                )

            # Sort by score
            scored_products.sort(key=lambda x: x["score"], reverse=True)

            # Limit per domain
            domain_counts = defaultdict(int)
            recommendations = []

            for scored_product in scored_products:
                domain = scored_product["details"]["domain"]

                if domain_counts[domain] < max_vendors_per_domain:
                    recommendations.append(scored_product)
                    domain_counts[domain] += 1

                if len(recommendations) >= limit:
                    break

            return {
                "requirements": requirements,
                "total_candidates": len(scored_products),
                "recommendations": recommendations[:limit],
                "domain_distribution": dict(domain_counts),
                "recommendation_summary": {
                    "domains_covered": len(domain_counts),
                    "avg_score": sum(r["score"] for r in recommendations) / len(recommendations)
                    if recommendations
                    else 0,
                    "high_confidence_count": len(
                        [r for r in recommendations if r["details"]["confidence"] == "high"]
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error in vendor recommendations: {str(e)}")
            return {"error": str(e)}

    def _generate_capability_recommendations(
        self, capability_analysis: Dict, uncovered: List[str], low_coverage: List[str]
    ) -> List[str]:
        """Generate recommendations based on capability analysis."""
        recommendations = []

        if uncovered:
            recommendations.append(
                f"Critical gaps found: {', '.join(uncovered)}. Consider finding vendors for these capabilities."
            )

        if low_coverage:
            recommendations.append(
                f"Low coverage capabilities: {', '.join(low_coverage)}. Consider diversifying vendors."
            )

        # Check for single-vendor dependencies
        single_vendor_caps = [
            cap for cap, analysis in capability_analysis.items() if analysis["vendor_count"] == 1
        ]

        if single_vendor_caps:
            recommendations.append(
                f"Single-vendor dependencies: {', '.join(single_vendor_caps)}. Consider backup vendors."
            )

        return recommendations

    def _generate_quality_recommendations(
        self, domain_quality: Dict, confidence_distribution: Counter
    ) -> List[str]:
        """Generate recommendations based on quality analysis."""
        recommendations = []

        # Confidence recommendations
        total_products = sum(confidence_distribution.values())
        low_confidence_pct = (
            (confidence_distribution.get("low", 0) / total_products * 100)
            if total_products > 0
            else 0
        )

        if low_confidence_pct > 30:
            recommendations.append(
                f"{low_confidence_pct:.1f}% of products have low confidence classification. Consider reviewing and improving data quality."
            )

        # Domain quality recommendations
        low_quality_domains = [
            domain
            for domain, stats in domain_quality.items()
            if stats["avg_score"] < 60 and stats["product_count"] > 5
        ]

        if low_quality_domains:
            recommendations.append(
                f"Low quality domains: {', '.join(low_quality_domains)}. Focus improvement efforts here."
            )

        return recommendations
