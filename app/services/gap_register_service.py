"""OA-001: Gap Register Service — unified gap view across TOGAF ADM Phases B, C, D.

Aggregates gap records from three source tables into a single queryable register:
  - 'capability'      → CapabilityGapAnalysis  (Phase B: Business Architecture)
  - 'implementation'  → Gap                    (Phase D: Technology / Migration)
  - 'roadmap'         → Gap with roadmap types  (Phase E: Opportunities & Solutions)

Contract (docs/adm_phases_d_a_g_e_f_h_tasks.json OA-001):
  - No raw SQL
  - No new ORM models — imports only
  - get_unified_gap_register() handles all 3 source tables being empty gracefully
  - Each item has gap_source in ['capability', 'implementation', 'roadmap']
  - severity value comes from DB column, never fabricated
"""

import logging
from typing import Any, Dict, List

from app import db
from app.models.capability_gap_analysis import CapabilityGapAnalysis
from app.models.implementation_migration import Gap

log = logging.getLogger(__name__)

_ROADMAP_GAP_TYPES = frozenset({"roadmap", "modernization", "retirement", "migration"})


def get_unified_gap_register(
    adm_phase: str = None,
    severity: str = None,
    status: str = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Return a unified list of gaps from all three ADM source tables.

    Args:
        adm_phase:  Optional TOGAF ADM phase filter (e.g. 'B', 'C', 'D').
        severity:   Optional severity filter (low/medium/high/critical).
        status:     Optional status filter (varies by source).
        limit:      Maximum total rows returned per source (default 500).

    Returns:
        List of dicts each containing:
          gap_source, gap_id, title, severity, status, adm_phase, description
        Returns empty list if all source tables are empty or an error occurs.
    """
    results: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Source 1: capability gaps — Phase B Business Architecture
    # ------------------------------------------------------------------
    try:
        q = db.session.query(CapabilityGapAnalysis)
        if severity:
            q = q.filter(CapabilityGapAnalysis.gap_severity == severity)
        if status:
            q = q.filter(CapabilityGapAnalysis.status == status)
        rows = q.limit(limit).all()
        for row in rows:
            results.append({
                "gap_source": "capability",
                "gap_id": row.id,
                "title": (
                    getattr(row, "gap_title", None)
                    or getattr(row, "title", None)
                    or f"CAP-GAP-{row.id}"
                ),
                "severity": row.gap_severity,
                "status": getattr(row, "status", None),
                "adm_phase": "B",
                "description": getattr(row, "gap_description", None),
                "capability_id": getattr(row, "capability_id", None),
            })
    except Exception as exc:
        log.warning("gap_register: capability source unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Source 2: implementation / technology gaps — Phase D
    # ------------------------------------------------------------------
    try:
        q = db.session.query(Gap)
        if severity:
            q = q.filter(Gap.severity == severity)
        if status:
            q = q.filter(Gap.resolution_status == status)
        if adm_phase:
            q = q.filter(Gap.togaf_phase == adm_phase)
        rows = q.limit(limit).all()
        for row in rows:
            results.append({
                "gap_source": "implementation",
                "gap_id": row.id,
                "title": getattr(row, "title", None) or f"IMPL-GAP-{row.id}",
                "severity": row.severity,
                "status": row.resolution_status,
                "adm_phase": getattr(row, "togaf_phase", None) or "D",
                "description": row.description,
                "gap_type": row.gap_type,
            })
    except Exception as exc:
        log.warning("gap_register: implementation source unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Source 3: roadmap / opportunities gaps — Phase E
    # Subset of Gap rows with roadmap-oriented gap_type values.
    # ------------------------------------------------------------------
    try:
        q = db.session.query(Gap).filter(Gap.gap_type.in_(_ROADMAP_GAP_TYPES))
        if severity:
            q = q.filter(Gap.severity == severity)
        rows = q.limit(limit).all()
        for row in rows:
            results.append({
                "gap_source": "roadmap",
                "gap_id": row.id,
                "title": getattr(row, "title", None) or f"ROAD-GAP-{row.id}",
                "severity": row.severity,
                "status": row.resolution_status,
                "adm_phase": "E",
                "description": row.description,
                "gap_type": row.gap_type,
            })
    except Exception as exc:
        log.warning("gap_register: roadmap source unavailable: %s", exc)

    return results


def gap_summary_by_phase() -> Dict[str, Any]:
    """Return a count summary of gaps grouped by source and severity.

    Returns:
        Dict with keys matching each gap_source; each value is a dict of
        severity → count.  All values come from DB columns; none fabricated.
    """
    summary: Dict[str, Any] = {
        "capability": {},
        "implementation": {},
        "roadmap": {},
        "total": 0,
    }

    try:
        rows = (
            db.session.query(
                CapabilityGapAnalysis.gap_severity,
                db.func.count(CapabilityGapAnalysis.id),
            )
            .group_by(CapabilityGapAnalysis.gap_severity)
            .all()
        )
        for sev, cnt in rows:
            summary["capability"][sev or "unknown"] = cnt
            summary["total"] += cnt
    except Exception as exc:
        log.warning("gap_register: capability summary unavailable: %s", exc)

    try:
        rows = (
            db.session.query(Gap.severity, db.func.count(Gap.id))
            .group_by(Gap.severity)
            .all()
        )
        for sev, cnt in rows:
            summary["implementation"][sev or "unknown"] = cnt
            summary["total"] += cnt
    except Exception as exc:
        log.warning("gap_register: implementation summary unavailable: %s", exc)

    try:
        rows = (
            db.session.query(Gap.severity, db.func.count(Gap.id))
            .filter(Gap.gap_type.in_(_ROADMAP_GAP_TYPES))
            .group_by(Gap.severity)
            .all()
        )
        for sev, cnt in rows:
            summary["roadmap"][sev or "unknown"] = cnt
    except Exception as exc:
        log.warning("gap_register: roadmap summary unavailable: %s", exc)

    return summary
