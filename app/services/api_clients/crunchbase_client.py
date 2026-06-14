"""
Crunchbase API Client

Integrates with Crunchbase API for company intelligence and funding data.
Provides comprehensive business information, funding history, and market analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_client import APIResponse, BaseAPIClient

logger = logging.getLogger(__name__)


class CrunchbaseAPIClient(BaseAPIClient):
    """
    Crunchbase API client for company intelligence.

    Provides access to:
    - Company profiles and descriptions
    - Funding history and valuations
    - Executive information
    - Industry classifications
    - Geographic data
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Crunchbase API client.

        Args:
            api_key: Crunchbase API key (optional, can be set via environment)
        """
        super().__init__(
            base_url="https://api.crunchbase.com/api/v4",
            api_key=api_key,
            rate_limit_per_minute=50,  # Crunchbase allows higher rate limits
            cache_ttl_seconds=7200,  # 2 hour cache for business data
        )

    def _setup_authentication(self):
        """Setup Crunchbase API authentication."""
        if self.api_key:
            self.session.headers.update({"X-cb-user-key": self.api_key})

    def health_check(self) -> bool:
        """Check if Crunchbase API is accessible."""
        try:
            # Try to get API status or make a simple search
            response = self.get("searches/organizations", params={"query": "test", "limit": 1})
            return response.success
        except Exception as e:
            logger.error(f"Crunchbase health check failed: {e}")
            return False

    def get_company_profile(self, company_name: str) -> APIResponse:
        """
        Get comprehensive company profile.

        Args:
            company_name: Name of the company to search for

        Returns:
            APIResponse with company profile data
        """
        try:
            # First, search for the company
            search_response = self.get(
                "searches/organizations", params={"query": company_name, "limit": 5}
            )

            if not search_response.success:
                return search_response

            entities = search_response.data.get("entities", [])

            if not entities:
                return APIResponse(success=False, error=f"No companies found for: {company_name}")

            # Get the best match (usually the first result)
            company = entities[0]
            company_id = company.get("uuid")

            if company_id:
                # Get detailed company information
                detail_response = self.get(f"organizations/{company_id}")

                if detail_response.success:
                    company_data = detail_response.data.get("properties", {})
                    formatted_data = self._format_company_profile(company_data)

                    return APIResponse(
                        success=True,
                        data=formatted_data,
                        rate_limit_remaining=detail_response.rate_limit_remaining,
                        rate_limit_reset=detail_response.rate_limit_reset,
                    )

            # Return basic search result if detailed data unavailable
            return APIResponse(
                success=True,
                data=self._format_search_result(company),
                rate_limit_remaining=search_response.rate_limit_remaining,
                rate_limit_reset=search_response.rate_limit_reset,
            )

        except Exception as e:
            logger.error(f"Error getting company profile for {company_name}: {e}")
            return APIResponse(success=False, error=str(e))

    def get_funding_history(self, company_name: str) -> APIResponse:
        """
        Get funding history for a company.

        Args:
            company_name: Name of the company

        Returns:
            APIResponse with funding history data
        """
        try:
            # First get company ID
            search_response = self.get(
                "searches/organizations", params={"query": company_name, "limit": 1}
            )

            if not search_response.success or not search_response.data.get("entities"):
                return APIResponse(success=False, error=f"Company not found: {company_name}")

            company_id = search_response.data["entities"][0]["uuid"]

            # Get funding rounds
            funding_response = self.get(
                f"organizations/{company_id}/funding_rounds", params={"order": "announced_on DESC"}
            )

            if not funding_response.success:
                return funding_response

            funding_rounds = funding_response.data.get("cards", [])
            formatted_funding = self._format_funding_history(funding_rounds)

            return APIResponse(
                success=True,
                data=formatted_funding,
                rate_limit_remaining=funding_response.rate_limit_remaining,
                rate_limit_reset=funding_response.rate_limit_reset,
            )

        except Exception as e:
            logger.error(f"Error getting funding history for {company_name}: {e}")
            return APIResponse(success=False, error=str(e))

    def get_executive_info(self, company_name: str) -> APIResponse:
        """
        Get executive and leadership information.

        Args:
            company_name: Name of the company

        Returns:
            APIResponse with executive data
        """
        try:
            # Get company ID first
            search_response = self.get(
                "searches/organizations", params={"query": company_name, "limit": 1}
            )

            if not search_response.success or not search_response.data.get("entities"):
                return APIResponse(success=False, error=f"Company not found: {company_name}")

            company_id = search_response.data["entities"][0]["uuid"]

            # Get current team
            team_response = self.get(f"organizations/{company_id}/current_team")

            if not team_response.success:
                return team_response

            team_members = team_response.data.get("cards", [])
            executives = self._format_executive_info(team_members)

            return APIResponse(
                success=True,
                data=executives,
                rate_limit_remaining=team_response.rate_limit_remaining,
                rate_limit_reset=team_response.rate_limit_reset,
            )

        except Exception as e:
            logger.error(f"Error getting executive info for {company_name}: {e}")
            return APIResponse(success=False, error=str(e))

    def get_industry_analysis(self, industry: str) -> APIResponse:
        """
        Get industry analysis and trends.

        Args:
            industry: Industry name or category

        Returns:
            APIResponse with industry analysis data
        """
        try:
            # Search for companies in the industry
            response = self.get("searches/organizations", params={"query": industry, "limit": 50})

            if not response.success:
                return response

            companies = response.data.get("entities", [])
            industry_data = self._analyze_industry(companies, industry)

            return APIResponse(success=True, data=industry_data)

        except Exception as e:
            logger.error(f"Error getting industry analysis for {industry}: {e}")
            return APIResponse(success=False, error=str(e))

    def _format_company_profile(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format company profile data."""
        return {
            "name": company_data.get("name"),
            "description": company_data.get("description"),
            "short_description": company_data.get("short_description"),
            "homepage_url": company_data.get("homepage_url"),
            "linkedin_url": company_data.get("linkedin_url"),
            "twitter_url": company_data.get("twitter_url"),
            "facebook_url": company_data.get("facebook_url"),
            "founded_on": company_data.get("founded_on"),
            "is_closed": company_data.get("is_closed", False),
            "contact_email": company_data.get("contact_email"),
            "phone_number": company_data.get("phone_number"),
            "num_employees_enum": company_data.get("num_employees_enum"),
            "total_funding_usd": company_data.get("total_funding_usd"),
            "valuation_usd": company_data.get("valuation_usd"),
            "last_funding_on": company_data.get("last_funding_on"),
            "categories": company_data.get("categories", []),
            "headquarters": {
                "city": company_data.get("city"),
                "region": company_data.get("region"),
                "country": company_data.get("country"),
                "continent": company_data.get("continent"),
            },
            "funding_stages": company_data.get("funding_stages", []),
            "investors": company_data.get("investors", []),
            "acquisitions": company_data.get("acquisitions", []),
            "ipo": company_data.get("ipo"),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _format_search_result(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Format basic search result."""
        return {
            "name": entity.get("properties", {}).get("name"),
            "short_description": entity.get("properties", {}).get("short_description"),
            "homepage_url": entity.get("properties", {}).get("homepage_url"),
            "num_employees_enum": entity.get("properties", {}).get("num_employees_enum"),
            "total_funding_usd": entity.get("properties", {}).get("total_funding_usd"),
            "categories": entity.get("properties", {}).get("categories", []),
            "location": {
                "city": entity.get("properties", {}).get("city"),
                "country": entity.get("properties", {}).get("country"),
            },
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _format_funding_history(self, funding_rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format funding history data."""
        formatted_rounds = []

        for round_data in funding_rounds:
            properties = round_data.get("properties", {})

            formatted_round = {
                "announced_on": properties.get("announced_on"),
                "series": properties.get("series"),
                "funding_type": properties.get("funding_type"),
                "money_raised_usd": properties.get("money_raised_usd"),
                "valuation_usd": properties.get("valuation_usd"),
                "investors": properties.get("investors", []),
                "news_url": properties.get("news_url"),
            }
            formatted_rounds.append(formatted_round)

        # Calculate summary statistics
        total_raised = sum(
            r.get("money_raised_usd", 0) for r in formatted_rounds if r.get("money_raised_usd")
        )
        latest_round = formatted_rounds[0] if formatted_rounds else None

        return {
            "total_rounds": len(formatted_rounds),
            "total_funding_usd": total_raised,
            "latest_round": latest_round,
            "funding_rounds": formatted_rounds,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _format_executive_info(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format executive information."""
        executives = []

        for member in team_members:
            properties = member.get("properties", {})

            # Focus on key executive roles
            title = properties.get("title", "").lower()
            if any(
                keyword in title
                for keyword in [
                    "ceo",
                    "cfo",
                    "cto",
                    "coo",
                    "founder",
                    "president",
                    "vp",
                    "director",
                ]
            ):
                executive = {
                    "name": properties.get("name"),
                    "title": properties.get("title"),
                    "linkedin_url": properties.get("linkedin_url"),
                    "started_on": properties.get("started_on"),
                    "ended_on": properties.get("ended_on"),
                }
                executives.append(executive)

        return {
            "total_executives": len(executives),
            "executives": executives[:10],  # Limit to top 10
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _analyze_industry(self, companies: List[Dict[str, Any]], industry: str) -> Dict[str, Any]:
        """Analyze industry trends from company data."""
        if not companies:
            return {"industry": industry, "error": "No companies found"}

        # Calculate industry statistics
        total_companies = len(companies)
        total_funding = sum(
            c.get("properties", {}).get("total_funding_usd", 0)
            for c in companies
            if c.get("properties", {}).get("total_funding_usd")
        )

        # Company size distribution
        size_distribution = {}
        for company in companies:
            size = company.get("properties", {}).get("num_employees_enum")
            if size:
                size_distribution[size] = size_distribution.get(size, 0) + 1

        # Geographic distribution
        country_distribution = {}
        for company in companies:
            country = company.get("properties", {}).get("country")
            if country:
                country_distribution[country] = country_distribution.get(country, 0) + 1

        # Top funded companies
        funded_companies = [
            c for c in companies if c.get("properties", {}).get("total_funding_usd")
        ]
        top_funded = sorted(
            funded_companies, key=lambda x: x["properties"]["total_funding_usd"], reverse=True
        )[:5]

        return {
            "industry": industry,
            "total_companies": total_companies,
            "total_funding_usd": total_funding,
            "average_funding_per_company": total_funding / total_companies
            if total_companies > 0
            else 0,
            "company_size_distribution": size_distribution,
            "geographic_distribution": country_distribution,
            "top_funded_companies": [
                {
                    "name": c["properties"]["name"],
                    "funding_usd": c["properties"]["total_funding_usd"],
                    "country": c["properties"].get("country"),
                }
                for c in top_funded
            ],
            "analysis_date": datetime.utcnow().isoformat(),
        }
