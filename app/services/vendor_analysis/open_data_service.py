"""
Open Vendor Data Service

Integration with external vendor data sources.
Provides access to public vendor information and market data.
"""

import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class OpenVendorDataService:
    """Service for accessing external vendor data sources."""

    def __init__(self):
        """Initialize with API endpoints and data sources."""
        self.data_sources = {
            'crunchbase': 'https://api.crunchbase.com/v4',
            'g2': 'https://data.g2.com/api',
            'capterra': 'https://www.capterra.com/api',
            'software_advice': 'https://www.softwareadvice.com/api'
        }
        self.api_keys = {}  # Would be configured in production

    def search_vendors(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for vendors across multiple data sources.
        Returns real API results only; no mock data.
        When no API keys are configured, returns empty list (honest error state).

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of vendor information from live API calls
        """
        results = []

        for source in self.data_sources:
            try:
                source_results = self._search_source(source, query, limit)
                results.extend(source_results)
            except Exception as e:
                logger.warning(f"Failed to search {source}: {e}")

        unique_results = self._deduplicate_results(results)
        return unique_results[:limit]

    def get_vendor_details(self, vendor_id: str, source: str = 'crunchbase') -> Optional[Dict]:
        """
        Get detailed information about a specific vendor.

        Args:
            vendor_id: Vendor identifier
            source: Data source to use

        Returns:
            Detailed vendor information, or error dict when API unavailable
        """
        api_key = self.api_keys.get(source)
        if not api_key:
            logger.warning(f"No API key configured for {source} — cannot fetch vendor details")
            return {"error": "API key not configured", "source": source, "data_available": False}

        endpoint = self.data_sources.get(source)
        if not endpoint:
            return {"error": "Unknown data source", "source": source, "data_available": False}

        try:
            response = requests.get(
                f"{endpoint}/vendors/{vendor_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get vendor details from {source}: {e}")
            return {"error": str(e), "source": source, "data_available": False}

    def get_market_insights(self, category: str) -> Dict:
        """
        Get market insights for a vendor category.

        Args:
            category: Vendor category

        Returns:
            Market analysis and insights, or error dict when API unavailable
        """
        api_key = self.api_keys.get('g2')
        if not api_key:
            logger.warning("No API key configured for market insights — cannot fetch data")
            return {"error": "API key not configured", "category": category, "data_available": False}

        try:
            response = requests.get(
                f"{self.data_sources['g2']}/market/{category}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get market insights for {category}: {e}")
            return {"error": str(e), "category": category, "data_available": False}

    def _search_source(self, source: str, query: str, limit: int) -> List[Dict]:
        """Search a specific data source."""
        api_key = self.api_keys.get(source)
        if not api_key:
            logger.warning(f"No API key configured for {source} — skipping search")
            return []

        endpoint = self.data_sources.get(source)
        if not endpoint:
            return []

        try:
            response = requests.get(
                f"{endpoint}/search",
                params={"q": query, "limit": limit},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("results", [])[:limit]
        except Exception as e:
            logger.warning(f"Failed to search {source}: {e}")
            return []

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate vendor entries."""
        seen = set()
        unique_results = []

        for result in results:
            key = result.get('name', '').lower()
            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        return unique_results
