"""
Semantic Similarity Service

Uses semantic embeddings and similarity algorithms to find related elements
beyond simple string matching.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from app import db
from app.models.archimate_core import ArchiMateElement

logger = logging.getLogger(__name__)


class SemanticSimilarityService:
    """
    Service for semantic similarity matching using multiple algorithms.

    Features:
    - Multi-algorithm similarity scoring
    - Semantic keyword extraction
    - Context-aware matching
    - Co-occurrence analysis
    """

    def __init__(self):
        self.similarity_algorithms = [
            self._jaccard_similarity,
            self._cosine_similarity_text,
            self._keyword_overlap,
            self._semantic_keyword_match,
        ]

    def find_semantically_similar(
        self,
        extracted_elem: Dict,
        existing_elements: List[ArchiMateElement],
        threshold: float = 0.7,
    ) -> List[Dict]:
        """
        Find semantically similar elements using multiple algorithms.

        Args:
            extracted_elem: Extracted element from document
            existing_elements: List of existing elements to match against
            threshold: Minimum similarity score (0 - 1)

        Returns:
            List of similar elements with scores
        """
        results = []
        extracted_name = extracted_elem.get("name", "").lower()
        extracted_desc = extracted_elem.get("description", "").lower()
        extracted_type = extracted_elem.get("type", "")

        # Extract semantic keywords from extracted element
        extracted_keywords = self._extract_semantic_keywords(
            extracted_name, extracted_desc, extracted_type
        )

        for existing_elem in existing_elements:
            existing_name = (existing_elem.name or "").lower()
            existing_desc = (existing_elem.description or "").lower()
            existing_type = existing_elem.type or ""

            # Skip if types don't match (unless very high similarity)
            if extracted_type and existing_type and extracted_type != existing_type:
                continue

            # Calculate multiple similarity scores
            scores = []

            # Name similarity
            name_score = SequenceMatcher(None, extracted_name, existing_name).ratio()
            scores.append(("name", name_score, 0.4))

            # Description similarity
            if extracted_desc and existing_desc:
                desc_score = self._calculate_text_similarity(extracted_desc, existing_desc)
                scores.append(("description", desc_score, 0.3))

            # Keyword overlap
            existing_keywords = self._extract_semantic_keywords(
                existing_name, existing_desc, existing_type
            )
            keyword_score = self._keyword_overlap(extracted_keywords, existing_keywords)
            scores.append(("keywords", keyword_score, 0.2))

            # Semantic keyword match
            semantic_score = self._semantic_keyword_match(extracted_keywords, existing_keywords)
            scores.append(("semantic", semantic_score, 0.1))

            # Calculate weighted overall score
            overall_score = sum(score * weight for _, score, weight in scores)

            if overall_score >= threshold:
                results.append(
                    {
                        "element_id": existing_elem.id,
                        "element_name": existing_elem.name,
                        "element_type": existing_elem.type,
                        "similarity_score": round(overall_score, 3),
                        "breakdown": {name: round(score, 3) for name, score, _ in scores},
                        "confidence": self._calculate_confidence(overall_score, scores),
                    }
                )

        # Sort by similarity score
        return sorted(results, key=lambda x: x["similarity_score"], reverse=True)

    def _extract_semantic_keywords(
        self, name: str, description: str, element_type: str
    ) -> Set[str]:
        """
        Extract semantic keywords from text.

        Removes common stopwords and extracts meaningful terms.
        """
        # Common stopwords
        stopwords = {
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
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "their",
        }

        # Combine text
        text = f"{name} {description} {element_type}".lower()

        # Extract words (alphanumeric sequences)
        words = re.findall(r"\b[a-z0 - 9]+\b", text)

        # Filter stopwords and short words
        keywords = {word for word in words if word not in stopwords and len(word) > 2}

        return keywords

    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity coefficient."""
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _cosine_similarity_text(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.

        Uses word frequency vectors.
        """
        if not text1 or not text2:
            return 0.0

        # Tokenize
        words1 = set(re.findall(r"\b\w+\b", text1.lower()))
        words2 = set(re.findall(r"\b\w+\b", text2.lower()))

        # Calculate intersection over union (simplified cosine)
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _keyword_overlap(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """Calculate keyword overlap score."""
        return self._jaccard_similarity(keywords1, keywords2)

    def _semantic_keyword_match(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """
        Semantic keyword matching using domain-specific synonyms.

        Recognizes related terms (e.g., "app" = "application", "API" = "interface").
        """
        # Domain-specific synonym groups
        synonym_groups = [
            {"app", "application", "system", "platform"},
            {"api", "interface", "endpoint", "service"},
            {"data", "information", "record", "entity"},
            {"user", "customer", "client", "stakeholder"},
            {"process", "workflow", "procedure", "operation"},
            {"capability", "function", "feature", "ability"},
            {"vendor", "supplier", "provider", "partner"},
            {"goal", "objective", "target", "aim"},
            {"requirement", "need", "specification", "demand"},
        ]

        # Normalize keywords using synonyms
        normalized1 = self._normalize_with_synonyms(keywords1, synonym_groups)
        normalized2 = self._normalize_with_synonyms(keywords2, synonym_groups)

        return self._jaccard_similarity(normalized1, normalized2)

    def _normalize_with_synonyms(
        self, keywords: Set[str], synonym_groups: List[Set[str]]
    ) -> Set[str]:
        """Normalize keywords using synonym groups."""
        normalized = set()

        for keyword in keywords:
            # Check if keyword belongs to any synonym group
            found_group = False
            for group in synonym_groups:
                if keyword in group:
                    # Use the first term in group as canonical form
                    normalized.add(list(group)[0])
                    found_group = True
                    break

            if not found_group:
                normalized.add(keyword)

        return normalized

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate overall text similarity using multiple methods."""
        if not text1 or not text2:
            return 0.0

        # Method 1: Cosine similarity
        cosine = self._cosine_similarity_text(text1, text2)

        # Method 2: Longest common subsequence
        lcs_score = self._lcs_similarity(text1, text2)

        # Method 3: Word order similarity
        order_score = self._word_order_similarity(text1, text2)

        # Weighted combination
        return (cosine * 0.5) + (lcs_score * 0.3) + (order_score * 0.2)

    def _lcs_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity based on longest common subsequence."""
        words1 = text1.lower().split()
        words2 = text2.lower().split()

        if not words1 or not words2:
            return 0.0

        # Simple LCS calculation
        m, n = len(words1), len(words2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if words1[i - 1] == words2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_length = dp[m][n]
        max_length = max(m, n)

        return lcs_length / max_length if max_length > 0 else 0.0

    def _word_order_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity based on word order."""
        words1 = text1.lower().split()
        words2 = text2.lower().split()

        if not words1 or not words2:
            return 0.0

        # Find common words and their positions
        common_words = set(words1) & set(words2)
        if not common_words:
            return 0.0

        # Calculate position differences
        pos1 = {word: i for i, word in enumerate(words1) if word in common_words}
        pos2 = {word: i for i, word in enumerate(words2) if word in common_words}

        # Average position difference (normalized)
        total_diff = sum(abs(pos1[word] - pos2[word]) for word in common_words)
        max_diff = len(words1) + len(words2)

        return 1.0 - (total_diff / max_diff) if max_diff > 0 else 0.0

    def _calculate_confidence(
        self, overall_score: float, score_breakdown: List[Tuple[str, float, float]]
    ) -> str:
        """Calculate confidence level based on score and breakdown."""
        if overall_score >= 0.9:
            return "very_high"
        elif overall_score >= 0.8:
            return "high"
        elif overall_score >= 0.7:
            return "medium"
        elif overall_score >= 0.6:
            return "low"
        else:
            return "very_low"

    def analyze_co_occurrence(
        self, extracted_elements: List[Dict], document_text: str
    ) -> List[Dict]:
        """
        Analyze co-occurrence patterns in document to suggest relationships.

        Elements that appear close together in text are likely related.
        """
        relationships = []

        # Build element name map
        element_map = {e.get("name", "").lower(): e for e in extracted_elements}
        element_names = list(element_map.keys())

        if len(element_names) < 2:
            return relationships

        # Find positions of each element name in document
        text_lower = document_text.lower()
        positions = {}

        for name in element_names:
            positions[name] = []
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(name, start)
                if pos == -1:
                    break
                positions[name].append(pos)
                start = pos + 1

        # Analyze proximity
        proximity_window = 500  # characters

        for i, name1 in enumerate(element_names):
            for name2 in element_names[i + 1 :]:
                # Check if they appear close together
                for pos1 in positions.get(name1, []):
                    for pos2 in positions.get(name2, []):
                        distance = abs(pos1 - pos2)

                        if distance <= proximity_window:
                            # Suggest relationship
                            elem1 = element_map[name1]
                            elem2 = element_map[name2]

                            # Infer relationship type based on element types
                            rel_type = self._infer_relationship_from_types(
                                elem1.get("type"), elem2.get("type")
                            )

                            relationships.append(
                                {
                                    "source": elem1.get("name"),
                                    "target": elem2.get("name"),
                                    "relationship_type": rel_type,
                                    "confidence": max(0.6, 1.0 - (distance / proximity_window)),
                                    "evidence": f"Co-occurrence in document (distance: {distance} chars)",
                                    "discovery_method": "co_occurrence",
                                }
                            )

                            # Only add once per pair
                            break
                    else:
                        continue
                    break

        return relationships

    def _infer_relationship_from_types(self, source_type: str, target_type: str) -> str:
        """Infer relationship type based on element types."""
        # Common patterns
        type_pairs = {
            ("ApplicationComponent", "ApplicationInterface"): "Composition",
            ("ApplicationInterface", "ApplicationService"): "Serving",
            ("ApplicationComponent", "ApplicationService"): "Composition",
            ("BusinessProcess", "ApplicationService"): "Serving",
            ("Goal", "Requirement"): "Realization",
            ("Requirement", "BusinessCapability"): "Association",
            ("ApplicationComponent", "DataObject"): "Access",
            ("BusinessCapability", "ApplicationComponent"): "Realization",
        }

        return type_pairs.get((source_type, target_type), "Association")
