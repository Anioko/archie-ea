"""
Smart APQC Classifier with Business Domain Knowledge

.. deprecated:: 2.0.0
   This module is deprecated. Use :mod:`app.services.unified_apqc_service` instead.

   Migration:
       # Old way (deprecated):
       from app.services.smart_apqc_classifier import SmartAPQCClassifier
       classifier = SmartAPQCClassifier()
       results = classifier.classify_text(text)

       # New way:
       from app.services.unified_apqc_service import get_unified_apqc_service
       service = get_unified_apqc_service()
       results = service.classify_text(text)

Combines vector embeddings with business process understanding.

NOTE: This module is kept for backward compatibility but should not be used directly.
Use the unified_apqc_service module instead.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

from app import db
from app.services.business_process_knowledge import BusinessProcessKnowledge
from app.utils.deprecation import APQC_UNIFIED_SERVICE, deprecated_function, deprecated_service

logger = logging.getLogger(__name__)

# Module-level deprecation warning
import warnings

warnings.warn(
    "smart_apqc_classifier is deprecated. Use unified_apqc_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import optional services
VECTOR_EMBEDDING_AVAILABLE = False
SEMANTIC_APQC_AVAILABLE = False

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


@deprecated_service(
    replacement=APQC_UNIFIED_SERVICE,
    version="2.0.0",
    reason="Consolidated into UnifiedAPQCService for maintainability",
    removal_version="3.0.0",
)
class SmartAPQCClassifier:
    """
    Smart APQC classifier with business domain knowledge.

    .. deprecated:: 2.0.0
       Use :class:`app.services.unified_apqc_service.UnifiedAPQCService` instead.
    """

    def __init__(self):
        self.knowledge = BusinessProcessKnowledge()
        self.vector_service = None
        if VECTOR_EMBEDDING_AVAILABLE:
            try:
                self.vector_service = VectorEmbeddingService()
            except Exception as e:
                logger.warning(f"Failed to initialize VectorEmbeddingService: {e}")

    def classify_text(self, text: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Classify text to APQC processes using smart combination of methods

        Args:
            text: Text to classify
            max_results: Maximum number of results to return

        Returns:
            List of classification results with business-aware scores
        """
        if not text or not text.strip():
            return []

        logger.info(f"Smart classification for: {text[:100]}...")

        # Step 1: Identify business domain
        domain, domain_confidence = self.knowledge.identify_business_domain(text)
        logger.info(
            f"Identified domain: {domain.domain_name if domain else 'Unknown'} (confidence: {domain_confidence:.3f})"
        )

        # Step 2: Expand text with synonyms
        expanded_texts = self.knowledge.expand_with_synonyms(text)
        logger.info(f"Expanded to {len(expanded_texts)} text variants")

        # Step 3: Get candidate processes using multiple methods
        candidates = self._get_candidate_processes(expanded_texts, max_results * 2)

        # Step 4: Score candidates with business knowledge
        scored_results = self._score_with_business_knowledge(text, candidates, domain)

        # Step 5: Apply business rules and filters
        filtered_results = self._apply_business_rules(text, scored_results, domain)

        # Step 6: Return top results
        final_results = sorted(filtered_results, key=lambda x: x["business_score"], reverse=True)[
            :max_results
        ]

        logger.info(f"Smart classification returned {len(final_results)} results")
        return final_results

    def _get_candidate_processes(
        self, texts: List[str], max_candidates: int
    ) -> List[Dict[str, Any]]:
        """Get candidate processes using multiple methods"""
        all_candidates = []

        # Method 1: Exact regex matching (highest precision)
        for text in texts:
            regex_matches = self._regex_classify(text)
            all_candidates.extend(regex_matches)

        # Method 2: Vector similarity (if available)
        if self.vector_service:
            try:
                vector_matches = self._vector_classify(texts[0], max_candidates // 2)
                all_candidates.extend(vector_matches)
            except Exception as e:
                logger.warning(f"Vector classification failed: {e}")

        # Method 3: Semantic APQC (if available)
        if SEMANTIC_APQC_AVAILABLE:
            try:
                import asyncio

                semantic_service = SemanticAPQCService()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    semantic_service.classify_to_apqc(texts[0], max_results=max_candidates // 2)
                )
                loop.close()

                if result and result.matches:
                    semantic_matches = self._convert_semantic_results(result.matches)
                    all_candidates.extend(semantic_matches)
            except Exception as e:
                logger.warning(f"Semantic classification failed: {e}")

        # Remove duplicates by process_code
        unique_candidates = {}
        for candidate in all_candidates:
            code = candidate.get("process_code")
            if code and code not in unique_candidates:
                unique_candidates[code] = candidate

        return list(unique_candidates.values())

    def _regex_classify(self, text: str) -> List[Dict[str, Any]]:
        """Enhanced regex classification with validation"""
        results = []

        # Multiple patterns for different APQC formats
        patterns = [r"(?=\b\d+\.\d+(?:\.\d+)*\s)", r"(?=\b\d\.\d\.\d\s)", r"(?=\b\d\.\d\s)"]

        for pattern in patterns:
            parts = re.split(pattern, text)

            for part in parts:
                part = part.strip()
                if part and len(part) > 3:
                    code_match = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s*(.*)$", part)
                    if code_match:
                        process_code = code_match.group(1)
                        process_name = code_match.group(2).strip()

                        if self._is_valid_apqc_code(process_code):
                            results.append(
                                {
                                    "process_code": process_code,
                                    "process_name": process_name,
                                    "raw_score": 0.95,  # High confidence for exact matches
                                    "source": "regex_exact",
                                    "existing_id": None,
                                    "business_score": 0.95,  # Will be adjusted later
                                }
                            )

        return results

    def _vector_classify(self, text: str, max_results: int) -> List[Dict[str, Any]]:
        """Vector similarity classification with business awareness"""
        from app.models.apqc_process import APQCProcess

        # Fix database transaction
        try:
            db.session.rollback()
        except Exception as e:
            logger.debug("Session rollback failed: %s", e)
        try:
            db.session.begin()
        except Exception as e:
            logger.debug("Session begin failed: %s", e)

        # Get processes
        try:
            processes = APQCProcess.query.all()
            if not processes:
                return []
        except Exception as e:
            logger.error(f"Error querying APQC processes: {e}")
            return []

        # Generate text embedding
        try:
            text_embedding = self.vector_service.embed_text(text)
            if not text_embedding:
                return []
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            return []

        # Calculate similarities
        similarities = []
        for process in processes:
            try:
                process_text = f"{process.process_code} {process.process_name}"
                if hasattr(process, "process_category"):
                    process_text += f" {process.process_category}"

                process_embedding = self.vector_service.embed_text(process_text)
                if process_embedding:
                    similarity = self._cosine_similarity(text_embedding, process_embedding)

                    similarities.append(
                        {
                            "process_code": process.process_code,
                            "process_name": process.process_name,
                            "raw_score": similarity,
                            "source": "vector_similarity",
                            "existing_id": process.id,
                            "business_score": similarity,  # Will be adjusted
                        }
                    )
            except Exception as e:
                logger.debug(f"Error processing {process.process_code}: {e}")
                continue

        # Return top results
        similarities.sort(key=lambda x: x["raw_score"], reverse=True)
        return similarities[:max_results]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity"""
        import numpy as np

        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _convert_semantic_results(self, matches: List) -> List[Dict[str, Any]]:
        """Convert semantic results to standard format"""
        results = []
        for match in matches:
            results.append(
                {
                    "process_code": match.process_code,
                    "process_name": match.process_name,
                    "raw_score": match.similarity_score,
                    "source": "semantic_similarity",
                    "existing_id": match.process_id,
                    "business_score": match.similarity_score,
                    "confidence": match.confidence,
                    "match_method": match.match_method,
                }
            )
        return results

    def _score_with_business_knowledge(
        self, text: str, candidates: List[Dict[str, Any]], domain
    ) -> List[Dict[str, Any]]:
        """Score candidates using business knowledge"""
        for candidate in candidates:
            process_code = candidate.get("process_code")
            if not process_code:
                continue

            # Calculate domain confidence
            domain_confidence = self.knowledge.calculate_domain_confidence(text, process_code)

            # Get related processes bonus
            related_bonus = 0.0
            related_processes = self.knowledge.get_related_processes(process_code, max_depth=1)
            for related_code, score in related_processes:
                # Check if related processes are in candidates
                for other_candidate in candidates:
                    if other_candidate.get("process_code") == related_code:
                        related_bonus += score * 0.1
                        break

            # Calculate final business score
            raw_score = candidate.get("raw_score", 0.5)
            business_score = (
                raw_score * 0.4
                + domain_confidence * 0.4  # Raw similarity weight
                + related_bonus * 0.2  # Domain alignment weight  # Related processes weight
            )

            candidate["business_score"] = min(1.0, business_score)
            candidate["domain_confidence"] = domain_confidence
            candidate["related_bonus"] = related_bonus

        return candidates

    def _apply_business_rules(
        self, text: str, candidates: List[Dict[str, Any]], domain
    ) -> List[Dict[str, Any]]:
        """Apply business rules to filter and rank results"""
        filtered = []

        for candidate in candidates:
            process_code = candidate.get("process_code")
            business_score = candidate.get("business_score", 0)

            # Rule 1: Minimum business score threshold
            if business_score < 0.3:
                continue

            # Rule 2: Boost for exact code matches
            if process_code in text:
                candidate["business_score"] = min(1.0, business_score + 0.2)
                candidate["boost_reason"] = "exact_code_match"

            # Rule 3: Boost for domain-specific keywords
            if domain and process_code.split(".")[0] in [
                code.split(".")[0] for code in domain.process_codes
            ]:
                candidate["business_score"] = min(1.0, business_score + 0.15)
                candidate["boost_reason"] = "domain_alignment"

            # Rule 4: Penalty for unrelated high-level categories
            if domain and process_code.split(".")[0] not in [
                code.split(".")[0] for code in domain.process_codes
            ]:
                if business_score > 0.7:  # Only penalize high scores
                    candidate["business_score"] *= 0.8
                    candidate["penalty_reason"] = "domain_mismatch"

            filtered.append(candidate)

        return filtered

    def _is_valid_apqc_code(self, code: str) -> bool:
        """Validate APQC code format"""
        parts = code.split(".")

        if len(parts) not in [2, 3]:
            return False

        for part in parts:
            if not part.isdigit():
                return False

        # First level validation
        if parts[0] and not (1 <= int(parts[0]) <= 13):
            return False

        return True


# Convenience function for backward compatibility
@deprecated_function(
    replacement="app.services.unified_apqc_service.classify_apqc_text_unified",
    version="2.0.0",
    reason="Use classify_apqc_text_unified from unified_apqc_service instead",
)
def classify_apqc_text_smart(text: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Smart APQC classification with business knowledge.

    .. deprecated:: 2.0.0
       Use :func:`app.services.unified_apqc_service.classify_apqc_text_unified` instead.
    """
    classifier = SmartAPQCClassifier()
    return classifier.classify_text(text, max_results)
