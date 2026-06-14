"""
G2 Crowd API Client

Integrates with G2 Crowd API for vendor ratings, reviews, and market analysis.
Provides comprehensive vendor intelligence and competitive analysis data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_client import APIResponse, BaseAPIClient

logger = logging.getLogger(__name__)


class G2CrowdAPIClient(BaseAPIClient):
    """
    G2 Crowd API client for vendor intelligence.

    Provides access to:
    - Vendor ratings and reviews
    - Product comparisons
    - Market analysis
    - User satisfaction metrics
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize G2 Crowd API client.

        Args:
            api_key: G2 Crowd API key (optional, can be set via environment)
        """
        super().__init__(
            base_url="https://api.g2.com",
            api_key=api_key,
            rate_limit_per_minute=30,  # Conservative rate limit
            cache_ttl_seconds=3600,  # 1 hour cache
        )

    def _setup_authentication(self):
        """Setup G2 Crowd API authentication."""
        if self.api_key:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.api_key}", "X-G2 - Api-Key": self.api_key}
            )

    def health_check(self) -> bool:
        """Check if G2 Crowd API is accessible."""
        try:
            # Try to get API status or make a simple request
            response = self.get("products", params={"per_page": 1})
            return response.success
        except Exception as e:
            logger.error(f"G2 Crowd health check failed: {e}")
            return False

    def get_vendor_ratings(self, vendor_name: str) -> APIResponse:
        """
        Get vendor ratings and review summary.

        Args:
            vendor_name: Name of the vendor to search for

        Returns:
            APIResponse with vendor rating data
        """
        try:
            # Search for products by vendor
            search_response = self.get(
                "products", params={"filter[name_cont]": vendor_name, "per_page": 10}
            )

            if not search_response.success:
                return search_response

            products = search_response.data.get("data", [])

            if not products:
                return APIResponse(
                    success=False, error=f"No products found for vendor: {vendor_name}"
                )

            # Get detailed ratings for the first matching product
            product = products[0]
            product_id = product.get("id")

            if product_id:
                ratings_response = self.get(
                    f"products/{product_id}/reviews",
                    params={"per_page": 50, "filter[verified]": "true"},
                )

                if ratings_response.success:
                    # Aggregate rating data
                    reviews = ratings_response.data.get("data", [])
                    aggregated_data = self._aggregate_ratings(product, reviews)

                    return APIResponse(
                        success=True,
                        data=aggregated_data,
                        rate_limit_remaining=ratings_response.rate_limit_remaining,
                        rate_limit_reset=ratings_response.rate_limit_reset,
                    )

            # Return basic product info if detailed ratings unavailable
            return APIResponse(
                success=True,
                data=self._format_product_data(product),
                rate_limit_remaining=search_response.rate_limit_remaining,
                rate_limit_reset=search_response.rate_limit_reset,
            )

        except Exception as e:
            logger.error(f"Error getting vendor ratings for {vendor_name}: {e}")
            return APIResponse(success=False, error=str(e))

    def get_product_comparison(self, product_names: List[str]) -> APIResponse:
        """
        Compare multiple products.

        Args:
            product_names: List of product names to compare

        Returns:
            APIResponse with comparison data
        """
        try:
            comparison_data = []

            for product_name in product_names[:5]:  # Limit to 5 products
                product_response = self.get(
                    "products", params={"filter[name_cont]": product_name, "per_page": 1}
                )

                if product_response.success and product_response.data.get("data"):
                    product = product_response.data["data"][0]
                    comparison_data.append(self._format_product_data(product))

            if not comparison_data:
                return APIResponse(success=False, error="No products found for comparison")

            return APIResponse(
                success=True,
                data={"comparison": comparison_data, "compared_products": len(comparison_data)},
            )

        except Exception as e:
            logger.error(f"Error getting product comparison: {e}")
            return APIResponse(success=False, error=str(e))

    def get_market_analysis(self, category: str) -> APIResponse:
        """
        Get market analysis for a category.

        Args:
            category: Market category (e.g., 'marketing-automation')

        Returns:
            APIResponse with market analysis data
        """
        try:
            # Get top products in category
            response = self.get(
                "products",
                params={
                    "filter[product_category]": category,
                    "sort": "-reviews_count",
                    "per_page": 20,
                },
            )

            if not response.success:
                return response

            products = response.data.get("data", [])
            market_data = {
                "category": category,
                "total_products": len(products),
                "top_products": [self._format_product_data(p) for p in products[:10]],
                "market_insights": self._analyze_market(products),
            }

            return APIResponse(success=True, data=market_data)

        except Exception as e:
            logger.error(f"Error getting market analysis for {category}: {e}")
            return APIResponse(success=False, error=str(e))

    def _aggregate_ratings(
        self, product: Dict[str, Any], reviews: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate rating data from reviews."""
        if not reviews:
            return self._format_product_data(product)

        # Calculate averages
        total_reviews = len(reviews)
        avg_rating = sum(r.get("attributes", {}).get("rating", 0) for r in reviews) / total_reviews

        # Count rating distribution
        rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            rating = review.get("attributes", {}).get("rating", 0)
            if rating in rating_distribution:
                rating_distribution[rating] += 1

        # Extract recent reviews (last 6 months)
        six_months_ago = datetime.now().timestamp() - (180 * 24 * 60 * 60)
        recent_reviews = []
        for review in reviews:
            created_at = review.get("attributes", {}).get("created_at")
            if (
                created_at
                and datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
                > six_months_ago
            ):
                recent_reviews.append(review)

        return {
            "product": self._format_product_data(product),
            "rating_summary": {
                "average_rating": round(avg_rating, 2),
                "total_reviews": total_reviews,
                "recent_reviews": len(recent_reviews),
                "rating_distribution": rating_distribution,
            },
            "reviews_sample": [self._format_review(r) for r in reviews[:5]],
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _format_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Format product data for consistent output."""
        attributes = product.get("attributes", {})

        return {
            "id": product.get("id"),
            "name": attributes.get("name"),
            "vendor": attributes.get("vendor_name"),
            "category": attributes.get("product_category"),
            "description": attributes.get("description"),
            "rating": attributes.get("avg_rating"),
            "reviews_count": attributes.get("reviews_count"),
            "url": f"https://www.g2.com/products/{attributes.get('slug')}",
            "tags": attributes.get("tags", []),
        }

    def _format_review(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """Format review data."""
        attributes = review.get("attributes", {})

        return {
            "id": review.get("id"),
            "rating": attributes.get("rating"),
            "title": attributes.get("title"),
            "comment": attributes.get("comment"),
            "pros": attributes.get("pros", []),
            "cons": attributes.get("cons", []),
            "verified": attributes.get("verified"),
            "created_at": attributes.get("created_at"),
            "reviewer": {
                "title": attributes.get("reviewer_title"),
                "company_size": attributes.get("company_size"),
                "industry": attributes.get("industry"),
            },
        }

    def _analyze_market(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze market trends from product data."""
        if not products:
            return {}

        # Calculate market statistics
        avg_rating = sum(p.get("attributes", {}).get("avg_rating", 0) for p in products) / len(
            products
        )
        total_reviews = sum(p.get("attributes", {}).get("reviews_count", 0) for p in products)

        # Find top vendors
        vendor_counts = {}
        for product in products:
            vendor = product.get("attributes", {}).get("vendor_name")
            if vendor:
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

        top_vendors = sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "average_rating": round(avg_rating, 2),
            "total_reviews": total_reviews,
            "market_leaders": [{"vendor": v, "products": c} for v, c in top_vendors],
            "competitive_intensity": len(products),
            "analysis_date": datetime.utcnow().isoformat(),
        }
