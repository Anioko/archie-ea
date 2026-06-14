"""
FAISS-based APQC Service - High-performance vector similarity

.. deprecated:: 2.0.0
   This service is deprecated. Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

   Migration:
       # Old way (deprecated):
       from app.services.faiss_apqc_service import get_faiss_apqc_service
       service = get_faiss_apqc_service()

       # New way:
       from app.services.unified_apqc_service import get_unified_apqc_service
       service = get_unified_apqc_service()

Uses FAISS (Facebook AI Similarity Search) for ultra-fast APQC process classification.
Superior to pgvector in performance and much easier to use.

Now uses direct sentence-transformers to avoid circular imports.

NOTE: This module is kept for backward compatibility but should not be used directly.
The UnifiedAPQCService automatically delegates to this service when appropriate.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from flask import current_app, has_app_context

from app.models.apqc_process import APQCProcess
from app.utils.deprecation import (
    APQC_UNIFIED_GETTER,
    APQC_UNIFIED_SERVICE,
    deprecated_function,
    deprecated_service,
)

logger = logging.getLogger(__name__)

# Module-level deprecation warning
import warnings

warnings.warn(
    "faiss_apqc_service is deprecated. Use unified_apqc_service instead.",
    DeprecationWarning,
    stacklevel=2,
)


@deprecated_service(
    replacement=APQC_UNIFIED_SERVICE,
    version="2.0.0",
    reason="Consolidated into UnifiedAPQCService for maintainability",
    removal_version="3.0.0",
)
class FAISSAPQCService:
    """
    High-performance APQC classification using FAISS with REAL AI embeddings.

    .. deprecated:: 2.0.0
       Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

    Features:
    - Ultra-fast similarity search (10k+ queries/sec)
    - REAL semantic embeddings via sentence-transformers
    - Multiple index types (IVF, HNSW, Flat)
    - Hybrid approach (regex + FAISS)
    - Memory-efficient indexing
    """

    def __init__(self, use_real_embeddings: bool = True):
        self.index = None
        self.process_metadata = {}  # {index_id: process_info}
        self.code_to_index = {}  # {process_code: index_id}
        self.index_to_code = {}  # {index_id: process_code}
        self.dimension = 384  # sentence-transformers all-MiniLM-L6-v2 dimension
        self.use_real_embeddings = use_real_embeddings
        self._embedding_model = None

    def build_index(self):
        """Explicitly build the FAISS index (requires app context)."""
        if self.index is not None:
            return True
        if not has_app_context():
            logger.warning(
                "No Flask app context; skipping FAISS index build to avoid circular imports"
            )
            return False
        self._build_faiss_index()
        return self.index is not None

    def _build_faiss_index(self):
        """Build FAISS index from APQC processes."""
        try:
            processes = APQCProcess.query.all()

            if not processes:
                logger.warning("No APQC processes found for FAISS indexing")
                return

            # Create vectors for all processes
            vectors = []
            metadata = []

            for i, process in enumerate(processes):
                text_parts = [
                    process.process_name or "",
                    process.category_level_1 or "",
                    process.category_level_2 or "",
                    process.process_category or "",
                ]
                text = " ".join(filter(None, text_parts))

                vector = self._text_to_vector(text)
                vectors.append(vector)

                self.process_metadata[i] = {
                    "process_code": process.process_code,
                    "process_name": process.process_name,
                    "category_level_1": process.category_level_1,
                    "category_level_2": process.category_level_2,
                    "process_category": process.process_category,
                    "apqc_level": process.apqc_level,
                    "id": process.id,
                }

                self.code_to_index[process.process_code] = i
                self.index_to_code[i] = process.process_code

            vectors_array = np.array(vectors, dtype=np.float32)

            n_vectors, dim = vectors_array.shape
            self.dimension = dim

            nlist = min(100, n_vectors // 4)  # Number of clusters
            quantizer = faiss.IndexFlatL2(dim)  # Base index
            self.index = faiss.IndexIVFFlat(quantizer, dim, nlist)

            self.index.train(vectors_array)
            self.index.add(vectors_array)

            self.index.nprobe = min(10, nlist)  # Number of clusters to search

            logger.info(f"FAISS APQC index built: {n_vectors} processes, {dim} dimensions")

        except Exception as e:
            logger.error(f"Error building FAISS index: {e}")
            # Fallback to simple flat index
            self._build_simple_index()

    def _build_simple_index(self):
        """Build simple flat index as fallback."""
        try:
            processes = APQCProcess.query.all()
            vectors = []

            for i, process in enumerate(processes):
                text_parts = [
                    process.process_name or "",
                    process.category_level_1 or "",
                    process.category_level_2 or "",
                    process.process_category or "",
                ]
                text = " ".join(filter(None, text_parts))
                vector = self._text_to_vector(text)
                vectors.append(vector)

                self.process_metadata[i] = {
                    "process_code": process.process_code,
                    "process_name": process.process_name,
                    "category_level_1": process.category_level_1,
                    "category_level_2": process.category_level_2,
                    "process_category": process.process_category,
                    "apqc_level": process.apqc_level,
                    "id": process.id,
                }
                self.index_to_code[i] = process.process_code

            vectors_array = np.array(vectors, dtype=np.float32)
            self.dimension = vectors_array.shape[1]

            # Simple flat index
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(vectors_array)

            logger.info(f"Simple FAISS index built: {len(vectors)} processes")

        except Exception as e:
            logger.error(f"Error building simple FAISS index: {e}")

    def _get_embedding_model(self):
        """Lazy-load the sentence transformer model to avoid circular imports."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence transformer model initialized for FAISS")
            except Exception as e:
                logger.warning(f"Could not initialize sentence transformer: {e}")
                self._embedding_model = False  # Mark as failed, use fallback
        return self._embedding_model if self._embedding_model else None

    def _text_to_vector(self, text: str) -> np.ndarray:
        """
        Convert text to vector representation using REAL AI embeddings.

        Uses sentence-transformers (all-MiniLM-L6-v2) for semantic understanding.
        Falls back to character-level hashing only if embedding service fails.
        """
        text = str(text).lower().strip() if text else ""

        if not text:
            return np.zeros(self.dimension, dtype=np.float32)

        # Try to use real embeddings
        if self.use_real_embeddings:
            embedding_model = self._get_embedding_model()
            if embedding_model:
                try:
                    # Use sentence-transformers directly
                    embedding = embedding_model.encode(text, convert_to_tensor=False)
                    result = np.array(embedding, dtype=np.float32)
                    # Log success on first embedding to confirm it's working
                    if not hasattr(self, "_logged_embedding_success"):
                        logger.info(
                            f"FAISS: Successfully using real embeddings (dim={len(embedding)})"
                        )
                        self._logged_embedding_success = True
                    return result
                except Exception as e:
                    logger.warning(f"FAISS: Real embedding failed, using fallback: {e}")
                    if not hasattr(self, "_logged_fallback_warning"):
                        logger.warning(
                            "FAISS: Using fallback hash-based embeddings - "
                            "semantic search quality will be degraded!"
                        )
                        self._logged_fallback_warning = True

        # Fallback to simple character/word hashing (NOT semantic, but fast)
        return self._fallback_text_to_vector(text)

    def _fallback_text_to_vector(self, text: str) -> np.ndarray:
        """
        Fallback vector generation using character/word hashing.
        This is NOT semantic - only use when real embeddings fail.
        """
        vector = np.zeros(self.dimension, dtype=np.float32)

        # Character-level features
        for i, char in enumerate(text[: self.dimension // 2]):
            vector[i] = ord(char) / 255.0

        # Word-level features
        words = text.split()
        for j, word in enumerate(words[: self.dimension // 2]):
            if j < self.dimension // 2:
                word_hash = hash(word) % 1000
                vector[self.dimension // 2 + j] = word_hash / 1000.0

        return vector

    def search_similar(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar APQC processes using FAISS.

        Args:
            query_text: Text to search for
            top_k: Number of results to return

        Returns:
            List of similar APQC processes with scores
        """
        if self.index is None:
            logger.warning("FAISS index not built")
            return []

        try:
            # Convert query to vector
            query_vector = self._text_to_vector(query_text)
            query_vector = query_vector.reshape(1, -1)

            # Search FAISS index
            distances, indices = self.index.search(query_vector, top_k)

            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx >= 0 and idx in self.process_metadata:
                    metadata = self.process_metadata[idx].copy()

                    # Convert distance to similarity score (lower distance = higher similarity)
                    similarity_score = 1.0 / (1.0 + dist)

                    result = {
                        "process_code": metadata["process_code"],
                        "process_name": metadata["process_name"],
                        "category_level_1": metadata["category_level_1"],
                        "category_level_2": metadata["category_level_2"],
                        "process_category": metadata["process_category"],
                        "apqc_level": metadata["apqc_level"],
                        "existing_id": metadata["id"],
                        "score": similarity_score,
                        "distance": float(dist),
                        "source": "faiss_similarity",
                        "rank": i + 1,
                    }
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error in FAISS search: {e}")
            return []

    def classify_text(self, text: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Classify text using hybrid approach (regex + FAISS).

        Args:
            text: Input text to classify
            max_results: Maximum number of results

        Returns:
            List of APQC matches with scores
        """
        all_results = []

        # Try regex first for structured PCF codes
        regex_matches = self._regex_classify(text)
        if regex_matches:
            all_results.extend(regex_matches)

        # Try FAISS for semantic similarity
        faiss_matches = self.search_similar(text, max_results - len(all_results))
        if faiss_matches:
            all_results.extend(faiss_matches)

        # Remove duplicates and sort by score
        seen_codes = set()
        unique_results = []
        for result in all_results:
            code = result.get("process_code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_results.append(result)

        # Sort by score (descending)
        unique_results.sort(key=lambda x: x["score"], reverse=True)

        return unique_results[:max_results]

    def _regex_classify(self, text: str) -> List[Dict[str, Any]]:
        """Extract PCF codes using regex patterns."""
        import re

        matches = []

        try:
            # Look for PCF patterns like "3.2.1 Digital content"
            pcf_pattern = r"(?=\b\d+\.\d+(?:\.\d+)*\s)"
            parts = re.split(pcf_pattern, text)

            for part in parts:
                part = part.strip()
                if part:
                    code_match = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s*(.*)$", part)
                    if code_match:
                        pcf_code = code_match.group(1)
                        process_name = code_match.group(2).strip()

                        # Validate against database
                        process = APQCProcess.query.filter_by(process_code=pcf_code).first()
                        if process:
                            matches.append(
                                {
                                    "process_code": pcf_code,
                                    "process_name": process_name,
                                    "description": process.process_description,
                                    "category_level_1": process.category_level_1,
                                    "category_level_2": process.category_level_2,
                                    "level": process.apqc_level,
                                    "existing_id": process.id,
                                    "score": 1.0,  # High confidence for exact matches
                                    "source": "regex_exact",
                                }
                            )

        except Exception as e:
            logger.error(f"Error in regex classification: {e}")

        return matches

    def search_by_vector(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar APQC processes using a pre-computed vector.

        This method allows direct vector search without re-embedding,
        useful when the caller has already computed the embedding.

        Args:
            query_vector: Pre-computed embedding vector (numpy array or list)
            top_k: Number of results to return

        Returns:
            List of similar APQC processes with scores
        """
        if self.index is None:
            logger.warning("FAISS index not built")
            return []

        try:
            # Ensure query vector is proper shape
            if isinstance(query_vector, list):
                query_vector = np.array(query_vector, dtype=np.float32)

            query_vector = query_vector.reshape(1, -1).astype(np.float32)

            # Handle dimension mismatch
            if query_vector.shape[1] != self.dimension:
                logger.warning(
                    f"Vector dimension mismatch: expected {self.dimension}, "
                    f"got {query_vector.shape[1]}. Adjusting..."
                )
                if query_vector.shape[1] < self.dimension:
                    # Pad with zeros
                    padding = np.zeros(
                        (1, self.dimension - query_vector.shape[1]), dtype=np.float32
                    )
                    query_vector = np.concatenate([query_vector, padding], axis=1)
                else:
                    # Truncate
                    query_vector = query_vector[:, : self.dimension]

            # Search FAISS index
            distances, indices = self.index.search(query_vector, top_k)

            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx >= 0 and idx in self.process_metadata:
                    metadata = self.process_metadata[idx].copy()

                    # Convert distance to similarity score
                    similarity_score = 1.0 / (1.0 + dist)

                    result = {
                        "process_code": metadata["process_code"],
                        "process_name": metadata["process_name"],
                        "category_level_1": metadata["category_level_1"],
                        "category_level_2": metadata["category_level_2"],
                        "process_category": metadata["process_category"],
                        "apqc_level": metadata["apqc_level"],
                        "existing_id": metadata["id"],
                        "score": similarity_score,
                        "distance": float(dist),
                        "source": "faiss_vector_search",
                        "rank": i + 1,
                    }
                    results.append(result)

            logger.info(f"FAISS vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in FAISS vector search: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get FAISS index statistics."""
        if self.index is None:
            return {"status": "not_built"}

        return {
            "status": "built",
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": type(self.index).__name__,
            "is_trained": hasattr(self.index, "is_trained") and self.index.is_trained,
        }


# Singleton instance
_faiss_apqc_service = None


@deprecated_function(
    replacement=APQC_UNIFIED_GETTER,
    version="2.0.0",
    reason="Use get_unified_apqc_service() instead",
)
def get_faiss_apqc_service() -> FAISSAPQCService:
    """
    Get the singleton FAISS APQC service instance.

    .. deprecated:: 2.0.0
       Use :func:`app.services.unified_apqc_service.get_unified_apqc_service` instead.
    """
    global _faiss_apqc_service
    if _faiss_apqc_service is None:
        _faiss_apqc_service = FAISSAPQCService()
    return _faiss_apqc_service
