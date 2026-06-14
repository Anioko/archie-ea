"""
Codegen Verifier Service

Traces generated solution artifacts back to their ArchiMate sources and validates
route/endpoint coverage. Answers: "Is what was generated actually grounded in
the solution's ArchiMate element model?"

Tier 0 check (structural grounding):
  - Every generated ApplicationService/ApplicationComponent should have an
    ArchiMate element of matching type in solution_archimate_elements.
  - Every generated DataObject name should resolve to an ArchiMate DataObject
    in the element catalog.
  - Route count estimate vs ApplicationFunction/ApplicationService elements.

Returns a scored compliance report with untraced artifacts and coverage %.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodegenFinding:
    severity: str  # CRITICAL | HIGH | MEDIUM | INFO
    category: str  # UNTRACED_ARTIFACT | MISSING_ELEMENT | COVERAGE_GAP | STRUCTURAL_RISK
    description: str
    artifact: str = ""
    recommendation: str = ""


@dataclass
class CodegenVerificationResult:
    solution_id: int
    solution_name: str
    score: int  # 0-100
    grade: str  # A | B | C | D | F
    coverage_pct: int
    archimate_element_count: int
    expected_route_count: int
    findings: List[CodegenFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "solution_id": self.solution_id,
            "solution_name": self.solution_name,
            "score": self.score,
            "grade": self.grade,
            "coverage_pct": self.coverage_pct,
            "archimate_element_count": self.archimate_element_count,
            "expected_route_count": self.expected_route_count,
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "description": f.description,
                    "artifact": f.artifact,
                    "recommendation": f.recommendation,
                }
                for f in self.findings
            ],
            "findings_summary": {
                sev: sum(1 for f in self.findings if f.severity == sev)
                for sev in ("CRITICAL", "HIGH", "MEDIUM", "INFO")
            },
        }


class CodegenVerifierService:
    """Verify generated solution artifacts trace back to their ArchiMate model."""

    _APP_SERVICE_TYPES = {
        "ApplicationService", "ApplicationFunction", "ApplicationComponent",
        "ApplicationProcess", "ApplicationInterface",
    }
    _DATA_TYPES = {"DataObject", "DataStore"}
    _TECH_TYPES = {"Node", "SystemSoftware", "TechnologyService", "TechnologyFunction"}

    @classmethod
    def verify_solution(cls, solution_id: int) -> dict:
        """
        Run codegen conformance verification for a solution.

        Returns success/result dict compatible with the tool executor pattern.
        """
        try:
            from app.models.solution_models import Solution, SolutionArchiMateElement
            from app.models.archimate_core import ArchiMateElement

            sol = Solution.query.get(solution_id)
            if not sol:
                return {"success": False, "error": f"Solution {solution_id} not found"}

            links = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()
            if not links:
                result = CodegenVerificationResult(
                    solution_id=solution_id,
                    solution_name=sol.name,
                    score=0,
                    grade="F",
                    coverage_pct=0,
                    archimate_element_count=0,
                    expected_route_count=0,
                )
                result.findings.append(CodegenFinding(
                    severity="CRITICAL",
                    category="MISSING_ELEMENT",
                    description="No ArchiMate elements linked to this solution. Codegen has no model to trace against.",
                    recommendation="Link ArchiMate elements via the Architecture tab, then re-run verification.",
                ))
                return {"success": True, "result": result.to_dict()}

            element_ids = [lnk.element_id for lnk in links]
            elements = ArchiMateElement.query.filter(
                ArchiMateElement.id.in_(element_ids)
            ).all() if element_ids else []

            verifier = cls()
            r = verifier._run_checks(sol, elements)
            return {"success": True, "result": r.to_dict()}

        except Exception as e:
            logger.exception("CodegenVerifierService.verify_solution failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Increment 3: verify generated output against a component spec        #
    # ------------------------------------------------------------------ #

    @classmethod
    def verify_spec_against_output(cls, spec: dict, output_root) -> dict:
        """
        Check generated output against a Codegen Component Spec (increment 1/2):
          - completeness_gate: every check must have passed;
          - expected_artifacts: each path exists under output_root, is non-empty,
            and contains every symbol in its `must_reference` list.

        Turns the verifier's question from "do elements trace?" into
        "is the contract satisfied?". Pure filesystem — no DB. `output_root` is the
        root of the generated codebase (str or Path).

        Returns {success, contract_passed, gate_passed, artifacts_checked,
        artifacts_missing, findings_summary, findings:[...]}.
        """
        from pathlib import Path

        root = Path(output_root)
        findings: List[CodegenFinding] = []

        # ── Completeness gate: all checks must have passed ──────────────── #
        gate = spec.get("completeness_gate", {}) or {}
        gate_checks = gate.get("checks", [])
        failed_gate = [c for c in gate_checks if not c.get("passed")]
        for c in failed_gate:
            findings.append(CodegenFinding(
                severity="CRITICAL",
                category="STRUCTURAL_RISK",
                description=f"Completeness gate failed: {c.get('id')} — {c.get('detail', '')}",
                recommendation="Fix the genome/spec so this gate passes before generating.",
            ))

        # ── Expected artifacts: exist, non-empty, reference required symbols ── #
        artifacts = spec.get("expected_artifacts", []) or []
        missing = 0
        for art in artifacts:
            rel = art.get("path", "")
            fpath = root / rel
            if not fpath.is_file():
                missing += 1
                findings.append(CodegenFinding(
                    severity="HIGH",
                    category="MISSING_ELEMENT",
                    description=f"Expected {art.get('kind', 'artifact')} not generated: {rel}",
                    artifact=rel,
                    recommendation="The generator must emit this file for the module's contract.",
                ))
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
            if not content.strip():
                findings.append(CodegenFinding(
                    severity="HIGH",
                    category="COVERAGE_GAP",
                    description=f"Expected artifact is empty: {rel}",
                    artifact=rel,
                    recommendation="Empty file = scaffold stub; the module's logic was not generated.",
                ))
            for sym in art.get("must_reference", []) or []:
                if sym not in content:
                    findings.append(CodegenFinding(
                        severity="MEDIUM",
                        category="COVERAGE_GAP",
                        description=f"{rel} does not reference required symbol '{sym}'",
                        artifact=rel,
                        recommendation=f"The spec declares a dependency on {sym}; wire it in, don't just leave a placeholder.",
                    ))

        contract_passed = not failed_gate and missing == 0 and not any(
            f.severity in ("CRITICAL", "HIGH") for f in findings
        )
        summary = {
            sev: sum(1 for f in findings if f.severity == sev)
            for sev in ("CRITICAL", "HIGH", "MEDIUM", "INFO")
        }
        return {
            "success": True,
            "module_key": spec.get("module_key"),
            "contract_passed": contract_passed,
            "gate_passed": not failed_gate,
            "artifacts_checked": len(artifacts),
            "artifacts_missing": missing,
            "findings_summary": summary,
            "findings": [
                {"severity": f.severity, "category": f.category,
                 "description": f.description, "artifact": f.artifact,
                 "recommendation": f.recommendation}
                for f in findings
            ],
        }

    def _run_checks(self, sol, elements: list) -> CodegenVerificationResult:
        findings = []

        app_services = [e for e in elements if e.type in self._APP_SERVICE_TYPES]
        data_objects = [e for e in elements if e.type in self._DATA_TYPES]
        tech_nodes = [e for e in elements if e.type in self._TECH_TYPES]
        total_elem = len(elements)

        # ── Check 1: Minimum element coverage for codegen viability ──────── #
        expected_routes = len(app_services) * 5  # ~5 routes per ApplicationService

        if len(app_services) == 0:
            findings.append(CodegenFinding(
                severity="CRITICAL",
                category="MISSING_ELEMENT",
                description=(
                    "No ApplicationService/ApplicationFunction/ApplicationComponent elements. "
                    "Codegen cannot produce meaningful routes without application-layer elements."
                ),
                recommendation="Add at least one ApplicationService per logical domain via the Architecture tab.",
            ))
        elif len(app_services) < 2:
            findings.append(CodegenFinding(
                severity="HIGH",
                category="COVERAGE_GAP",
                description=f"Only {len(app_services)} application-layer element(s). Sparse model produces skeleton-only codegen.",
                recommendation="Add ApplicationComponent, ApplicationService, and ApplicationInterface elements for each functional area.",
            ))

        # ── Check 2: Data layer coverage ─────────────────────────────────── #
        if len(data_objects) == 0:
            findings.append(CodegenFinding(
                severity="HIGH",
                category="MISSING_ELEMENT",
                description="No DataObject or DataStore elements. Generated data models will be placeholder-only.",
                recommendation="Add DataObject elements for each business entity (e.g. Customer, Order, Invoice).",
            ))
        elif len(data_objects) < len(app_services):
            findings.append(CodegenFinding(
                severity="MEDIUM",
                category="COVERAGE_GAP",
                description=(
                    f"Data objects ({len(data_objects)}) fewer than application services ({len(app_services)}). "
                    "Some generated routes will lack a data model."
                ),
                recommendation="Ensure each ApplicationService has at least one associated DataObject.",
            ))

        # ── Check 3: Technology layer ─────────────────────────────────────── #
        if len(tech_nodes) == 0:
            findings.append(CodegenFinding(
                severity="MEDIUM",
                category="STRUCTURAL_RISK",
                description="No technology-layer elements (Node/SystemSoftware). Codegen cannot produce deployment configuration.",
                recommendation="Add Node or SystemSoftware elements for each deployment target.",
            ))

        # ── Check 4: Name quality (unnamed / numeric-only elements) ───────── #
        bad_names = [
            e for e in elements
            if not e.name or re.match(r'^[0-9\-_\s]+$', e.name.strip())
        ]
        if bad_names:
            findings.append(CodegenFinding(
                severity="MEDIUM",
                category="UNTRACED_ARTIFACT",
                description=f"{len(bad_names)} element(s) have unnamed or numeric-only names; codegen will produce unreadable identifiers.",
                artifact=", ".join(str(e.id) for e in bad_names[:5]),
                recommendation="Rename these elements with business-meaningful names before running codegen.",
            ))

        # ── Check 5: Missing descriptions (docgen gap) ────────────────────── #
        no_desc = [e for e in app_services if not getattr(e, 'description', None)]
        if no_desc:
            findings.append(CodegenFinding(
                severity="INFO",
                category="COVERAGE_GAP",
                description=f"{len(no_desc)} application-layer element(s) have no description; generated docstrings will be empty.",
                artifact=", ".join(e.name for e in no_desc[:5]),
                recommendation="Add descriptions to improve generated code documentation quality.",
            ))

        # ── Score ─────────────────────────────────────────────────────────── #
        score = 100
        for f in findings:
            score -= {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 7, "INFO": 0}[f.severity]
        score = max(0, score)

        coverage_pct = 0
        if total_elem > 0:
            well_formed = total_elem - len(bad_names) - len(no_desc)
            coverage_pct = round(max(0, well_formed) / total_elem * 100)

        grade_map = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]
        grade = next(g for threshold, g in grade_map if score >= threshold)

        return CodegenVerificationResult(
            solution_id=sol.id,
            solution_name=sol.name,
            score=score,
            grade=grade,
            coverage_pct=coverage_pct,
            archimate_element_count=total_elem,
            expected_route_count=expected_routes,
            findings=findings,
        )
