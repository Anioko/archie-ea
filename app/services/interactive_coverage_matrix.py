"""
Interactive Coverage Matrix Service - LLM-PRD - 04 Implementation

Interactive capability-vendor coverage matrix with heatmap visualization,
gap analysis modal, and AI-powered coverage estimation.

Key Features:
- Interactive heatmap showing vendor vs capability coverage
- Color-coded cells (80 - 100%: green, 60 - 79%: yellow, <60%: red)
- Click interactions for detailed gap analysis
- AI coverage estimation from product descriptions
- Responsive design for mobile/desktop
- Real-time matrix updates and filtering
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
)
from app.services.semantic_vendor_discovery import SemanticVendorDiscovery
from app.services.unified_ai_llm_service import UnifiedAILLMService

logger = logging.getLogger(__name__)


@dataclass
class CoverageCell:
    """Represents a single cell in the coverage matrix."""

    vendor_id: int
    vendor_name: str
    product_id: int
    product_name: str
    capability_id: int
    capability_name: str
    coverage_percentage: float
    maturity_level: int
    color_class: str
    confidence_level: str
    gaps: List[str]
    strengths: List[str]


@dataclass
class GapAnalysis:
    """Detailed gap analysis for a specific vendor-capability combination."""

    vendor_name: str
    product_name: str
    capability_name: str
    current_coverage: float
    identified_gaps: List[str]
    workarounds: List[str]
    implementation_options: List[str]
    estimated_effort: str
    risk_factors: List[str]
    recommendations: List[str]
    evidence_sources: List[str]
    ai_estimation_confidence: float


@dataclass
class MatrixFilter:
    """Filter options for the coverage matrix."""

    vendor_categories: List[str]
    capability_domains: List[str]
    minimum_coverage: float
    minimum_maturity: int
    strategic_tiers: List[str]
    deployment_models: List[str]


class InteractiveCoverageMatrix:
    """
    Interactive coverage matrix service with heatmap visualization and gap analysis.
    """

    # Color coding for coverage percentages
    COVERAGE_COLORS = {
        (80, 100): "coverage-high",  # Green
        (60, 79): "coverage-medium",  # Yellow
        (0, 59): "coverage-low",  # Red
    }

    # Confidence level colors
    CONFIDENCE_COLORS = {
        "very_high": "confidence-very-high",
        "high": "confidence-high",
        "medium": "confidence-medium",
        "low": "confidence-low",
    }

    def __init__(self):
        """Initialize the interactive coverage matrix service."""
        self.logger = logging.getLogger(__name__)
        self.semantic_discovery = SemanticVendorDiscovery()
        self.llm_service = UnifiedAILLMService()

    def generate_coverage_matrix(
        self,
        capability_ids: Optional[List[int]] = None,
        vendor_ids: Optional[List[int]] = None,
        filters: Optional[MatrixFilter] = None,
        include_ai_estimation: bool = True,
        max_vendors: int = 20,
        max_capabilities: int = 50,
    ) -> Dict[str, Any]:
        """
        Generate interactive coverage matrix with heatmap visualization.

        Args:
            capability_ids: Specific capability IDs to include (optional)
            vendor_ids: Specific vendor IDs to include (optional)
            filters: Matrix filtering options
            include_ai_estimation: Whether to include AI-powered coverage estimation
            max_vendors: Maximum number of vendors to include
            max_capabilities: Maximum number of capabilities to include

        Returns:
            Comprehensive coverage matrix data
        """

        try:
            # Get capabilities
            capabilities = self._get_capabilities(capability_ids, max_capabilities)

            # Get vendors
            vendors = self._get_vendors(vendor_ids, max_vendors, filters)

            # Build coverage matrix
            matrix_data = self._build_coverage_matrix(capabilities, vendors, filters)

            # Add AI estimation for missing coverage data
            if include_ai_estimation:
                matrix_data = self._add_ai_estimation(matrix_data)

            # Calculate matrix statistics
            matrix_stats = self._calculate_matrix_statistics(matrix_data)

            # Generate visualization data
            visualization_data = self._generate_visualization_data(matrix_data)

            # Create interactive elements
            interactive_elements = self._create_interactive_elements(matrix_data)

            result = {
                "matrix_metadata": {
                    "total_capabilities": len(capabilities),
                    "total_vendors": len(vendors),
                    "matrix_cells": len(matrix_data["cells"]),
                    "ai_estimation_enabled": include_ai_estimation,
                    "generated_at": datetime.utcnow().isoformat(),
                },
                "capabilities": matrix_data["capabilities"],
                "vendors": matrix_data["vendors"],
                "coverage_matrix": matrix_data["cells"],
                "matrix_statistics": matrix_stats,
                "visualization_data": visualization_data,
                "interactive_elements": interactive_elements,
                "color_legend": self._get_color_legend(),
                "filter_options": self._get_filter_options(),
            }

            return result

        except Exception as e:
            self.logger.error(f"Coverage matrix generation failed: {e}")
            raise

    def get_gap_analysis(self, vendor_id: int, product_id: int, capability_id: int) -> GapAnalysis:
        """
        Get detailed gap analysis for a specific vendor-capability combination.

        Args:
            vendor_id: Vendor ID
            product_id: Product ID
            capability_id: Capability ID

        Returns:
            Detailed gap analysis
        """

        try:
            # Get vendor and capability information
            vendor_product = self._get_vendor_product(vendor_id, product_id)
            capability = self._get_capability(capability_id)

            if not vendor_product or not capability:
                raise ValueError("Vendor product or capability not found")

            # Get existing coverage data
            coverage_data = self._get_coverage_data(product_id, capability_id)

            # Generate gap analysis using AI
            gap_analysis = self._generate_ai_gap_analysis(vendor_product, capability, coverage_data)

            return gap_analysis

        except Exception as e:
            self.logger.error(f"Gap analysis failed: {e}")
            raise

    def estimate_coverage_from_description(
        self, vendor_product_id: int, capability_id: int
    ) -> Dict[str, Any]:
        """
        Estimate coverage percentage from product description using AI.

        Args:
            vendor_product_id: Vendor product ID
            capability_id: Capability ID

        Returns:
            AI-powered coverage estimation
        """

        try:
            # Get product and capability information
            vendor_product = self._get_vendor_product_by_id(vendor_product_id)
            capability = self._get_capability(capability_id)

            if not vendor_product or not capability:
                raise ValueError("Vendor product or capability not found")

            # Build AI prompt for coverage estimation
            prompt = self._build_coverage_estimation_prompt(vendor_product, capability)

            # Generate AI response
            llm_response = self.llm_service.generate_response(
                prompt=prompt, response_format="json", max_tokens=500
            )

            if llm_response and llm_response.get("success"):
                estimation_data = llm_response.get("data", {})

                return {
                    "estimated_coverage": estimation_data.get("coverage_percentage", 50),
                    "confidence_level": estimation_data.get("confidence_level", "medium"),
                    "reasoning": estimation_data.get("reasoning", ""),
                    "identified_strengths": estimation_data.get("strengths", []),
                    "potential_gaps": estimation_data.get("gaps", []),
                    "estimation_method": "ai_powered",
                    "generated_at": datetime.utcnow().isoformat(),
                }
            else:
                # Fallback estimation
                return self._generate_fallback_estimation(vendor_product, capability)

        except Exception as e:
            self.logger.error(f"Coverage estimation failed: {e}")
            return self._generate_fallback_estimation(vendor_product, capability)

    def _get_capabilities(
        self, capability_ids: Optional[List[int]], max_capabilities: int
    ) -> List[BusinessCapability]:
        """Get capabilities for the matrix."""

        query = BusinessCapability.query

        if capability_ids:
            query = query.filter(BusinessCapability.id.in_(capability_ids))

        capabilities = query.order_by(BusinessCapability.name).limit(max_capabilities).all()

        return capabilities

    def _get_vendors(
        self, vendor_ids: Optional[List[int]], max_vendors: int, filters: Optional[MatrixFilter]
    ) -> List[Dict[str, Any]]:
        """Get vendors for the matrix."""

        query = db.session.query(VendorOrganization, VendorProduct).join(VendorProduct)

        if vendor_ids:
            query = query.filter(VendorOrganization.id.in_(vendor_ids))

        # Apply filters
        if filters:
            if filters.vendor_categories:
                query = query.filter(VendorOrganization.vendor_type.in_(filters.vendor_categories))

            if filters.strategic_tiers:
                query = query.filter(VendorOrganization.strategic_tier.in_(filters.strategic_tiers))

            if filters.deployment_models:
                query = query.filter(
                    VendorProduct.deployment_model.in_(filters.deployment_models)
                )

        vendors = query.limit(max_vendors).all()

        vendor_list = []
        for vendor, product in vendors:
            vendor_list.append(
                {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "product_id": product.id,
                    "product_name": product.name,
                    "category": vendor.vendor_type,
                    "strategic_tier": vendor.strategic_tier,
                    "deployment_models": [product.deployment_model] if product.deployment_model else [],
                }
            )

        return vendor_list

    def _build_coverage_matrix(
        self,
        capabilities: List[BusinessCapability],
        vendors: List[Dict[str, Any]],
        filters: Optional[MatrixFilter],
    ) -> Dict[str, Any]:
        """Build the coverage matrix data structure."""

        matrix_cells = []

        for vendor_data in vendors:
            for capability in capabilities:
                # Get coverage data
                coverage_data = self._get_coverage_data(vendor_data["product_id"], capability.id)

                # Create coverage cell
                cell = self._create_coverage_cell(vendor_data, capability, coverage_data)

                # Apply filters
                if self._passes_filters(cell, filters):
                    matrix_cells.append(cell)

        return {
            "capabilities": [
                {
                    "id": cap.id,
                    "name": cap.name,
                    "description": cap.description,
                    "domain": cap.business_domain,
                    "level": cap.level,
                }
                for cap in capabilities
            ],
            "vendors": vendors,
            "cells": matrix_cells,
        }

    def _get_coverage_data(self, product_id: int, capability_id: int) -> Optional[Dict[str, Any]]:
        """Get existing coverage data for a product-capability combination."""

        coverage = (
            db.session.query(VendorProductCapability)
            .filter_by(vendor_product_id=product_id, business_capability_id=capability_id)
            .first()
        )

        if coverage:
            return {
                "coverage_percentage": coverage.coverage_percentage,
                "maturity_level": coverage.maturity_level,
                "gaps": coverage.gaps or [],
                "strengths": coverage.strengths or [],
                "confidence_score": getattr(coverage, "confidence_score", None) or 0.8,
            }

        return None

    def _create_coverage_cell(
        self,
        vendor_data: Dict[str, Any],
        capability: BusinessCapability,
        coverage_data: Optional[Dict[str, Any]],
    ) -> CoverageCell:
        """Create a coverage cell for the matrix."""

        if coverage_data:
            coverage_percentage = coverage_data["coverage_percentage"]
            maturity_level = coverage_data["maturity_level"]
            gaps = coverage_data.get("gaps", [])
            strengths = coverage_data.get("strengths", [])
            confidence_score = coverage_data.get("confidence_score", 0.8)
        else:
            # Default values for missing data
            coverage_percentage = 0
            maturity_level = 1
            gaps = []
            strengths = []
            confidence_score = 0.0

        # Determine color class
        color_class = self._get_coverage_color_class(coverage_percentage)

        # Determine confidence level
        confidence_level = self._get_confidence_level(confidence_score)

        return CoverageCell(
            vendor_id=vendor_data["vendor_id"],
            vendor_name=vendor_data["vendor_name"],
            product_id=vendor_data["product_id"],
            product_name=vendor_data["product_name"],
            capability_id=capability.id,
            capability_name=capability.name,
            coverage_percentage=coverage_percentage,
            maturity_level=maturity_level,
            color_class=color_class,
            confidence_level=confidence_level,
            gaps=gaps,
            strengths=strengths,
        )

    def _get_coverage_color_class(self, coverage_percentage: float) -> str:
        """Get color class based on coverage percentage."""

        for (min_cov, max_cov), color_class in self.COVERAGE_COLORS.items():
            if min_cov <= coverage_percentage <= max_cov:
                return color_class

        return "coverage-none"

    def _get_confidence_level(self, confidence_score: float) -> str:
        """Get confidence level based on confidence score."""

        if confidence_score >= 0.9:
            return "very_high"
        elif confidence_score >= 0.7:
            return "high"
        elif confidence_score >= 0.5:
            return "medium"
        else:
            return "low"

    def _passes_filters(self, cell: CoverageCell, filters: Optional[MatrixFilter]) -> bool:
        """Check if a cell passes the applied filters."""

        if not filters:
            return True

        # Coverage filter
        if cell.coverage_percentage < filters.minimum_coverage:
            return False

        # Maturity filter
        if cell.maturity_level < filters.minimum_maturity:
            return False

        return True

    def _add_ai_estimation(self, matrix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add AI-powered estimation for missing coverage data."""

        enhanced_cells = []

        for cell in matrix_data["cells"]:
            if cell.coverage_percentage == 0:  # Missing coverage data
                try:
                    # Estimate coverage using AI
                    estimation = self.estimate_coverage_from_description(
                        cell.product_id, cell.capability_id
                    )

                    # Update cell with estimated data
                    cell.coverage_percentage = estimation["estimated_coverage"]
                    cell.confidence_level = estimation["confidence_level"]
                    cell.ai_estimated = True
                    cell.ai_reasoning = estimation["reasoning"]

                except Exception as e:
                    self.logger.warning(f"AI estimation failed for cell: {e}")
                    cell.ai_estimated = False

            enhanced_cells.append(cell)

        matrix_data["cells"] = enhanced_cells
        return matrix_data

    def _calculate_matrix_statistics(self, matrix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistics for the coverage matrix."""

        cells = matrix_data["cells"]

        if not cells:
            return {
                "total_cells": 0,
                "average_coverage": 0,
                "high_coverage_count": 0,
                "medium_coverage_count": 0,
                "low_coverage_count": 0,
                "no_coverage_count": 0,
            }

        coverage_values = [cell.coverage_percentage for cell in cells]
        average_coverage = sum(coverage_values) / len(coverage_values)

        # Count by coverage level
        high_coverage = len([c for c in cells if c.coverage_percentage >= 80])
        medium_coverage = len([c for c in cells if 60 <= c.coverage_percentage < 80])
        low_coverage = len([c for c in cells if 0 < c.coverage_percentage < 60])
        no_coverage = len([c for c in cells if c.coverage_percentage == 0])

        return {
            "total_cells": len(cells),
            "average_coverage": round(average_coverage, 2),
            "high_coverage_count": high_coverage,
            "medium_coverage_count": medium_coverage,
            "low_coverage_count": low_coverage,
            "no_coverage_count": no_coverage,
            "coverage_distribution": {
                "high": high_coverage,
                "medium": medium_coverage,
                "low": low_coverage,
                "none": no_coverage,
            },
        }

    def _generate_visualization_data(self, matrix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for heatmap visualization."""

        heatmap_data = []

        for cell in matrix_data["cells"]:
            heatmap_data.append(
                {
                    "x": cell.capability_name,
                    "y": cell.vendor_name,
                    "value": cell.coverage_percentage,
                    "color": cell.color_class,
                    "confidence": cell.confidence_level,
                    "maturity": cell.maturity_level,
                    "vendor_id": cell.vendor_id,
                    "product_id": cell.product_id,
                    "capability_id": cell.capability_id,
                }
            )

        return {
            "heatmap_data": heatmap_data,
            "x_axis": [cell["x"] for cell in heatmap_data],
            "y_axis": [cell["y"] for cell in heatmap_data],
            "color_scale": [
                {"range": [80, 100], "color": "#22c55e", "label": "High Coverage"},
                {"range": [60, 79], "color": "#eab308", "label": "Medium Coverage"},
                {"range": [0, 59], "color": "#ef4444", "label": "Low Coverage"},
            ],
        }

    def _create_interactive_elements(self, matrix_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create interactive elements for the matrix."""

        interactive_elements = {
            "click_actions": [
                {
                    "type": "gap_analysis",
                    "description": "Click any cell to view detailed gap analysis",
                    "endpoint": "/api/coverage-matrix/gap-analysis",
                    "parameters": ["vendor_id", "product_id", "capability_id"],
                }
            ],
            "hover_info": [
                {"field": "coverage_percentage", "label": "Coverage", "format": "percentage"},
                {"field": "maturity_level", "label": "Maturity", "format": "level"},
                {"field": "confidence_level", "label": "Confidence", "format": "confidence"},
            ],
            "filter_options": self._get_filter_options(),
        }

        return interactive_elements

    def _get_color_legend(self) -> List[Dict[str, Any]]:
        """Get color legend for the heatmap."""

        return [
            {
                "color": "#22c55e",
                "range": "80 - 100%",
                "label": "High Coverage",
                "description": "Strong capability coverage",
            },
            {
                "color": "#eab308",
                "range": "60 - 79%",
                "label": "Medium Coverage",
                "description": "Moderate capability coverage",
            },
            {
                "color": "#ef4444",
                "range": "0 - 59%",
                "label": "Low Coverage",
                "description": "Limited capability coverage",
            },
        ]

    def _get_filter_options(self) -> Dict[str, List[str]]:
        """Get available filter options."""

        # Get vendor categories
        vendor_categories = db.session.query(VendorOrganization.vendor_type).distinct().all()

        # Get capability domains
        capability_domains = db.session.query(BusinessCapability.business_domain).distinct().all()

        # Get strategic tiers
        strategic_tiers = db.session.query(VendorOrganization.strategic_tier).distinct().all()

        return {
            "vendor_categories": [cat[0] for cat in vendor_categories if cat[0]],
            "capability_domains": [dom[0] for dom in capability_domains if dom[0]],
            "strategic_tiers": [tier[0] for tier in strategic_tiers if tier[0]],
            "deployment_models": ["cloud", "on-premise", "hybrid"],
            "maturity_levels": [1, 2, 3, 4, 5],
        }

    def _generate_ai_gap_analysis(
        self,
        vendor_product: VendorProduct,
        capability: BusinessCapability,
        coverage_data: Optional[Dict[str, Any]],
    ) -> GapAnalysis:
        """Generate AI-powered gap analysis."""

        try:
            # Build AI prompt
            prompt = self._build_gap_analysis_prompt(vendor_product, capability, coverage_data)

            # Generate AI response
            llm_response = self.llm_service.generate_response(
                prompt=prompt, response_format="json", max_tokens=1000
            )

            if llm_response and llm_response.get("success"):
                analysis_data = llm_response.get("data", {})

                return GapAnalysis(
                    vendor_name=vendor_product.vendor_organization.name,
                    product_name=vendor_product.name,
                    capability_name=capability.name,
                    current_coverage=coverage_data["coverage_percentage"] if coverage_data else 0,
                    identified_gaps=analysis_data.get("gaps", []),
                    workarounds=analysis_data.get("workarounds", []),
                    implementation_options=analysis_data.get("implementation_options", []),
                    estimated_effort=analysis_data.get("estimated_effort", "medium"),
                    risk_factors=analysis_data.get("risk_factors", []),
                    recommendations=analysis_data.get("recommendations", []),
                    evidence_sources=analysis_data.get("evidence_sources", []),
                    ai_estimation_confidence=analysis_data.get("confidence", 0.7),
                )
            else:
                # Fallback gap analysis
                return self._generate_fallback_gap_analysis(
                    vendor_product, capability, coverage_data
                )

        except Exception as e:
            self.logger.error(f"AI gap analysis failed: {e}")
            return self._generate_fallback_gap_analysis(vendor_product, capability, coverage_data)

    def _build_gap_analysis_prompt(
        self,
        vendor_product: VendorProduct,
        capability: BusinessCapability,
        coverage_data: Optional[Dict[str, Any]],
    ) -> str:
        """Build AI prompt for gap analysis."""

        current_coverage = coverage_data["coverage_percentage"] if coverage_data else 0
        existing_gaps = coverage_data.get("gaps", []) if coverage_data else []

        prompt = f"""
Analyze the gap between vendor product capability and business requirements:

VENDOR PRODUCT:
- Vendor: {vendor_product.vendor_organization.name}
- Product: {vendor_product.name}
- Description: {vendor_product.description}
- Category: {vendor_product.product_type}

BUSINESS CAPABILITY:
- Name: {capability.name}
- Description: {capability.description}
- Domain: {capability.business_domain}
- Level: {capability.level}

CURRENT STATUS:
- Coverage: {current_coverage}%
- Known Gaps: {', '.join(existing_gaps) if existing_gaps else 'None identified'}

Provide a comprehensive gap analysis in JSON format:
{{
    "gaps": ["gap1", "gap2", "gap3"],
    "workarounds": ["workaround1", "workaround2"],
    "implementation_options": ["option1", "option2"],
    "estimated_effort": "low/medium/high",
    "risk_factors": ["risk1", "risk2"],
    "recommendations": ["recommendation1", "recommendation2"],
    "evidence_sources": ["source1", "source2"],
    "confidence": 0.8
}}
"""

        return prompt

    def _build_coverage_estimation_prompt(
        self, vendor_product: VendorProduct, capability: BusinessCapability
    ) -> str:
        """Build AI prompt for coverage estimation."""

        prompt = f"""
Estimate the coverage percentage of a business capability by a vendor product:

VENDOR PRODUCT:
- Vendor: {vendor_product.vendor_organization.name}
- Product: {vendor_product.name}
- Description: {vendor_product.description}
- Category: {vendor_product.product_type}
- Target Industries: {vendor_product.industry_focus or 'N/A'}

BUSINESS CAPABILITY:
- Name: {capability.name}
- Description: {capability.description}
- Domain: {capability.business_domain}
- Level: {capability.level}

Based on the product description and capability requirements, estimate:
1. Coverage percentage (0 - 100)
2. Confidence level (very_high/high/medium/low)
3. Reasoning for the estimation
4. Identified strengths
5. Potential gaps

Provide response in JSON format:
{{
    "coverage_percentage": 75,
    "confidence_level": "high",
    "reasoning": "Based on product features...",
    "strengths": ["strength1", "strength2"],
    "gaps": ["gap1", "gap2"]
}}
"""

        return prompt

    def _generate_fallback_gap_analysis(
        self,
        vendor_product: VendorProduct,
        capability: BusinessCapability,
        coverage_data: Optional[Dict[str, Any]],
    ) -> GapAnalysis:
        """Generate fallback gap analysis when AI fails."""

        current_coverage = coverage_data["coverage_percentage"] if coverage_data else 0

        return GapAnalysis(
            vendor_name=vendor_product.vendor_organization.name,
            product_name=vendor_product.name,
            capability_name=capability.name,
            current_coverage=current_coverage,
            identified_gaps=coverage_data.get("gaps", [])
            if coverage_data
            else ["No detailed analysis available"],
            workarounds=["Manual processes", "Third-party integrations"],
            implementation_options=["Standard configuration", "Custom development"],
            estimated_effort="medium",
            risk_factors=["Limited documentation", "Integration complexity"],
            recommendations=[
                "Conduct detailed requirements analysis",
                "Consider vendor consultation",
            ],
            evidence_sources=["Product documentation", "Vendor website"],
            ai_estimation_confidence=0.3,
        )

    def _generate_fallback_estimation(
        self, vendor_product: VendorProduct, capability: BusinessCapability
    ) -> Dict[str, Any]:
        """Generate fallback coverage estimation."""

        # Simple heuristic based on product category and capability domain
        category_match = (vendor_product.product_type or "").lower() in capability.description.lower()

        if category_match:
            estimated_coverage = 75
            confidence_level = "medium"
        else:
            estimated_coverage = 45
            confidence_level = "low"

        return {
            "estimated_coverage": estimated_coverage,
            "confidence_level": confidence_level,
            "reasoning": "Fallback estimation based on category matching",
            "identified_strengths": ["Basic functionality"],
            "potential_gaps": ["Limited domain-specific features"],
            "estimation_method": "heuristic_fallback",
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _get_vendor_product(self, vendor_id: int, product_id: int) -> Optional[VendorProduct]:
        """Get vendor product by IDs."""
        return (
            db.session.query(VendorProduct)
            .filter_by(id=product_id, vendor_organization_id=vendor_id)
            .first()
        )

    def _get_vendor_product_by_id(self, product_id: int) -> Optional[VendorProduct]:
        """Get vendor product by product ID."""
        return db.session.query(VendorProduct).filter_by(id=product_id).first()

    def _get_capability(self, capability_id: int) -> Optional[BusinessCapability]:
        """Get business capability by ID."""
        return db.session.query(BusinessCapability).filter_by(id=capability_id).first()


# Convenience function for direct usage
def generate_coverage_matrix(
    capability_ids: Optional[List[int]] = None,
    vendor_ids: Optional[List[int]] = None,
    max_vendors: int = 20,
    max_capabilities: int = 50,
) -> Dict[str, Any]:
    """
    Convenience function to generate coverage matrix.

    Args:
        capability_ids: Specific capability IDs to include
        vendor_ids: Specific vendor IDs to include
        max_vendors: Maximum number of vendors
        max_capabilities: Maximum number of capabilities

    Returns:
        Coverage matrix data
    """
    service = InteractiveCoverageMatrix()
    return service.generate_coverage_matrix(
        capability_ids=capability_ids,
        vendor_ids=vendor_ids,
        max_vendors=max_vendors,
        max_capabilities=max_capabilities,
    )


if __name__ == "__main__":
    # Test the interactive coverage matrix
    logging.basicConfig(level=logging.INFO)

    print("Testing Interactive Coverage Matrix...")

    service = InteractiveCoverageMatrix()

    # Test color coding
    print(f"Coverage colors: {len(service.COVERAGE_COLORS)}")
    print(f"Confidence colors: {len(service.CONFIDENCE_COLORS)}")

    # Test matrix generation (small scale)
    try:
        matrix = service.generate_coverage_matrix(max_vendors=5, max_capabilities=10)
        print(f"Generated matrix with {matrix['matrix_metadata']['total_cells']} cells")
    except Exception as e:
        print(f"Matrix generation test failed: {e}")
