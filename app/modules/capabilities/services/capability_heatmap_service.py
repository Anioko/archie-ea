"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.analysis_service

Capability Heatmap Service

Provides aggregated data for capability maturity heatmaps,
gap alerts, and domain health indicators on the framework dashboard.
"""

import logging
import time
from typing import Any, Dict, List

from sqlalchemy import event, func

from app import db
from app.models.unified_application_capability_mapping import UnifiedApplicationCapabilityMapping
from app.models.unified_capability import BusinessDomain, UnifiedCapability

logger = logging.getLogger(__name__)


# ============================================================================
# QUERY PROFILING (Phase 2: Performance Baseline)
# ============================================================================
class QueryCounter:
    """Count SQL queries executed during service calls."""
    
    def __init__(self):
        self.count = 0
        self.queries = []
    
    def reset(self):
        """Reset counter."""
        self.count = 0
        self.queries = []
    
    def on_before_execute(self, conn, cursor, statement, parameters, context, executemany):
        """Track query execution. Matches SQLAlchemy before_cursor_execute signature."""
        self.count += 1
        query_str = str(statement).replace('\n', ' ')[:100]
        self.queries.append(query_str)
    
    def start(self):
        """Start tracking queries."""
        self.reset()
        event.listen(db.engine, "before_cursor_execute", self.on_before_execute)
    
    def stop(self):
        """Stop tracking queries."""
        event.remove(db.engine, "before_cursor_execute", self.on_before_execute)
    
    def report(self, method_name: str, elapsed_time: float):
        """Log query statistics."""
        logger.info(f"\n{'='*70}")
        logger.info(f"HEATMAP SERVICE: {method_name}")
        logger.info(f"{'='*70}")
        logger.info(f"⏱️  Elapsed: {elapsed_time:.2f}s")
        logger.info(f"📊 Queries: {self.count}")
        logger.info(f"")
        for i, q in enumerate(self.queries[:5], 1):
            logger.info(f"  {i}. {q}...")
        if len(self.queries) > 5:
            logger.info(f"  ... and {len(self.queries) - 5} more queries")
        logger.info(f"{'='*70}\n")


query_counter = QueryCounter()


class CapabilityHeatmapService:
    """Aggregation service for capability maturity heatmaps and gap analysis."""

    def get_maturity_heatmap(self) -> Dict[str, Any]:
        """
        Build maturity heatmap data: domains (rows) x maturity levels 1 - 5 (columns).

        Each cell contains the count and names of capabilities at that maturity level.
        Each domain row includes an overall health score.

        Returns:
            Dict with domains list, legend, and summary stats.
        """
        # PHASE 2: Query profiling - measure execution time and queries
        query_counter.start()
        start_time = time.time()
        
        try:
            # Try UnifiedCapability first (empty), fall back to BusinessCapability (with Abacus data)
            capabilities = (
                db.session.query(UnifiedCapability, BusinessDomain.name, BusinessDomain.code)
                .join(BusinessDomain, UnifiedCapability.domain_id == BusinessDomain.id)
                .all()
            )
            
            # Fallback: if UnifiedCapability is empty, try BusinessCapability
            if not capabilities:
                try:
                    from app.models.business_capabilities import BusinessCapability
                    logger.info("UnifiedCapability empty, falling back to BusinessCapability for heatmap")
                    
                    # BusinessCapability has domain name stored directly - no need to join
                    cap_data = db.session.query(BusinessCapability).all()
                    
                    # Transform to same format as UnifiedCapability results
                    # (cap object, domain_name, domain_code)
                    capabilities = [(cap, cap.business_domain or "Unknown", cap.code or "UNK") for cap in cap_data]
                    
                except (ImportError, Exception) as e:
                    logger.warning(f"BusinessCapability fallback failed: {e}, using empty result")
                    capabilities = []

            # Group by domain
            domain_map = {}
            for cap, domain_name, domain_code in capabilities:
                key = domain_code
                if key not in domain_map:
                    domain_map[key] = {
                        "name": domain_name,
                        "code": domain_code,
                        "capabilities_by_maturity": {1: [], 2: [], 3: [], 4: [], 5: []},
                        "maturity_values": [],
                        "target_values": [],
                    }
                maturity = cap.current_maturity_level or 1
                maturity = max(1, min(5, maturity))
                domain_map[key]["capabilities_by_maturity"][maturity].append(
                    {
                        "id": cap.id,
                        "name": cap.name,
                        "target": cap.target_maturity_level or 3,
                    }
                )
                domain_map[key]["maturity_values"].append(maturity)
                domain_map[key]["target_values"].append(cap.target_maturity_level or 3)

            # Build domain rows with health scores
            domains = []
            for code in sorted(domain_map.keys()):
                d = domain_map[code]
                maturity_vals = d["maturity_values"]
                target_vals = d["target_values"]

                avg_maturity = sum(maturity_vals) / len(maturity_vals) if maturity_vals else 0
                avg_target = sum(target_vals) / len(target_vals) if target_vals else 0

                # Health score: ratio of current to target maturity (0 - 100)
                if avg_target > 0:
                    health_score = round((avg_maturity / avg_target) * 100, 1)
                else:
                    health_score = 0

                counts = {}
                names = {}
                for level in range(1, 6):
                    caps_at_level = d["capabilities_by_maturity"][level]
                    counts[level] = len(caps_at_level)
                    names[level] = [c["name"] for c in caps_at_level]

                domains.append(
                    {
                        "name": d["name"],
                        "code": d["code"],
                        "counts": counts,
                        "capability_names": names,
                        "avg_maturity": round(avg_maturity, 1),
                        "avg_target": round(avg_target, 1),
                        "health_score": min(health_score, 100),
                        "total_capabilities": len(maturity_vals),
                    }
                )

            legend = [
                {"level": 1, "label": "Initial", "color": "#ef4444"},
                {"level": 2, "label": "Managed", "color": "#f97316"},
                {"level": 3, "label": "Defined", "color": "#eab308"},
                {"level": 4, "label": "Quantitatively Managed", "color": "#84cc16"},
                {"level": 5, "label": "Optimizing", "color": "#22c55e"},
            ]

            result = {
                "domains": domains,
                "legend": legend,
                "total_capabilities": len(capabilities),
                "total_domains": len(domains),
            }
            
            return result
            
        finally:
            # PHASE 2: Report query statistics
            elapsed = time.time() - start_time
            query_counter.stop()
            query_counter.report("get_maturity_heatmap", elapsed)

    def get_gap_alerts(self) -> Dict[str, Any]:
        """
        Detect capabilities with gaps requiring attention.

        Three alert categories:
        - Unmapped: capabilities with zero application mappings
        - Low coverage: capabilities where average coverage < 50%
        - Critical maturity gaps: current maturity 2+ levels below target

        Returns:
            Dict with unmapped, low_coverage, maturity_gaps lists and summary.
        """
        # 1. Unmapped capabilities (no entries in mapping table)
        mapped_ids_subq = (
            db.session.query(UnifiedApplicationCapabilityMapping.unified_capability_id)
            .distinct()
            .subquery()
        )

        unmapped_caps = (
            db.session.query(UnifiedCapability, BusinessDomain.name)
            .join(BusinessDomain, UnifiedCapability.domain_id == BusinessDomain.id)
            .filter(~UnifiedCapability.id.in_(db.session.query(mapped_ids_subq)))
            .order_by(UnifiedCapability.strategic_importance.desc())
            .all()
        )

        unmapped = []
        for cap, domain_name in unmapped_caps:
            unmapped.append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "domain": domain_name,
                    "level": cap.level,
                    "strategic_importance": cap.strategic_importance or "medium",
                    "business_criticality": cap.business_criticality or "supporting",
                }
            )

        # 2. Low coverage capabilities (average coverage_percentage < 50%)
        low_coverage_data = (
            db.session.query(
                UnifiedCapability.id,
                UnifiedCapability.name,
                BusinessDomain.name.label("domain_name"),
                func.avg(UnifiedApplicationCapabilityMapping.coverage_percentage).label(
                    "avg_coverage"
                ),
                func.count(UnifiedApplicationCapabilityMapping.id).label("app_count"),
            )
            .join(BusinessDomain, UnifiedCapability.domain_id == BusinessDomain.id)
            .join(
                UnifiedApplicationCapabilityMapping,
                UnifiedApplicationCapabilityMapping.unified_capability_id == UnifiedCapability.id,
            )
            .group_by(UnifiedCapability.id, UnifiedCapability.name, BusinessDomain.name)
            .having(func.avg(UnifiedApplicationCapabilityMapping.coverage_percentage) < 50)
            .order_by(func.avg(UnifiedApplicationCapabilityMapping.coverage_percentage))
            .all()
        )

        low_coverage = []
        for cap_id, cap_name, domain_name, avg_cov, app_count in low_coverage_data:
            low_coverage.append(
                {
                    "id": cap_id,
                    "name": cap_name,
                    "domain": domain_name,
                    "coverage_avg": round(float(avg_cov or 0), 1),
                    "app_count": app_count,
                }
            )

        # 3. Critical maturity gaps (current_maturity_level < target by 2+)
        maturity_gap_caps = (
            db.session.query(UnifiedCapability, BusinessDomain.name)
            .join(BusinessDomain, UnifiedCapability.domain_id == BusinessDomain.id)
            .filter(
                UnifiedCapability.target_maturity_level.isnot(None),
                UnifiedCapability.current_maturity_level.isnot(None),
                (UnifiedCapability.target_maturity_level - UnifiedCapability.current_maturity_level)
                >= 2,
            )
            .order_by(
                (
                    UnifiedCapability.target_maturity_level
                    - UnifiedCapability.current_maturity_level
                ).desc()
            )
            .all()
        )

        maturity_gaps = []
        for cap, domain_name in maturity_gap_caps:
            gap = (cap.target_maturity_level or 0) - (cap.current_maturity_level or 0)
            maturity_gaps.append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "domain": domain_name,
                    "current": cap.current_maturity_level or 0,
                    "target": cap.target_maturity_level or 0,
                    "gap": gap,
                }
            )

        # Count critical items (strategic_importance=critical or business_criticality=mission_critical)
        critical_unmapped = sum(
            1
            for u in unmapped
            if u["strategic_importance"] == "critical"
            or u["business_criticality"] == "mission_critical"
        )

        return {
            "unmapped": unmapped,
            "low_coverage": low_coverage,
            "maturity_gaps": maturity_gaps,
            "summary": {
                "unmapped_count": len(unmapped),
                "low_coverage_count": len(low_coverage),
                "maturity_gap_count": len(maturity_gaps),
                "critical_gaps": critical_unmapped,
                "total_alerts": len(unmapped) + len(low_coverage) + len(maturity_gaps),
            },
        }

    def get_domain_health(self) -> List[Dict[str, Any]]:
        """
        Calculate health score for each business domain.

        Health score = weighted(avg_maturity_ratio * 60% + avg_coverage * 40%)
        Status thresholds: healthy (>=80), attention (60 - 79), at_risk (40 - 59), critical (<40)

        Returns:
            List of domain health dicts sorted by health score ascending (worst first).
        """
        domains = BusinessDomain.query.all()

        results = []
        for domain in domains:
            # Get capabilities for this domain
            caps = UnifiedCapability.query.filter_by(domain_id=domain.id).all()
            if not caps:
                results.append(
                    {
                        "domain_name": domain.name,
                        "domain_code": domain.code,
                        "health_score": 0,
                        "capability_count": 0,
                        "avg_maturity": 0,
                        "avg_coverage": 0,
                        "status": "critical",
                    }
                )
                continue

            cap_ids = [c.id for c in caps]

            # Average maturity ratio
            maturity_ratios = []
            for c in caps:
                current = c.current_maturity_level or 1
                target = c.target_maturity_level or 3
                if target > 0:
                    maturity_ratios.append(current / target)
            avg_maturity_ratio = (
                sum(maturity_ratios) / len(maturity_ratios) if maturity_ratios else 0
            )

            # Average coverage from mappings
            coverage_result = (
                db.session.query(func.avg(UnifiedApplicationCapabilityMapping.coverage_percentage))
                .filter(UnifiedApplicationCapabilityMapping.unified_capability_id.in_(cap_ids))
                .scalar()
            )
            avg_coverage = float(coverage_result or 0) / 100.0  # normalize to 0 - 1

            # Weighted health score
            health_score = round((avg_maturity_ratio * 0.6 + avg_coverage * 0.4) * 100, 1)
            health_score = min(health_score, 100)

            # Status classification
            if health_score >= 80:
                status = "healthy"
            elif health_score >= 60:
                status = "attention"
            elif health_score >= 40:
                status = "at_risk"
            else:
                status = "critical"

            avg_maturity = sum(c.current_maturity_level or 1 for c in caps) / len(caps)

            results.append(
                {
                    "domain_name": domain.name,
                    "domain_code": domain.code,
                    "health_score": health_score,
                    "capability_count": len(caps),
                    "avg_maturity": round(avg_maturity, 1),
                    "avg_coverage": round(avg_coverage * 100, 1),
                    "status": status,
                }
            )

        # Sort by health score ascending (worst first for attention)
        results.sort(key=lambda r: r["health_score"])
        return results
