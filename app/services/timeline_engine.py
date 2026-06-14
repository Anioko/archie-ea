"""
Unified Timeline Engine
Synchronizes and manages timelines across all roadmap systems
"""

import json  # dead-code-ok
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple  # dead-code-ok

from sqlalchemy import text


@dataclass
class TimelinePeriod:
    """Represents a time period in the timeline"""

    label: str
    start: datetime
    end: datetime
    period_type: str  # month, quarter, year
    display_format: str


@dataclass
class TimelineConflict:
    """Represents a conflict between initiatives"""

    initiative_1_id: int
    initiative_2_id: int
    conflict_type: str  # overlap, resource, dependency
    severity: str  # low, medium, high, critical
    description: str


class UnifiedTimelineEngine:
    """Unified timeline management for all roadmap systems"""

    def __init__(self, db_session):
        self.db_session = db_session
        self.periods = []
        self.conflicts = []
        self.critical_path = []

    def generate_unified_timeline(
        self, start_date: datetime, end_date: datetime, display_type: str = "months"
    ) -> List[TimelinePeriod]:
        """Generate unified timeline periods for all roadmaps"""
        self.periods = []
        current = start_date

        if display_type == "months":
            while current <= end_date:
                # Calculate month end
                next_month = current.replace(day=1) + timedelta(days=32)
                month_end = next_month.replace(day=1) - timedelta(days=1)

                period = TimelinePeriod(
                    label=current.strftime("%b %Y"),
                    start=current,
                    end=month_end,
                    period_type="month",
                    display_format="MMM YYYY",
                )
                self.periods.append(period)
                current = next_month

        elif display_type == "quarters":
            while current <= end_date:
                quarter = (current.month - 1) // 3 + 1
                quarter_start = datetime(current.year, (quarter - 1) * 3 + 1, 1)
                quarter_end = datetime(current.year, quarter * 3, 1) + timedelta(days=32)
                quarter_end = quarter_end.replace(day=1) - timedelta(days=1)

                period = TimelinePeriod(
                    label=f"Q{quarter} {current.year}",
                    start=quarter_start,
                    end=quarter_end,
                    period_type="quarter",
                    display_format="QQQ YYYY",
                )
                self.periods.append(period)
                current = quarter_end + timedelta(days=1)

        elif display_type == "years":
            while current <= end_date:
                year_start = datetime(current.year, 1, 1)
                year_end = datetime(current.year, 12, 31)

                period = TimelinePeriod(
                    label=str(current.year),
                    start=year_start,
                    end=year_end,
                    period_type="year",
                    display_format="YYYY",
                )
                self.periods.append(period)
                current = datetime(current.year + 1, 1, 1)

        return self.periods

    def synchronize_all_roadmaps(self) -> Dict[str, any]:
        """Synchronize timelines across all roadmap systems"""
        try:
            # Get current timeline bounds from all initiatives
            bounds_query = """
                SELECT MIN(start_date) as min_start, MAX(end_date) as max_end,
                       COUNT(*) as total_initiatives
                FROM enterprise_initiatives
                WHERE start_date IS NOT NULL AND end_date IS NOT NULL
            """
            result = self.db_session.execute(bounds_query).fetchone()

            if not result.min_start or not result.max_end:
                return {"error": "No valid timeline bounds found"}

            # Generate unified timeline
            unified_periods = self.generate_unified_timeline(
                result.min_start, result.max_end, "months"
            )

            # Update each roadmap system
            sync_results = {}

            # Sync Hybrid Roadmap
            sync_results["hybrid"] = self._sync_hybrid_roadmap(unified_periods)

            # Sync Capability Roadmap
            sync_results["capability"] = self._sync_capability_roadmap(unified_periods)

            # Sync ArchiMate Roadmap
            sync_results["archimate"] = self._sync_archimate_roadmap(unified_periods)

            # Detect and resolve conflicts
            self.conflicts = self._detect_timeline_conflicts()
            resolved_conflicts = self._resolve_conflicts()

            # Calculate critical path
            self.critical_path = self._calculate_critical_path()

            return {
                "unified_periods": [self._period_to_dict(p) for p in unified_periods],
                "sync_results": sync_results,
                "conflicts_detected": len(self.conflicts),
                "conflicts_resolved": len(resolved_conflicts),
                "critical_path": self.critical_path,
                "synchronization_date": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": f"Timeline synchronization failed: {str(e)}"}

    def _sync_hybrid_roadmap(self, unified_periods: List[TimelinePeriod]) -> Dict[str, any]:
        """Synchronize Hybrid Roadmap with unified timeline"""
        try:
            # Update hybrid roadmap timeline periods
            update_query = """
                UPDATE enterprise_initiatives
                SET updated_at = :now
                WHERE portfolio_type IN ('strategic', 'operational', 'transformational')
            """
            self.db_session.execute(update_query, {"now": datetime.utcnow()})

            # Recalculate initiative positions
            initiatives_query = """
                SELECT id, name, start_date, end_date, portfolio_type
                FROM enterprise_initiatives
                WHERE portfolio_type IN ('strategic', 'operational', 'transformational')
                ORDER BY start_date
            """
            initiatives = self.db_session.execute(initiatives_query).fetchall()

            positioned_initiatives = []
            for initiative in initiatives:
                position = self._calculate_initiative_position(
                    initiative.start_date, initiative.end_date, unified_periods
                )
                positioned_initiatives.append(
                    {"id": initiative.id, "name": initiative.name, "position": position}
                )

            return {
                "status": "success",
                "initiatives_positioned": len(positioned_initiatives),
                "periods_synchronized": len(unified_periods),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _sync_capability_roadmap(self, unified_periods: List[TimelinePeriod]) -> Dict[str, any]:
        """Synchronize Capability Roadmap with unified timeline"""
        try:
            # Update capability roadmap timeline periods
            update_query = """
                UPDATE enterprise_initiatives
                SET updated_at = :now
                WHERE strategic_importance IS NOT NULL
            """
            self.db_session.execute(update_query, {"now": datetime.utcnow()})

            # Recalculate work package positions
            work_packages_query = """
                SELECT id, name, start_date, end_date, strategic_importance
                FROM enterprise_initiatives
                WHERE strategic_importance IS NOT NULL
                ORDER BY strategic_importance DESC, start_date
            """
            work_packages = self.db_session.execute(work_packages_query).fetchall()

            positioned_packages = []
            for package in work_packages:
                position = self._calculate_initiative_position(
                    package.start_date, package.end_date, unified_periods
                )
                positioned_packages.append(
                    {
                        "id": package.id,
                        "name": package.name,
                        "position": position,
                        "strategic_importance": package.strategic_importance,
                    }
                )

            return {
                "status": "success",
                "work_packages_positioned": len(positioned_packages),
                "periods_synchronized": len(unified_periods),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _sync_archimate_roadmap(self, unified_periods: List[TimelinePeriod]) -> Dict[str, any]:
        """Synchronize ArchiMate Roadmap with unified timeline"""
        try:
            # Update ArchiMate roadmap timeline periods
            update_query = """
                UPDATE enterprise_initiatives
                SET updated_at = :now
                WHERE work_package_type IS NOT NULL
            """
            self.db_session.execute(update_query, {"now": datetime.utcnow()})

            # Recalculate ArchiMate work package positions
            archimate_packages_query = """
                SELECT id, name, start_date, end_date, work_package_type, archimate_layer
                FROM enterprise_initiatives
                WHERE work_package_type IS NOT NULL
                ORDER BY archimate_layer, work_package_type, start_date
            """
            archimate_packages = self.db_session.execute(archimate_packages_query).fetchall()

            positioned_packages = []
            for package in archimate_packages:
                position = self._calculate_initiative_position(
                    package.start_date, package.end_date, unified_periods
                )
                positioned_packages.append(
                    {
                        "id": package.id,
                        "name": package.name,
                        "position": position,
                        "work_package_type": package.work_package_type,
                        "archimate_layer": package.archimate_layer,
                    }
                )

            return {
                "status": "success",
                "archimate_packages_positioned": len(positioned_packages),
                "periods_synchronized": len(unified_periods),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _calculate_initiative_position(
        self, start_date: datetime, end_date: datetime, periods: List[TimelinePeriod]
    ) -> Dict[str, any]:
        """Calculate initiative position within timeline periods"""
        if not start_date or not end_date or not periods:
            return {"left": 0, "width": 0}

        # Find start and end period indices
        start_index = 0
        end_index = len(periods) - 1

        for i, period in enumerate(periods):
            if start_date >= period.start and start_date <= period.end:
                start_index = i
            if end_date >= period.start and end_date <= period.end:
                end_index = i
                break

        # Calculate position as percentages
        total_periods = len(periods)
        period_width = 100 / total_periods

        left_percent = start_index * period_width
        width_percent = (end_index - start_index + 1) * period_width

        return {
            "left": round(left_percent, 2),
            "width": round(width_percent, 2),
            "start_period_index": start_index,
            "end_period_index": end_index,
        }

    def _detect_timeline_conflicts(self) -> List[TimelineConflict]:
        """Detect conflicts between initiatives"""
        conflicts = []

        # Get all initiatives with their dates
        initiatives_query = """
            SELECT id, name, start_date, end_date, portfolio_type, strategic_importance
            FROM enterprise_initiatives
            WHERE start_date IS NOT NULL AND end_date IS NOT NULL
            ORDER BY start_date
        """
        initiatives = self.db_session.execute(initiatives_query).fetchall()

        # Check for overlapping initiatives
        for i, init1 in enumerate(initiatives):
            for init2 in initiatives[i + 1 :]:
                if self._initiatives_overlap(init1, init2):
                    severity = self._calculate_conflict_severity(init1, init2)
                    conflicts.append(
                        TimelineConflict(
                            initiative_1_id=init1.id,
                            initiative_2_id=init2.id,
                            conflict_type="overlap",
                            severity=severity,
                            description=f"Timeline overlap between {init1.name} and {init2.name}",
                        )
                    )

        # Check for resource conflicts
        resource_conflicts = self._detect_resource_conflicts()
        conflicts.extend(resource_conflicts)

        # Check for dependency conflicts
        dependency_conflicts = self._detect_dependency_conflicts()
        conflicts.extend(dependency_conflicts)

        return conflicts

    def _initiatives_overlap(self, init1, init2) -> bool:
        """Check if two initiatives overlap in time"""
        return not (init1.end_date < init2.start_date or init2.end_date < init1.start_date)

    def _calculate_conflict_severity(self, init1, init2) -> str:
        """Calculate conflict severity based on initiative properties"""
        # High severity if both are critical or strategic
        if (init1.strategic_importance == "critical" or init1.portfolio_type == "strategic") and (
            init2.strategic_importance == "critical" or init2.portfolio_type == "strategic"
        ):
            return "critical"

        # Medium severity if one is critical/strategic
        if (
            init1.strategic_importance in ["critical", "high"]
            or init1.portfolio_type == "strategic"
        ) or (
            init2.strategic_importance in ["critical", "high"]
            or init2.portfolio_type == "strategic"
        ):
            return "high"

        # Low severity for operational initiatives
        return "medium"

    def _detect_resource_conflicts(self) -> List[TimelineConflict]:
        """Detect resource allocation conflicts"""
        conflicts = []

        # Get resource allocations
        resources_query = """
            SELECT ir1.initiative_id as init1_id, ir2.initiative_id as init2_id,
                   ir1.resource_type, ir1.allocation_percentage as alloc1,
                   ir2.allocation_percentage as alloc2,
                   i1.name as name1, i2.name as name2
            FROM initiative_resources ir1
            JOIN initiative_resources ir2 ON ir1.resource_type = ir2.resource_type
                AND ir1.initiative_id < ir2.initiative_id
            JOIN enterprise_initiatives i1 ON ir1.initiative_id = i1.id
            JOIN enterprise_initiatives i2 ON ir2.initiative_id = i2.id
            WHERE i1.start_date <= i2.end_date AND i2.start_date <= i1.end_date
            AND (ir1.allocation_percentage + ir2.allocation_percentage) > 100
        """
        resource_conflicts = self.db_session.execute(resources_query).fetchall()

        for conflict in resource_conflicts:
            conflicts.append(
                TimelineConflict(
                    initiative_1_id=conflict.init1_id,
                    initiative_2_id=conflict.init2_id,
                    conflict_type="resource",
                    severity="high",
                    description=f"Resource conflict: {conflict.name1} and {conflict.name2} both require {conflict.alloc1 + conflict.alloc2}% of {conflict.resource_type}",
                )
            )

        return conflicts

    def _detect_dependency_conflicts(self) -> List[TimelineConflict]:
        """Detect dependency conflicts"""
        conflicts = []

        # Get dependency violations
        dependency_query = """
            SELECT id.source_id, id.target_id, id.dependency_type, id.lag_days,
                   i1.name as source_name, i1.end_date as source_end,
                   i2.name as target_name, i2.start_date as target_start
            FROM initiative_dependencies id
            JOIN enterprise_initiatives i1 ON id.source_id = i1.id
            JOIN enterprise_initiatives i2 ON id.target_id = i2.id
            WHERE i1.end_date > i2.start_date - id.lag_days
        """
        dependency_violations = self.db_session.execute(dependency_query).fetchall()

        for violation in dependency_violations:
            conflicts.append(
                TimelineConflict(
                    initiative_1_id=violation.source_id,
                    initiative_2_id=violation.target_id,
                    conflict_type="dependency",
                    severity="critical",
                    description=f"Dependency violation: {violation.source_name} must complete before {violation.target_name} starts",
                )
            )

        return conflicts

    def _resolve_conflicts(self) -> List[TimelineConflict]:
        """Resolve detected conflicts"""
        resolved = []

        for conflict in self.conflicts:
            resolution = self._resolve_single_conflict(conflict)
            if resolution:
                resolved.append(resolution)

        return resolved

    def _resolve_single_conflict(self, conflict: TimelineConflict) -> Optional[TimelineConflict]:
        """Resolve a single conflict"""
        if conflict.conflict_type == "overlap":
            # Suggest timeline adjustment
            return self._suggest_timeline_adjustment(conflict)
        elif conflict.conflict_type == "resource":
            # Suggest resource reallocation
            return self._suggest_resource_reallocation(conflict)
        elif conflict.conflict_type == "dependency":
            # Suggest dependency fix
            return self._suggest_dependency_fix(conflict)

        return None

    def _suggest_timeline_adjustment(self, conflict: TimelineConflict) -> TimelineConflict:
        """Suggest timeline adjustment for overlapping initiatives"""
        # Get initiative details
        initiatives_query = """
            SELECT id, name, start_date, end_date, strategic_importance
            FROM enterprise_initiatives
            WHERE id IN (:id1, :id2)
        """
        result = self.db_session.execute(
            initiatives_query, {"id1": conflict.initiative_1_id, "id2": conflict.initiative_2_id}
        ).fetchall()

        # Suggest moving the less critical initiative
        if len(result) == 2:
            if (
                result[0].strategic_importance == "critical"
                and result[1].strategic_importance != "critical"
            ):
                # Move initiative 2
                new_start = result[0].end_date + timedelta(days=1)
                new_end = new_start + (result[1].end_date - result[1].start_date)

                conflict.description += (
                    f" - Suggested: Move {result[1].name} to start {new_start.strftime('%Y-%m-%d')}"
                )
            elif (
                result[1].strategic_importance == "critical"
                and result[0].strategic_importance != "critical"
            ):
                # Move initiative 1
                new_start = result[1].end_date + timedelta(days=1)
                new_end = new_start + (result[0].end_date - result[0].start_date)

                conflict.description += (
                    f" - Suggested: Move {result[0].name} to start {new_start.strftime('%Y-%m-%d')}"
                )

        return conflict

    def _suggest_resource_reallocation(self, conflict: TimelineConflict) -> TimelineConflict:
        """Suggest resource reallocation for resource conflicts"""
        conflict.description += (
            " - Suggested: Reduce resource allocation or add additional resources"
        )
        return conflict

    def _suggest_dependency_fix(self, conflict: TimelineConflict) -> TimelineConflict:
        """Suggest dependency fix for dependency conflicts"""
        conflict.description += " - Suggested: Adjust timeline to respect dependency constraints"
        return conflict

    def _calculate_critical_path(self) -> List[int]:
        """Calculate critical path through all initiatives"""
        # This is a simplified critical path calculation
        # In a real implementation, you'd use proper critical path method (CPM)

        # Get all dependencies
        dependencies_query = text(
            """
            SELECT source_id, target_id, dependency_type, lag_days
            FROM initiative_dependencies
            WHERE dependency_type = 'prerequisite'
        """
        )
        dependencies = self.db_session.execute(dependencies_query).fetchall()

        # Build dependency graph
        graph = {}
        for dep in dependencies:
            if dep.source_id not in graph:
                graph[dep.source_id] = []
            graph[dep.source_id].append(dep.target_id)

        # Find longest path (simplified)
        critical_path = []
        visited = set()

        def dfs(node, path):
            if node in visited:
                return
            visited.add(node)
            path.append(node)

            if node in graph:
                for neighbor in graph[node]:
                    dfs(neighbor, path.copy())

            # Update critical path if this is longer
            if len(path) > len(critical_path):
                critical_path.clear()
                critical_path.extend(path)

        # Start from nodes with no prerequisites
        all_targets = {dep.target_id for dep in dependencies}
        all_sources = {dep.source_id for dep in dependencies}
        start_nodes = all_sources - all_targets

        for start in start_nodes:
            dfs(start, [])

        return critical_path

    def _period_to_dict(self, period: TimelinePeriod) -> Dict[str, any]:
        """Convert TimelinePeriod to dictionary"""
        return {
            "label": period.label,
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "period_type": period.period_type,
            "display_format": period.display_format,
        }
