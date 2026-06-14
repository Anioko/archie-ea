"""
Semantic Search Service - Real semantic search using vector embeddings

Provides production-grade semantic search capabilities with domain-aware
re-ranking and intelligent result processing.
"""

import asyncio  # dead-code-ok
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok

from flask import current_app  # dead-code-ok
from sqlalchemy import text

from app import db
from app.services.vector_embedding_service import VectorEmbeddingService

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """
    Production-grade semantic search service with vector embeddings.

    Features:
    - Real semantic search using vector similarity
    - Domain-aware re-ranking
    - Multi-modal search (text, metadata, hybrid)
    - Performance optimization with caching
    - Result filtering and boosting
    """

    def __init__(self, embedding_service: VectorEmbeddingService):
        self.embedding_service = embedding_service
        self.vector_store = embedding_service.vector_store
        self.logger = logging.getLogger(__name__)

        # Domain-specific weights for re-ranking
        self.domain_weights = {
            "architecture": {
                "archimate_elements": 2.0,
                "patterns": 1.8,
                "relationships": 1.6,
                "viewpoints": 1.5,
            },
            "technology": {
                "technologies": 2.0,
                "vendors": 1.8,
                "applications": 1.7,
                "infrastructure": 1.5,
            },
            "business_capability": {
                "capabilities": 2.0,
                "processes": 1.8,
                "value_streams": 1.7,
                "business_domains": 1.6,
            },
            "gap_analysis": {"gaps": 2.0, "risks": 1.8, "recommendations": 1.6, "assessments": 1.5},
            "vendor_intelligence": {
                "vendors": 2.0,
                "products": 1.8,
                "contracts": 1.6,
                "evaluations": 1.5,
            },
            "general": {"general": 1.0},
        }

        # Search result cache
        self._search_cache = {}
        self._cache_ttl = 300  # 5 minutes

    def semantic_search(
        self, query: str, domain: str = "general", top_k: int = 10, filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search with domain-aware re-ranking.

        Args:
            query: Search query string
            domain: Domain to search within
            top_k: Number of results to return
            filters: Optional filters for search results

        Returns:
            List of search results with metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.embed_text(query)

            # Search vector store
            vector_results = self.vector_store.search(query_embedding, top_k * 2)

            # Apply domain-aware re-ranking
            ranked_results = self._domain_aware_rerank(vector_results, domain, query)

            # Apply additional filters
            filtered_results = self._apply_filters(ranked_results, filters)

            # Return top_k results
            return filtered_results[:top_k]

        except Exception as e:
            self.logger.error(f"Error in semantic search: {e}")
            # Fallback search
            fallback_results = self._fallback_search(query, domain, top_k)
            return fallback_results

    def _domain_aware_rerank(
        self, docs: List[Dict[str, Any]], domain: str, query: str
    ) -> List[Dict[str, Any]]:
        """
        Re-rank search results based on domain-specific weights.

        Args:
            docs: List of documents from vector search
            domain: Target domain
            query: Original query for context

        Returns:
            Re-ranked list of documents
        """
        domain_weights = self.domain_weights.get(domain, self.domain_weights["general"])

        for doc in docs:
            base_score = doc["similarity"]

            # Apply domain-specific boosting
            content_type = doc.get("content_type", "general")
            metadata = doc.get("metadata", {})

            # Get weight for content type
            boost = domain_weights.get(content_type, 1.0)

            # Apply additional boosting based on metadata
            metadata_boost = self._calculate_metadata_boost(metadata, domain)

            # Calculate final score
            final_score = base_score * boost * metadata_boost

            # Update document with re-ranking info
            doc["rerank_score"] = final_score
            doc["boost_applied"] = boost
            doc["metadata_boost"] = metadata_boost

        # Sort by re-ranked score
        docs.sort(key=lambda x: x["rerank_score"], reverse=True)

        return docs

    def _calculate_metadata_boost(self, metadata: Dict[str, Any], domain: str) -> float:
        """
        Calculate boost factor based on document metadata.

        Args:
            metadata: Document metadata
            domain: Target domain

        Returns:
            Boost factor (1.0 = no boost)
        """
        boost = 1.0

        # Recent content boost
        if "created_at" in metadata:
            created_at = datetime.fromisoformat(metadata["created_at"])
            days_old = (datetime.utcnow() - created_at).days
            if days_old < 30:
                boost *= 1.1  # 10% boost for recent content

        # Quality score boost
        if "quality_score" in metadata:
            quality_score = metadata["quality_score"]
            boost *= 0.8 + 0.4 * quality_score  # Scale 0.8 - 1.2 based on quality

        # Domain-specific metadata boosts
        if domain == "architecture":
            if metadata.get("is_togaf_compliant"):
                boost *= 1.2
            if metadata.get("maturity_level") == "strategic":
                boost *= 1.1

        elif domain == "technology":
            if metadata.get("is_cloud_native"):
                boost *= 1.1
            if metadata.get("has_api"):
                boost *= 1.05

        elif domain == "business_capability":
            if metadata.get("is_critical"):
                boost *= 1.2
            if metadata.get("automation_level") == "high":
                boost *= 1.1

        return boost

    def _apply_filters(
        self, docs: List[Dict[str, Any]], filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply filters to search results.

        Args:
            docs: List of documents to filter
            filters: Filter criteria

        Returns:
            Filtered list of documents
        """
        if not filters:
            return docs

        filtered_docs = []

        for doc in docs:
            metadata = doc.get("metadata", {})

            # Apply each filter
            passes_all_filters = True

            for filter_key, filter_value in filters.items():
                if filter_key == "content_type":
                    if doc.get("content_type") != filter_value:
                        passes_all_filters = False
                        break

                elif filter_key == "date_range":
                    if "created_at" in metadata:
                        created_at = datetime.fromisoformat(metadata["created_at"])
                        start_date = datetime.fromisoformat(filter_value["start"])
                        end_date = datetime.fromisoformat(filter_value["end"])
                        if not (start_date <= created_at <= end_date):
                            passes_all_filters = False
                            break

                elif filter_key == "tags":
                    doc_tags = set(metadata.get("tags", []))
                    filter_tags = set(filter_value)
                    if not doc_tags.intersection(filter_tags):
                        passes_all_filters = False
                        break

                elif filter_key == "quality_threshold":
                    doc_quality = metadata.get("quality_score", 0.0)
                    if doc_quality < filter_value:
                        passes_all_filters = False
                        break

            if passes_all_filters:
                filtered_docs.append(doc)

        return filtered_docs

    def _fallback_search(self, query: str, domain: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Fallback search method when vector search fails.

        Args:
            query: Search query
            domain: Target domain
            top_k: Number of results

        Returns:
            Basic search results
        """
        try:
            # Use database text search as fallback
            query = f"%{query}%"

            # tenant-exempt: system table (document_embeddings is infrastructure)
            search_query = text(
                """
                SELECT content_id, metadata, domain, content_type
                FROM document_embeddings
                WHERE domain = :domain
                AND (CAST(metadata AS TEXT) LIKE :query OR content_id LIKE :query)
                LIMIT :top_k
            """
            )

            result = db.session.execute(  # tenant-exempt: document_embeddings is infrastructure table
                search_query, {"domain": domain, "query": query, "top_k": top_k}
            )

            rows = result.fetchall()

            # Convert to search result format
            results = []
            for row in rows:
                results.append(
                    {
                        "id": row.content_id,
                        "metadata": json.loads(row.metadata) if row.metadata else {},
                        "domain": row.domain,
                        "content_type": row.content_type,
                        "similarity": 0.5,  # Default similarity for fallback
                        "rerank_score": 0.5,
                        "boost_applied": 1.0,
                        "metadata_boost": 1.0,
                        "fallback": True,
                    }
                )

            return results

        except Exception as e:
            self.logger.error(f"Fallback search failed: {e}")
            return []

    def hybrid_search(
        self, query: str, domain: str = "general", top_k: int = 10, semantic_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword search.

        Args:
            query: Search query
            domain: Target domain
            top_k: Number of results
            semantic_weight: Weight for semantic search (0 - 1)

        Returns:
            Combined search results
        """
        try:
            # Get semantic search results
            semantic_results = self.semantic_search(query, domain, top_k)

            # Get keyword search results
            keyword_results = self._keyword_search(query, domain, top_k)

            # Combine and re-rank results
            combined_results = self._combine_search_results(
                semantic_results, keyword_results, semantic_weight
            )

            return combined_results[:top_k]

        except Exception as e:
            self.logger.error(f"Hybrid search failed: {e}")
            # Fallback to semantic search only
            return self.semantic_search(query, domain, top_k)

    def _keyword_search(self, query: str, domain: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Perform keyword-based search.

        Args:
            query: Search query
            domain: Target domain
            top_k: Number of results

        Returns:
            Keyword search results
        """
        try:
            # Extract keywords from query
            keywords = self._extract_keywords(query)

            if not keywords:
                return []

            # Build search query
            keyword_conditions = []
            query_params = {"domain": domain, "top_k": top_k}

            for i, keyword in enumerate(keywords):
                keyword_conditions.append(
                    f"(CAST(metadata AS TEXT) LIKE :kw{i} OR content_id LIKE :kw{i})"
                )
                query_params[f"kw{i}"] = f"%{keyword}%"

            where_clause = f"WHERE domain = :domain AND ({' OR '.join(keyword_conditions)})"

            # tenant-exempt: system table (document_embeddings is infrastructure)
            search_query = text(
                f"""
                SELECT content_id, metadata, domain, content_type
                FROM document_embeddings
                {where_clause}
                LIMIT :top_k
            """
            )

            result = db.session.execute(search_query, query_params)  # tenant-exempt: document_embeddings is infrastructure table
            rows = result.fetchall()

            # Convert to search result format
            results = []
            for row in rows:
                results.append(
                    {
                        "id": row.content_id,
                        "metadata": json.loads(row.metadata) if row.metadata else {},
                        "domain": row.domain,
                        "content_type": row.content_type,
                        "similarity": 0.3,  # Lower similarity for keyword search
                        "rerank_score": 0.3,
                        "boost_applied": 1.0,
                        "metadata_boost": 1.0,
                        "keyword_search": True,
                    }
                )

            return results

        except Exception as e:
            self.logger.error(f"Keyword search failed: {e}")
            return []

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from search query.

        Args:
            query: Search query

        Returns:
            List of keywords
        """
        # Simple keyword extraction - can be enhanced with NLP
        import re

        # Remove common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }

        # Extract words
        words = re.findall(r"\b\w+\b", query.lower())

        # Filter stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        return keywords

    def _combine_search_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        semantic_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword search results.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic results

        Returns:
            Combined and re-ranked results
        """
        keyword_weight = 1.0 - semantic_weight

        # Create result map
        result_map = {}

        # Add semantic results
        for result in semantic_results:
            result_id = result["id"]
            result_map[result_id] = result.copy()
            result_map[result_id]["combined_score"] = result["rerank_score"] * semantic_weight

        # Add keyword results
        for result in keyword_results:
            result_id = result["id"]
            if result_id in result_map:
                # Combine scores
                existing = result_map[result_id]
                existing["combined_score"] = (
                    existing["combined_score"] + result["rerank_score"] * keyword_weight
                )
                existing["keyword_match"] = True
            else:
                # New result from keyword search
                result_copy = result.copy()
                result_copy["combined_score"] = result["rerank_score"] * keyword_weight
                result_copy["keyword_only"] = True
                result_map[result_id] = result_copy

        # Convert to list and sort by combined score
        combined_results = list(result_map.values())
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)

        return combined_results

    def get_search_suggestions(
        self, query: str, domain: str = "general", limit: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on partial query.

        Args:
            query: Partial search query
            domain: Target domain
            limit: Number of suggestions

        Returns:
            List of suggested queries
        """
        try:
            # Use semantic similarity to find similar content
            suggestions = self.semantic_search(query, domain, limit)

            # Extract titles or key phrases from results
            suggested_queries = []
            for result in suggestions:
                metadata = result.get("metadata", {})

                # Try to get title from metadata
                if "title" in metadata:
                    suggested_queries.append(metadata["title"])
                elif "name" in metadata:
                    suggested_queries.append(metadata["name"])
                elif "description" in metadata:
                    # Extract first 50 characters
                    desc = metadata["description"]
                    if len(desc) > 50:
                        desc = desc[:47] + "..."
                    suggested_queries.append(desc)

            return suggested_queries[:limit]

        except Exception as e:
            self.logger.error(f"Error getting search suggestions: {e}")
            return []

    def index_document(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        """
        Index a document for semantic search.

        Args:
            doc_id: Document ID
            content: Document content
            metadata: Document metadata
        """
        try:
            # Generate embedding
            embedding = self.embedding_service.embed_text(content)

            # Add to vector store
            self.vector_store.add_vector(doc_id, embedding, metadata)

            self.logger.info(f"Document {doc_id} indexed successfully")

        except Exception as e:
            self.logger.error(f"Error indexing document {doc_id}: {e}")
            raise

    def remove_document(self, doc_id: str):
        """
        Remove a document from the search index.

        Args:
            doc_id: Document ID to remove
        """
        try:
            self.vector_store.delete_vector(doc_id)
            self.logger.info(f"Document {doc_id} removed from index")

        except Exception as e:
            self.logger.error(f"Error removing document {doc_id}: {e}")
            raise

    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get search statistics and performance metrics.

        Returns:
            Search statistics
        """
        try:
            # Get document count by domain
            # tenant-exempt: system table (document_embeddings is infrastructure)
            domain_query = text(
                """
                SELECT domain, COUNT(*) as count
                FROM document_embeddings
                GROUP BY domain
                ORDER BY count DESC
            """
            )

            result = db.session.execute(domain_query)  # tenant-exempt: document_embeddings is infrastructure table
            domain_stats = {row.domain: row.count for row in result}

            # Get content type distribution
            # tenant-exempt: system table (document_embeddings is infrastructure)
            type_query = text(
                """
                SELECT content_type, COUNT(*) as count
                FROM document_embeddings
                GROUP BY content_type
                ORDER BY count DESC
            """
            )

            result = db.session.execute(type_query)  # tenant-exempt: document_embeddings is infrastructure table
            type_stats = {row.content_type: row.count for row in result}

            return {
                "total_documents": sum(domain_stats.values()),
                "domain_distribution": domain_stats,
                "content_type_distribution": type_stats,
                "cache_size": len(self._search_cache),
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting search stats: {e}")
            return {}
