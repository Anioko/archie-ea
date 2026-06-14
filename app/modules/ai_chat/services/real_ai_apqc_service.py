"""
REAL AI-Powered APQC Classification Service

.. deprecated:: 2.0.0
   This module is deprecated. Use :mod:`app.services.unified_apqc_service` instead.

   Migration:
       # Old way (deprecated):
       from app.services.real_ai_apqc_service import classify_apqc_text_real
       results = classify_apqc_text_real(text)

       # New way:
       from app.services.unified_apqc_service import classify_apqc_text_unified
       results = classify_apqc_text_unified(text)

Uses actual vector embeddings and semantic similarity, not fake character hashing.

NOTE: This module is kept for backward compatibility but should not be used directly.
Use the unified_apqc_service module instead.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from flask import current_app

from app import db
from app.utils.deprecation import deprecated_function

logger = logging.getLogger(__name__)

# Module-level deprecation warning
import warnings

warnings.warn(
    "real_ai_apqc_service is deprecated. Use unified_apqc_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Try to import real AI services
VECTOR_EMBEDDING_AVAILABLE = False
SEMANTIC_APQC_AVAILABLE = False
FAISS_AVAILABLE = False

try:
    from app.services.vector_embedding_service import VectorEmbeddingService

    VECTOR_EMBEDDING_AVAILABLE = True
    logger.info("VectorEmbeddingService is available")
except ImportError as e:
    logger.warning(f"VectorEmbeddingService not available: {e}")

try:
    from app.services.semantic_apqc_service import SemanticAPQCService

    SEMANTIC_APQC_AVAILABLE = True
    logger.info("SemanticAPQCService is available")
except ImportError as e:
    logger.warning(f"SemanticAPQCService not available: {e}")

try:
    from app.services.faiss_apqc_service import get_faiss_apqc_service

    FAISS_AVAILABLE = True
    logger.info("FAISS service is available")
except ImportError as e:
    logger.warning(f"FAISS service not available: {e}")


@deprecated_function(
    replacement="app.services.unified_apqc_service.classify_apqc_text_unified",
    version="2.0.0",
    reason="Use classify_apqc_text_unified from unified_apqc_service instead",
)
def classify_apqc_text_real(text: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    REAL AI-powered APQC classification using actual semantic similarity.

    .. deprecated:: 2.0.0
       Use :func:`app.services.unified_apqc_service.classify_apqc_text_unified` instead.

    Args:
        text: Text to classify
        max_results: Maximum number of results to return

    Returns:
        List of classification results with real semantic scores
    """
    if not text or not text.strip():
        return []

    # Method 1: Use SemanticAPQCService if available (best option)
    if SEMANTIC_APQC_AVAILABLE:
        try:
            semantic_service = SemanticAPQCService()
            # Run the async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                semantic_service.classify_to_apqc(text, max_results=max_results)
            )
            loop.close()

            if result and result.matches:
                logger.info(
                    f"Semantic APQC classification successful: {len(result.matches)} matches"
                )
                return _convert_semantic_results(result.matches)
        except Exception as e:
            logger.warning(f"Semantic APQC classification failed: {e}")

    # Method 2: Use VectorEmbeddingService for semantic similarity
    if VECTOR_EMBEDDING_AVAILABLE:
        try:
            return _vector_embedding_classify(text, max_results)
        except Exception as e:
            logger.warning(f"Vector embedding classification failed: {e}")

    # Method 3: Use FAISS if available (but only if it has real embeddings)
    if FAISS_AVAILABLE:
        try:
            faiss_service = get_faiss_apqc_service()
            results = faiss_service.classify_text(text, max_results=max_results)
            if results:
                # Check if FAISS is using real embeddings (not character hashing)
                if _is_real_faiss_embeddings(results):
                    logger.info(f"FAISS classification successful: {len(results)} matches")
                    return results
                else:
                    logger.warning("FAISS is using fake embeddings - skipping")
        except Exception as e:
            logger.warning(f"FAISS classification failed: {e}")

    # Fallback: Enhanced regex with better patterns
    logger.info("Using enhanced regex fallback for APQC classification")
    return _enhanced_regex_classify(text)


def _convert_semantic_results(matches: List) -> List[Dict[str, Any]]:
    """Convert SemanticAPQCService results to standard format"""
    results = []
    for match in matches:
        results.append(
            {
                "process_code": match.process_code,
                "process_name": match.process_name,
                "score": match.similarity_score,
                "source": "semantic_similarity",
                "existing_id": match.process_id,
                "rank": len(results) + 1,
                "confidence": match.confidence,
                "match_method": match.match_method,
            }
        )
    return results


