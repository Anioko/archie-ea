"""Solution Architecture Document builder (OPS-003).

Gathers the full SAD content for one Solution from every junction that
feeds the TOGAF ADM phases, and returns a single context dict the
exports/solution_architecture_document.html template renders.

Design rules:
  - Every section is independently fault-tolerant (_safe wrapper). A
    missing table or column degrades one section to empty, never breaks
    the document.
  - Every quantitative claim is a query result — no fabricated content
    (Rule 11). Empty sections render an honest "not yet documented".
  - The builder is read-only.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List

from app import db

logger = logging.getLogger(__name__)


def _safe(name: str, fn: Callable[[], Any], default):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — one bad section must not break the doc
        logger.debug("SAD section %s unavailable: %s", name, exc)
        return default


class SADDocumentBuilder:
    """Assemble the full SAD render context for a Solution."""

    @classmethod
    def build(cls, solution) -> Dict[str, Any]:
        sid = solution.id
        session_id = solution.analysis_session_id
        problem_ids = cls._problem_ids(session_id)

        ctx: Dict[str, Any] = {
            "solution": solution,
            "generated_at": datetime.utcnow(),
            "doc_version": solution.blueprint_version or "1.0",
        }

        # Phase A — Architecture Vision
        ctx["stakeholders"] = _safe("stakeholders", lambda: cls._stakeholders(sid), [])
        ctx["drivers"] = _safe("drivers", lambda: cls._drivers(problem_ids), [])
        ctx["goals"] = _safe("goals", lambda: cls._goals(problem_ids), [])
        ctx["constraints"] = _safe("constraints", lambda: cls._constraints(problem_ids), [])
        ctx["principles"] = _safe("principles", lambda: cls._principles(problem_ids), [])

        # Phase B–D — Business / IS / Technology architecture
        ctx["capabilities"] = _safe("capabilities", lambda: cls._capabilities(sid), [])
        ctx["applications"] = _safe("applications", lambda: cls._applications(sid), [])
        ctx["requirements"] = _safe("requirements", lambda: cls._requirements(sid, problem_ids), [])
        ctx["elements_by_layer"] = _safe("elements", lambda: cls._elements_by_layer(sid), {})

        # Phase E — Opportunities & Solutions
        ctx["options"] = _safe("options", lambda: cls._options(session_id), [])
        ctx["vendor_products"] = _safe("vendors", lambda: cls._vendor_products(sid), [])
        ctx["fit_gap"] = _safe("fit_gap", lambda: cls._fit_gap(sid), [])

        # Phase F — Migration planning
        ctx["plateaus"] = _safe("plateaus", lambda: cls._plateaus(sid), [])

        # Phase G — Governance
        ctx["governance"] = _safe("governance", lambda: cls._governance(solution), {})

        # Phase H — Change management
        ctx["metrics"] = _safe("metrics", lambda: cls._metrics(sid), [])
        ctx["risks"] = _safe("risks", lambda: cls._risks(sid), [])

        # Document control / executive summary derivations
        ctx["maturity"] = solution.maturity_current or 0
        ctx["section_counts"] = cls._counts(ctx)
        return ctx

    # ----------------------------------------------------------------- #
    # Helpers                                                            #
    # ----------------------------------------------------------------- #

    @staticmethod
    def _problem_ids(session_id) -> List[int]:
        if not session_id:
            return []
        from app.models.solution_architect_models import SolutionProblemDefinition
        return [
            r[0] for r in db.session.query(SolutionProblemDefinition.id)
            .filter_by(session_id=session_id).all()
        ]

    @staticmethod
    def _drivers(problem_ids):
        if not problem_ids:
            return []
        from app.models.solution_architect_models import SolutionDriver
        rows = SolutionDriver.query.filter(SolutionDriver.problem_id.in_(problem_ids)).all()
        return [{
            "name": d.name,
            "description": d.description or "",
            "type": d.driver_type.value if d.driver_type else "",
            "impact": d.impact_level,
            "urgency": d.urgency,
            "source": d.source or "",
        } for d in rows]

    @staticmethod
    def _goals(problem_ids):
        if not problem_ids:
            return []
        from app.models.solution_architect_models import SolutionGoal
        rows = SolutionGoal.query.filter(SolutionGoal.problem_id.in_(problem_ids)).all()
        return [{
            "name": g.name,
            "description": g.description or "",
            "measurement": g.measurement_criteria or "",
            "priority": g.priority,
            "target_date": g.target_date.strftime("%Y-%m-%d") if g.target_date else "",
        } for g in rows]

    @staticmethod
    def _constraints(problem_ids):
        if not problem_ids:
            return []
        from app.models.solution_architect_models import SolutionConstraint
        rows = SolutionConstraint.query.filter(
            SolutionConstraint.problem_id.in_(problem_ids)
        ).all()
        return [{
            "name": c.name,
            "description": c.description or "",
            "type": c.constraint_type.value if c.constraint_type else "",
            "value": c.value or "",
            "severity": c.severity,
        } for c in rows]

    @staticmethod
    def _principles(problem_ids):
        if not problem_ids:
            return []
        from app.models.solution_architect_models import SolutionPrinciple
        rows = SolutionPrinciple.query.filter(
            SolutionPrinciple.problem_id.in_(problem_ids)
        ).all()
        return [{
            "name": p.name,
            "statement": p.statement or "",
            "rationale": p.rationale or "",
            "implications": p.implications or "",
        } for p in rows]

    @staticmethod
    def _stakeholders(sid):
        from app.models.solution_stakeholder import SolutionStakeholder
        rows = SolutionStakeholder.query.filter_by(solution_id=sid).all()
        return [{
            "name": getattr(s, "name", "") or "",
            "role": getattr(s, "role", "") or "",
            "concerns": getattr(s, "concerns", "") or getattr(s, "key_concerns", "") or "",
            "influence": getattr(s, "influence_level", "") or getattr(s, "influence", "") or "",
        } for s in rows]

    @staticmethod
    def _capabilities(sid):
        from app.models.solution_models import SolutionCapabilityMapping
        from app.models.business_capabilities import BusinessCapability
        rows = (
            db.session.query(BusinessCapability.name, SolutionCapabilityMapping.support_level)
            .join(SolutionCapabilityMapping,
                  SolutionCapabilityMapping.capability_id == BusinessCapability.id)
            .filter(SolutionCapabilityMapping.solution_id == sid)
            .all()
        )
        return [{"name": n, "support_level": sl or ""} for n, sl in rows]

    @staticmethod
    def _applications(sid):
        from app.models.solution_models import solution_applications
        from app.models.application_portfolio import ApplicationComponent
        rows = (
            db.session.query(
                ApplicationComponent.name,
                ApplicationComponent.lifecycle_status,
                ApplicationComponent.vendor_name,
                ApplicationComponent.business_owner,
            )
            .join(solution_applications,
                  solution_applications.c.application_component_id == ApplicationComponent.id)
            .filter(solution_applications.c.solution_id == sid)
            .all()
        )
        return [{
            "name": n, "lifecycle": ls or "", "vendor": v or "", "owner": o or "",
        } for n, ls, v, o in rows]

    @staticmethod
    def _requirements(sid, problem_ids):
        from sqlalchemy import or_
        from app.models.solution_architect_models import SolutionRequirement
        q = SolutionRequirement.query
        conds = [SolutionRequirement.solution_id == sid]
        if problem_ids:
            conds.append(SolutionRequirement.problem_id.in_(problem_ids))
        rows = q.filter(or_(*conds)).all()
        out = []
        for r in rows:
            out.append({
                "name": r.name,
                "description": r.description or "",
                "type": r.requirement_type.value if r.requirement_type else "",
                "priority": r.priority,
                "mandatory": bool(r.is_mandatory),
                "acceptance_criteria": r.acceptance_criteria or "",
            })
        return out

    @staticmethod
    def _elements_by_layer(sid):
        from app.models.solution_models import SolutionArchiMateElement
        rows = SolutionArchiMateElement.query.filter_by(solution_id=sid).all()
        by_layer: Dict[str, List[Dict[str, str]]] = {}
        for e in rows:
            layer = (getattr(e, "layer_type", None) or "Unspecified").title()
            by_layer.setdefault(layer, []).append({
                "name": getattr(e, "element_name", None) or "(unnamed)",
                "type": getattr(e, "element_type", None) or getattr(e, "element_table", "") or "",
            })
        return by_layer

    @staticmethod
    def _options(session_id):
        if not session_id:
            return []
        from app.models.solution_architect_models import SolutionRecommendation
        rows = (
            SolutionRecommendation.query.filter_by(session_id=session_id)
            .order_by(SolutionRecommendation.rank).all()
        )
        out = []
        for o in rows:
            out.append({
                "name": o.name or (o.option_type.value if o.option_type else "Option"),
                "type": o.option_type.value if o.option_type else "",
                "rank": o.rank,
                "score": float(o.score) if o.score is not None else None,
                "is_recommended": bool(o.is_recommended),
                "cost_min": float(o.estimated_cost_min) if o.estimated_cost_min is not None else None,
                "cost_max": float(o.estimated_cost_max) if o.estimated_cost_max is not None else None,
                "currency": o.cost_currency or "GBP",
                "timeline_months": o.timeline_months,
                "pros": o.pros if isinstance(o.pros, list) else [],
                "cons": o.cons if isinstance(o.cons, list) else [],
                "justification": o.justification or "",
            })
        return out

    @staticmethod
    def _vendor_products(sid):
        from app.models.solution_models import solution_vendor_products
        from app.models.vendor.vendor_organization import VendorProduct
        rows = (
            db.session.query(VendorProduct.name, VendorProduct.category)
            .join(solution_vendor_products,
                  solution_vendor_products.c.vendor_product_id == VendorProduct.id)
            .filter(solution_vendor_products.c.solution_id == sid)
            .all()
        )
        return [{"name": n, "category": c or ""} for n, c in rows]

    @staticmethod
    def _fit_gap(sid):
        from app.models.solution_models import SolutionFitGapEntry
        rows = (
            SolutionFitGapEntry.query.filter_by(solution_id=sid)
            .order_by(SolutionFitGapEntry.erp_module, SolutionFitGapEntry.sort_order).all()
        )
        return [{
            "process": e.business_process,
            "module": e.erp_module or "",
            "fit_type": e.fit_type or "unclassified",
            "status": e.status or "draft",
            "justification": e.justification or "",
        } for e in rows]

    @staticmethod
    def _plateaus(sid):
        from app.models.solution_lifecycle_models import SolutionPlateau
        rows = (
            SolutionPlateau.query.filter_by(solution_id=sid)
            .order_by(SolutionPlateau.order, SolutionPlateau.id).all()
        )
        return [{
            "name": p.name,
            "description": p.description or "",
            "target_date": p.target_date.strftime("%Y-%m-%d") if p.target_date else "",
        } for p in rows]

    @staticmethod
    def _metrics(sid):
        from app.models.solution_lifecycle_models import SolutionMetric
        rows = SolutionMetric.query.filter_by(solution_id=sid).all()
        return [{
            "name": getattr(m, "name", "") or getattr(m, "metric_name", "") or "",
            "target": getattr(m, "target_value", "") or getattr(m, "target", "") or "",
            "current": getattr(m, "current_value", "") or "",
            "status": getattr(m, "status", "") or "",
        } for m in rows]

    @staticmethod
    def _risks(sid):
        from app.models.solution_lifecycle_models import SolutionRisk
        rows = SolutionRisk.query.filter_by(solution_id=sid).all()
        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        out = [{
            "description": getattr(r, "risk_description", "") or getattr(r, "description", "") or "",
            "impact": r.impact or "",
            "probability": getattr(r, "probability", "") or "",
            "mitigation": getattr(r, "mitigation", "") or getattr(r, "mitigation_plan", "") or "",
            "status": r.status or "open",
        } for r in rows]
        out.sort(key=lambda x: sev_rank.get((x["impact"] or "").lower(), 4))
        return out

    @staticmethod
    def _governance(solution):
        # governance_status + arb_review_item_id are guaranteed Solution columns
        gov = {
            "status": solution.governance_status or "draft",
            "arb_item_id": solution.arb_review_item_id,
            "reviews": [],
        }
        try:
            from app.models.architecture_review_board import ARBReviewItem
            if gov["arb_item_id"]:
                item = db.session.get(ARBReviewItem, gov["arb_item_id"])
                if item is not None:
                    # ARBReviewItem schema varies — getattr is intentional here
                    gov["arb_status"] = (item.status or "") if hasattr(item, "status") else ""  # model-safety-ok: cross-version ARB schema
                    gov["arb_decision"] = (item.decision or "") if hasattr(item, "decision") else ""  # model-safety-ok: cross-version ARB schema
        except Exception as exc:
            logger.debug("ARB context unavailable: %s", exc)
        return gov

    @staticmethod
    def _counts(ctx):
        keys = ["stakeholders", "drivers", "goals", "constraints", "principles",
                "capabilities", "applications", "requirements", "options",
                "vendor_products", "fit_gap", "plateaus", "metrics", "risks"]
        n = {k: len(ctx.get(k) or []) for k in keys}
        n["elements"] = sum(len(v) for v in (ctx.get("elements_by_layer") or {}).values())
        n["total"] = sum(n.values())
        return n
