# mass-deletion-ok
"""

Unified Duplicate Detection Utilities

Provides consistent duplicate detection across all import systems.
Replaces multiple algorithms with a single, configurable approach.

Algorithms:
1. EXACT: Case-insensitive exact match (default)
2. FUZZY: Jaccard word-set similarity with configurable threshold

Usage:
    from app.services.duplicate_detection_utils import DuplicateDetectionUtils

    # Check if two names are duplicates (exact match)
    is_dup = DuplicateDetectionUtils.is_duplicate("Customer Portal", "customer portal")

    # Check with custom threshold (fuzzy matching)
    is_dup = DuplicateDetectionUtils.is_duplicate(
        "Customer Portal",
        "Customer Self-Service Portal",
        mode="fuzzy",
        threshold=0.6
    )

    # Find duplicates in a list of names
    duplicates = DuplicateDetectionUtils.find_duplicates(
        ["App A", "app a", "App B"],
        mode="exact"
    )  # Returns: {"app a": [0, 1]}  (indices of duplicates)

    # Check import row against database
    exists = DuplicateDetectionUtils.find_database_match(
        import_name="Customer Portal",
        existing_names=["customer portal", "other app"],
        mode="exact"
    )  # Returns: "customer portal" (matched name) or None
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Information about a duplicate match."""

    import_name: str
    matched_name: str
    score: float  # 0.0-1.0 for fuzzy, 1.0 for exact
    mode: str  # "exact" or "fuzzy"
    matched_index: Optional[int] = None  # Index in existing names list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "import_name": self.import_name,
            "matched_name": self.matched_name,
            "score": self.score,
            "mode": self.mode,
            "matched_index": self.matched_index,
        }


@dataclass
class DuplicateDetectionConfig:
    """Configuration for duplicate detection."""

    mode: str = "exact"  # "exact" or "fuzzy"
    threshold: float = 1.0  # Minimum score for fuzzy matching (0.0-1.0)
    description_weight: float = 0.3  # Weight for description similarity
    min_name_length: int = 2  # Minimum name length to check


class DuplicateDetectionUtils:
    """
    Unified duplicate detection utilities for consistent behavior
    across all import systems.
    """

    # Default configuration
    DEFAULT_CONFIG = DuplicateDetectionConfig()

    @staticmethod
    def tokenize(text: str) -> Set[str]:
        """
        Tokenize text into word set.

        Args:
            text: Text to tokenize

        Returns:
            Set of lowercase words
        """
        if not text:
            return set()
        return set(text.lower().split())

    @staticmethod
    def is_duplicate(
        name1: str,
        name2: str,
        mode: str = "exact",
        threshold: float = 1.0,
        config: Optional[DuplicateDetectionConfig] = None,
    ) -> Tuple[bool, float]:
        """
        Check if two names are duplicates.

        Args:
            name1: First name
            name2: Second name
            mode: "exact" or "fuzzy"
            threshold: Minimum score for fuzzy match (0.0-1.0)
            config: Optional configuration object

        Returns:
            Tuple of (is_duplicate: bool, score: float)
        """
        if config:
            mode = config.mode
            threshold = config.threshold

        norm1 = DuplicateDetectionUtils.normalize_name(name1)
        norm2 = DuplicateDetectionUtils.normalize_name(name2)

        if not norm1 or not norm2:
            return False, 0.0

        # Exact match (case-insensitive)
        if mode == "exact":
            score = 1.0 if norm1 == norm2 else 0.0
            return score >= threshold, score

        # Fuzzy match (Jaccard)
        score = DuplicateDetectionUtils.calculate_jaccard_similarity(norm1, norm2)
        return score >= threshold, score

    @staticmethod
    def find_duplicates(
        names: List[str],
        mode: str = "exact",
        threshold: float = 1.0,
        config: Optional[DuplicateDetectionConfig] = None,
    ) -> Dict[str, List[int]]:
        """
        Find duplicate names in a list.

        Args:
            names: List of names to check
            mode: "exact" or "fuzzy"
            threshold: Minimum score for fuzzy match
            config: Optional configuration object

        Returns:
            Dict mapping normalized name to list of indices where it appears
            Example: {"customer portal": [0, 2, 5]}
        """
        if config:
            mode = config.mode
            threshold = config.threshold

        duplicates: Dict[str, List[int]] = {}
        seen: Dict[str, int] = {}  # normalized_name -> first_index

        for idx, name in enumerate(names):
            if not name or len(name.strip()) < 2:
                continue

            norm_name = DuplicateDetectionUtils.normalize_name(name)

            if mode == "exact":
                if norm_name in seen:
                    if norm_name not in duplicates:
                        duplicates[norm_name] = [seen[norm_name]]
                    duplicates[norm_name].append(idx)
                else:
                    seen[norm_name] = idx
            else:
                # Fuzzy: check against all previous names
                for prev_norm, prev_idx in seen.items():
                    is_dup, score = DuplicateDetectionUtils.is_duplicate(
                        name, names[prev_idx], mode=mode, threshold=threshold
                    )
                    if is_dup:
                        if norm_name not in duplicates:
                            duplicates[norm_name] = [prev_idx]
                        duplicates[norm_name].append(idx)
                        break
                if norm_name not in duplicates:
                    seen[norm_name] = idx

        return duplicates

    @staticmethod
    def find_all_database_matches(
        import_name: str,
        existing_names: List[str],
        mode: str = "exact",
        threshold: float = 1.0,
        config: Optional[DuplicateDetectionConfig] = None,
        max_matches: int = 5,
    ) -> List[DuplicateMatch]:
        """
        Find all matching names in the database for an import name.

        Useful for preview/dry-run scenarios showing all potential matches.

        Args:
            import_name: Name from import file
            existing_names: List of existing names in database
            mode: "exact" or "fuzzy"
            threshold: Minimum score for fuzzy match
            config: Optional configuration object
            max_matches: Maximum number of matches to return

        Returns:
            List of DuplicateMatch objects, sorted by score descending
        """
        if config:
            mode = config.mode
            threshold = config.threshold

        if not import_name or not existing_names:
            return []

        matches: List[DuplicateMatch] = []

        for idx, existing_name in enumerate(existing_names):
            if not existing_name:
                continue

            is_dup, score = DuplicateDetectionUtils.is_duplicate(
                import_name, existing_name, mode=mode, threshold=threshold
            )

            if is_dup:
                matches.append(
                    DuplicateMatch(
                        import_name=import_name,
                        matched_name=existing_name,
                        score=score,
                        mode=mode,
                        matched_index=idx,
                    )
                )

        # Sort by score descending and limit
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:max_matches]


# Backward compatibility aliases
DuplicateDetectorUtils = DuplicateDetectionUtils
DuplicateDetectionService = DuplicateDetectionUtils