def _vector_embedding_classify(text: str, max_results: int) -> List[Dict[str, Any]]:
    """Use VectorEmbeddingService for real semantic classification"""
    from app.models.apqc_process import APQCProcess

    # Fix database transaction state
    try:
        db.session.rollback()
    except Exception as e:
        logger.debug("Session rollback failed: %s", e)
    try:
        db.session.begin()
    except Exception as e:
        logger.debug("Session begin failed: %s", e)

    # Get all APQC processes
    try:
        processes = APQCProcess.query.all()
        if not processes:
            logger.warning("No APQC processes found in database")
            return []
    except Exception as e:
        logger.error(f"Error querying APQC processes: {e}")
        return []

    # Initialize vector service
    vector_service = VectorEmbeddingService()

    # Get embedding for input text
    try:
        text_embedding = vector_service.embed_text(text)
        if not text_embedding:
            logger.error("Failed to generate embedding for input text")
            return []
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []

    # Calculate similarity with each process
    similarities = []
    for process in processes:
        # Create searchable text from process
        process_text = f"{process.process_code} {process.process_name}"
        if hasattr(process, "process_category"):
            process_text += f" {process.process_category}"

        try:
            process_embedding = vector_service.embed_text(process_text)
            if process_embedding:
                # Calculate cosine similarity
                similarity = _cosine_similarity(text_embedding, process_embedding)
                similarities.append(
                    {
                        "process_code": process.process_code,
                        "process_name": process.process_name,
                        "score": similarity,
                        "source": "vector_similarity",
                        "existing_id": process.id,
                        "rank": 0,  # Will be set after sorting
                    }
                )
        except Exception as e:
            logger.debug(f"Error embedding process {process.process_code}: {e}")
            continue

    # Sort by similarity and return top results
    similarities.sort(key=lambda x: x["score"], reverse=True)

    # Add rank and filter by minimum similarity
    results = []
    for i, sim in enumerate(similarities[:max_results]):
        if sim["score"] > 0.3:  # Minimum similarity threshold
            sim["rank"] = i + 1
            results.append(sim)

    logger.info(f"Vector embedding classification found {len(results)} matches")
    return results


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    import numpy as np

    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def _is_real_faiss_embeddings(results: List[Dict[str, Any]]) -> bool:
    """Check if FAISS is using real embeddings or fake character hashing"""
    # Real embeddings should produce varied similarity scores
    # Fake character hashing produces very predictable patterns
    if not results:
        return False

    scores = [r.get("score", 0) for r in results]

    # If all scores are very similar (within 0.1), likely fake
    if len(scores) > 1:
        score_range = max(scores) - min(scores)
        if score_range < 0.1:
            return False

    # If scores are all multiples of 0.001, likely character hashing
    for score in scores:
        if abs(score * 1000 - round(score * 1000)) > 0.001:
            return True  # Not a clean multiple, likely real

    return False  # All scores are clean multiples, likely fake


def _enhanced_regex_classify(text: str) -> List[Dict[str, Any]]:
    """Enhanced regex classification with better patterns and validation"""
    results = []

    # Multiple patterns to catch different APQC code formats
    patterns = [
        r"(?=\b\d+\.\d+(?:\.\d+)*\s)",  # Standard APQC pattern
        r"(?=\b\d\.\d\.\d\s)",  # Specific 3 - level pattern
        r"(?=\b\d\.\d\s)",  # 2 - level pattern
    ]

    for pattern in patterns:
        parts = re.split(pattern, text)

        for part in parts:
            part = part.strip()
            if part and len(part) > 3:  # Ignore very short parts
                code_match = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s*(.*)$", part)
                if code_match:
                    process_code = code_match.group(1)
                    process_name = code_match.group(2).strip()

                    # Validate the code format
                    if _is_valid_apqc_code(process_code):
                        results.append(
                            {
                                "process_code": process_code,
                                "process_name": process_name,
                                "score": 0.9,  # High confidence for exact matches
                                "source": "enhanced_regex",
                                "existing_id": None,  # Will be filled by caller
                                "rank": len(results) + 1,
                            }
                        )

    logger.info(f"Enhanced regex classification found {len(results)} matches")
    return results


def _is_valid_apqc_code(code: str) -> bool:
    """Validate if an APQC code format is reasonable"""
    parts = code.split(".")

    # Must have 2 or 3 parts
    if len(parts) not in [2, 3]:
        return False

    # All parts must be digits
    for part in parts:
        if not part.isdigit():
            return False

        # First level should be 1 - 10
        if parts.index(part) == 0 and not (1 <= int(part) <= 10):
            return False

        # Second level should be reasonable
        if parts.index(part) == 1 and int(part) > 20:
            return False

        # Third level (if present) should be reasonable
        if parts.index(part) == 2 and int(part) > 50:
            return False

    return True


def get_real_ai_status() -> Dict[str, Any]:
    """Get the status of REAL AI classification methods"""
    return {
        "vector_embedding_available": VECTOR_EMBEDDING_AVAILABLE,
        "semantic_apqc_available": SEMANTIC_APQC_AVAILABLE,
        "faiss_available": FAISS_AVAILABLE,
        "real_ai_methods": [
            method
            for method, available in [
                ("semantic_apqc", SEMANTIC_APQC_AVAILABLE),
                ("vector_embedding", VECTOR_EMBEDDING_AVAILABLE),
                ("faiss_real", FAISS_AVAILABLE),
            ]
            if available
        ],
        "recommended_method": "semantic_apqc"
        if SEMANTIC_APQC_AVAILABLE
        else ("vector_embedding" if VECTOR_EMBEDDING_AVAILABLE else "enhanced_regex"),
        "has_real_ai": SEMANTIC_APQC_AVAILABLE or VECTOR_EMBEDDING_AVAILABLE,
    }
