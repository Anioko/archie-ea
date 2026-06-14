"""
Capability-Based Planning: AI Requirement Generator Service.

Generates EARS-format requirements from business capability gap data,
persisting them as SolutionRequirement rows with full traceability:
- capability_id FK (what capability this requirement addresses)
- apqc_process_id FK (which APQC PCF process it enables)
- togaf_phase (ADM phase assignment: A-H or REQ)
- moscow_priority (MUST / SHOULD / WONT / optional)
- ai_generated=True, ai_confidence marker

Zero fabricated data — all context comes from live DB rows.
"""

import json
import logging
from typing import List, Dict, Any

from app import db
from app.models.unified_capability import UnifiedCapability
from app.models.solution_architect_models import SolutionRequirement
from app.models.solution_sad_models import SolutionAPQCProcess

logger = logging.getLogger(__name__)

# EARS requirement format instructions for LLM prompt
_EARS_SYSTEM_PROMPT = (
    "You are an enterprise architect generating EARS-format software requirements. "
    "EARS syntax: WHERE <condition>, WHEN <trigger>, the <system> shall <response>. "
    "Output ONLY valid JSON — no markdown, no explanation. "
    "Respond with a JSON array of requirement objects, each with keys: "
    "name (string, 10 words max), "
    "description (EARS-format string), "
    "acceptance_criteria (string, measurable pass/fail condition), "
    "moscow_priority (one of: MUST, SHOULD, WONT), "
    "togaf_phase (one of: B, C, D, E, F, REQ), "
    "suggested_apqc_process_id (integer or null). "
    "Generate exactly {count} requirements. No other output."
)

_GENERATION_PROMPT = (
    "Business Capability: {name}\n"
    "Domain: {domain}\n"
    "Current maturity level: {current_maturity}/5\n"
    "Target maturity level: {target_maturity}/5\n"
    "Maturity gap: {gap}\n"
    "Available APQC processes (id: name): {apqc_processes}\n"
    "\nGenerate {count} traceable requirements to close the capability gap."
)

_VALID_MOSCOW = {"MUST", "SHOULD", "WONT"}
_VALID_PHASES = {"A", "B", "C", "D", "E", "F", "G", "H", "REQ"}
_DEFAULT_COUNT = 4

# MoSCoW → KanbanCard.priority string mapping
_MOSCOW_TO_PRIORITY = {"MUST": "critical", "SHOULD": "high", "WONT": "low"}


