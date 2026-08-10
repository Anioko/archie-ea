"""ADMPhaseGateService — enforces TOGAF ADM phase sequencing via ArchiMate element contracts.

Each TOGAF ADM phase has a gate contract: a list of required ArchiMate element types
that must exist in the workflow_instance_archimate_elements junction table (from a
prior phase run) before the next phase can start.

Phase chain:
    Prelim → A (Vision) → B (Business) → C (IS/Tech) → D (Tech) →
    E (Opportunities) → F (Migration) → G (Implementation) → H (Change Mgmt)

Default required outputs per phase (used when definition.phase_gate_contract is None):
    Phase A requires: nothing (entry point — seeded by Motivation layer)
    Phase B requires: Phase A output containing Driver or Goal elements
    Phase C requires: Phase B output
    Phase D requires: Phase C output
    Phase E requires: Phase D output
    Phase F requires: Phase E output
    Phase G requires: Phase F output
    Phase H requires: Phase G output
"""

from dataclasses import dataclass, field
from typing import List, Optional

from flask import g

from app import db


def _org_filter(prefix: str = "") -> tuple[str, dict]:
    """(' AND <prefix>organization_id = :org_id', {'org_id': id}) inside a tenant
    request, else ('', {}) for system/CLI callers with no ``g.current_org_id``.

    Mirrors ``app.services.architecture_rag_service._org_filter``. Raw SQL is not
    covered by the ORM tenant listener (``do_orm_execute`` only instruments
    ORM-mapped statements), so any raw query touching a tenant-scoped table —
    here, ``archimate_elements``, which carries ``organization_id`` via
    ``TenantMixin`` — must add the predicate explicitly or it aggregates every
    organization's rows.
    """
    org_id = getattr(g, "current_org_id", None)
    if org_id is None:
        return "", {}
    return f" AND {prefix}organization_id = :org_id", {"org_id": org_id}


# Default phase gate chain: phase → list of prior phases whose outputs are required
_DEFAULT_PHASE_CHAIN: dict[str, list[str]] = {
    "A": [],
    "B": ["A"],
    "C": ["B"],
    "D": ["C"],
    "E": ["D"],
    "F": ["E"],
    "G": ["F"],
    "H": ["G"],
}


@dataclass
class GateResult:
    """Result of an ADM phase gate check."""
    passed: bool
    phase: str
    missing_phases: List[str] = field(default_factory=list)
    missing_types: List[str] = field(default_factory=list)
    element_counts: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "phase": self.phase,
            "missing_phases": self.missing_phases,
            "missing_types": self.missing_types,
            "element_counts": self.element_counts,
            "message": self.message,
        }


