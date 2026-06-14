"""
Document Comparison and Versioning Service

Compares document analyses to identify changes, additions, and deletions.
Features:
- Version comparison (before/after)
- Change detection (added/removed/modified elements)
- Diff generation
- Change impact analysis
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from app import db
from app.models.document_analysis import DocumentAnalysis

logger = logging.getLogger(__name__)


@dataclass
class ElementChange:
    """Represents a change to an element."""

    element_name: str
    change_type: str  # 'added', 'removed', 'modified'
    old_value: Optional[Dict]
    new_value: Optional[Dict]
    changes: Dict[str, Tuple[Optional[str], Optional[str]]]  # Field: (old, new)


@dataclass
class ComparisonResult:
    """Result of document comparison."""

    added_elements: List[Dict]
    removed_elements: List[Dict]
    modified_elements: List[ElementChange]
    unchanged_elements: List[Dict]
    added_relationships: List[Dict]
    removed_relationships: List[Dict]
    summary: Dict


class DocumentComparisonService:
    """
    Service for comparing document analyses and detecting changes.
    """

    def __init__(self):
        """Initialize comparison service."""
        pass

    def compare_analyses(
        self, analysis1: Dict, analysis2: Dict, similarity_threshold: float = 0.85
    ) -> ComparisonResult:
        """
        Compare two document analyses.

        Args:
            analysis1: First analysis (baseline)
            analysis2: Second analysis (newer)
            similarity_threshold: Threshold for considering elements the same

        Returns:
            ComparisonResult with detected changes
        """
        elements1 = analysis1.get("elements", [])
        elements2 = analysis2.get("elements", [])
        relationships1 = analysis1.get("relationships", [])
        relationships2 = analysis2.get("relationships", [])

        # Compare elements
        element_comparison = self._compare_elements(elements1, elements2, similarity_threshold)

        # Compare relationships
        relationship_comparison = self._compare_relationships(relationships1, relationships2)

        # Generate summary
        summary = {
            "total_elements_before": len(elements1),
            "total_elements_after": len(elements2),
            "elements_added": len(element_comparison["added"]),
            "elements_removed": len(element_comparison["removed"]),
            "elements_modified": len(element_comparison["modified"]),
            "elements_unchanged": len(element_comparison["unchanged"]),
            "relationships_added": len(relationship_comparison["added"]),
            "relationships_removed": len(relationship_comparison["removed"]),
            "change_percentage": self._calculate_change_percentage(
                len(elements1),
                len(elements2),
                len(element_comparison["added"]),
                len(element_comparison["removed"]),
            ),
        }

        return ComparisonResult(
            added_elements=element_comparison["added"],
            removed_elements=element_comparison["removed"],
            modified_elements=element_comparison["modified"],
            unchanged_elements=element_comparison["unchanged"],
            added_relationships=relationship_comparison["added"],
            removed_relationships=relationship_comparison["removed"],
            summary=summary,
        )

    def compare_versions(
        self, document_id: int, version1_id: Optional[int] = None, version2_id: Optional[int] = None
    ) -> ComparisonResult:
        """
        Compare two versions of a document analysis.

        Args:
            document_id: Document ID
            version1_id: First version ID (if None, uses latest)
            version2_id: Second version ID (if None, uses latest)

        Returns:
            ComparisonResult
        """
        # Get analyses from database
        if version1_id:
            analysis1_record = DocumentAnalysis.query.get(version1_id)
        else:
            # Get latest analysis for this document
            analysis1_record = (
                DocumentAnalysis.query.filter_by(entity_id=document_id)
                .order_by(DocumentAnalysis.created_at.desc())
                .first()
            )

        if version2_id:
            analysis2_record = DocumentAnalysis.query.get(version2_id)
        else:
            # Get second latest
            analysis2_record = (
                DocumentAnalysis.query.filter_by(entity_id=document_id)
                .order_by(DocumentAnalysis.created_at.desc())
                .offset(1)
                .first()
            )

        if not analysis1_record or not analysis2_record:
            raise ValueError("Could not find analysis versions to compare")

        # Parse JSON results
        import json

        analysis1 = json.loads(analysis1_record.analysis_results or "{}")
        analysis2 = json.loads(analysis2_record.analysis_results or "{}")

        return self.compare_analyses(analysis1, analysis2)

    def _compare_elements(
        self, elements1: List[Dict], elements2: List[Dict], similarity_threshold: float
    ) -> Dict:
        """Compare two lists of elements."""
        # Build name index for quick lookup
        elements1_by_name = {e.get("name", ""): e for e in elements1}
        elements2_by_name = {e.get("name", ""): e for e in elements2}

        added = []
        removed = []
        modified = []
        unchanged = []
        matched_pairs = []

        # Find matches using similarity
        for elem1 in elements1:
            name1 = elem1.get("name", "")
            best_match = None
            best_similarity = 0.0

            for elem2 in elements2:
                name2 = elem2.get("name", "")
                similarity = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = elem2

            if best_match:
                matched_pairs.append((elem1, best_match))
            else:
                # No match found - element was removed
                removed.append(elem1)

        # Find added elements (in elements2 but not matched)
        matched_names = {pair[1].get("name", "") for pair in matched_pairs}
        for elem2 in elements2:
            if elem2.get("name", "") not in matched_names:
                added.append(elem2)

        # Compare matched pairs
        for elem1, elem2 in matched_pairs:
            changes = self._compare_element_fields(elem1, elem2)
            if changes:
                modified.append(
                    ElementChange(
                        element_name=elem1.get("name", ""),
                        change_type="modified",
                        old_value=elem1,
                        new_value=elem2,
                        changes=changes,
                    )
                )
            else:
                unchanged.append(elem1)

        return {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged}

    def _compare_element_fields(
        self, elem1: Dict, elem2: Dict
    ) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Compare fields of two elements."""
        changes = {}
        fields_to_compare = ["name", "type", "layer", "description"]

        for field in fields_to_compare:
            val1 = elem1.get(field, "")
            val2 = elem2.get(field, "")
            if val1 != val2:
                changes[field] = (str(val1), str(val2))

        # Compare properties
        props1 = elem1.get("properties", {})
        props2 = elem2.get("properties", {})
        if props1 != props2:
            changes["properties"] = (str(props1), str(props2))

        return changes

    def _compare_relationships(self, rels1: List[Dict], rels2: List[Dict]) -> Dict:
        """Compare two lists of relationships."""

        # Create relationship keys (source-target-type)
        def rel_key(rel):
            return (rel.get("source", ""), rel.get("target", ""), rel.get("type", ""))

        rels1_keys = {rel_key(r): r for r in rels1}
        rels2_keys = {rel_key(r): r for r in rels2}

        added = [r for k, r in rels2_keys.items() if k not in rels1_keys]
        removed = [r for k, r in rels1_keys.items() if k not in rels2_keys]

        return {"added": added, "removed": removed}

    def _calculate_change_percentage(
        self, count1: int, count2: int, added: int, removed: int
    ) -> float:
        """Calculate overall change percentage."""
        if count1 == 0:
            return 100.0 if count2 > 0 else 0.0

        total_changes = added + removed
        return (total_changes / max(count1, count2)) * 100.0

    def generate_diff_report(self, comparison: ComparisonResult, format: str = "json") -> Dict:
        """Generate a human-readable diff report."""
        report = {
            "summary": comparison.summary,
            "added_elements": [
                {"name": e.get("name"), "type": e.get("type"), "layer": e.get("layer")}
                for e in comparison.added_elements
            ],
            "removed_elements": [
                {"name": e.get("name"), "type": e.get("type"), "layer": e.get("layer")}
                for e in comparison.removed_elements
            ],
            "modified_elements": [
                {
                    "name": change.element_name,
                    "changes": {
                        field: {"old": old_val, "new": new_val}
                        for field, (old_val, new_val) in change.changes.items()
                    },
                }
                for change in comparison.modified_elements
            ],
            "relationships_changes": {
                "added": len(comparison.added_relationships),
                "removed": len(comparison.removed_relationships),
            },
        }

        return report