class CapabilityRequirementGeneratorService:
    """
    Generates EARS requirements from a business capability's gap analysis.

    Usage:
        svc = CapabilityRequirementGeneratorService()
        result = svc.generate_requirements(capability_id=5, solution_id=12, current_user_id=1)
        # result = {"status": "success", "requirement_ids": [...], "kanban_card_ids": [...], "count": 4}
    """

    def generate_requirements(
        self,
        capability_id: int,
        solution_id: int,
        current_user_id: int,
        count: int = _DEFAULT_COUNT,
    ) -> Dict[str, Any]:
        """
        Generate EARS requirements for a capability and attach to a solution.

        Returns dict with keys: status, requirement_ids, kanban_card_ids, count, error (on failure).
        Never raises — all exceptions are caught and returned as status=error.
        """
        try:
            cap = UnifiedCapability.query.get(capability_id)
            if cap is None:
                return {"status": "error", "error": f"Capability {capability_id} not found"}

            apqc_context = self._get_apqc_context(solution_id)
            prompt = self._build_prompt(cap, apqc_context, count)
            raw = self._call_llm(prompt)
            req_dicts = self._parse_response(raw)
            if not req_dicts:
                return {
                    "status": "error",
                    "error": "LLM response could not be parsed as a JSON array of requirements.",
                }

            requirements = self._persist_requirements(
                req_dicts, capability_id, solution_id, current_user_id, apqc_context
            )
            kanban_card_ids = self._create_kanban_cards_for_requirements(
                requirements, capability_id, current_user_id
            )
            return {
                "status": "success",
                "requirement_ids": [r.id for r in requirements],
                "kanban_card_ids": kanban_card_ids,
                "count": len(requirements),
            }
        except ValueError as ve:
            logger.warning("CBP generator: %s", ve)
            return {"status": "error", "error": str(ve)}
        except Exception as exc:
            logger.error("CBP generator unexpected error: %s", exc, exc_info=True)
            db.session.rollback()
            return {"status": "error", "error": f"Unexpected error: {exc}"}

    # ------------------------------------------------------------------
    # Kanban write-back
    # ------------------------------------------------------------------

    def _create_kanban_cards_for_requirements(
        self,
        requirements: List[SolutionRequirement],
        capability_id: int,
        current_user_id: int,
    ) -> List[int]:
        """
        Write one KanbanCard per requirement in the REQ ADM phase.
        Stores capability_id in implements_capabilities JSON field.
        Returns list of created KanbanCard.id values.
        If ADMPhase REQ does not exist, logs warning and returns [].
        """
        from app.models.adm_kanban import ADMPhase, KanbanBoard, KanbanCard

        req_phase = ADMPhase.query.filter_by(code="REQ").first()
        if req_phase is None:
            logger.warning("CBP-005: ADMPhase with code='REQ' not found — Kanban write-back skipped.")
            return []

        board = self._get_or_create_cbp_board(current_user_id)
        if board is None:
            logger.warning("CBP-005: No KanbanBoard available — Kanban write-back skipped.")
            return []

        card_ids = []
        for req in requirements:
            priority = _MOSCOW_TO_PRIORITY.get(req.moscow_priority or "SHOULD", "medium")
            card = KanbanCard(
                title=req.name,
                description=req.acceptance_criteria or req.description,
                card_type="requirement",
                adm_phase_id=req_phase.id,
                board_id=board.id,
                status="backlog",
                priority=priority,
                implements_capabilities=[capability_id],
                created_by_id=current_user_id,
            )
            db.session.add(card)
            db.session.flush()  # populate card.id
            card_ids.append(card.id)

        db.session.commit()
        return card_ids

    def _get_or_create_cbp_board(self, current_user_id: int):
        """Return the first KanbanBoard or create a CBP default board."""
        from app.models.adm_kanban import KanbanBoard
        board = KanbanBoard.query.order_by(KanbanBoard.id).first()
        if board is not None:
            return board
        board = KanbanBoard(
            name="Capability-Based Planning",
            description="Auto-created by CapabilityRequirementGeneratorService",
            project_name="CBP",
            created_by_id=current_user_id,
        )
        db.session.add(board)
        db.session.flush()
        return board

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_apqc_context(self, solution_id: int) -> Dict[int, str]:
        """Return {apqc_process_id: name} for processes linked to this solution."""
        try:
            links = SolutionAPQCProcess.query.filter_by(solution_id=solution_id).all()
            result = {}
            for link in links:
                proc = getattr(link, "apqc_process", None)
                if proc:
                    result[proc.id] = proc.name
            return result
        except Exception:
            return {}

    def _build_prompt(
        self, cap: UnifiedCapability, apqc_context: Dict[int, str], count: int
    ) -> str:
        gap = (cap.target_maturity_level or 3) - (cap.current_maturity_level or 1)
        apqc_str = (
            ", ".join(f"{pid}: {name}" for pid, name in apqc_context.items())
            if apqc_context
            else "none linked"
        )
        system_part = _EARS_SYSTEM_PROMPT.format(count=count)
        user_part = _GENERATION_PROMPT.format(
            name=cap.name or "",
            domain=getattr(cap, 'business_domain', None) or cap.category or "General",
            current_maturity=cap.current_maturity_level or 1,
            target_maturity=cap.target_maturity_level or 3,
            gap=gap,
            apqc_processes=apqc_str,
            count=count,
        )
        return f"{system_part}\n\n{user_part}"

    def _fill_empty_ac(self, requirements: List[SolutionRequirement]) -> None:
        """Generate BDD acceptance criteria for any requirement where the LLM left it empty."""
        from app.services.llm_service import LLMService

        updated = False
        for req in requirements:
            if req.acceptance_criteria:
                continue
            try:
                prompt = (
                    f"You are a business analyst writing acceptance criteria.\n"
                    f"Requirement: {req.name}\n"
                    f"Description: {req.description or 'N/A'}\n"
                    f"Type: {req.requirement_type.value if req.requirement_type else 'functional'}\n"
                    f"Priority: {req.moscow_priority or 'MUST'}\n\n"
                    f"Write 3-5 acceptance criteria in BDD Gherkin format (GIVEN/WHEN/THEN). "
                    f"Be specific and testable. Return only the criteria, one per line."
                )
                req.acceptance_criteria = LLMService.generate_from_prompt(
                    prompt=prompt, use_cache=False
                )
                updated = True
            except Exception as exc:
                logger.warning("AC generation failed for req id=%s: %s", req.id, exc)
        if updated:
            try:
                db.session.commit()
            except Exception as exc:
                logger.warning("AC save failed: %s", exc)
                db.session.rollback()

    def _call_llm(self, prompt: str) -> str:
        """Call LLMService.generate_from_prompt; raise ValueError if unavailable."""
        from app.services.llm_service import LLMService
        try:
            return LLMService.generate_from_prompt(
                prompt=prompt,
                use_cache=False,
                expected_schema="array",
            )
        except Exception as exc:
            raise ValueError(
                f"LLM unavailable — check API configuration at /admin/api-settings. Detail: {exc}"
            ) from exc

    def _parse_response(self, raw: str) -> List[Dict]:
        """Extract JSON array from raw LLM response string."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning("No JSON array in LLM response: %s", text[:200])
            return []
        try:
            data = json.loads(text[start: end + 1])
            return [d for d in data if isinstance(d, dict) and d.get("name")]
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error in LLM response: %s", exc)
            return []

    def _persist_requirements(
        self,
        req_dicts: List[Dict],
        capability_id: int,
        solution_id: int,
        current_user_id: int,
        apqc_context: Dict[int, str],
    ) -> List[SolutionRequirement]:
        """Write SolutionRequirement rows to DB and return created instances."""
        created = []
        for rd in req_dicts:
            moscow = rd.get("moscow_priority", "SHOULD").upper()
            if moscow not in _VALID_MOSCOW:
                moscow = "SHOULD"
            phase = str(rd.get("togaf_phase", "REQ")).upper()
            if phase not in _VALID_PHASES:
                phase = "REQ"
            suggested_apqc = rd.get("suggested_apqc_process_id")
            apqc_id = int(suggested_apqc) if suggested_apqc and int(suggested_apqc) in apqc_context else None

            req = SolutionRequirement(
                solution_id=solution_id,
                problem_id=None,
                capability_id=capability_id,
                apqc_process_id=apqc_id,
                name=str(rd.get("name", ""))[:200],
                description=str(rd.get("description", "")),
                acceptance_criteria=str(rd.get("acceptance_criteria", "")),
                moscow_priority=moscow,
                togaf_phase=phase,
                ai_generated=True,
                ai_confidence=0.75,
            )
            db.session.add(req)
            created.append(req)

        db.session.commit()
        self._fill_empty_ac(created)
        return created
