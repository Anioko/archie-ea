"""
Enhanced APQC Service using NumPy vectors as pgvector alternative

.. deprecated:: 2.0.0
   This service is deprecated. Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

   Migration:
       # Old way (deprecated):
       from app.services.enhanced_apqc_service import get_enhanced_apqc_service
       service = get_enhanced_apqc_service()

       # New way:
       from app.services.unified_apqc_service import get_unified_apqc_service
       service = get_unified_apqc_service()

Combines regex fallback with NumPy-based semantic similarity
for improved APQC classification without PostgreSQL extensions.

NOTE: This module is kept for backward compatibility but should not be used directly.
The UnifiedAPQCService automatically delegates to this service when appropriate.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import numpy as np

from app.models.apqc_process import APQCProcess
from app.services.numpy_vector_service import get_numpy_vector_service
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
    "enhanced_apqc_service is deprecated. Use unified_apqc_service instead.",
    DeprecationWarning,
    stacklevel=2,
)


@deprecated_service(
    replacement=APQC_UNIFIED_SERVICE,
    version="2.0.0",
    reason="Consolidated into UnifiedAPQCService for maintainability",
    removal_version="3.0.0",
)
class EnhancedAPQCService:
    """
    Enhanced APQC classification using NumPy vectors.

    .. deprecated:: 2.0.0
       Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.

    Combines:
    1. Regex fallback for structured PCF codes
    2. NumPy-based semantic similarity for descriptions
    3. Hybrid approach for best results
    """

    def __init__(self):
        self.vector_service = get_numpy_vector_service()
        self._build_apqc_vectors()

    def _build_apqc_vectors(self):
        """Build vector index from APQC processes."""
        try:
            processes = APQCProcess.query.all()

            # Create text representations for vectorization
            vectors = {}
            metadata = {}

            for process in processes:
                # Build comprehensive text representation
                text_parts = [
                    process.process_name or "",
                    process.description or "",
                    process.category_level_1 or "",
                    process.category_level_2 or "",
                ]
                text = " ".join(filter(None, text_parts))

                if text.strip():
                    # Simple text-to-vector (can be enhanced with embeddings)
                    vector = self._text_to_vector(text)
                    vectors[process.process_code] = vector
                    metadata[process.process_code] = {
                        "process_name": process.process_name,
                        "description": process.description,
                        "category_level_1": process.category_level_1,
                        "category_level_2": process.category_level_2,
                        "level": process.level,
                    }

            # Add to vector service
            self.vector_service.add_vectors("apqc_pcf", vectors, metadata)

            stats = self.vector_service.get_stats("apqc_pcf")
            logger.info(f"Built APQC vector index: {stats}")

        except Exception as e:
            logger.error(f"Error building APQC vectors: {e}")

    def _text_to_vector(self, text: str) -> np.ndarray:
        """
        Convert text to vector representation.

        Simple implementation using character n-grams.
        Can be enhanced with proper embeddings later.
        """
        # Simple character-level vectorization
        text = text.lower().strip()

        # Create fixed-size vector (adjust dimension as needed)
        dimension = 100
        vector = np.zeros(dimension, dtype=np.float32)

        if not text:
            return vector

        # Character n-gram features
        for i, char in enumerate(text[:dimension]):
            vector[i] = ord(char) / 255.0  # Normalize character codes

        return vector

    def classify_text(self, text: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Classify text to APQC processes using enhanced approach.

        Args:
            text: Input text to classify
            max_results: Maximum number of results

        Returns:
            List of APQC matches with scores
        """
        results = []

        # Try regex first for structured PCF codes
        regex_matches = self._regex_classify(text)
        if regex_matches:
            results.extend(regex_matches)

        # Try semantic similarity for descriptions
        semantic_matches = self._semantic_classify(text, max_results - len(results))
        if semantic_matches:
            results.extend(semantic_matches)

        # Remove duplicates and sort by score
        seen_codes = set()
        unique_results = []
        for result in results:
            code = result.get("process_code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_results.append(result)

        return unique_results[:max_results]

    def _regex_classify(self, text: str) -> List[Dict[str, Any]]:
        """Extract PCF codes using regex patterns."""
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
                                    "score": 1.0,  # High confidence for exact matches
                                    "source": "regex_exact",
                                    "existing_id": process.id,
                                    "category_level_1": process.category_level_1,
                                    "category_level_2": process.category_level_2,
                                    "level": process.level,
                                }
                            )

        except Exception as e:
            logger.error(f"Error in regex classification: {e}")

        return matches

    def _semantic_classify(self, text: str, max_results: int) -> List[Dict[str, Any]]:
        """Classify using semantic similarity."""
        matches = []

        try:
            # Convert text to vector
            query_vector = self._text_to_vector(text)

            # Search for similar APQC processes
            similar = self.vector_service.search_similar(
                "apqc_pcf", query_vector, top_k=max_results, similarity_type="cosine"
            )

            for result in similar:
                metadata = result.get("metadata", {})
                matches.append(
                    {
                        "process_code": result["id"],
                        "process_name": metadata.get("process_name", ""),
                        "score": result["score"],
                        "source": "semantic_similarity",
                        "similarity_type": result["similarity_type"],
                        "category_level_1": metadata.get("category_level_1"),
                        "category_level_2": metadata.get("category_level_2"),
                        "level": metadata.get("level"),
                    }
                )

        except Exception as e:
            logger.error(f"Error in semantic classification: {e}")

        return matches


# Singleton instance
_enhanced_apqc_service = None


@deprecated_function(
    replacement=APQC_UNIFIED_GETTER,
    version="2.0.0",
    reason="Use get_unified_apqc_service() instead",
)
def get_enhanced_apqc_service() -> EnhancedAPQCService:
    """
    Get the singleton enhanced APQC service instance.

    .. deprecated:: 2.0.0
       Use :func:`app.services.unified_apqc_service.get_unified_apqc_service` instead.
    """
    global _enhanced_apqc_service
    if _enhanced_apqc_service is None:
        _enhanced_apqc_service = EnhancedAPQCService()
    return _enhanced_apqc_service