class ADMPhaseGateService:
    """Checks whether a TOGAF ADM phase can be entered based on prior phase outputs."""

    def can_enter_phase(
        self,
        architecture_id: int,
        phase: str,
        phase_gate_contract: Optional[list] = None,
    ) -> GateResult:
        """Check if the given ADM phase can start for an architecture.

        Args:
            architecture_id: The architecture context (used to scope workflow instances).
            phase: The ADM phase code to enter (e.g. 'B', 'C').
            phase_gate_contract: Optional list of gate requirements from EAWorkflowDefinition.
                                  Format: [{"phase": "A", "required_types": ["Driver", "Goal"]}]
                                  If None, the default phase chain is used.

        Returns:
            GateResult with passed=True if all prerequisites are satisfied.
        """
        phase = phase.upper()
        if phase not in _DEFAULT_PHASE_CHAIN:
            return GateResult(
                passed=False,
                phase=phase,
                message=f"Unknown ADM phase: {phase}. Valid phases: {list(_DEFAULT_PHASE_CHAIN.keys())}",
            )

        # Phase A has no prerequisites — always allowed
        if phase == "A":
            return GateResult(passed=True, phase="A", message="Phase A is the entry point, no prerequisites.")

        # Build list of required prior phases
        if phase_gate_contract:
            required_phases = [c["phase"].upper() for c in phase_gate_contract]
        else:
            required_phases = _DEFAULT_PHASE_CHAIN[phase]

        if not required_phases:
            return GateResult(passed=True, phase=phase, message="No prior phases required.")

        missing_phases = []
        element_counts: dict[str, int] = {}

        for req_phase in required_phases:
            count = self._count_phase_outputs(architecture_id, req_phase)
            element_counts[req_phase] = count
            if count == 0:
                missing_phases.append(req_phase)

        # Check specific required types from contract if provided
        missing_types: list[str] = []
        if phase_gate_contract:
            for contract_entry in phase_gate_contract:
                req_phase = contract_entry["phase"].upper()
                for req_type in contract_entry.get("required_types", []):
                    if not self._has_type_in_phase(architecture_id, req_phase, req_type):
                        missing_types.append(f"{req_phase}:{req_type}")

        passed = not missing_phases and not missing_types
        if passed:
            msg = f"Phase {phase} gate passed. Prior phases present: {element_counts}"
        else:
            parts = []
            if missing_phases:
                parts.append(f"missing outputs from phases: {missing_phases}")
            if missing_types:
                parts.append(f"missing element types: {missing_types}")
            msg = f"Phase {phase} gate BLOCKED — " + "; ".join(parts)

        return GateResult(
            passed=passed,
            phase=phase,
            missing_phases=missing_phases,
            missing_types=missing_types,
            element_counts=element_counts,
            message=msg,
        )

    def _count_phase_outputs(self, architecture_id: Optional[int], phase_code: str) -> int:
        """Count ArchiMate elements produced in a given ADM phase for this architecture.

        ``ea_workflow_instances`` has no ``architecture_id`` column — the
        architecture context an instance runs against is only ever recorded in
        its JSON ``context`` (see ``EAWorkflowEngine.start_workflow``, which reads
        ``context.get("architecture_id")``), never as a table column. A query
        against ``i.architecture_id`` therefore fails with ``UndefinedColumn`` on
        every call, 500ing every caller. Filter through the JSON field instead;
        when no architecture is given (the phase-summary caller's default),
        count across all instances rather than filtering on nothing.

        Joins ``archimate_elements`` and applies ``_org_filter`` explicitly:
        neither ``ea_workflow_instances`` nor ``workflow_instance_archimate_elements``
        carries ``organization_id``, but ``archimate_elements`` does (it is
        ``TenantMixin``-scoped), and it's the only tenant-scoped table reachable
        from this junction. Without that predicate this raw query — which the
        ORM tenant listener does not touch — would aggregate every
        organization's ADM phase outputs and present them as the current org's.

        No exception handler: a swallowed query error would report ``0``, which
        ``can_enter_phase`` and ``get_phase_summary`` state as fact — "missing
        outputs from phases: [...]" — when nothing is actually known about the
        phase. Both callers run inside handlers that surface the failure, so the
        error is better reported than converted into a gate verdict.
        """
        org_clause, org_params = _org_filter("ae.")
        if architecture_id is None:
            row = db.session.execute(
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE w.adm_phase = :phase "
                    "AND w.element_role = 'output'" + org_clause
                ),
                {"phase": phase_code, **org_params},
            ).scalar()
        else:
            row = db.session.execute(
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE i.context->>'architecture_id' = :arch_id "
                    "AND w.adm_phase = :phase "
                    "AND w.element_role = 'output'" + org_clause
                ),
                {"arch_id": str(architecture_id), "phase": phase_code, **org_params},
            ).scalar()
        return int(row or 0)

    def _has_type_in_phase(self, architecture_id: Optional[int], phase_code: str, element_type: str) -> bool:
        """Check if a specific ArchiMate element type exists for a phase/architecture.

        See ``_count_phase_outputs`` for why this filters through the JSON
        ``context`` field rather than a nonexistent ``architecture_id`` column,
        and why ``_org_filter`` is applied explicitly against the joined
        ``archimate_elements`` row.

        No exception handler, for the same reason as ``_count_phase_outputs``:
        ``False`` here becomes a "missing element types" gate rejection that
        names a cause which was never established.
        """
        org_clause, org_params = _org_filter("ae.")
        if architecture_id is None:
            row = db.session.execute(
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE w.adm_phase = :phase "
                    "AND ae.type = :etype "
                    "AND w.element_role = 'output'" + org_clause
                ),
                {"phase": phase_code, "etype": element_type, **org_params},
            ).scalar()
        else:
            row = db.session.execute(
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE i.context->>'architecture_id' = :arch_id "
                    "AND w.adm_phase = :phase "
                    "AND ae.type = :etype "
                    "AND w.element_role = 'output'" + org_clause
                ),
                {"arch_id": str(architecture_id), "phase": phase_code, "etype": element_type, **org_params},
            ).scalar()
        return int(row or 0) > 0

    def get_phase_summary(self, architecture_id: Optional[int]) -> list[dict]:
        """Return a summary of all ADM phases A-H with element counts and gate status."""
        results = []
        for phase in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            count = self._count_phase_outputs(architecture_id, phase)
            gate = self.can_enter_phase(architecture_id, phase)
            results.append({
                "phase": phase,
                "element_count": count,
                "has_outputs": count > 0,
                "gate_passed": gate.passed,
                "gate_message": gate.message,
                "missing_phases": gate.missing_phases,
            })
        return results
