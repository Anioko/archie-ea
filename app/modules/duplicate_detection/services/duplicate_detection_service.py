"""

Enhanced Duplicate Application Detection Service

Enterprise-grade duplicate detection system using multi-criteria analysis.
Aligns with ArchiMate 3.2 principles for application rationalization.

Features:
- Multi-dimensional similarity analysis (functional, technical, capability, data)
- Business process hierarchy analysis (L0 - L3)
- AI-powered similarity scoring
- Consolidation recommendations
- Interactive grouping and analysis
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload, selectinload

from app import db
from app.models.application_duplicate_detection import (
    ApplicationProcessMapping,
    BusinessProcess,
    ConsolidationRecommendation,
    DuplicateAnalysis,
    DuplicateDetectionRun,
    DuplicateGroup,
    DuplicateType,
    ProcessLevel,
)
from app.models.application_layer import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.missing_capability_models import ApplicationCapability

logger = logging.getLogger(__name__)


@dataclass
class SimilarityWeights:
    """Weighting configuration for similarity calculations"""

    functional: float = 0.40  # Business process overlap
    capability: float = 0.30  # Business capability overlap
    technical: float = 0.15  # Technology stack similarity
    data: float = 0.10  # Data object overlap
    name_description: float = 0.05  # Name/description similarity


@dataclass
class SimilarityResult:
    """Result of similarity analysis between two applications"""

    app1_id: int
    app2_id: int
    overall_score: float
    functional_similarity: float
    capability_similarity: float
    technical_similarity: float
    data_similarity: float
    name_similarity: float
    shared_processes: List[int]
    shared_capabilities: List[int]
    shared_technologies: List[str]
    confidence_level: float


class DuplicateDetectionService:
    """
    Enhanced Duplicate Application Detection Service

    Provides comprehensive duplicate detection using multiple criteria:
    1. Business Process Alignment (L0 - L3)
    2. Business Capability Overlap
    3. Technical Architecture Similarity
    4. Data Object Processing
    5. Name/Description Semantic Analysis
    """

    def __init__(self, weights: Optional[SimilarityWeights] = None):
        self.weights = weights or SimilarityWeights()
        self.logger = logging.getLogger(__name__)

    def run_duplicate_detection(
        self, run_name: str, similarity_threshold: float = 0.7, scope_filter: Optional[Dict] = None
    ) -> DuplicateDetectionRun:
        """
        Run comprehensive duplicate detection analysis

        Args:
            run_name: Name for this detection run
            similarity_threshold: Minimum similarity score for grouping (0 - 1)
            scope_filter: Optional filter to limit analysis scope

        Returns:
            DuplicateDetectionRun with results
        """
        self.logger.info(f"Starting duplicate detection run: {run_name}")

        # Create detection run record
        detection_run = DuplicateDetectionRun(
            run_name=run_name,
            similarity_threshold=similarity_threshold,
            weighting_config=self.weights.__dict__,
            analysis_scope=scope_filter or {},
            status="running",
            started_at=datetime.utcnow(),
        )
        db.session.add(detection_run)

        try:
            # Get applications to analyze
            applications = self._get_applications_for_analysis(scope_filter)
            detection_run.applications_analyzed = len(applications)

            # Calculate pairwise similarities
            similarity_results = self._calculate_pairwise_similarities(applications)
            detection_run.similarity_calculations_performed = len(similarity_results)

            # Group applications by similarity
            duplicate_groups = self._group_applications_by_similarity(
                similarity_results, similarity_threshold, detection_run.id
            )

            # Generate consolidation recommendations
            self._generate_consolidation_recommendations(duplicate_groups)

            # Update run with results
            detection_run.status = "completed"
            detection_run.completed_at = datetime.utcnow()
            detection_run.duration_seconds = int(
                (detection_run.completed_at - detection_run.started_at).total_seconds()
            )
            detection_run.duplicate_groups_found = len(duplicate_groups)
            detection_run.total_duplicates_found = sum(
                len(group.applications) for group in duplicate_groups
            )
            detection_run.estimated_savings = sum(
                group.estimated_savings or 0 for group in duplicate_groups
            )

            if similarity_results:
                detection_run.average_similarity_score = sum(
                    r.overall_score for r in similarity_results
                ) / len(similarity_results)
                detection_run.processing_rate = (
                    len(applications) / detection_run.duration_seconds
                    if detection_run.duration_seconds > 0
                    else 0
                )

            db.session.commit()
            self.logger.info(f"Completed duplicate detection: {len(duplicate_groups)} groups found")

            return detection_run

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Duplicate detection failed: {e}")
            raise

    def get_duplicate_analysis_for_application(
        self, application_id: int, group_by: str = "similarity_type"
    ) -> Dict[str, Any]:
        """
        Get detailed duplicate analysis for a specific application

        Args:
            application_id: ID of application to analyze
            group_by: How to group results ('similarity_type', 'business_process', 'capability')

        Returns:
            Comprehensive analysis data
        """
        app = ApplicationComponent.query.get_or_404(application_id)

        # Get all similarity analyses involving this application
        analyses = (
            DuplicateAnalysis.query.filter(
                or_(
                    DuplicateAnalysis.application_1_id == application_id,
                    DuplicateAnalysis.application_2_id == application_id,
                )
            )
            .options(
                joinedload(DuplicateAnalysis.application_1),
                joinedload(DuplicateAnalysis.application_2),
                joinedload(DuplicateAnalysis.duplicate_group),
            )
            .all()
        )

        # Group by specified criteria
        grouped_results = self._group_analyses(analyses, group_by)

        # Get business process mapping
        process_mappings = (
            ApplicationProcessMapping.query.filter_by(application_id=application_id)
            .options(joinedload(ApplicationProcessMapping.business_process))
            .all()
        )

        # Get capability mappings
        app_capabilities = self._get_application_capabilities(application_id)

        return {
            "application": app.to_dict(),
            "duplicate_analyses": [analysis.to_dict() for analysis in analyses],
            "grouped_results": grouped_results,
            "process_mappings": [mapping.to_dict() for mapping in process_mappings],
            "capabilities": app_capabilities,
            "summary": self._generate_application_summary(app, analyses),
        }

    def _get_applications_for_analysis(
        self, scope_filter: Optional[Dict]
    ) -> List[ApplicationComponent]:
        """Get applications based on scope filter"""
        query = ApplicationComponent.query

        if scope_filter:
            if "domains" in scope_filter:
                query = query.filter(ApplicationComponent.domain.in_(scope_filter["domains"]))
            if "categories" in scope_filter:
                query = query.filter(ApplicationComponent.category.in_(scope_filter["categories"]))
            if "exclude_retired" in scope_filter and scope_filter["exclude_retired"]:
                query = query.filter(ApplicationComponent.status != "retired")

        return query.all()

    def _calculate_pairwise_similarities(
        self, applications: List[ApplicationComponent]
    ) -> List[SimilarityResult]:
        """Calculate similarity scores between all application pairs"""
        results = []

        for i, app1 in enumerate(applications):
            for j, app2 in enumerate(applications[i + 1 :], i + 1):
                similarity = self._calculate_application_similarity(app1, app2)
                results.append(similarity)

                # Store detailed analysis
                analysis = DuplicateAnalysis(
                    application_1_id=app1.id,
                    application_2_id=app2.id,
                    overall_similarity_score=similarity.overall_score,
                    confidence_level=similarity.confidence_level,
                    functional_similarity=similarity.functional_similarity,
                    capability_similarity=similarity.capability_similarity,
                    technical_similarity=similarity.technical_similarity,
                    data_similarity=similarity.data_similarity,
                    name_similarity=similarity.name_similarity,
                    shared_processes=similarity.shared_processes,
                    shared_capabilities=similarity.shared_capabilities,
                    shared_technologies=similarity.shared_technologies,
                    process_overlap_percentage=len(similarity.shared_processes),
                    capability_overlap_percentage=len(similarity.shared_capabilities),
                )
                db.session.add(analysis)

        return results

    def _calculate_application_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> SimilarityResult:
        """Calculate comprehensive similarity between two applications"""

        # 1. Business Process Similarity
        functional_sim, shared_processes = self._calculate_process_similarity(app1.id, app2.id)

        # 2. Business Capability Similarity
        capability_sim, shared_capabilities = self._calculate_capability_similarity(
            app1.id, app2.id
        )

        # 3. Technical Similarity
        technical_sim, shared_tech = self._calculate_technical_similarity(app1, app2)

        # 4. Data Similarity
        data_sim = self._calculate_data_similarity(app1.id, app2.id)

        # 5. Name/Description Similarity
        name_sim = self._calculate_name_description_similarity(app1, app2)

        # Calculate weighted overall score
        overall_score = (
            functional_sim * self.weights.functional
            + capability_sim * self.weights.capability
            + technical_sim * self.weights.technical
            + data_sim * self.weights.data
            + name_sim * self.weights.name_description
        )

        # Calculate confidence based on data availability
        confidence = self._calculate_confidence_score(app1, app2)

        return SimilarityResult(
            app1_id=app1.id,
            app2_id=app2.id,
            overall_score=overall_score,
            functional_similarity=functional_sim,
            capability_similarity=capability_sim,
            technical_similarity=technical_sim,
            data_similarity=data_sim,
            name_similarity=name_sim,
            shared_processes=shared_processes,
            shared_capabilities=shared_capabilities,
            shared_technologies=shared_tech,
            confidence_level=confidence,
        )

    def _calculate_process_similarity(self, app1_id: int, app2_id: int) -> Tuple[float, List[int]]:
        """Calculate business process similarity between applications"""

        # Get process mappings for both applications
        processes1 = ApplicationProcessMapping.query.filter_by(application_id=app1_id).all()
        processes2 = ApplicationProcessMapping.query.filter_by(application_id=app2_id).all()

        # Extract process IDs
        process_ids1 = {p.business_process_id for p in processes1}
        process_ids2 = {p.business_process_id for p in processes2}

        # Calculate intersection and union
        shared_processes = process_ids1.intersection(process_ids2)
        all_processes = process_ids1.union(process_ids2)

        if not all_processes:
            return 0.0, []

        # Weight by support type and criticality
        weighted_similarity = 0.0
        for shared_process_id in shared_processes:
            mapping1 = next(
                (p for p in processes1 if p.business_process_id == shared_process_id), None
            )
            mapping2 = next(
                (p for p in processes2 if p.business_process_id == shared_process_id), None
            )

            if mapping1 and mapping2:
                # Higher weight for primary support and critical processes
                weight1 = self._get_process_mapping_weight(mapping1)
                weight2 = self._get_process_mapping_weight(mapping2)
                weighted_similarity += (weight1 + weight2) / 2

        similarity = weighted_similarity / len(all_processes) if all_processes else 0.0

        return min(similarity, 1.0), list(shared_processes)

    def _calculate_capability_similarity(
        self, app1_id: int, app2_id: int
    ) -> Tuple[float, List[int]]:
        """Calculate business capability similarity between applications"""

        # Get capabilities for both applications
        capabilities1 = self._get_application_capabilities(app1_id)
        capabilities2 = self._get_application_capabilities(app2_id)

        # Extract capability IDs
        cap_ids1 = {cap["id"] for cap in capabilities1}
        cap_ids2 = {cap["id"] for cap in capabilities2}

        # Calculate intersection and union
        shared_capabilities = cap_ids1.intersection(cap_ids2)
        all_capabilities = cap_ids1.union(cap_ids2)

        if not all_capabilities:
            return 0.0, []

        # Weight by capability level and importance
        weighted_similarity = 0.0
        for shared_cap_id in shared_capabilities:
            cap1 = next((cap for cap in capabilities1 if cap["id"] == shared_cap_id), None)
            cap2 = next((cap for cap in capabilities2 if cap["id"] == shared_cap_id), None)

            if cap1 and cap2:
                # Higher weight for strategic capabilities and core differentiators
                weight1 = self._get_capability_weight(cap1)
                weight2 = self._get_capability_weight(cap2)
                weighted_similarity += (weight1 + weight2) / 2

        similarity = weighted_similarity / len(all_capabilities) if all_capabilities else 0.0

        return min(similarity, 1.0), list(shared_capabilities)

    def _calculate_technical_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Tuple[float, List[str]]:
        """Calculate technical architecture similarity"""

        # Parse technology stacks
        tech1 = self._parse_technology_stack(app1.technology_stack or "{}")
        tech2 = self._parse_technology_stack(app2.technology_stack or "{}")

        # Calculate technology overlap
        all_tech = set(tech1).union(set(tech2))
        shared_tech = set(tech1).intersection(set(tech2))

        if not all_tech:
            return 0.0, []

        # Weight by technology category importance
        weighted_similarity = 0.0
        for tech in shared_tech:
            weight = self._get_technology_weight(tech)
            weighted_similarity += weight

        # Normalize by total possible weight
        total_weight = sum(self._get_technology_weight(t) for t in all_tech)
        similarity = weighted_similarity / total_weight if total_weight > 0 else 0.0

        return min(similarity, 1.0), list(shared_tech)

    def _calculate_data_similarity(self, app1_id: int, app2_id: int) -> float:
        """Calculate data object processing similarity"""
        # This would integrate with data governance models
        # For now, return a placeholder
        return 0.0

    def _calculate_name_description_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> float:
        """Calculate semantic similarity of names and descriptions"""

        # Simple text similarity for now - could be enhanced with NLP
        name_sim = self._text_similarity(app1.name, app2.name)

        desc_sim = 0.0
        if app1.description and app2.description:
            desc_sim = self._text_similarity(app1.description, app2.description)
        elif not app1.description and not app2.description:
            desc_sim = 1.0  # Both missing descriptions

        return (name_sim + desc_sim) / 2

    def _group_applications_by_similarity(
        self, similarities: List[SimilarityResult], threshold: float, detection_run_id: int
    ) -> List[DuplicateGroup]:
        """Group applications into duplicate groups based on similarity threshold"""

        groups = []
        processed_applications = set()

        # Sort similarities by overall score (descending)
        sorted_similarities = sorted(similarities, key=lambda x: x.overall_score, reverse=True)

        for similarity in sorted_similarities:
            if similarity.overall_score < threshold:
                continue

            app1_id, app2_id = similarity.app1_id, similarity.app2_id

            # Skip if either application already processed
            if app1_id in processed_applications or app2_id in processed_applications:
                continue

            # Find existing group or create new one
            group = self._find_or_create_group(similarity, groups, detection_run_id)

            # Add applications to group
            if app1_id not in processed_applications:
                group.applications.append(ApplicationComponent.query.get(app1_id))
                processed_applications.add(app1_id)

            if app2_id not in processed_applications:
                group.applications.append(ApplicationComponent.query.get(app2_id))
                processed_applications.add(app2_id)

        # Save groups
        for group in groups:
            db.session.add(group)

        return groups

    def _generate_consolidation_recommendations(self, groups: List[DuplicateGroup]):
        """Generate AI-powered consolidation recommendations for each group"""

        for group in groups:
            if len(group.applications) < 2:
                continue

            recommendation = self._create_consolidation_recommendation(group)
            if recommendation:
                db.session.add(recommendation)

    def _create_consolidation_recommendation(
        self, group: DuplicateGroup
    ) -> Optional[ConsolidationRecommendation]:
        """Create consolidation recommendation for a duplicate group"""

        # Analyze group to determine best consolidation approach
        if group.overall_similarity_score > 0.8:
            rec_type = "merge"  # Very similar - merge functionality
        elif group.estimated_savings and group.estimated_savings > 100000:
            rec_type = "replace"  # High savings - replace with best option
        elif group.consolidation_complexity == "low":
            rec_type = "retire"  # Easy to retire duplicates
        else:
            rec_type = "replatform"  # Complex case - replatform

        # Select target application (best candidate to keep)
        target_app = self._select_target_application(group)

        # Estimate costs and timeline
        implementation_cost = self._estimate_implementation_cost(group, rec_type)
        annual_savings = group.estimated_savings or 0
        timeline_months = self._estimate_timeline(group, rec_type)

        return ConsolidationRecommendation(
            duplicate_group_id=group.id,
            recommendation_type=rec_type,
            target_application_id=target_app.id if target_app else None,
            target_justification=self._generate_target_justification(target_app, group),
            source_applications=[
                app.id
                for app in group.applications
                if app.id != (target_app.id if target_app else None)
            ],
            implementation_approach="phased" if len(group.applications) > 2 else "big_bang",
            estimated_timeline_months=timeline_months,
            implementation_cost=implementation_cost,
            annual_savings=annual_savings,
            payback_period_months=int(implementation_cost / annual_savings * 12)
            if annual_savings > 0
            else None,
            roi_percentage=(annual_savings / implementation_cost * 100)
            if implementation_cost > 0
            else None,
            overall_risk_level=self._assess_risk_level(group),
            confidence_score=min(group.overall_similarity_score + 0.1, 1.0),
            implementation_phases=self._generate_implementation_phases(group, timeline_months),
        )

    # Helper methods
    def _get_process_mapping_weight(self, mapping: ApplicationProcessMapping) -> float:
        """Calculate weight for process mapping based on support type and criticality"""
        base_weight = {"primary": 1.0, "secondary": 0.7, "supporting": 0.4}.get(
            mapping.support_type, 0.5
        )

        criticality_multiplier = {"critical": 1.2, "high": 1.0, "medium": 0.8, "low": 0.6}.get(
            mapping.criticality, 1.0
        )

        return base_weight * criticality_multiplier

    def _get_capability_weight(self, capability: Dict) -> float:
        """Calculate weight for capability based on level and type"""
        level_weight = {1: 1.2, 2: 1.0, 3: 0.8}.get(  # Strategic  # Tactical  # Operational
            capability.get("level", 2), 1.0
        )

        type_weight = {"core": 1.2, "supporting": 1.0, "differentiating": 1.1}.get(
            capability.get("capability_type", "supporting"), 1.0
        )

        return level_weight * type_weight

    def _parse_technology_stack(self, tech_json: str) -> List[str]:
        """Parse technology stack JSON into list"""
        try:
            tech_data = json.loads(tech_json)
            if isinstance(tech_data, list):
                return tech_data
            elif isinstance(tech_data, dict):
                return list(tech_data.keys())
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def _get_technology_weight(self, technology: str) -> float:
        """Get weight for technology based on category importance"""
        # Higher weight for core technologies
        core_tech = {"java", "python", "javascript", "sql", "aws", "azure", "gcp"}
        if technology.lower() in core_tech:
            return 1.0
        return 0.7

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity calculation"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _calculate_confidence_score(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> float:
        """Calculate confidence in similarity analysis based on data completeness"""
        factors = []

        # Check if both have process mappings
        if (
            ApplicationProcessMapping.query.filter_by(application_id=app1.id).first()
            and ApplicationProcessMapping.query.filter_by(application_id=app2.id).first()
        ):
            factors.append(0.3)
        else:
            factors.append(0.1)

        # Check if both have technology stacks
        if app1.technology_stack and app2.technology_stack:
            factors.append(0.2)
        else:
            factors.append(0.05)

        # Check if both have descriptions
        if app1.description and app2.description:
            factors.append(0.2)
        else:
            factors.append(0.05)

        # Check if both have good metadata
        metadata_score = 0.3
        if app1.name and app2.name:
            metadata_score *= 1.0
        else:
            metadata_score *= 0.5

        factors.append(metadata_score)

        return sum(factors)

    def _get_application_capabilities(self, application_id: int) -> List[Dict]:
        """Get capabilities for an application"""
        # This would integrate with the capability models
        # For now, return empty list
        return []

    def _group_analyses(self, analyses: List[DuplicateAnalysis], group_by: str) -> Dict:
        """Group duplicate analyses by specified criteria"""
        grouped = {}

        for analysis in analyses:
            key = None

            if group_by == "similarity_type":
                # Group by highest similarity type
                similarities = [
                    ("Functional", analysis.functional_similarity),
                    ("Capability", analysis.capability_similarity),
                    ("Technical", analysis.technical_similarity),
                    ("Data", analysis.data_similarity),
                ]
                key = max(similarities, key=lambda x: x[1])[0]

            elif group_by == "business_process":
                # Group by primary shared business process
                if analysis.shared_processes:
                    key = str(analysis.shared_processes[0])
                else:
                    key = "No Shared Processes"

            elif group_by == "capability":
                # Group by primary shared capability
                if analysis.shared_capabilities:
                    key = str(analysis.shared_capabilities[0])
                else:
                    key = "No Shared Capabilities"

            if key not in grouped:
                grouped[key] = []

            grouped[key].append(analysis)

        return grouped

    def _generate_application_summary(
        self, app: ApplicationComponent, analyses: List[DuplicateAnalysis]
    ) -> Dict:
        """Generate summary statistics for an application"""
        if not analyses:
            return {
                "total_duplicates": 0,
                "average_similarity": 0.0,
                "highest_similarity": 0.0,
                "duplicate_types": {},
            }

        similarities = [a.overall_similarity_score for a in analyses]

        return {
            "total_duplicates": len(analyses),
            "average_similarity": sum(similarities) / len(similarities),
            "highest_similarity": max(similarities),
            "duplicate_types": {
                "functional": len([a for a in analyses if a.functional_similarity > 0.7]),
                "capability": len([a for a in analyses if a.capability_similarity > 0.7]),
                "technical": len([a for a in analyses if a.technical_similarity > 0.7]),
                "data": len([a for a in analyses if a.data_similarity > 0.7]),
            },
        }

    def _find_or_create_group(
        self, similarity: SimilarityResult, groups: List[DuplicateGroup], detection_run_id: int
    ) -> DuplicateGroup:
        """Find existing group for similarity or create new one"""

        # Try to find existing group that contains either application
        for group in groups:
            app_ids = {app.id for app in group.applications}
            if similarity.app1_id in app_ids or similarity.app2_id in app_ids:
                # Update group similarity to include this new similarity
                group.overall_similarity_score = max(
                    group.overall_similarity_score, similarity.overall_score
                )
                return group

        # Create new group
        duplicate_type = self._determine_duplicate_type(similarity)

        group = DuplicateGroup(
            group_name=f"Duplicate Group {len(groups) + 1}",
            description=f"Applications with {duplicate_type.value} similarity",
            duplicate_type=duplicate_type,
            detection_run_id=detection_run_id,
            overall_similarity_score=similarity.overall_score,
            functional_similarity=similarity.functional_similarity,
            capability_similarity=similarity.capability_similarity,
            technical_similarity=similarity.technical_similarity,
            data_similarity=similarity.data_similarity,
            consolidation_priority=self._assess_consolidation_priority(similarity),
            estimated_savings=self._estimate_savings(similarity),
        )

        groups.append(group)
        return group

    def _determine_duplicate_type(self, similarity: SimilarityResult) -> DuplicateType:
        """Determine primary type of duplication"""

        if similarity.functional_similarity > 0.8:
            return DuplicateType.FUNCTIONAL
        elif similarity.capability_similarity > 0.8:
            return DuplicateType.CAPABILITY
        elif similarity.technical_similarity > 0.8:
            return DuplicateType.TECHNICAL
        elif similarity.data_similarity > 0.8:
            return DuplicateType.DATA
        else:
            return DuplicateType.PARTIAL

    def _assess_consolidation_priority(self, similarity: SimilarityResult) -> str:
        """Assess consolidation priority based on similarity and potential impact"""
        if similarity.overall_score > 0.9:
            return "high"
        elif similarity.overall_score > 0.7:
            return "medium"
        else:
            return "low"

    def _estimate_savings(self, similarity: SimilarityResult) -> float:
        """Estimate potential annual savings from consolidation"""
        # Base savings calculation - could be enhanced with actual cost data
        base_savings = 50000  # $50k base savings per duplicate
        similarity_multiplier = similarity.overall_score

        return base_savings * similarity_multiplier

    def _select_target_application(self, group: DuplicateGroup) -> Optional[ApplicationComponent]:
        """Select best target application for consolidation"""
        if not group.applications:
            return None

        # Simple selection - could be enhanced with more sophisticated criteria
        # Prefer applications with more complete data, higher maturity, etc.
        best_app = None
        best_score = 0

        for app in group.applications:
            score = 0

            # Prefer apps with descriptions
            if app.description:
                score += 1

            # Prefer apps with technology stacks
            if app.technology_stack:
                score += 1

            # Prefer apps with better status
            if app.status == "active":
                score += 2
            elif app.status == "maintenance":
                score += 1

            if score > best_score:
                best_score = score
                best_app = app

        return best_app or group.applications[0]

    def _generate_target_justification(
        self, target_app: ApplicationComponent, group: DuplicateGroup
    ) -> str:
        """Generate justification for selecting target application"""
        if not target_app:
            return "No clear target application identified"

        justifications = []

        if target_app.description:
            justifications.append("Has comprehensive documentation")

        if target_app.technology_stack:
            justifications.append("Well-defined technology stack")

        if target_app.status == "active":
            justifications.append("Currently active and maintained")

        if group.duplicate_type == DuplicateType.FUNCTIONAL:
            justifications.append("Best represents core business functionality")

        return (
            "; ".join(justifications) if justifications else "Selected as most suitable candidate"
        )

    def _estimate_implementation_cost(self, group: DuplicateGroup, rec_type: str) -> float:
        """Estimate implementation cost for consolidation"""
        base_costs = {"merge": 100000, "replace": 150000, "retire": 50000, "replatform": 200000}

        base_cost = base_costs.get(rec_type, 100000)

        # Adjust for group size
        size_multiplier = 1 + (len(group.applications) - 2) * 0.2

        # Adjust for complexity
        complexity_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.5}.get(
            group.consolidation_complexity, 1.0
        )

        return base_cost * size_multiplier * complexity_multiplier

    def _estimate_timeline(self, group: DuplicateGroup, rec_type: str) -> int:
        """Estimate implementation timeline in months"""
        base_timelines = {"merge": 6, "replace": 9, "retire": 3, "replatform": 12}

        base_timeline = base_timelines.get(rec_type, 6)

        # Adjust for group size
        size_adjustment = max(0, (len(group.applications) - 2) * 2)

        return base_timeline + size_adjustment

    def _assess_risk_level(self, group: DuplicateGroup) -> str:
        """Assess overall risk level for consolidation"""
        risk_factors = []

        # High similarity reduces risk
        if group.overall_similarity_score < 0.7:
            risk_factors.append("low_similarity")

        # Many applications increase risk
        if len(group.applications) > 3:
            risk_factors.append("many_applications")

        # High complexity increases risk
        if group.consolidation_complexity == "high":
            risk_factors.append("high_complexity")

        risk_score = len(risk_factors)

        if risk_score >= 2:
            return "high"
        elif risk_score == 1:
            return "medium"
        else:
            return "low"

    def _generate_implementation_phases(
        self, group: DuplicateGroup, total_months: int
    ) -> List[Dict]:
        """Generate implementation phases for consolidation"""
        phases = []

        if total_months <= 3:
            # Single phase for short projects
            phases.append(
                {
                    "phase": 1,
                    "name": "Implementation",
                    "duration_months": total_months,
                    "activities": ["Data migration", "User training", "System retirement"],
                }
            )
        else:
            # Multi-phase for longer projects
            phase_count = min(4, max(2, total_months // 3))
            months_per_phase = total_months // phase_count

            phase_names = [
                "Planning & Analysis",
                "Development & Migration",
                "Testing & Validation",
                "Deployment & Retirement",
            ]

            for i in range(phase_count):
                phases.append(
                    {
                        "phase": i + 1,
                        "name": phase_names[i] if i < len(phase_names) else f"Phase {i + 1}",
                        "duration_months": months_per_phase,
                        "activities": self._get_phase_activities(i + 1),
                    }
                )

        return phases

    def _get_phase_activities(self, phase_number: int) -> List[str]:
        """Get typical activities for a given phase"""
        phase_activities = {
            1: ["Requirements analysis", "Architecture design", "Risk assessment"],
            2: ["Data migration", "Feature development", "Integration updates"],
            3: ["User acceptance testing", "Performance testing", "Security validation"],
            4: ["Production deployment", "User training", "System retirement"],
        }

        return phase_activities.get(phase_number, ["Implementation activities"])
