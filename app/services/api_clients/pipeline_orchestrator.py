"""
API Pipeline Orchestrator

Coordinates multiple API clients for comprehensive data enrichment.
Provides unified interface for vendor intelligence, market analysis, and technical insights.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .crunchbase_client import CrunchbaseAPIClient
from .g2_crowd_client import G2CrowdAPIClient
from .github_client import GitHubAPIClient

logger = logging.getLogger(__name__)


class APIPipelineOrchestrator:
    """
    Orchestrates multiple API clients for comprehensive data enrichment.

    Provides unified interface for:
    - Vendor intelligence gathering
    - Product analysis and comparison
    - Technical capability assessment
    - Market trend analysis
    """

    def __init__(self):
        """Initialize API pipeline with all clients."""
        # Initialize API clients with environment variables
        self.g2_client = G2CrowdAPIClient(api_key=os.getenv("G2_CROWD_API_KEY"))
        self.crunchbase_client = CrunchbaseAPIClient(api_key=os.getenv("CRUNCHBASE_API_KEY"))
        self.github_client = GitHubAPIClient(api_token=os.getenv("GITHUB_API_TOKEN"))

        self.clients = {
            "g2_crowd": self.g2_client,
            "crunchbase": self.crunchbase_client,
            "github": self.github_client,
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all API clients.

        Returns:
            Dict with health status for each client
        """
        health_status = {}

        for name, client in self.clients.items():
            try:
                is_healthy = client.health_check()
                health_status[name] = {
                    "healthy": is_healthy,
                    "rate_limit_status": client.get_rate_limit_status(),
                }
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                health_status[name] = {"healthy": False, "error": str(e)}

        overall_healthy = all(status["healthy"] for status in health_status.values())

        return {
            "overall_healthy": overall_healthy,
            "clients": health_status,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def enrich_vendor_data(self, vendor_name: str) -> Dict[str, Any]:
        """
        Enrich vendor data from multiple sources.

        Args:
            vendor_name: Name of the vendor to enrich

        Returns:
            Dict with enriched vendor data
        """
        logger.info(f"Enriching data for vendor: {vendor_name}")

        enriched_data = {
            "vendor_name": vendor_name,
            "data_sources": {},
            "enrichment_timestamp": datetime.utcnow().isoformat(),
            "success": False,
        }

        # G2 Crowd ratings and reviews
        try:
            g2_response = self.g2_client.get_vendor_ratings(vendor_name)
            if g2_response.success:
                enriched_data["data_sources"]["g2_crowd"] = g2_response.data
                logger.info(f"✅ G2 Crowd data retrieved for {vendor_name}")
            else:
                logger.warning(f"❌ G2 Crowd data failed for {vendor_name}: {g2_response.error}")
                enriched_data["data_sources"]["g2_crowd"] = {"error": g2_response.error}
        except Exception as e:
            logger.error(f"Error getting G2 Crowd data for {vendor_name}: {e}")
            enriched_data["data_sources"]["g2_crowd"] = {"error": str(e)}

        # Crunchbase company profile
        try:
            cb_response = self.crunchbase_client.get_company_profile(vendor_name)
            if cb_response.success:
                enriched_data["data_sources"]["crunchbase"] = cb_response.data
                logger.info(f"✅ Crunchbase data retrieved for {vendor_name}")
            else:
                logger.warning(f"❌ Crunchbase data failed for {vendor_name}: {cb_response.error}")
                enriched_data["data_sources"]["crunchbase"] = {"error": cb_response.error}
        except Exception as e:
            logger.error(f"Error getting Crunchbase data for {vendor_name}: {e}")
            enriched_data["data_sources"]["crunchbase"] = {"error": str(e)}

        # Analyze success and aggregate data
        successful_sources = [
            k for k, v in enriched_data["data_sources"].items() if "error" not in v
        ]
        enriched_data["success"] = len(successful_sources) > 0
        enriched_data["successful_sources"] = successful_sources

        if enriched_data["success"]:
            enriched_data["aggregated_insights"] = self._aggregate_vendor_insights(
                enriched_data["data_sources"]
            )

        logger.info(
            f"Vendor enrichment completed for {vendor_name}: {len(successful_sources)}/{len(self.clients)} sources successful"
        )
        return enriched_data

    def enrich_product_data(
        self, product_name: str, vendor_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich product data from multiple sources.

        Args:
            product_name: Name of the product to enrich
            vendor_name: Optional vendor name for context

        Returns:
            Dict with enriched product data
        """
        logger.info(f"Enriching data for product: {product_name}")

        enriched_data = {
            "product_name": product_name,
            "vendor_name": vendor_name,
            "data_sources": {},
            "enrichment_timestamp": datetime.utcnow().isoformat(),
            "success": False,
        }

        # G2 Crowd product analysis
        try:
            g2_response = self.g2_client.get_vendor_ratings(product_name)
            if g2_response.success:
                enriched_data["data_sources"]["g2_crowd"] = g2_response.data
                logger.info(f"✅ G2 Crowd data retrieved for {product_name}")
            else:
                logger.warning(f"❌ G2 Crowd data failed for {product_name}: {g2_response.error}")
                enriched_data["data_sources"]["g2_crowd"] = {"error": g2_response.error}
        except Exception as e:
            logger.error(f"Error getting G2 Crowd data for {product_name}: {e}")
            enriched_data["data_sources"]["g2_crowd"] = {"error": str(e)}

        # GitHub repository analysis (if applicable)
        if vendor_name:
            try:
                # Try to find GitHub repos for this vendor/product combination
                search_query = f"{product_name} {vendor_name}"
                github_response = self.github_client.search_repositories(search_query)

                if github_response.success and github_response.data.get("total_count", 0) > 0:
                    # Get the top result for detailed analysis
                    top_repo = github_response.data["repositories"][0]
                    owner = top_repo.get("owner")
                    repo_name = top_repo.get("name")

                    if owner and repo_name:
                        detailed_response = self.github_client.get_repository_analysis(
                            owner, repo_name
                        )
                        if detailed_response.success:
                            enriched_data["data_sources"]["github"] = detailed_response.data
                            logger.info(f"✅ GitHub data retrieved for {owner}/{repo_name}")
                        else:
                            enriched_data["data_sources"]["github"] = {
                                "error": detailed_response.error
                            }
                    else:
                        enriched_data["data_sources"]["github"] = {
                            "error": "No valid repository found"
                        }
                else:
                    enriched_data["data_sources"]["github"] = {"error": "No repositories found"}
            except Exception as e:
                logger.error(f"Error getting GitHub data for {product_name}: {e}")
                enriched_data["data_sources"]["github"] = {"error": str(e)}

        # Analyze success and aggregate data
        successful_sources = [
            k for k, v in enriched_data["data_sources"].items() if "error" not in v
        ]
        enriched_data["success"] = len(successful_sources) > 0
        enriched_data["successful_sources"] = successful_sources

        if enriched_data["success"]:
            enriched_data["aggregated_insights"] = self._aggregate_product_insights(
                enriched_data["data_sources"]
            )

        logger.info(
            f"Product enrichment completed for {product_name}: {len(successful_sources)} sources successful"
        )
        return enriched_data

    def get_market_analysis(self, category: str) -> Dict[str, Any]:
        """
        Get comprehensive market analysis for a category.

        Args:
            category: Market category to analyze

        Returns:
            Dict with market analysis data
        """
        logger.info(f"Analyzing market for category: {category}")

        market_data = {
            "category": category,
            "data_sources": {},
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "success": False,
        }

        # G2 Crowd market analysis
        try:
            g2_response = self.g2_client.get_market_analysis(category)
            if g2_response.success:
                market_data["data_sources"]["g2_crowd"] = g2_response.data
                logger.info(f"✅ G2 Crowd market analysis retrieved for {category}")
            else:
                logger.warning(
                    f"❌ G2 Crowd market analysis failed for {category}: {g2_response.error}"
                )
                market_data["data_sources"]["g2_crowd"] = {"error": g2_response.error}
        except Exception as e:
            logger.error(f"Error getting G2 Crowd market analysis for {category}: {e}")
            market_data["data_sources"]["g2_crowd"] = {"error": str(e)}

        # Crunchbase industry analysis
        try:
            cb_response = self.crunchbase_client.get_industry_analysis(category)
            if cb_response.success:
                market_data["data_sources"]["crunchbase"] = cb_response.data
                logger.info(f"✅ Crunchbase industry analysis retrieved for {category}")
            else:
                logger.warning(
                    f"❌ Crunchbase industry analysis failed for {category}: {cb_response.error}"
                )
                market_data["data_sources"]["crunchbase"] = {"error": cb_response.error}
        except Exception as e:
            logger.error(f"Error getting Crunchbase industry analysis for {category}: {e}")
            market_data["data_sources"]["crunchbase"] = {"error": str(e)}

        # GitHub technology analysis
        try:
            github_response = self.github_client.search_repositories(category, sort="stars")
            if github_response.success:
                market_data["data_sources"]["github"] = github_response.data
                logger.info(f"✅ GitHub technology analysis retrieved for {category}")
            else:
                logger.warning(
                    f"❌ GitHub technology analysis failed for {category}: {github_response.error}"
                )
                market_data["data_sources"]["github"] = {"error": github_response.error}
        except Exception as e:
            logger.error(f"Error getting GitHub technology analysis for {category}: {e}")
            market_data["data_sources"]["github"] = {"error": str(e)}

        # Analyze success and aggregate data
        successful_sources = [k for k, v in market_data["data_sources"].items() if "error" not in v]
        market_data["success"] = len(successful_sources) > 0
        market_data["successful_sources"] = successful_sources

        if market_data["success"]:
            market_data["aggregated_analysis"] = self._aggregate_market_analysis(
                market_data["data_sources"]
            )

        logger.info(
            f"Market analysis completed for {category}: {len(successful_sources)} sources successful"
        )
        return market_data

    def _aggregate_vendor_insights(self, data_sources: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate insights from multiple vendor data sources."""
        insights = {
            "rating_summary": {},
            "company_profile": {},
            "market_positioning": {},
            "confidence_score": 0,
        }

        # Aggregate G2 Crowd data
        if "g2_crowd" in data_sources and "error" not in data_sources["g2_crowd"]:
            g2_data = data_sources["g2_crowd"]
            if "rating_summary" in g2_data:
                insights["rating_summary"] = g2_data["rating_summary"]
                insights["confidence_score"] += 30  # G2 data is highly reliable

        # Aggregate Crunchbase data
        if "crunchbase" in data_sources and "error" not in data_sources["crunchbase"]:
            cb_data = data_sources["crunchbase"]
            insights["company_profile"] = {
                "founded_year": cb_data.get("founded_on", "").split("-")[0]
                if cb_data.get("founded_on")
                else None,
                "headquarters": cb_data.get("headquarters", {}),
                "funding_total": cb_data.get("total_funding_usd"),
                "employee_count": cb_data.get("num_employees_enum"),
                "categories": cb_data.get("categories", []),
            }
            insights["confidence_score"] += 25  # Crunchbase data is reliable

        # Calculate market positioning
        insights["market_positioning"] = self._calculate_market_positioning(insights)

        return insights

    def _aggregate_product_insights(self, data_sources: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate insights from multiple product data sources."""
        insights = {
            "rating_summary": {},
            "technical_stack": {},
            "community_metrics": {},
            "confidence_score": 0,
        }

        # Aggregate G2 Crowd data
        if "g2_crowd" in data_sources and "error" not in data_sources["g2_crowd"]:
            g2_data = data_sources["g2_crowd"]
            if "rating_summary" in g2_data:
                insights["rating_summary"] = g2_data["rating_summary"]
                insights["confidence_score"] += 35

        # Aggregate GitHub data
        if "github" in data_sources and "error" not in data_sources["github"]:
            gh_data = data_sources["github"]
            insights["technical_stack"] = gh_data.get("languages", {})
            insights["community_metrics"] = {
                "stars": gh_data.get("stars", 0),
                "forks": gh_data.get("forks", 0),
                "contributors": gh_data.get("contributors", {}).get("count", 0),
                "activity_score": gh_data.get("activity", {}).get("activity_score", 0),
            }
            insights["confidence_score"] += 30

        return insights

    def _aggregate_market_analysis(self, data_sources: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate market analysis from multiple sources."""
        analysis = {
            "market_size": {},
            "competitive_landscape": {},
            "technology_trends": {},
            "confidence_score": 0,
        }

        # Aggregate G2 Crowd market data
        if "g2_crowd" in data_sources and "error" not in data_sources["g2_crowd"]:
            g2_data = data_sources["g2_crowd"]
            analysis["market_size"]["g2_competitors"] = g2_data.get("total_products", 0)
            analysis["competitive_landscape"]["top_vendors"] = g2_data.get("market_leaders", [])
            analysis["confidence_score"] += 30

        # Aggregate Crunchbase industry data
        if "crunchbase" in data_sources and "error" not in data_sources["crunchbase"]:
            cb_data = data_sources["crunchbase"]
            analysis["market_size"]["crunchbase_companies"] = cb_data.get("total_companies", 0)
            analysis["market_size"]["total_funding"] = cb_data.get("total_funding_usd", 0)
            analysis["competitive_landscape"]["funded_companies"] = cb_data.get(
                "top_funded_companies", []
            )
            analysis["confidence_score"] += 25

        # Aggregate GitHub technology data
        if "github" in data_sources and "error" not in data_sources["github"]:
            gh_data = data_sources["github"]
            analysis["technology_trends"]["repositories"] = gh_data.get("total_count", 0)
            analysis["technology_trends"]["top_projects"] = gh_data.get("repositories", [])[:5]
            analysis["confidence_score"] += 20

        return analysis

    def _calculate_market_positioning(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate market positioning based on aggregated data."""
        positioning = {
            "maturity_level": "Unknown",
            "market_segment": "Unknown",
            "growth_stage": "Unknown",
        }

        # Determine maturity from funding and age
        profile = insights.get("company_profile", {})
        founded_year = profile.get("founded_year")
        funding = profile.get("funding_total", 0)

        if founded_year:
            try:
                age = datetime.utcnow().year - int(founded_year)
                if age < 3:
                    positioning["growth_stage"] = "Early Stage"
                elif age < 7:
                    positioning["growth_stage"] = "Growth Stage"
                else:
                    positioning["growth_stage"] = "Mature"
            except ValueError:
                pass

        if funding > 100000000:  # $100M+
            positioning["maturity_level"] = "Enterprise"
        elif funding > 10000000:  # $10M+
            positioning["maturity_level"] = "Established"
        elif funding > 1000000:  # $1M+
            positioning["maturity_level"] = "Growing"
        else:
            positioning["maturity_level"] = "Startup"

        return positioning

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get rate limit status for all clients."""
        status = {}
        for name, client in self.clients.items():
            status[name] = client.get_rate_limit_status()
        return status

    def clear_all_caches(self):
        """Clear caches for all API clients."""
        for client in self.clients.values():
            client.clear_cache()
        logger.info("All API client caches cleared")
