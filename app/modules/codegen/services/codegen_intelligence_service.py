"""Unified AI intelligence actions for the Code Workbench (advisory LLM + deterministic helpers).

Each action maps to one product-facing capability described in docs/ARCHITECTURE_JOURNEY_CODEGEN_ASSURANCE.md
and the codegen workbench design. Outputs are advisory only — not legal/regulatory attestation.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_ACTIONS = frozenset({
    "requirements_to_tests",
    "gap_ambiguity_coach",
    "regeneration_copilot",
    "traceability_explainer",
    "failure_triage",
    "nfr_compliance_assistant",
    "journey_copilot_tips",
})


def _compact_json(obj: Any, max_len: int = 12000) -> str:
    raw = json.dumps(obj, ensure_ascii=False, default=str)
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 20] + "\n…(truncated)…"


def _latest_quality(gen) -> Tuple[Optional[float], Optional[dict]]:
    """Return (score, details) from latest history or None."""
    try:
        from app.modules.codegen.models import CodegenGenerationHistory

        history = (
            CodegenGenerationHistory.query.filter_by(codegen_generation_id=gen.id)
            .order_by(CodegenGenerationHistory.generated_at.desc())
            .first()
        )
        if history:
            return getattr(history, "quality_score", None), getattr(
                history, "quality_details", None
            ) or {}
    except Exception as e:
        logger.debug("quality history load: %s", e)
    return None, None


def _find_uml_refs(uml: dict, element_id: int) -> List[str]:
    """Return human-readable locations where source_element_id matches."""
    hits: List[str] = []
    if not uml:
        return hits
    eid = int(element_id)
    cd = uml.get("class_diagram") or {}
    for c in cd.get("classes") or []:
        if c.get("source_element_id") == eid:
            hits.append(f"class_diagram.classes[{c.get('name')}]")
    seq = uml.get("sequence_diagram") or {}
    for f in seq.get("flows") or []:
        if f.get("source_element_id") == eid:
            hits.append(f"sequence_diagram.flows[{f.get('name')}]")
    comp = uml.get("component_diagram") or {}
    for c in comp.get("components") or []:
        if c.get("source_element_id") == eid:
            hits.append(f"component_diagram.components[{c.get('name')}]")
    dep = uml.get("deployment_diagram") or {}
    for n in dep.get("nodes") or []:
        if n.get("source_element_id") == eid:
            hits.append(f"deployment_diagram.nodes[{n.get('name')}]")
    return hits


def _find_code_refs(files: dict, element_id: int) -> List[str]:
    """Return file paths whose contents reference the ArchiMate element id."""
    if not files:
        return []
    needle = str(int(element_id))
    out: List[str] = []
    for path, content in files.items():
        if not isinstance(content, str):
            continue
        if needle in content or f"ARCHIMATE_SOURCE: {needle}" in content:
            out.append(path)
    return out[:40]


def _regeneration_copilot_deterministic(
    quality_details: Optional[dict], uml: Optional[dict]
) -> Dict[str, Any]:
    """Rank codegen prompt groups using deterministic quality signals + UML shape."""
    qd = quality_details or {}
    recs = list(qd.get("recommendations") or [])
    per_class = qd.get("per_class") or {}
    order = ["models", "schemas", "routes", "services", "integrations", "tests", "infrastructure"]
    reasons: Dict[str, str] = {}

    schema = float(qd.get("schema_completeness") or 0)
    tests = float(qd.get("test_coverage") or 0)
    trace = float(qd.get("traceability") or 0)
    rules = float(qd.get("rule_coverage") or 0)

    if schema < 70:
        reasons["models"] = "Schema completeness is below target — refresh models and schemas first."
        reasons["schemas"] = reasons["models"]
    if tests < 60:
        reasons["tests"] = "Test coverage signal is low — regenerate tests after routes stabilize."
    if trace < 70:
        reasons["routes"] = "Traceability score suggests API routes may need re-alignment with flows."
        reasons["services"] = "Service layer may be missing trace links from sequence flows."
    if rules < 70:
        reasons["services"] = "Business rule coverage is low — services and routes likely need enrichment."
        reasons["routes"] = reasons.get("routes") or "Routes should enforce validators tied to MUST rules."

    classes = (uml or {}).get("class_diagram", {}).get("classes") or []
    if len(classes) > 8 and schema >= 70:
        reasons["integrations"] = "Many entities — confirm external integrations are still accurate."

    # Weighted sort: groups with reasons first, then by intrinsic order
    def sort_key(k: str) -> Tuple[int, int]:
        has = 0 if k in reasons else 1
        return (has, order.index(k) if k in order else 99)

    ranked = sorted(order, key=sort_key)
    return {
        "ranked_groups": ranked,
        "group_reasons": reasons,
        "quality_signals": {
            "schema_completeness": schema,
            "test_coverage": tests,
            "traceability": trace,
            "rule_coverage": rules,
        },
        "recommendations_echo": recs,
        "sparse_classes": [
            c.get("name")
            for c in classes
            if isinstance(c.get("fields"), list) and len(c.get("fields", [])) <= 3
        ][:12],
    }


def _journey_copilot_tips(payload: dict) -> Dict[str, Any]:
    """Deterministic next-step tips — no LLM (governance + predictable UX)."""
    phase = int(payload.get("phase") or 1)
    has_uml = bool(payload.get("has_uml"))
    has_files = bool(payload.get("has_files"))
    blueprint_stale = bool(payload.get("blueprint_stale"))
    quality_score = payload.get("quality_score")

    tips: List[str] = []
    if blueprint_stale:
        tips.append(
            "Blueprint changed since last enrichment — run Phase 1 (Enrich) again so UML matches the architecture."
        )
    if phase <= 1 and not has_uml:
        tips.append("Complete Phase 1 UML enrichment before configuring stack options.")
    if phase >= 2 and has_uml and not has_files:
        tips.append("Review UML in Phase 2, confirm field specs, then apply confirmed specs before generating.")
    if has_files:
        tips.append("Use the Quality tab to inspect dimensions; open API preview to smoke-test endpoints.")
        tips.append("Regenerate individual prompt groups (Deploy tab) instead of full rebuild when fixing one layer.")
    if quality_score is not None:
        try:
            qs = float(quality_score)
            if qs < 70:
                tips.append(
                    f"Quality score is {qs:.0f}/100 — check recommendations in the Quality tab and re-run targeted regeneration."
                )
        except (TypeError, ValueError):
            pass

    if not tips:
        tips.append("Complete each phase top-to-bottom; revisit earlier phases if the architecture changes.")

    return {"tips": tips, "source": "deterministic"}


def _requirements_for_solution(solution_id: int) -> List[Dict[str, Any]]:
    from app.models.solution_architect_models import SolutionRequirement

    rows = (
        SolutionRequirement.query.filter_by(solution_id=solution_id)
        .filter(SolutionRequirement.deleted_at.is_(None))
        .limit(50)
        .all()
    )
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "name": r.name,
            "description": (r.description or "")[:800],
            "acceptance_criteria": (r.acceptance_criteria or "")[:800],
            "requirement_type": str(r.requirement_type) if r.requirement_type else None,
            "is_mandatory": bool(r.is_mandatory),
            "verification_method": getattr(r, "verification_method", None),
        })
    return out


def _call_llm(prompt: str, max_tokens: int = 3072) -> Tuple[Optional[str], Optional[str]]:
    try:
        from app.modules.ai_chat.services.llm_service import LLMService

        provider, model = LLMService._get_configured_provider()
        tok = LLMService.get_max_tokens_limit(provider, model, requested_max=max_tokens)
        raw_text, _ = LLMService._call_llm(
            prompt=prompt, model=model, provider=provider, max_tokens=tok
        )
        return (raw_text or "").strip(), None
    except Exception as e:
        logger.warning("codegen intelligence LLM failed: %s", e)
        return None, str(e)


def run(
    solution_id: int,
    action: str,
    payload: Optional[dict] = None,
) -> Dict[str, Any]:
    """Dispatch one intelligence action. Returns {success, action, result|error}."""
    payload = payload or {}
    if action not in VALID_ACTIONS:
        return {"success": False, "error": f"Unknown action: {action}", "action": action}

    from app.modules.codegen.models import CodegenGeneration
    from app.models.solution_models import Solution

    gen = CodegenGeneration.query.filter_by(solution_id=solution_id).first()
    uml = gen.uml_snapshot if gen else None
    files = gen.generated_files if gen else None
    cfg = gen.config if gen else {}

    if action == "journey_copilot_tips":
        return {
            "success": True,
            "action": action,
            "result": _journey_copilot_tips(payload),
            "llm": False,
        }

    if action == "regeneration_copilot":
        _score, qd = _latest_quality(gen) if gen else (None, None)
        if not qd and gen and gen.generated_files and gen.uml_snapshot:
            from app.modules.codegen.routes.codegen_routes import (
                _compute_quality_score,
                _get_solution_business_rules,
            )

            br = _get_solution_business_rules(solution_id)
            qd = _compute_quality_score(
                gen.uml_snapshot,
                gen.generated_files,
                business_rules=br,
                seed_context=(cfg or {}).get("seed_context"),
            )[1]
        det = _regeneration_copilot_deterministic(qd, uml)
        expl, err = _call_llm(
            "You are a codegen workbench assistant. Given this deterministic ranking and signals, "
            "write 2–4 short paragraphs for an architect: what to regenerate first and why. "
            "Do not invent file paths. Output markdown.\n\n"
            + _compact_json(det),
            max_tokens=1200,
        )
        det["narrative"] = expl or "(LLM unavailable — use ranked_groups and group_reasons as guidance.)"
        if err:
            det["llm_warning"] = err
        return {"success": True, "action": action, "result": det, "llm": bool(expl)}

    if action == "requirements_to_tests":
        reqs = _requirements_for_solution(solution_id)
        if not reqs:
            return {
                "success": True,
                "action": action,
                "result": {
                    "content": "No `SolutionRequirement` rows linked to this solution yet. "
                    "Promote requirements from the journey or add them before generating tests.",
                    "llm": False,
                },
            }
        prompt = (
            "You are a senior QA engineer. Propose pytest test cases (names + scenarios) that trace to "
            "these requirements. For each requirement id, list Given/When/Then style cases. "
            "Output markdown with sections per requirement. Requirements JSON:\n"
            + _compact_json(reqs)
        )
        text, err = _call_llm(prompt, max_tokens=3500)
        if err and not text:
            return {"success": False, "action": action, "error": err}
        return {
            "success": True,
            "action": action,
            "result": {"content": text, "disclaimer": "Draft only — wire into tests after human review."},
            "llm": True,
        }

    if action == "gap_ambiguity_coach":
        sol = Solution.query.get(solution_id)
        brief = (getattr(sol, "section_narratives", None) or {}).get("problem_statement") or ""
        if not isinstance(brief, str):
            brief = str(brief)[:2000]
        ctx = {
            "problem_statement_excerpt": brief[:2000],
            "uml_present": bool(uml),
            "class_count": len((uml or {}).get("class_diagram", {}).get("classes") or []),
            "flow_count": len((uml or {}).get("sequence_diagram", {}).get("flows") or []),
        }
        prompt = (
            "You are an enterprise architect coach. Identify gaps and ambiguities that could cause "
            "generic or wrong codegen. Reference the data below; do not invent portfolio counts. "
            "Output markdown with: (1) Missing architecture signals (2) Clarifying questions for the team "
            "(3) What to fix in the Journey before re-enriching.\n\n"
            f"Context:\n{_compact_json(ctx)}"
        )
        text, err = _call_llm(prompt, max_tokens=3500)
        if err and not text:
            return {"success": False, "action": action, "error": err}
        return {"success": True, "action": action, "result": {"content": text}, "llm": True}

    if action == "traceability_explainer":
        raw_id = payload.get("source_element_id")
        if raw_id is None:
            return {"success": False, "action": action, "error": "payload.source_element_id is required"}
        try:
            eid = int(raw_id)
        except (TypeError, ValueError):
            return {"success": False, "action": action, "error": "source_element_id must be an integer"}

        uml_hits = _find_uml_refs(uml or {}, eid)
        code_hits = _find_code_refs(files or {}, eid)
        bundle = {
            "source_element_id": eid,
            "uml_locations": uml_hits,
            "code_paths": code_hits,
        }
        prompt = (
            "Explain how this ArchiMate element traces through enriched UML into generated code. "
            "Use the facts below. If a list is empty, say what that means. Output markdown.\n"
            + _compact_json(bundle)
        )
        text, err = _call_llm(prompt, max_tokens=2000)
        if err and not text:
            return {"success": False, "action": action, "error": err}
        return {
            "success": True,
            "action": action,
            "result": {"content": text, "facts": bundle},
            "llm": True,
        }

    if action == "failure_triage":
        err_text = (payload.get("error_text") or "").strip()
        if not err_text:
            err_text = (payload.get("log_excerpt") or "").strip()
        if not err_text:
            return {
                "success": False,
                "action": action,
                "error": "payload.error_text or payload.log_excerpt is required",
            }
        qex = _compact_json({
            "error": err_text[:8000],
            "selected_file": payload.get("selected_file"),
        })
        prompt = (
            "You are a senior engineer triaging a codegen / Docker / pytest failure. "
            "Propose the smallest likely fix steps. Output markdown: Diagnosis, Likely cause, "
            "Concrete next steps (numbered). Do not claim success without verification.\n\n"
            f"Context:\n{qex}"
        )
        text, lerr = _call_llm(prompt, max_tokens=2500)
        if lerr and not text:
            return {"success": False, "action": action, "error": lerr}
        return {"success": True, "action": action, "result": {"content": text}, "llm": True}

    if action == "nfr_compliance_assistant":
        from app.modules.codegen.routes.codegen_routes import _get_solution_business_rules

        rules = _get_solution_business_rules(solution_id)
        nfr = [r for r in rules if r.get("source") == "quality_attribute"]
        other = [
            r for r in rules
            if r.get("severity") == "must" and r.get("source") != "quality_attribute"
        ]
        prompt = (
            "You are assisting with operational NFR / compliance posture for a generated codebase. "
            "Map each quality attribute to concrete engineering checks (monitoring, tests, reviews). "
            "IMPORTANT: Regulatory compliance claims require human or system-of-record sign-off — "
            "state this explicitly. Output markdown.\n\n"
            + _compact_json({"quality_attributes": nfr[:20], "must_rules": other[:15]})
        )
        text, err = _call_llm(prompt, max_tokens=3500)
        if err and not text:
            return {"success": False, "action": action, "error": err}
        return {
            "success": True,
            "action": action,
            "result": {
                "content": text,
                "disclaimer": "Advisory only — not legal or regulatory attestation.",
            },
            "llm": True,
        }

    return {"success": False, "error": "Unhandled action", "action": action}
