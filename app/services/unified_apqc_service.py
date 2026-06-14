"""
Unified APQC Service
=====================
PRD - 011.1: Consolidated APQC classification service

This is the SINGLE ENTRY POINT for all APQC classification functionality.
All other APQC services are deprecated and should not be used directly.

Combines:
- SemanticAPQCService (primary) - semantic similarity using embeddings
- FAISSAPQCService (fallback) - fast vector search
- ChromaDBAPQCService (metadata filtering) - rich metadata support
- EnhancedAPQCService (numpy-based) - simple vector operations

DEPRECATED SERVICES (do not import directly):
- semantic_apqc_service.SemanticAPQCService
- faiss_apqc_service.FAISSAPQCService
- chromadb_apqc_service.ChromaDBAPQCService
- enhanced_apqc_service.EnhancedAPQCService
- real_ai_apqc_service.classify_apqc_text_real
- smart_apqc_classifier.SmartAPQCClassifier

Usage:
    from app.services.unified_apqc_service import get_unified_apqc_service

    service = get_unified_apqc_service()
    results = service.classify("Customer relationship management")

    # For backward compatibility with old APIs:
    from app.services.unified_apqc_service import classify_text, search_similar
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class APQCBackend(Enum):
    """Available APQC classification backends."""

    SEMANTIC = "semantic"
    FAISS = "faiss"
    CHROMADB = "chromadb"
    ENHANCED = "enhanced"
    REGEX = "regex"
    AUTO = "auto"  # Automatically select best available


@dataclass
class APQCClassificationResult:
    """Standardized result from APQC classification."""

    process_id: int
    process_code: str
    process_name: str
    confidence: float
    confidence_level: str  # high, medium, low
    classification_method: str  # semantic, faiss, chromadb, regex
    match_rationale: Optional[str] = None
    parent_process_id: Optional[int] = None
    apqc_level: int = 1
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "process_id": self.process_id,
            "process_code": self.process_code,
            "process_name": self.process_name,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "classification_method": self.classification_method,
            "match_rationale": self.match_rationale,
            "parent_process_id": self.parent_process_id,
            "apqc_level": self.apqc_level,
            "category_level_1": self.category_level_1,
            "category_level_2": self.category_level_2,
            "timestamp": self.timestamp,
        }


class UnifiedAPQCService:
    """
    Unified APQC classification service - SINGLE ENTRY POINT.

    This service consolidates all APQC classification functionality into a single
    interface. It automatically selects the best available backend and provides
    consistent results regardless of which backend is used.

    Usage:
        service = UnifiedAPQCService()
        results = service.classify("Customer relationship management")

    The service automatically selects the best available classification method:
    1. SemanticAPQCService (best accuracy, LLM-enhanced)
    2. FAISSAPQCService (fast vector search)
    3. ChromaDBAPQCService (when metadata filtering needed)
    4. EnhancedAPQCService (numpy-based fallback)
    5. Regex fallback (always available)
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50
    MIN_THRESHOLD = 0.30

    def __init__(self, preferred_backend: APQCBackend = APQCBackend.AUTO):
        """
        Initialize the unified APQC service.

        Args:
            preferred_backend: Which backend to prefer (AUTO selects best available)
        """
        self._semantic_service = None
        self._faiss_service = None
        self._chromadb_service = None
        self._enhanced_service = None
        self._hierarchy_service = None
        self._services_initialized = False
        self._preferred_backend = preferred_backend
        self._available_backends = []

    def _init_services(self):
        """Lazy initialization of services with graceful degradation."""
        if self._services_initialized:
            return

        # Try to initialize services (graceful degradation)
        # SemanticAPQCService - primary, best accuracy
        try:
            from app.services.semantic_apqc_service import SemanticAPQCService

            self._semantic_service = SemanticAPQCService()
            self._available_backends.append(APQCBackend.SEMANTIC)
            logger.info("UnifiedAPQC: SemanticAPQCService initialized")
        except Exception as e:
            logger.warning(f"UnifiedAPQC: SemanticAPQCService not available: {e}")

        # FAISSAPQCService - fast vector search (explicit build to avoid circular imports)
        try:
            from app.services.faiss_apqc_service import FAISSAPQCService

            self._faiss_service = FAISSAPQCService()
            if self._faiss_service.build_index():
                self._available_backends.append(APQCBackend.FAISS)
                logger.info("UnifiedAPQC: FAISSAPQCService initialized")
            else:
                logger.warning(
                    "UnifiedAPQC: FAISSAPQCService index not built (build_index returned False)"
                )
        except Exception as e:
            logger.warning(f"UnifiedAPQC: FAISSAPQCService not available: {e}")

        # ChromaDBAPQCService - metadata filtering support
        try:
            from app.services.chromadb_apqc_service import ChromaDBAPQCService

            self._chromadb_service = ChromaDBAPQCService()
            if self._chromadb_service.collection is not None:
                self._available_backends.append(APQCBackend.CHROMADB)
                logger.info("UnifiedAPQC: ChromaDBAPQCService initialized")
            else:
                logger.warning("UnifiedAPQC: ChromaDBAPQCService collection not built")
        except Exception as e:
            logger.warning(f"UnifiedAPQC: ChromaDBAPQCService not available: {e}")

        # EnhancedAPQCService - numpy-based fallback
        try:
            from app.services.enhanced_apqc_service import EnhancedAPQCService

            self._enhanced_service = EnhancedAPQCService()
            self._available_backends.append(APQCBackend.ENHANCED)
            logger.info("UnifiedAPQC: EnhancedAPQCService initialized")
        except Exception as e:
            logger.warning(f"UnifiedAPQC: EnhancedAPQCService not available: {e}")

        # Hierarchy service for enrichment
        try:
            from app.services.apqc_hierarchy_service import APQCHierarchyService

            self._hierarchy_service = APQCHierarchyService()
            logger.info("UnifiedAPQC: APQCHierarchyService initialized")
        except Exception as e:
            logger.warning(f"UnifiedAPQC: APQCHierarchyService not available: {e}")

        # Regex is always available
        self._available_backends.append(APQCBackend.REGEX)

        self._services_initialized = True
        logger.info(
            f"UnifiedAPQC: Available backends: {[b.value for b in self._available_backends]}"
        )

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        min_confidence: float = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        industry: Optional[str] = None,
        top_k: int = 5,
        backend: APQCBackend = None,
    ) -> List[APQCClassificationResult]:
        """
        Classify text to APQC processes.

        This is the main entry point for APQC classification. It automatically
        selects the best available backend or uses the specified one.

        Args:
            text: Text to classify
            context: Optional context (business domain, etc.)
            min_confidence: Minimum confidence threshold (default: 0.30)
            metadata_filter: Filter by metadata (requires ChromaDB)
            industry: Industry code for industry-specific matching
            top_k: Number of results to return
            backend: Specific backend to use (default: auto-select)

        Returns:
            List of APQCClassificationResult ordered by confidence
        """
        self._init_services()

        if not text or not text.strip():
            return []

        if min_confidence is None:
            min_confidence = self.MIN_THRESHOLD

        backend = backend or self._preferred_backend
        results = []
        method_used = None

        # If metadata filtering requested, use ChromaDB
        if metadata_filter and APQCBackend.CHROMADB in self._available_backends:
            try:
                results = self._classify_with_chromadb(text, metadata_filter, top_k)
                method_used = "chromadb"
            except Exception as e:
                logger.warning(f"UnifiedAPQC: ChromaDB classification failed: {e}")

        # Backend selection based on preference or auto
        if not results:
            if backend == APQCBackend.SEMANTIC or backend == APQCBackend.AUTO:
                if APQCBackend.SEMANTIC in self._available_backends:
                    try:
                        results = self._classify_with_semantic(text, context, top_k)
                        method_used = "semantic"
                    except Exception as e:
                        logger.warning(f"UnifiedAPQC: Semantic classification failed: {e}")

            if not results and (backend == APQCBackend.FAISS or backend == APQCBackend.AUTO):
                if APQCBackend.FAISS in self._available_backends:
                    try:
                        results = self._classify_with_faiss(text, top_k)
                        method_used = "faiss"
                    except Exception as e:
                        logger.warning(f"UnifiedAPQC: FAISS classification failed: {e}")

            if not results and (backend == APQCBackend.CHROMADB or backend == APQCBackend.AUTO):
                if APQCBackend.CHROMADB in self._available_backends:
                    try:
                        results = self._classify_with_chromadb(text, None, top_k)
                        method_used = "chromadb"
                    except Exception as e:
                        logger.warning(f"UnifiedAPQC: ChromaDB classification failed: {e}")

            if not results and (backend == APQCBackend.ENHANCED or backend == APQCBackend.AUTO):
                if APQCBackend.ENHANCED in self._available_backends:
                    try:
                        results = self._classify_with_enhanced(text, top_k)
                        method_used = "enhanced"
                    except Exception as e:
                        logger.warning(f"UnifiedAPQC: Enhanced classification failed: {e}")

        # Final fallback: regex
        if not results:
            results = self._classify_with_regex(text)
            method_used = "regex"

        # Filter by confidence
        results = [r for r in results if r.confidence >= min_confidence]

        # Add hierarchy information if available
        if self._hierarchy_service:
            results = self._enrich_with_hierarchy(results)

        logger.info(
            f"UnifiedAPQC: Classified '{text[:50]}...' using {method_used}, got {len(results)} results"
        )

        return results[:top_k]

    def classify_text(
        self, text: str, max_results: int = 5, threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Classify text - backward compatible method returning dictionaries.

        This method provides backward compatibility with older service APIs
        that return dictionaries instead of dataclasses.

        Args:
            text: Text to classify
            max_results: Maximum number of results
            threshold: Minimum confidence threshold

        Returns:
            List of dictionaries with classification results
        """
        results = self.classify(text, min_confidence=threshold, top_k=max_results)
        return [r.to_dict() for r in results]

    def search_similar(
        self, text: str, top_k: int = 5, where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar APQC processes - backward compatible method.

        This method provides backward compatibility with ChromaDB/FAISS APIs.

        Args:
            text: Text to search for
            top_k: Number of results
            where_filter: Optional metadata filter

        Returns:
            List of similar APQC processes with scores
        """
        self._init_services()

        # Use ChromaDB if filter provided and available
        if where_filter and self._chromadb_service:
            try:
                return self._chromadb_service.search_similar(text, top_k, where_filter)
            except Exception as e:
                logger.warning(f"UnifiedAPQC: ChromaDB search failed: {e}")

        # Use FAISS for similarity search
        if self._faiss_service and self._faiss_service.index:
            try:
                return self._faiss_service.search_similar(text, top_k)
            except Exception as e:
                logger.warning(f"UnifiedAPQC: FAISS search failed: {e}")

        # Fallback to ChromaDB without filter
        if self._chromadb_service and self._chromadb_service.collection:
            try:
                return self._chromadb_service.search_similar(text, top_k)
            except Exception as e:
                logger.warning(f"UnifiedAPQC: ChromaDB search failed: {e}")

        # Final fallback
        return self.classify_text(text, max_results=top_k)

    def _classify_with_semantic(
        self, text: str, context: Optional[Dict], top_k: int
    ) -> List[APQCClassificationResult]:
        """Use semantic service for classification."""
        # Use synchronous method to avoid async issues
        raw_result = self._semantic_service.classify_text(text, max_results=top_k)
        return self._convert_semantic_results(raw_result)

    def _classify_with_faiss(self, text: str, top_k: int) -> List[APQCClassificationResult]:
        """Use FAISS service for classification."""
        raw_results = self._faiss_service.classify_text(text, max_results=top_k)
        return self._convert_dict_results(raw_results, "faiss")

    def _classify_with_chromadb(
        self, text: str, metadata_filter: Optional[Dict], top_k: int
    ) -> List[APQCClassificationResult]:
        """Use ChromaDB service for classification with metadata filtering."""
        raw_results = self._chromadb_service.classify_text(
            text, max_results=top_k, filters=metadata_filter
        )
        return self._convert_dict_results(raw_results, "chromadb")

    def _classify_with_enhanced(self, text: str, top_k: int) -> List[APQCClassificationResult]:
        """Use enhanced numpy-based service for classification."""
        raw_results = self._enhanced_service.classify_text(text, max_results=top_k)
        return self._convert_dict_results(raw_results, "enhanced")

    def _classify_with_regex(self, text: str) -> List[APQCClassificationResult]:
        """Fallback regex-based classification."""
        import re

        from app import db
        from app.models.apqc_process import APQCProcess

        # Extract PCF codes (e.g., 1.0, 1.1.1, 10.2.3.4)
        pattern = r"\b(\d{1,2}(?:\.\d{1,2}){0,4})\b"
        matches = re.findall(pattern, text)

        results = []
        for match in matches:
            try:
                process = APQCProcess.query.filter_by(process_code=match).first()
                if process:
                    results.append(
                        APQCClassificationResult(
                            process_id=process.id,
                            process_code=process.process_code,
                            process_name=process.process_name,
                            confidence=0.6,  # Regex match is medium confidence
                            confidence_level="medium",
                            classification_method="regex",
                            match_rationale=f"Direct code match: {match}",
                            category_level_1=getattr(process, "category_level_1", None),
                            category_level_2=getattr(process, "category_level_2", None),
                        )
                    )
            except Exception as e:
                logger.debug(f"Error looking up process {match}: {e}")

        return results

    def _convert_semantic_results(self, raw_result: Any) -> List[APQCClassificationResult]:
        """Convert SemanticAPQCService results to standardized format."""
        results = []

        # Handle APQCClassificationResult from SemanticAPQCService
        if hasattr(raw_result, "matches"):
            for match in raw_result.matches:
                confidence = getattr(match, "similarity_score", 0.5)
                confidence_level = self._get_confidence_level(confidence)

                results.append(
                    APQCClassificationResult(
                        process_id=getattr(match, "process_id", 0),
                        process_code=getattr(match, "process_code", ""),
                        process_name=getattr(match, "process_name", ""),
                        confidence=confidence,
                        confidence_level=confidence_level,
                        classification_method="semantic",
                        apqc_level=getattr(match, "level", 1),
                        category_level_1=getattr(match, "category_level_1", None),
                        category_level_2=getattr(match, "category_level_2", None),
                    )
                )
        # Handle list of matches directly
        elif isinstance(raw_result, list):
            for match in raw_result:
                if hasattr(match, "similarity_score"):
                    confidence = match.similarity_score
                    results.append(
                        APQCClassificationResult(
                            process_id=getattr(match, "process_id", 0),
                            process_code=getattr(match, "process_code", ""),
                            process_name=getattr(match, "process_name", ""),
                            confidence=confidence,
                            confidence_level=self._get_confidence_level(confidence),
                            classification_method="semantic",
                            apqc_level=getattr(match, "level", 1),
                            category_level_1=getattr(match, "category_level_1", None),
                            category_level_2=getattr(match, "category_level_2", None),
                        )
                    )

        return results

    def _convert_dict_results(
        self, raw_results: List[Dict], method: str
    ) -> List[APQCClassificationResult]:
        """Convert dictionary results to standardized format."""
        results = []
        for r in raw_results:
            if isinstance(r, dict):
                process_id = r.get("process_id") or r.get("id") or r.get("existing_id") or 0
                process_code = r.get("process_code") or r.get("code") or ""
                process_name = r.get("process_name") or r.get("name") or ""
                confidence = r.get("confidence") or r.get("score", 0.5)

                results.append(
                    APQCClassificationResult(
                        process_id=process_id,
                        process_code=process_code,
                        process_name=process_name,
                        confidence=confidence,
                        confidence_level=self._get_confidence_level(confidence),
                        classification_method=method,
                        category_level_1=r.get("category_level_1"),
                        category_level_2=r.get("category_level_2"),
                    )
                )

        return results

    def _get_confidence_level(self, confidence: float) -> str:
        """Determine confidence level from score."""
        if confidence >= self.HIGH_CONFIDENCE:
            return "high"
        elif confidence >= self.MEDIUM_CONFIDENCE:
            return "medium"
        else:
            return "low"

    def _enrich_with_hierarchy(
        self, results: List[APQCClassificationResult]
    ) -> List[APQCClassificationResult]:
        """Add hierarchy information to results."""
        for result in results:
            try:
                hierarchy = self._hierarchy_service.get_hierarchy_path(result.process_id)
                if hierarchy:
                    result.apqc_level = len(hierarchy)
                    if len(hierarchy) > 1:
                        result.parent_process_id = hierarchy[-2].get("id")
            except Exception as e:
                logger.debug("Failed to enrich APQC result with hierarchy: %s", e)
        return results

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all available services."""
        self._init_services()
        return {
            "available_backends": [b.value for b in self._available_backends],
            "preferred_backend": self._preferred_backend.value,
            "semantic_available": APQCBackend.SEMANTIC in self._available_backends,
            "faiss_available": APQCBackend.FAISS in self._available_backends,
            "chromadb_available": APQCBackend.CHROMADB in self._available_backends,
            "enhanced_available": APQCBackend.ENHANCED in self._available_backends,
            "hierarchy_available": self._hierarchy_service is not None,
            "regex_available": True,  # Always available
        }

    def get_backend_stats(self) -> Dict[str, Any]:
        """Get statistics from available backends."""
        self._init_services()
        stats = {}

        if self._faiss_service:
            try:
                stats["faiss"] = self._faiss_service.get_stats()
            except Exception as e:
                stats["faiss"] = {"error": str(e)}

        if self._chromadb_service:
            try:
                stats["chromadb"] = self._chromadb_service.get_stats()
            except Exception as e:
                stats["chromadb"] = {"error": str(e)}

        return stats


# Singleton instance
_unified_service: Optional[UnifiedAPQCService] = None


def get_unified_apqc_service() -> UnifiedAPQCService:
    """
    Get or create unified APQC service instance.

    This is the recommended way to get an APQC classification service.
    Do not import individual services directly.

    Returns:
        UnifiedAPQCService instance
    """
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedAPQCService()
    return _unified_service


# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# =============================================================================
# These functions provide backward compatibility with older service APIs.
# New code should use UnifiedAPQCService directly.


def classify_text(text: str, max_results: int = 5, threshold: float = None) -> List[Dict[str, Any]]:
    """
    Backward compatible classification function.

    .. deprecated:: 2.0.0
       Use :func:`get_unified_apqc_service().classify()` instead.
    """
    return get_unified_apqc_service().classify_text(text, max_results, threshold)


def search_similar(
    text: str, top_k: int = 5, where_filter: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    Backward compatible similarity search function.

    .. deprecated:: 2.0.0
       Use :func:`get_unified_apqc_service().search_similar()` instead.
    """
    return get_unified_apqc_service().search_similar(text, top_k, where_filter)


def classify_apqc_text_unified(text: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Unified classification function - replacement for classify_apqc_text_real.

    This function replaces the deprecated real_ai_apqc_service.classify_apqc_text_real.

    Args:
        text: Text to classify
        max_results: Maximum number of results

    Returns:
        List of classification results
    """
    return get_unified_apqc_service().classify_text(text, max_results=max_results)


# =============================================================================
# RE-EXPORTS FOR MIGRATION
# =============================================================================
# These re-exports help with migration. Import from here instead of the
# individual services.

# APQCMatch dataclass for semantic results
try:
    from app.services.semantic_apqc_service import APQCMatch
except ImportError:
    APQCMatch = None
