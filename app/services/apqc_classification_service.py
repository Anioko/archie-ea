"""
APQC Classification Service (delegates to unified_apqc_service)
All legacy service calls now go through UnifiedAPQCService.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.unified_apqc_service import get_unified_apqc_service

logger = logging.getLogger(__name__)


def classify_apqc_text(
    text: str, max_results: int = 10, filters: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    Classify text to APQC processes using unified service (preferred).

    Args:
        text: Text to classify
        max_results: Maximum number of results to return
        filters: Optional metadata filters (used by unified service when ChromaDB available)

    Returns:
        List of classification results with process codes and scores
    """
    if not text or not text.strip():
        return []

    try:
        unified_service = get_unified_apqc_service()
        results = unified_service.classify_text(text, max_results=max_results)
        if results:
            return results
    except Exception as e:
        logger.warning(f"Unified APQC classification failed, falling back to regex: {e}")

    # Final fallback to regex-based classification
    logger.info("Using regex fallback for APQC classification")
    return _regex_classify_apqc(text)


def _regex_classify_apqc(text: str) -> List[Dict[str, Any]]:
    """
    Regex-based APQC classification as fallback

    Args:
        text: Text to classify

    Returns:
        List of classification results
    """
    results = []

    # Pattern to match APQC codes (e.g., "4.1.1 Process Name")
    pcf_pattern = r"(?=\b\d+\.\d+(?:\.\d+)*\s)"
    parts = re.split(pcf_pattern, text)

    for part in parts:
        part = part.strip()
        if part:
            code_match = re.match(r"^(\d+\.\d+(?:\.\d+)*)\s*(.*)$", part)
            if code_match:
                process_code = code_match.group(1)
                process_name = code_match.group(2).strip()

                results.append(
                    {
                        "process_code": process_code,
                        "process_name": process_name,
                        "score": 0.8,  # High confidence for exact matches
                        "source": "regex_extraction",
                        "existing_id": None,  # Will be filled by caller
                        "rank": len(results) + 1,
                    }
                )

    logger.info(f"Regex classification found {len(results)} matches")
    return results


def get_classification_status() -> Dict[str, Any]:
    """Get the status of classification methods"""
    unified_service = get_unified_apqc_service()
    status = unified_service.get_service_status()
    return {
        "chromadb_available": status.get("chromadb_available", False),
        "faiss_available": status.get("faiss_available", False),
        "classification_methods": status.get("available_backends", []),
        "recommended_method": status.get("preferred_backend", "regex"),
        "metadata_filtering": status.get("chromadb_available", False),
    }


def classify_apqc_with_metadata(
    text: str, where_filter: Dict, max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Classify text with metadata filtering (ChromaDB only feature)

    Args:
        text: Text to classify
        where_filter: Metadata filter dictionary
        max_results: Maximum number of results

    Returns:
        List of classification results with metadata filtering applied
    """
    if not text or not text.strip():
        return []

    try:
        unified_service = get_unified_apqc_service()
        return unified_service.search_similar(text, top_k=max_results, where_filter=where_filter)
    except Exception as e:
        logger.error(f"Unified APQC metadata classification failed: {e}")
        return classify_apqc_text(text, max_results=max_results)
