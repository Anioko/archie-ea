"""
Market Intelligence Service

Provides market intelligence data enrichment for solutions, including:
- Industry trend analysis
- Competitive landscape assessment
- Technology adoption rates
- Vendor market positioning

This service degrades gracefully when external data sources are unavailable.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketIntelligenceService:
    """Provides market intelligence data for strategic solution analysis."""

    def get_industry_trends(self, industry: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve industry trends for a given sector.

        Args:
            industry: Industry sector name (e.g. 'Financial Services', 'Healthcare')
            limit: Maximum number of trends to return

        Returns:
            List of trend dicts with keys: name, description, adoption_rate, horizon
        """
        try:
            from app import db
            from app.models.models import ArchiMateElement
            elements = (
                db.session.query(ArchiMateElement)
                .filter(ArchiMateElement.type == "trend")
                .limit(limit)
                .all()
            )
            return [
                {
                    "name": el.name,
                    "description": getattr(el, "description", ""),
                    "adoption_rate": None,
                    "horizon": None,
                }
                for el in elements
            ]
        except Exception as exc:
            logger.warning("get_industry_trends unavailable for industry=%s: %s", industry, exc)
            return []

    def get_competitive_landscape(self, solution_id: int) -> Dict[str, Any]:
        """Return competitive landscape data for a solution.

        Args:
            solution_id: Primary key of the Solution record

        Returns:
            Dict with keys: competitors, market_share, positioning
        """
        try:
            from app import db
            from app.models.solution_models import Solution
            solution = db.session.get(Solution, solution_id)
            if solution is None:
                return {"competitors": [], "market_share": {}, "positioning": "unknown"}
            return {
                "competitors": [],
                "market_share": {},
                "positioning": "not_yet_assessed",
                "solution_name": solution.name,
            }
        except Exception as exc:
            logger.warning(
                "get_competitive_landscape unavailable for solution_id=%s: %s", solution_id, exc
            )
            return {"competitors": [], "market_share": {}, "positioning": "unavailable"}

    def get_technology_adoption_rate(self, technology_name: str) -> Dict[str, Any]:
        """Return adoption rate metrics for a named technology.

        Args:
            technology_name: Technology name (e.g. 'Kubernetes', 'Microservices')

        Returns:
            Dict with keys: technology, adoption_rate, trend, source
        """
        logger.info("get_technology_adoption_rate called for technology=%s", technology_name)
        return {
            "technology": technology_name,
            "adoption_rate": None,
            "trend": "unknown",
            "source": "not_configured",
            "message": (
                "External market intelligence connector is not configured. "
                "Adoption data will be available once the connector is set up."
            ),
        }

    def get_vendor_market_position(self, vendor_name: str) -> Dict[str, Any]:
        """Return market positioning data for a vendor.

        Args:
            vendor_name: Vendor name to look up

        Returns:
            Dict with keys: vendor, quadrant, market_share, growth_rate
        """
        try:
            from app import db
            from app.models.vendor import Vendor
            vendor = db.session.query(Vendor).filter(Vendor.name == vendor_name).first()
            if vendor is None:
                return {
                    "vendor": vendor_name,
                    "quadrant": "unknown",
                    "market_share": None,
                    "growth_rate": None,
                    "status": "vendor_not_found",
                }
            return {
                "vendor": vendor_name,
                "vendor_id": vendor.id,
                "quadrant": "not_yet_assessed",
                "market_share": None,
                "growth_rate": None,
                "status": "data_not_available",
            }
        except Exception as exc:
            logger.warning(
                "get_vendor_market_position unavailable for vendor=%s: %s", vendor_name, exc
            )
            return {
                "vendor": vendor_name,
                "quadrant": "unavailable",
                "market_share": None,
                "growth_rate": None,
                "status": "error",
            }

    def get_market_sizing(self, segment: str) -> Dict[str, Any]:
        """Return market sizing data for a segment.

        Args:
            segment: Market segment identifier

        Returns:
            Dict with keys: segment, tam, sam, som, currency, year
        """
        logger.info("get_market_sizing called for segment=%s", segment)
        return {
            "segment": segment,
            "tam": None,
            "sam": None,
            "som": None,
            "currency": "USD",
            "year": None,
            "status": "external_data_not_configured",
            "message": (
                "Market sizing data requires an external market intelligence connector. "
                "Configure the connector to enable this feature."
            ),
        }

    def get_regulatory_landscape(
        self, industry: str, region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return regulatory requirements relevant to an industry and region.

        Args:
            industry: Industry sector
            region: Optional region/jurisdiction (e.g. 'EU', 'US', 'UK')

        Returns:
            List of regulatory items with keys: name, description, jurisdiction, effective_date
        """
        logger.info(
            "get_regulatory_landscape called for industry=%s region=%s", industry, region
        )
        return []
