"""Reference catalogue — the "has this been solved before?" lens for solution architects.

A solution architect's first move on any new problem should be to check what the
enterprise has already built and had approved, and reuse it. The data is there —
governed, ARB-approved Solutions — but there was no way to browse them *as a reuse
catalogue*, filtered to the ones proven enough to copy. This provides it: the
approved/endorsed solutions, searchable and filterable by domain and type, each
showing what makes it reusable (its ADM maturity, approval, owner, domain).

Reads only; tenant-scoped by the ORM inside a request.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_APPROVED_STATES = ("approved", "endorsed", "baselined", "published")
_LIMIT = 300


def _is_reference_filter(model):
    from sqlalchemy import or_  # noqa: PLC0415
    return or_(
        model.arb_approval_date.isnot(None),
        model.governance_status.in_(_APPROVED_STATES),
    )


def build_reference_catalog(domain: Optional[str] = None,
                            solution_type: Optional[str] = None,
                            q: Optional[str] = None) -> Dict[str, Any]:
    from app.models.solution_models import Solution  # noqa: PLC0415

    base = Solution.query.filter(_is_reference_filter(Solution))

    # Facets come from the full reference set, so the dropdowns list every
    # available choice regardless of the current filter.
    all_refs = base.limit(_LIMIT).all()
    domains = sorted({s.business_domain for s in all_refs if s.business_domain})
    types = sorted({s.solution_type for s in all_refs if s.solution_type})

    filtered = base
    if domain:
        filtered = filtered.filter(Solution.business_domain == domain)
    if solution_type:
        filtered = filtered.filter(Solution.solution_type == solution_type)
    if q:
        like = f"%{q.strip()}%"
        filtered = filtered.filter(Solution.name.ilike(like))

    rows = (filtered.order_by(Solution.arb_approval_date.desc().nullslast())
            .limit(_LIMIT).all())

    items: List[Dict[str, Any]] = []
    for s in rows:
        items.append({
            "id": s.id,
            "name": getattr(s, "name", None) or f"Solution {s.id}",
            "description": (getattr(s, "description", None) or "")[:200],
            "domain": getattr(s, "business_domain", None),
            "type": getattr(s, "solution_type", None),
            "owner": getattr(s, "solution_owner", None),
            "adm_phase": getattr(s, "adm_phase", None),
            "complexity": getattr(s, "complexity_level", None),
            "approved_on": getattr(s, "arb_approval_date", None),
            "governance": getattr(s, "governance_status", None),
        })

    return {
        "items": items,
        "total": len(items),
        "total_reference": len(all_refs),
        "facets": {"domains": domains, "types": types},
        "active": {"domain": domain or "", "type": solution_type or "", "q": q or ""},
    }
