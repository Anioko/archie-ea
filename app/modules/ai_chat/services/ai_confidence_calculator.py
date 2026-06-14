"""
-> app.modules.ai_chat.services.ai_analysis_service

AI Confidence Calculator Service

Calculates confidence scores for AI-generated outputs based on:
- Keyword match strength
- Data quality of source entities
- Validation results
- Historical accuracy
- Model reliability
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.archimate_validation_service import ArchiMateValidationService

logger = logging.getLogger(__name__)


class AIConfidenceCalculator:
    """
    Calculates confidence scores for AI Chat operations.
    
    Replaces hardcoded confidence scores (e.g., 0.85) with calculated values
    based on actual data quality and validation results.
    """
    
    # Weight factors for confidence calculation
    WEIGHTS = {
        "keyword_match": 0.25,
        "data_quality": 0.25,
        "validation": 0.30,
        "historical": 0.20,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.archimate_validator = ArchiMateValidationService()
    
    def calculate_archimate_confidence(
        self,
        elements: List[Dict],
        keyword_matches: List[str],
        source_application: Dict,
    ) -> Dict[str, Any]:
        """
        Calculate confidence score for ArchiMate element generation.
        
        Args:
            elements: Generated ArchiMate elements
            keyword_matches: Keywords that matched in the source
            source_application: Source application data
            
        Returns:
            Confidence score breakdown and overall score
        """
        # 1. Keyword match strength (0-1)
        keyword_score = min(len(keyword_matches) * 0.1, 1.0) if keyword_matches else 0.3
        
        # 2. Data quality score based on source application
        data_quality = self._calculate_data_quality(source_application)
        
        # 3. Validation score
        validation_result = self.archimate_validator.validate_element_list(elements)
        validation_score = 1.0 if validation_result["valid"] else 0.5
        if validation_result["warnings"]:
            validation_score -= len(validation_result["warnings"]) * 0.1
        validation_score = max(validation_score, 0.0)
        
        # 4. Historical accuracy (default to 0.7 if no history)
        historical_score = 0.7  # Could be enhanced with actual historical tracking
        
        # Calculate weighted confidence
        overall_confidence = (
            keyword_score * self.WEIGHTS["keyword_match"] +
            data_quality * self.WEIGHTS["data_quality"] +
            validation_score * self.WEIGHTS["validation"] +
            historical_score * self.WEIGHTS["historical"]
        )
        
        return {
            "confidence": round(overall_confidence, 2),
            "breakdown": {
                "keyword_match": round(keyword_score, 2),
                "data_quality": round(data_quality, 2),
                "validation": round(validation_score, 2),
                "historical": round(historical_score, 2),
            },
            "weights": self.WEIGHTS,
            "validation_errors": validation_result["errors"],
            "validation_warnings": validation_result["warnings"],
        }
    
    def calculate_vendor_match_confidence(
        self,
        vendor_name: str,
        capability_keywords: List[str],
        match_factors: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate confidence score for vendor-to-capability matching.
        
        Args:
            vendor_name: Name of the vendor
            capability_keywords: Keywords from the capability
            match_factors: Additional matching factors
            
        Returns:
            Confidence score breakdown
        """
        # 1. Name similarity score
        name_score = match_factors.get("name_similarity", 0.5)
        
        # 2. Keyword overlap
        keyword_overlap = match_factors.get("keyword_overlap", 0.0)
        
        # 3. Data completeness
        data_completeness = match_factors.get("data_completeness", 0.5)
        
        # 4. Category alignment
        category_alignment = match_factors.get("category_alignment", 0.5)
        
        # Calculate weighted score
        overall = (name_score * 0.3 + keyword_overlap * 0.3 + 
                   data_completeness * 0.2 + category_alignment * 0.2)
        
        return {
            "confidence": round(overall, 2),
            "breakdown": {
                "name_similarity": round(name_score, 2),
                "keyword_overlap": round(keyword_overlap, 2),
                "data_completeness": round(data_completeness, 2),
                "category_alignment": round(category_alignment, 2),
            },
        }
    
    def calculate_entity_match_confidence(
        self,
        query: str,
        matched_entity: Dict,
        alternative_matches: List[Dict],
    ) -> Dict[str, Any]:
        """
        Calculate confidence score for entity matching.
        
        Args:
            query: Original search query
            matched_entity: The matched entity
            alternative_matches: Other potential matches
            
        Returns:
            Confidence score with disambiguation info
        """
        # 1. Exact match bonus
        query_lower = query.lower()
        entity_name = matched_entity.get("name", "").lower()
        exact_match = 1.0 if query_lower == entity_name else 0.0
        
        # 2. Partial match score
        if entity_name in query_lower or query_lower in entity_name:
            partial_score = 0.8
        else:
            # Word overlap
            query_words = set(query_lower.split())
            entity_words = set(entity_name.split())
            overlap = len(query_words & entity_words)
            partial_score = min(overlap / max(len(query_words), 1), 0.7)
        
        # 3. Uniqueness score (fewer alternatives = higher confidence)
        uniqueness = 1.0 / (1 + len(alternative_matches))
        
        # 4. Data quality of matched entity
        data_quality = self._calculate_entity_data_quality(matched_entity)
        
        # Overall confidence
        overall = max(exact_match, partial_score) * 0.4 + uniqueness * 0.3 + data_quality * 0.3
        
        return {
            "confidence": round(overall, 2),
            "breakdown": {
                "exact_match": round(exact_match, 2),
                "partial_match": round(partial_score, 2),
                "uniqueness": round(uniqueness, 2),
                "data_quality": round(data_quality, 2),
            },
            "requires_disambiguation": len(alternative_matches) > 0 and overall < 0.8,
            "alternative_count": len(alternative_matches),
        }
    
    def calculate_apqc_match_confidence(
        self,
        keyword: str,
        apqc_codes: List[str],
        match_context: str,
    ) -> Dict[str, Any]:
        """
        Calculate confidence for APQC keyword matching.
        
        Args:
            keyword: Matched keyword
            apqc_codes: Matched APQC process codes
            match_context: Context where keyword was found
            
        Returns:
            Confidence score for the match
        """
        # 1. Keyword strength (specificity)
        keyword_length_factor = min(len(keyword) / 10, 1.0)  # Longer keywords more specific
        
        # 2. Context quality
        context_quality = 0.7 if match_context else 0.5
        
        # 3. Code count (more codes = broader but less specific match)
        code_count_factor = max(1.0 - (len(apqc_codes) - 1) * 0.1, 0.5)
        
        # 4. Word boundary match bonus (already implemented in APQC matcher)
        boundary_match = 1.0  # Assuming regex word boundary was used
        
        overall = (keyword_length_factor * 0.3 + context_quality * 0.3 + 
                   code_count_factor * 0.2 + boundary_match * 0.2)
        
        return {
            "confidence": round(overall, 2),
            "breakdown": {
                "keyword_specificity": round(keyword_length_factor, 2),
                "context_quality": round(context_quality, 2),
                "code_specificity": round(code_count_factor, 2),
                "match_precision": round(boundary_match, 2),
            },
            "apqc_codes": apqc_codes,
        }
    
    def _calculate_data_quality(self, data: Dict) -> float:
        """Calculate data quality score based on field completeness."""
        if not data:
            return 0.3
        
        # Count non-empty fields
        total_fields = len(data)
        populated_fields = sum(1 for v in data.values() if v is not None and v != "")
        
        # Penalize if critical fields missing
        base_score = populated_fields / max(total_fields, 1)
        
        # Boost for description quality
        description = data.get("description", "")
        if description and len(description) > 50:
            base_score = min(base_score + 0.1, 1.0)
        
        return round(base_score, 2)
    
    def _calculate_entity_data_quality(self, entity: Dict) -> float:
        """Calculate data quality for an entity."""
        critical_fields = ["name", "id"]
        bonus_fields = ["description", "status", "owner"]
        
        # Check critical fields
        critical_score = sum(1 for f in critical_fields if entity.get(f)) / len(critical_fields)
        
        # Check bonus fields
        bonus_score = sum(0.1 for f in bonus_fields if entity.get(f))
        
        return min(critical_score + bonus_score, 1.0)
    
    def get_confidence_level(self, score: float) -> str:
        """Convert numeric score to confidence level."""
        if score >= 0.9:
            return "very_high"
        elif score >= 0.7:
            return "high"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.3:
            return "low"
        else:
            return "very_low"
    
    def should_require_review(self, confidence: float, operation_type: str) -> bool:
        """Determine if an operation should require human review."""
        thresholds = {
            "create": 0.6,
            "update": 0.5,
            "delete": 0.8,
            "archimate_generate": 0.7,
            "vendor_match": 0.6,
        }
        threshold = thresholds.get(operation_type, 0.6)
        return confidence < threshold
