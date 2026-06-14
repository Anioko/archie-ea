"""

Application Merging Service

Intelligent application merging functionality with similarity scoring,
conflict resolution, and audit trail.
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app import db
from app.models.application_portfolio import ApplicationComponent as ApplicationComponent

logger = logging.getLogger(__name__)


@dataclass
class MergeCandidate:
    """Represents a potential merge candidate"""

    primary_app: ApplicationComponent
    duplicate_app: ApplicationComponent
    similarity_score: float
    match_reasons: List[str]
    conflicts: List[str]


@dataclass
class MergeConfig:
    """Configuration for merge behavior"""

    name_weight: float = 0.3
    description_weight: float = 0.25
    vendor_weight: float = 0.2
    capability_weight: float = 0.15
    technology_weight: float = 0.1
    similarity_threshold: float = 0.7


class ApplicationMatchingService:
    """Service for finding and analyzing potential application merges"""

    def __init__(self, config: MergeConfig = None):
        self.config = config or MergeConfig()

    def find_merge_candidates(
        self, applications: List[ApplicationComponent]
    ) -> List[MergeCandidate]:
        """
        Find potential merge candidates among applications

        Args:
            applications: List of applications to analyze

        Returns:
            List of merge candidates with similarity scores
        """
        candidates = []

        for i, app1 in enumerate(applications):
            for app2 in applications[i + 1 :]:
                similarity = self._calculate_similarity(app1, app2)

                if similarity >= self.config.similarity_threshold:
                    match_reasons = self._get_match_reasons(app1, app2, similarity)
                    conflicts = self._detect_conflicts(app1, app2)

                    candidate = MergeCandidate(
                        primary_app=app1,
                        duplicate_app=app2,
                        similarity_score=similarity,
                        match_reasons=match_reasons,
                        conflicts=conflicts,
                    )
                    candidates.append(candidate)

        # Sort by similarity score (highest first)
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates

    def _calculate_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> float:
        """Calculate overall similarity score between two applications"""
        scores = []

        # Name similarity
        name_score = self._text_similarity(app1.name, app2.name)
        scores.append(("name", name_score, self.config.name_weight))

        # Description similarity
        desc1 = app1.description or ""
        desc2 = app2.description or ""
        if desc1 and desc2:
            desc_score = self._text_similarity(desc1, desc2)
            scores.append(("description", desc_score, self.config.description_weight))

        # Vendor similarity
        vendor1 = getattr(app1, "vendor", "") or ""
        vendor2 = getattr(app2, "vendor", "") or ""
        if vendor1 and vendor2:
            vendor_score = 1.0 if vendor1.lower() == vendor2.lower() else 0.0
            scores.append(("vendor", vendor_score, self.config.vendor_weight))

        # Capability overlap
        cap_score = self._capability_similarity(app1, app2)
        if cap_score is not None:
            scores.append(("capability", cap_score, self.config.capability_weight))

        # Technology stack similarity
        tech_score = self._technology_similarity(app1, app2)
        if tech_score is not None:
            scores.append(("technology", tech_score, self.config.technology_weight))

        # Calculate weighted average
        total_weight = sum(weight for _, _, weight in scores)
        weighted_score = (
            sum(score * weight for _, score, weight in scores) / total_weight
            if total_weight > 0
            else 0.0
        )

        return round(weighted_score, 3)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using multiple methods"""
        # Normalize text
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)

        if not text1 or not text2:
            return 0.0

        # Exact match
        if text1 == text2:
            return 1.0

        # Sequence matcher
        seq_score = SequenceMatcher(None, text1, text2).ratio()

        # Word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        if words1 and words2:
            word_score = len(words1 & words2) / len(words1 | words2)
        else:
            word_score = 0.0

        # Combined score
        return round((seq_score * 0.7 + word_score * 0.3), 3)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""

        # Convert to lowercase and remove extra whitespace
        text = re.sub(r"\s+", " ", text.lower().strip())

        # Remove common words that don't affect similarity
        stop_words = {
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
        }
        words = text.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 1]

        return " ".join(filtered_words)

    def _capability_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Optional[float]:
        """Calculate capability overlap similarity"""
        try:
            caps1 = set(getattr(app1, "capabilities", []))
            caps2 = set(getattr(app2, "capabilities", []))

            if not caps1 or not caps2:
                return None

            intersection = len(caps1 & caps2)
            union = len(caps1 | caps2)

            return round(intersection / union, 3) if union > 0 else 0.0
        except Exception as e:
            logger.warning(f"Error calculating capability similarity: {e}")
            return None

    def _technology_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Optional[float]:
        """Calculate technology stack similarity"""
        try:
            tech1 = set(getattr(app1, "technologies", []))
            tech2 = set(getattr(app2, "technologies", []))

            if not tech1 or not tech2:
                return None

            intersection = len(tech1 & tech2)
            union = len(tech1 | tech2)

            return round(intersection / union, 3) if union > 0 else 0.0
        except Exception as e:
            logger.warning(f"Error calculating technology similarity: {e}")
            return None

    def _get_match_reasons(
        self, app1: ApplicationComponent, app2: ApplicationComponent, similarity: float
    ) -> List[str]:
        """Get human-readable reasons for the match"""
        reasons = []

        # Name similarity
        name_sim = self._text_similarity(app1.name, app2.name)
        if name_sim > 0.8:
            reasons.append(f"Very similar names ({name_sim:.0%} match)")
        elif name_sim > 0.6:
            reasons.append(f"Similar names ({name_sim:.0%} match)")

        # Vendor match
        vendor1 = getattr(app1, "vendor", "") or ""
        vendor2 = getattr(app2, "vendor", "") or ""
        if vendor1 and vendor2 and vendor1.lower() == vendor2.lower():
            reasons.append("Same vendor")

        # Capability overlap
        cap_sim = self._capability_similarity(app1, app2)
        if cap_sim and cap_sim > 0.5:
            reasons.append(f"High capability overlap ({cap_sim:.0%})")

        # Technology overlap
        tech_sim = self._technology_similarity(app1, app2)
        if tech_sim and tech_sim > 0.5:
            reasons.append(f"Similar technology stack ({tech_sim:.0%})")

        # Overall similarity
        if similarity > 0.9:
            reasons.append("Extremely high overall similarity")
        elif similarity > 0.8:
            reasons.append("High overall similarity")

        return reasons or ["General similarity detected"]

    def _detect_conflicts(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> List[str]:
        """Detect potential conflicts between applications"""
        conflicts = []

        # Different business owners
        owner1 = getattr(app1, "business_owner", "") or ""
        owner2 = getattr(app2, "business_owner", "") or ""
        if owner1 and owner2 and owner1 != owner2:
            conflicts.append(f"Different business owners: {owner1} vs {owner2}")

        # Different criticality levels
        crit1 = getattr(app1, "criticality", "") or ""
        crit2 = getattr(app2, "criticality", "") or ""
        if crit1 and crit2 and crit1 != crit2:
            conflicts.append(f"Different criticality: {crit1} vs {crit2}")

        # Different cost centers
        cost1 = getattr(app1, "cost_center", "") or ""
        cost2 = getattr(app2, "cost_center", "") or ""
        if cost1 and cost2 and cost1 != cost2:
            conflicts.append(f"Different cost centers: {cost1} vs {cost2}")

        # Both have active deployments
        deploy1 = getattr(app1, "is_deployed", False)
        deploy2 = getattr(app2, "is_deployed", False)
        if deploy1 and deploy2:
            conflicts.append("Both applications have active deployments")

        # Different user counts (significant difference)
        users1 = getattr(app1, "user_count", 0) or 0
        users2 = getattr(app2, "user_count", 0) or 0
        if users1 and users2 and abs(users1 - users2) > max(users1, users2) * 0.5:
            conflicts.append(f"Significant user count difference: {users1} vs {users2}")

        return conflicts


class ApplicationMergeService:
    """Service for executing application merges"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute_merge(
        self,
        primary_app: ApplicationComponent,
        duplicate_app: ApplicationComponent,
        merge_strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute merge between primary and duplicate applications

        Args:
            primary_app: ApplicationComponent to keep (primary)
            duplicate_app: ApplicationComponent to merge into primary
            merge_strategy: Dictionary defining how to handle conflicts

        Returns:
            Merge result with details
        """
        try:
            # Create merge record for audit trail
            merge_record = self._create_merge_record(primary_app, duplicate_app, merge_strategy)

            # Apply merge strategy
            merged_data = self._apply_merge_strategy(primary_app, duplicate_app, merge_strategy)

            # Update primary application
            for field, value in merged_data.items():
                if hasattr(primary_app, field):
                    setattr(primary_app, field, value)

            # Mark duplicate as retired (don't delete for audit trail)
            duplicate_app.lifecycle_status = "retired"
            merge_note = f"[MERGED into #{primary_app.id} {primary_app.name}] "
            duplicate_app.description = merge_note + (duplicate_app.description or "")

            # Single atomic commit — both primary update and duplicate retirement
            db.session.commit()

            result = {
                "success": True,
                "primary_app_id": primary_app.id,
                "duplicate_app_id": duplicate_app.id,
                "merge_record_id": merge_record.id,
                "merged_fields": list(merged_data.keys()),
                "message": "Merge completed successfully",
            }

            self.logger.info(f"Successfully merged app {duplicate_app.id} into {primary_app.id}")
            return result

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Merge failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Merge failed - changes rolled back",
            }

    def _create_merge_record(
        self,
        primary_app: ApplicationComponent,
        duplicate_app: ApplicationComponent,
        strategy: Dict[str, Any],
    ) -> Any:
        """Create audit record for the merge"""
        # This would typically use a MergeRecord model
        # For now, return a placeholder
        return type("MergeRecord", (), {"id": 1})()

    def _apply_merge_strategy(
        self,
        primary_app: ApplicationComponent,
        duplicate_app: ApplicationComponent,
        strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply merge strategy to resolve conflicts"""
        merged_data = {}

        # Default strategy: keep primary's data, enrich with duplicate's missing data
        for field in ["description", "business_owner", "cost_center", "criticality"]:
            primary_value = getattr(primary_app, field, None)
            duplicate_value = getattr(duplicate_app, field, None)

            if not primary_value and duplicate_value:
                merged_data[field] = duplicate_value
            elif field in strategy and strategy[field] == "duplicate":
                merged_data[field] = duplicate_value

        # Merge capabilities (union)
        primary_caps = set(getattr(primary_app, "capabilities", []))
        duplicate_caps = set(getattr(duplicate_app, "capabilities", []))
        merged_capabilities = list(primary_caps | duplicate_caps)
        if merged_capabilities != list(primary_caps):
            merged_data["capabilities"] = merged_capabilities

        # Merge technologies (union)
        primary_tech = set(getattr(primary_app, "technologies", []))
        duplicate_tech = set(getattr(duplicate_app, "technologies", []))
        merged_technologies = list(primary_tech | duplicate_tech)
        if merged_technologies != list(primary_tech):
            merged_data["technologies"] = merged_technologies

        # Merge user counts (take max)
        primary_users = getattr(primary_app, "user_count", 0) or 0
        duplicate_users = getattr(duplicate_app, "user_count", 0) or 0
        if duplicate_users > primary_users:
            merged_data["user_count"] = duplicate_users

        return merged_data
