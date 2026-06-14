"""
NumPy-based Vector Service - Alternative to pgvector

Provides vector similarity search using NumPy and Scikit-learn
without requiring PostgreSQL extensions.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)


class NumPyVectorService:
    """
    In-memory vector similarity service using NumPy and Scikit-learn.

    Alternative to pgvector that doesn't require PostgreSQL extensions.
    Perfect for APQC process classification and semantic search.
    """

    def __init__(self):
        self.vector_index = {}  # {domain: {id: vector}}
        self.metadata = {}  # {domain: {id: metadata}}
        self.dimension = None

    def add_vectors(
        self, domain: str, vectors: Dict[str, np.ndarray], metadata: Dict[str, Any] = None
    ):
        """
        Add vectors to the index for a specific domain.

        Args:
            domain: Domain name (e.g., 'apqc_pcf')
            vectors: Dictionary of {id: vector}
            metadata: Optional metadata for each vector
        """
        if domain not in self.vector_index:
            self.vector_index[domain] = {}
            self.metadata[domain] = {}

        # Set dimension from first vector if not set
        if self.dimension is None and vectors:
            first_vector = next(iter(vectors.values()))
            self.dimension = len(first_vector)

        # Add vectors and metadata
        for vector_id, vector in vectors.items():
            if len(vector) != self.dimension:
                logger.warning(
                    f"Vector {vector_id} dimension mismatch: {len(vector)} vs {self.dimension}"
                )
                continue

            self.vector_index[domain][vector_id] = np.array(vector, dtype=np.float32)
            if metadata and vector_id in metadata:
                self.metadata[domain][vector_id] = metadata[vector_id]

    def search_similar(
        self, domain: str, query_vector: np.ndarray, top_k: int = 5, similarity_type: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Find similar vectors using NumPy.

        Args:
            domain: Domain to search in
            query_vector: Query vector
            top_k: Number of results to return
            similarity_type: 'cosine', 'euclidean', or 'dot_product'

        Returns:
            List of similar vectors with scores
        """
        if domain not in self.vector_index or not self.vector_index[domain]:
            return []

        # Convert query to numpy array
        query_vector = np.array(query_vector, dtype=np.float32)

        # Get all vectors for the domain
        vector_ids = list(self.vector_index[domain].keys())
        vectors = np.array([self.vector_index[domain][vid] for vid in vector_ids])

        # Calculate similarities
        if similarity_type == "cosine":
            # Normalize vectors for cosine similarity
            query_norm = query_vector / np.linalg.norm(query_vector)
            vectors_norm = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
            similarities = np.dot(vectors_norm, query_norm)
        elif similarity_type == "euclidean":
            # Use negative euclidean distance (higher = more similar)
            distances = euclidean_distances([query_vector], vectors)[0]
            similarities = -distances
        else:  # dot_product
            similarities = np.dot(vectors, query_vector)

        # Get top-k results
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            vector_id = vector_ids[idx]
            result = {
                "id": vector_id,
                "score": float(similarities[idx]),
                "metadata": self.metadata[domain].get(vector_id, {}),
                "similarity_type": similarity_type,
            }
            results.append(result)

        return results

    def get_stats(self, domain: str) -> Dict[str, Any]:
        """Get statistics for a domain."""
        if domain not in self.vector_index:
            return {"total_vectors": 0, "dimension": self.dimension}

        return {
            "total_vectors": len(self.vector_index[domain]),
            "dimension": self.dimension,
            "has_metadata": len(self.metadata[domain]) > 0,
        }


# Singleton instance
_numpy_vector_service = NumPyVectorService()


def get_numpy_vector_service() -> NumPyVectorService:
    """Get the singleton NumPy vector service instance."""
    return _numpy_vector_service
