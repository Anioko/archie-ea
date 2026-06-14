"""Prioritisation service — MoSCoW, WSJF, RICE backlog scoring (TPM-006)."""
from __future__ import annotations

import logging
from typing import Optional

from app import db
from app.models.models import Requirement

logger = logging.getLogger(__name__)

_VALID_MOSCOW = {"MUST", "SHOULD", "COULD", "WONT"}


def _req_to_dict(req: Requirement) -> dict:
    return {
        "id": req.id,
        "title": req.title,
        "description": req.description,
        "story_points": req.story_points,
        "moscow_priority": req.moscow_priority,
        "business_value": req.business_value,
        "time_criticality": req.time_criticality,
        "risk_reduction": req.risk_reduction,
        "job_size": req.job_size,
        "wsjf_score": req.wsjf_score,
        "reach": req.reach,
        "impact": req.impact,
        "confidence": req.confidence,
        "rice_score": req.rice_score,
        "requirement_type": req.requirement_type,
    }


def get_backlog_prioritised(solution_id: Optional[int] = None, method: str = "wsjf") -> list[dict]:
    """Return requirements sorted by the chosen method (wsjf/rice/moscow/manual)."""
    query = Requirement.query
    if solution_id is not None:
        query = query.filter_by(architecture_id=solution_id)

    reqs = query.all()
    items = [_req_to_dict(r) for r in reqs]

    _MOSCOW_ORDER = {"MUST": 0, "SHOULD": 1, "COULD": 2, "WONT": 3, None: 4}

    if method == "wsjf":
        items.sort(key=lambda x: x["wsjf_score"], reverse=True)
    elif method == "rice":
        items.sort(key=lambda x: x["rice_score"], reverse=True)
    elif method == "moscow":
        items.sort(key=lambda x: _MOSCOW_ORDER.get(x["moscow_priority"], 4))
    # "manual" — preserve DB order

    return items


def set_moscow(requirement_id: int, priority: str) -> dict:
    """Set MoSCoW priority for a requirement. Returns updated dict."""
    priority = (priority or "").upper().strip()
    if priority not in _VALID_MOSCOW:
        raise ValueError(f"priority must be one of {_VALID_MOSCOW}, got {priority!r}")

    req = Requirement.query.get_or_404(requirement_id)
    req.moscow_priority = priority
    db.session.commit()
    logger.info("TPM-006 MoSCoW set req=%d priority=%s", requirement_id, priority)
    return _req_to_dict(req)


def set_wsjf_components(
    requirement_id: int,
    business_value: int,
    time_criticality: int,
    risk_reduction: int,
    job_size: int,
) -> dict:
    """Set WSJF scoring components and return updated dict with computed wsjf_score."""
    req = Requirement.query.get_or_404(requirement_id)
    req.business_value = max(business_value, 1)
    req.time_criticality = max(time_criticality, 1)
    req.risk_reduction = max(risk_reduction, 1)
    req.job_size = max(job_size, 1)
    db.session.commit()
    logger.info("TPM-006 WSJF set req=%d score=%.2f", requirement_id, req.wsjf_score)
    return _req_to_dict(req)


def set_rice_components(
    requirement_id: int,
    reach: int,
    impact: int,
    confidence: int,
) -> dict:
    """Set RICE scoring components and return updated dict with computed rice_score."""
    req = Requirement.query.get_or_404(requirement_id)
    req.reach = max(reach, 0)
    req.impact = max(min(impact, 5), 1)
    req.confidence = max(min(confidence, 100), 0)
    db.session.commit()
    logger.info("TPM-006 RICE set req=%d score=%.2f", requirement_id, req.rice_score)
    return _req_to_dict(req)
