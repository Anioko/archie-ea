"""
pgvector Semantic Discovery Service Adapter

Provides backward-compatible wrapper for ai_semantic_discovery_service
that uses pgvector instead of ChromaDB + FAISS.

This adapter allows existing code to work with pgvector seamlessly.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.services.pgvector_embedding_service import get_pgvector_service

logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    """Result of semantic search with confidence scores."""

    vendor_product_id: int
    product_name: str
    vendor_name: str
    similarity_score: float
    capability_coverage: float
    relevance_factors: List[str]
    confidence_level: str  # "high", "medium", "low"


class PgvectorSemanticDiscoveryAdapter:
    """
    Adapter providing pgvector-based semantic discovery.
    Compatible with existing AISemanticDiscoveryService interface.
    """

    def __init__(self):
        """Initialize the adapter."""
        self.pgvector_service = get_pgvector_service()
        logger.info("Initialized pgvector semantic discovery adapter")

    def index_vendor_products(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Index vendor products using pgvector.

        Args:
            limit: Maximum number of products to index

        Returns:
            Indexing results with counts and status
        """
        try:
            logger.info(f"Starting vendor product indexing with pgvector (limit: {limit})")

            # Get vendor products with their descriptions
            products = (
                db.session.query(VendorProduct)
                .options(joinedload(VendorProduct.vendor_organization))
                .limit(limit)
                .all()
            )

            if not products:
                return {"error": "No vendor products found", "success": False}

            indexed_count = 0
            failed_count = 0

            for product in products:
                try:
                    # Combine product name, description, and features
                    text_parts = [
                        product.name or "",
                        product.description or "",
                        product.functional_scope or "",
                    ]

                    combined_text = " ".join(filter(None, text_parts))
                    if combined_text.strip():
                        result = self.pgvector_service.create_vendor_product_embedding(
                            product.id, combined_text
                        )
                        if result:
                            indexed_count += 1
                        else:
                            failed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to index product {product.id}: {e}")
                    failed_count += 1

            logger.info(f"Indexed {indexed_count} products, {failed_count} failed")
            return {
                "success": True,
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "embedding_dimension": 384,
                "total_stored": indexed_count,
            }
        except Exception as e:
            logger.error(f"Vendor product indexing failed: {e}")
            return {"error": str(e), "success": False}

    def index_business_capabilities(self, limit: int = 500) -> Dict[str, Any]:
        """
        Index business capabilities using pgvector.

        Args:
            limit: Maximum number of capabilities to index

        Returns:
            Indexing results with counts and status
        """
        try:
            logger.info(f"Starting capability indexing with pgvector (limit: {limit})")

            # Get business capabilities
            capabilities = db.session.query(BusinessCapability).limit(limit).all()

            if not capabilities:
                return {"error": "No capabilities found", "success": False}

            indexed_count = 0
            failed_count = 0

            for capability in capabilities:
                try:
                    text_parts = [capability.name or "", capability.description or ""]
                    combined_text = " ".join(filter(None, text_parts))

                    if combined_text.strip():
                        result = self.pgvector_service.create_capability_embedding(
                            capability.id, combined_text
                        )
                        if result:
                            indexed_count += 1
                        else:
                            failed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to index capability {capability.id}: {e}")
                    failed_count += 1

            logger.info(f"Indexed {indexed_count} capabilities, {failed_count} failed")
            return {
                "success": True,
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "embedding_dimension": 384,
            }
        except Exception as e:
            logger.error(f"Capability indexing failed: {e}")
            return {"error": str(e), "success": False}

    def search_vendor_products_by_capability(
        self, capability_name: str, limit: int = 10
    ) -> List[SemanticSearchResult]:
        """
        Search vendor products that match a capability.

        Args:
            capability_name: Name or description of capability
            limit: Maximum results to return

        Returns:
            List of SemanticSearchResult objects
        """
        try:
            # Search using pgvector
            results = self.pgvector_service.search_vendor_products(
                capability_name, limit=limit, threshold=0.3
            )

            output = []
            for product_id, product_name, similarity in results:
                try:
                    product = db.session.get(VendorProduct, product_id)
                    if product:
                        vendor_name = (
                            product.vendor_organization.name
                            if product.vendor_organization
                            else "Unknown"
                        )

                        # Determine confidence level
                        if similarity > 0.8:
                            confidence = "high"
                        elif similarity > 0.6:
                            confidence = "medium"
                        else:
                            confidence = "low"

                        result = SemanticSearchResult(
                            vendor_product_id=product_id,
                            product_name=product_name,
                            vendor_name=vendor_name,
                            similarity_score=similarity,
                            capability_coverage=similarity,  # Simplified for adapter
                            relevance_factors=[f"Similarity: {similarity:.1%}"],
                            confidence_level=confidence,
                        )
                        output.append(result)
                except Exception as e:
                    logger.debug(f"Error processing result {product_id}: {e}")

            return output
        except Exception as e:
            logger.error(f"Vendor product search failed: {e}")
            return []

    def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings."""
        try:
            stats = self.pgvector_service.get_embedding_stats()
            return {
                "success": True,
                "statistics": stats,
                "backend": "pgvector",
                "model": "all-MiniLM-L6-v2",
            }
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_adapter_instance = None


def get_pgvector_semantic_discovery_adapter() -> PgvectorSemanticDiscoveryAdapter:
    """Get or create adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = PgvectorSemanticDiscoveryAdapter()
    return _adapter_instance
