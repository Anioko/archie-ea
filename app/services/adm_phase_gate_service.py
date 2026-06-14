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

from app import db


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

    def _count_phase_outputs(self, architecture_id: int, phase_code: str) -> int:
        """Count ArchiMate elements produced in a given ADM phase for this architecture."""
        try:
            row = db.session.execute(  # tenant-filtered: scoped via architecture_id FK
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "WHERE i.architecture_id = :arch_id "
                    "AND w.adm_phase = :phase "
                    "AND w.element_role = 'output'"
                ),
                {"arch_id": architecture_id, "phase": phase_code},
            ).scalar()
            return int(row or 0)
        except Exception:
            return 0

    def _has_type_in_phase(self, architecture_id: int, phase_code: str, element_type: str) -> bool:
        """Check if a specific ArchiMate element type exists for a phase/architecture."""
        try:
            row = db.session.execute(  # tenant-filtered: scoped via architecture_id FK
                db.text(
                    "SELECT COUNT(*) FROM workflow_instance_archimate_elements w "
                    "JOIN ea_workflow_instances i ON i.id = w.instance_id "
                    "JOIN archimate_elements ae ON ae.id = w.element_id "
                    "WHERE i.architecture_id = :arch_id "
                    "AND w.adm_phase = :phase "
                    "AND ae.type = :etype "
                    "AND w.element_role = 'output'"
                ),
                {"arch_id": architecture_id, "phase": phase_code, "etype": element_type},
            ).scalar()
            return int(row or 0) > 0
        except Exception:
            return False

    def get_phase_summary(self, architecture_id: int) -> list[dict]:
        """Return a summary of all ADM phases A-H with element counts and gate status."""
        results = []
        prev_result = None
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
            prev_result = gate
        return results
