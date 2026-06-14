"""
Fuzzy String Matching Service

Provides advanced fuzzy matching algorithms for duplicate detection,
replacing binary exact string matching with gradual similarity scores.

Implements:
- Levenshtein distance (edit distance)
- Jaro-Winkler similarity (good for typos, prefix matching)
- Token-based matching (word overlap)
- Domain-specific synonym dictionary
- Text preprocessing and normalization

Usage:
    matcher = FuzzyMatcher()
    score = matcher.calculate_similarity("HR System", "HR Management System")
    # Returns: 0.78 (gradual score, not binary 0 or 1)
"""

import re
from typing import Dict, List, Optional, Tuple

try:
    import Levenshtein

    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False

try:
    import jellyfish

    HAS_JELLYFISH = True
except ImportError:
    HAS_JELLYFISH = False


class FuzzyMatcher:
    """
    Fuzzy string matching service for duplicate detection

    Provides gradual similarity scores (0.0 - 1.0) instead of binary (0 or 1).
    """

    # Domain-specific synonyms for enterprise applications
    SYNONYMS = {
        "erp": ["enterprise resource planning", "enterprise resource planning system"],
        "crm": ["customer relationship management", "customer relationship management system"],
        "scm": ["supply chain management", "supply chain management system"],
        "hrms": [
            "human resources management system",
            "hr management system",
            "human resources system",
        ],
        "hr": ["human resources", "human resource"],
        "iam": ["identity and access management", "identity access management"],
        "cms": ["content management system", "content management"],
        "bpm": ["business process management", "business process management system"],
        "bi": ["business intelligence", "business intelligence system"],
        "dms": ["document management system", "document management"],
        "wms": ["warehouse management system", "warehouse management"],
        "tms": ["transportation management system", "transport management system"],
        "pim": ["product information management", "product information management system"],
        "plm": ["product lifecycle management", "product lifecycle management system"],
        "eam": ["enterprise asset management", "enterprise asset management system"],
        "mdm": ["master data management", "master data management system"],
        "ecommerce": ["e-commerce", "e commerce", "electronic commerce"],
        "db": ["database", "data base"],
        "app": ["application"],
        "mgmt": ["management"],
        "sys": ["system"],
    }

    # Stop words to remove from text
    STOP_WORDS = {
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
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
    }

    def __init__(self, use_synonyms: bool = True, use_preprocessing: bool = True):
        """
        Initialize fuzzy matcher

        Args:
            use_synonyms: Enable domain synonym expansion
            use_preprocessing: Enable text normalization/preprocessing
        """
        self.use_synonyms = use_synonyms
        self.use_preprocessing = use_preprocessing

        # Build reverse synonym map for faster lookup
        self._synonym_map: Dict[str, str] = {}
        if use_synonyms:
            for abbrev, expansions in self.SYNONYMS.items():
                for expansion in expansions:
                    self._synonym_map[expansion.lower()] = abbrev.lower()
                # Also map abbreviation to itself
                self._synonym_map[abbrev.lower()] = abbrev.lower()

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for better matching

        - Convert to lowercase
        - Remove extra whitespace
        - Remove punctuation (except hyphens in words)
        - Replace hyphens with spaces (normalize word separators)
        - Remove stop words
        - Remove version numbers
        - Standardize common patterns

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower().strip()

        # Remove version patterns (v1.0, version 2.0, 2.0.1, etc.)
        text = re.sub(r"\bv\d+(\.\d+)*\b", "", text)
        text = re.sub(r"\bversion\s+\d+(\.\d+)*\b", "", text)
        text = re.sub(r"\b\d+(\.\d+){1,3}\b", "", text)  # Standalone version numbers

        # Replace hyphens with spaces (normalize word separators)
        text = text.replace("-", " ")

        # Replace punctuation with spaces
        text = re.sub(r"[^\w\s]", " ", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove stop words
        words = text.split()
        words = [w for w in words if w not in self.STOP_WORDS]
        text = " ".join(words)

        return text

    def tokenize(self, text: str, remove_stop_words: bool = True) -> List[str]:
        """
        Tokenize text into words

        Args:
            text: Input text
            remove_stop_words: Remove common stop words

        Returns:
            List of tokens
        """
        text = self.normalize_text(text)
        tokens = text.split()

        if remove_stop_words:
            tokens = [t for t in tokens if t not in self.STOP_WORDS]

        return tokens

    def expand_synonyms(self, text: str) -> str:
        """
        Expand domain-specific synonyms

        Converts abbreviations to full forms for better matching.
        E.g., "CRM" → "customer relationship management"

        Args:
            text: Input text

        Returns:
            Text with synonyms expanded
        """
        if not self.use_synonyms:
            return text

        text_lower = text.lower()

        # Check for exact abbreviation match (as whole word)
        for abbrev, expansions in self.SYNONYMS.items():
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(abbrev) + r"\b"
            if re.search(pattern, text_lower):
                # Replace with first expansion
                text_lower = re.sub(pattern, expansions[0], text_lower)

        return text_lower

    def levenshtein_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate Levenshtein (edit distance) similarity

        Measures minimum number of single-character edits needed to transform
        str1 into str2. Normalized to 0.0-1.0 range.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0

        if HAS_LEVENSHTEIN:
            distance = Levenshtein.distance(str1, str2)
            max_len = max(len(str1), len(str2))
            return 1.0 - (distance / max_len) if max_len > 0 else 1.0
        else:
            # Fallback: simple ratio
            return self._simple_ratio(str1, str2)

    def jaro_winkler_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate Jaro-Winkler similarity

        Good for detecting typos and strings that share a common prefix.
        More lenient than Levenshtein distance.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 - 1.0)
        """
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0

        if HAS_JELLYFISH:
            return jellyfish.jaro_winkler_similarity(str1, str2)
        else:
            # Fallback to Levenshtein
            return self.levenshtein_similarity(str1, str2)

    def token_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate token-based similarity (Jaccard coefficient)

        Measures overlap of words between two strings.
        Good for detecting similar applications with different word orders.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 - 1.0)
        """
        tokens1 = set(self.tokenize(str1))
        tokens2 = set(self.tokenize(str2))

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union) if union else 0.0

    def _simple_ratio(self, str1: str, str2: str) -> float:
        """
        Simple character-based similarity ratio (fallback)

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 - 1.0)
        """
        if str1 == str2:
            return 1.0

        len1, len2 = len(str1), len(str2)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0

        # Count matching characters
        matches = sum(c1 == c2 for c1, c2 in zip(str1, str2))
        return matches / max_len

    def calculate_similarity(
        self, str1: str, str2: str, weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate comprehensive similarity score using multiple algorithms

        Combines Levenshtein, Jaro-Winkler, and token-based similarity
        with configurable weights.

        Args:
            str1: First string
            str2: Second string
            weights: Algorithm weights (default: equal weights)
                - 'levenshtein': Edit distance weight
                - 'jaro_winkler': Jaro-Winkler weight
                - 'token': Token overlap weight

        Returns:
            Weighted average similarity score (0.0 - 1.0)
        """
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0

        # Default weights
        if weights is None:
            weights = {"levenshtein": 0.35, "jaro_winkler": 0.35, "token": 0.30}

        # Preprocess text
        if self.use_preprocessing:
            str1_processed = self.normalize_text(str1)
            str2_processed = self.normalize_text(str2)

            # Expand synonyms
            str1_expanded = self.expand_synonyms(str1_processed)
            str2_expanded = self.expand_synonyms(str2_processed)
        else:
            str1_expanded = str1
            str2_expanded = str2

        # Calculate individual scores
        lev_score = self.levenshtein_similarity(str1_expanded, str2_expanded)
        jw_score = self.jaro_winkler_similarity(str1_expanded, str2_expanded)
        token_score = self.token_similarity(str1_expanded, str2_expanded)

        # Weighted average
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0

        weighted_score = (
            lev_score * weights.get("levenshtein", 0)
            + jw_score * weights.get("jaro_winkler", 0)
            + token_score * weights.get("token", 0)
        ) / total_weight

        return weighted_score

    def are_similar(self, str1: str, str2: str, threshold: float = 0.60) -> Tuple[bool, float]:
        """
        Check if two strings are similar above threshold

        Args:
            str1: First string
            str2: Second string
            threshold: Minimum similarity score (default: 0.60)

        Returns:
            Tuple of (is_similar, similarity_score)
        """
        score = self.calculate_similarity(str1, str2)
        return (score >= threshold, score)

    def find_best_match(
        self, query: str, candidates: List[str], threshold: float = 0.60
    ) -> Optional[Tuple[str, float]]:
        """
        Find best matching string from candidates

        Args:
            query: Query string
            candidates: List of candidate strings
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (best_match, score) or None if no match above threshold
        """
        best_match = None
        best_score = threshold

        for candidate in candidates:
            score = self.calculate_similarity(query, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        return (best_match, best_score) if best_match else None
