"""
SAP Clean-Core Conformance Validator.

Validates a solution's architecture against SAP RISE clean-core extension model.
Returns structured findings with severity, violated rule, evidence, and remediation.

SAP Extension Model tiers (SAP published model):
  Tier 0: SAP Standard           — use as-is, no modification
  Tier 1: In-App Extensibility   — custom fields, BAdIs, ABAP Cloud RAP (COMPLIANT)
  Tier 2: Side-by-Side on BTP    — BTP services, Integration Suite, Event Mesh (COMPLIANT)
  Tier 3: Classic Extensibility  — user exits, BADIs modifying core (NON-COMPLIANT)
  Tier 4: Modifications          — CMOD/SMOD, direct SAP namespace changes (NON-COMPLIANT)

Score: 0–100 (100 = fully clean-core compliant)
  80–100 → CLEAN CORE COMPLIANT (green)
  50–79  → AT RISK              (amber) — remediation plan required
  0–49   → NON-COMPLIANT        (red)   — upgrade blocker
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Keyword lists ────────────────────────────────────────────────────────────

_SAP_APP_KEYWORDS = {
    "sap", "s/4hana", "s4hana", "s4", "r/3", "r3", "fiori", "hana",
    "rise with sap", "sap ecc", "sap erp", "sap ariba", "sap successfactors",
    "sap bw", "sap bpc", "sap apo", "sap scm", "sap tm", "sap wm",
    "sap mm", "sap sd", "sap fi", "sap co", "sap pp", "sap hr", "sap pm",
    "sap qm", "sap cs", "sap ps", "sap re", "sap is-u", "sap crm",
    "sap central finance", "sap group reporting",
}

_CLASSIC_INTEGRATION_KEYWORDS = {
    "rfc call", "remote function call", "bapi", "idoc", "trfc", "qrfc",
    "ale integration", "edi idoc", "file-based idoc", "intermediate document",
    "direct rfc", "synchronous rfc", "asynchronous rfc",
}

_MODIFICATION_KEYWORDS = {
    "cmod", "smod", "user exit", "enhancement spot modification", "include program",
    "modification assistant", "direct table access", "direct database select",
    "z-table modification", "custom include", "oss note override",
    "kernel patch", "custom namespace sap", "se38 modification",
}

_BTP_KEYWORDS = {
    "sap btp", "business technology platform", "integration suite",
    "sap integration suite", "event mesh", "enterprise event enablement",
    "sap build", "build work zone", "sap launchpad", "btp subaccount",
    "cloud connector", "api hub", "sap api business hub",
}

_CLEAN_INTEGRATION_KEYWORDS = {
    "odata", "odata v4", "rest api", "soap api", "api hub", "stable api",
    "integration suite", "event-driven", "enterprise event enablement",
    "asynchronous event", "sap api gateway",
}

# ─── Finding severities ────────────────────────────────────────────────────────

SEVERITY_DEDUCTIONS = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 5, "INFO": 0}

# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CleanCoreFinding:
    severity: str            # CRITICAL | HIGH | MEDIUM | INFO
    rule: str                # short rule name
    description: str         # what was found
    evidence: str            # specific element/pattern names or counts
    remediation: str         # concrete fix
    extension_tier: int      # 0–4 (SAP tier that was violated)


@dataclass
class CleanCoreResult:
    solution_id: int
    solution_name: str
    score: int               # 0–100
    compliance_tier: str     # CLEAN_CORE_COMPLIANT | AT_RISK | NON_COMPLIANT
    findings: list = field(default_factory=list)
    sap_footprint: dict = field(default_factory=dict)
    extension_model: dict = field(default_factory=dict)
    upgrade_risk: str = "UNKNOWN"
    summary: str = ""


# ─── Service ──────────────────────────────────────────────────────────────────

class SAPCleanCoreService:

    # ── Public entry point ────────────────────────────────────────────────────

    @classmethod
    def validate_solution(cls, solution_id: int) -> dict:
        """
        Run full clean-core validation for a solution.
        Returns a serialisable dict of CleanCoreResult.
        """
        try:
            from app.models.solution_models import Solution
            sol = Solution.query.get(solution_id)
            if not sol:
                return {"success": False, "error": f"Solution {solution_id} not found"}
            result = cls._run(sol)
            return {"success": True, "result": cls._serialise(result)}
        except Exception as exc:
            logger.exception("SAPCleanCoreService.validate_solution failed")
            return {"success": False, "error": str(exc)}

    @classmethod
    def quick_scan_portfolio(cls, limit: int = 20) -> dict:
        """
        Lightweight scan across solutions that contain SAP elements.
        Returns a summary list ordered by compliance score ascending.
        """
        try:
            from app.models.solution_models import Solution
            solutions = Solution.query.filter(
                Solution.name.isnot(None)
            ).limit(limit * 3).all()

            results = []
            for sol in solutions:
                footprint = cls._detect_sap_footprint(sol)
                if footprint["sap_app_count"] + footprint["sap_element_count"] == 0:
                    continue
                result = cls._run(sol)
                results.append({
                    "solution_id": sol.id,
                    "solution_name": sol.name,
                    "score": result.score,
                    "compliance_tier": result.compliance_tier,
                    "critical_count": sum(1 for f in result.findings if f.severity == "CRITICAL"),
                    "high_count": sum(1 for f in result.findings if f.severity == "HIGH"),
                })
                if len(results) >= limit:
                    break

            results.sort(key=lambda r: r["score"])
            return {
                "success": True,
                "solutions_scanned": len(results),
                "non_compliant": sum(1 for r in results if r["compliance_tier"] == "NON_COMPLIANT"),
                "at_risk": sum(1 for r in results if r["compliance_tier"] == "AT_RISK"),
                "compliant": sum(1 for r in results if r["compliance_tier"] == "CLEAN_CORE_COMPLIANT"),
                "results": results,
            }
        except Exception as exc:
            logger.exception("SAPCleanCoreService.quick_scan_portfolio failed")
            return {"success": False, "error": str(exc)}

    # ── Core validation ───────────────────────────────────────────────────────

    @classmethod
    def _run(cls, solution) -> CleanCoreResult:
        findings: list[CleanCoreFinding] = []

        footprint = cls._detect_sap_footprint(solution)
        btp_present = footprint["btp_element_count"] > 0 or footprint["btp_pattern_count"] > 0

        # Run all checks
        findings += cls._check_modification_signals(solution, footprint)
        findings += cls._check_classic_integration(solution, footprint)
        findings += cls._check_missing_btp_layer(solution, footprint, btp_present)
        findings += cls._check_blocked_integration_patterns(solution)
        findings += cls._check_direct_relationships(solution, footprint)
        findings += cls._check_upgrade_risk_signals(solution, footprint)
        findings += cls._check_documentation_gaps(solution, footprint)

        score = cls._compute_score(findings)
        compliance_tier = cls._score_to_tier(score)
        upgrade_risk = cls._assess_upgrade_risk(findings, footprint)
        extension_model = cls._build_extension_model(footprint, findings)

        result = CleanCoreResult(
            solution_id=solution.id,
            solution_name=solution.name,
            score=score,
            compliance_tier=compliance_tier,
            findings=findings,
            sap_footprint=footprint,
            extension_model=extension_model,
            upgrade_risk=upgrade_risk,
        )
        result.summary = cls._build_summary(result)
        return result

    # ── SAP footprint detection ────────────────────────────────────────────────

    @classmethod
    def _detect_sap_footprint(cls, solution) -> dict:
        from app import db
        from sqlalchemy import text

        sap_apps, sap_elements, btp_elements, classic_patterns, clean_patterns = [], [], [], [], []

        # Applications linked to solution
        try:
            from app.models.solution_models import SolutionApplication
            from app.models.application_portfolio import ApplicationComponent
            app_ids = [
                row.application_id
                for row in SolutionApplication.query.filter_by(solution_id=solution.id).all()
            ]
            if app_ids:
                apps = ApplicationComponent.query.filter(
                    ApplicationComponent.id.in_(app_ids)
                ).all()
                for app in apps:
                    name_lower = (app.name or "").lower()
                    desc_lower = (app.description or "").lower()
                    combined = name_lower + " " + desc_lower
                    if cls._matches_keywords(combined, _SAP_APP_KEYWORDS):
                        sap_apps.append({
                            "id": app.id,
                            "name": app.name,
                            "lifecycle": app.lifecycle_status or "unknown",
                            "deployment": getattr(app, "deployment_model", None) or "unknown",
                        })
                    if cls._matches_keywords(combined, _BTP_KEYWORDS):
                        btp_elements.append({"id": app.id, "name": app.name, "source": "application"})
        except Exception as exc:
            logger.debug("footprint: app scan failed: %s", exc)

        # ArchiMate elements linked to solution
        try:
            from app.models.solution_models import SolutionArchiMateElement
            from app.models.archimate_core import ArchiMateElement
            saes = SolutionArchiMateElement.query.filter_by(solution_id=solution.id).all()
            element_ids = [sae.element_id for sae in saes if sae.element_id]
            if element_ids:
                elements = ArchiMateElement.query.filter(
                    ArchiMateElement.id.in_(element_ids)
                ).all()
                for el in elements:
                    name_lower = (el.name or "").lower()
                    desc_lower = (getattr(el, "description", None) or "").lower()
                    combined = name_lower + " " + desc_lower
                    if cls._matches_keywords(combined, _SAP_APP_KEYWORDS):
                        sap_elements.append({
                            "id": el.id,
                            "name": el.name,
                            "type": el.type,
                            "layer": el.layer,
                        })
                    if cls._matches_keywords(combined, _BTP_KEYWORDS):
                        btp_elements.append({"id": el.id, "name": el.name, "source": "element"})
                    if cls._matches_keywords(combined, _CLASSIC_INTEGRATION_KEYWORDS):
                        classic_patterns.append({"id": el.id, "name": el.name, "signal": "classic_integration_keyword"})
                    if cls._matches_keywords(combined, _CLASSIC_INTEGRATION_KEYWORDS | _MODIFICATION_KEYWORDS):
                        pass  # handled below
        except Exception as exc:
            logger.debug("footprint: element scan failed: %s", exc)

        # Integration patterns on this solution
        try:
            from app.models.solution_models import SolutionIntegrationPattern
            from app.models.integration_pattern import IntegrationPattern
            sip_ids = [
                r.pattern_id
                for r in SolutionIntegrationPattern.query.filter_by(solution_id=solution.id).all()
            ]
            if sip_ids:
                patterns = IntegrationPattern.query.filter(
                    IntegrationPattern.id.in_(sip_ids)
                ).all()
                for p in patterns:
                    combined = ((p.name or "") + " " + (p.description or "")).lower()
                    if p.approval_status == "blocked" or cls._matches_keywords(combined, _CLASSIC_INTEGRATION_KEYWORDS):
                        classic_patterns.append({
                            "id": p.id,
                            "name": p.name,
                            "status": p.approval_status,
                            "signal": "blocked_pattern",
                        })
                    elif cls._matches_keywords(combined, _CLEAN_INTEGRATION_KEYWORDS):
                        clean_patterns.append({"id": p.id, "name": p.name})
                    if cls._matches_keywords(combined, _BTP_KEYWORDS):
                        btp_elements.append({"id": p.id, "name": p.name, "source": "pattern"})
        except Exception as exc:
            logger.debug("footprint: pattern scan failed: %s", exc)

        # Also scan solution name/description for SAP signals
        sol_text = ((solution.name or "") + " " + (getattr(solution, "description", None) or "")).lower()
        sol_has_sap = cls._matches_keywords(sol_text, _SAP_APP_KEYWORDS)

        return {
            "sap_app_count": len(sap_apps),
            "sap_apps": sap_apps,
            "sap_element_count": len(sap_elements),
            "sap_elements": sap_elements,
            "btp_element_count": len(btp_elements),
            "btp_elements": btp_elements,
            "classic_pattern_count": len(classic_patterns),
            "classic_patterns": classic_patterns,
            "clean_pattern_count": len(clean_patterns),
            "sol_has_sap_signal": sol_has_sap,
            "btp_pattern_count": sum(1 for b in btp_elements if b.get("source") == "pattern"),
        }

    # ── Individual checks ─────────────────────────────────────────────────────

    @classmethod
    def _check_modification_signals(cls, solution, footprint: dict) -> list:
        findings = []
        all_elements = footprint["sap_elements"]
        # Scan ArchiMate element names/descriptions for modification keywords
        try:
            from app.models.solution_models import SolutionArchiMateElement
            from app.models.archimate_core import ArchiMateElement
            saes = SolutionArchiMateElement.query.filter_by(solution_id=solution.id).all()
            ids = [s.element_id for s in saes if s.element_id]
            if ids:
                elements = ArchiMateElement.query.filter(ArchiMateElement.id.in_(ids)).all()
                for el in elements:
                    combined = ((el.name or "") + " " + (getattr(el, "description", None) or "")).lower()
                    hits = [kw for kw in _MODIFICATION_KEYWORDS if kw in combined]
                    if hits:
                        findings.append(CleanCoreFinding(
                            severity="CRITICAL",
                            rule="SAP_MODIFICATION_DETECTED",
                            description=(
                                f"Element '{el.name}' contains modification signals: {', '.join(hits)}. "
                                "Direct SAP object modifications (CMOD/SMOD/user exits) are Tier 4 "
                                "violations — they break on every SAP upgrade and cannot be shipped on RISE."
                            ),
                            evidence=f"Element ID {el.id}: {el.name} [{el.type}]",
                            remediation=(
                                "Migrate to BAdI (ABAP Cloud) or ABAP RAP in-app extensibility (Tier 1), "
                                "or move the logic to a BTP side-by-side extension (Tier 2). "
                                "Remove any CMOD/SMOD entries from the transport request."
                            ),
                            extension_tier=4,
                        ))
        except Exception as exc:
            logger.debug("_check_modification_signals failed: %s", exc)
        return findings

    @classmethod
    def _check_classic_integration(cls, solution, footprint: dict) -> list:
        findings = []
        classic = footprint["classic_patterns"]
        if not classic:
            return findings

        # Group by signal type
        blocked = [p for p in classic if p.get("status") == "blocked"]
        keyword_hits = [p for p in classic if p.get("signal") == "classic_integration_keyword"]

        if blocked:
            names = ", ".join(p["name"] for p in blocked[:5])
            findings.append(CleanCoreFinding(
                severity="HIGH",
                rule="BLOCKED_INTEGRATION_PATTERN",
                description=(
                    f"{len(blocked)} blocked integration pattern(s) linked to this solution. "
                    "Blocked patterns typically represent RFC/BAPI or direct IDoc integrations "
                    "that bypass the SAP Integration Suite API layer."
                ),
                evidence=f"Blocked patterns: {names}",
                remediation=(
                    "Replace with OData v4 or REST APIs via SAP Integration Suite. "
                    "Use Enterprise Event Enablement for async scenarios. "
                    "See the integration pattern catalog at /architecture/integration-patterns."
                ),
                extension_tier=3,
            ))

        if keyword_hits:
            names = ", ".join(p["name"] for p in keyword_hits[:5])
            findings.append(CleanCoreFinding(
                severity="HIGH",
                rule="CLASSIC_INTEGRATION_SIGNAL",
                description=(
                    f"{len(keyword_hits)} element(s) reference classic SAP integration methods "
                    "(RFC/BAPI/IDoc). These are Tier 3 patterns incompatible with clean-core RISE contracts."
                ),
                evidence=f"Elements: {names}",
                remediation=(
                    "Remodel using SAP API Business Hub stable APIs. "
                    "For process integration use SAP Integration Suite (CPI). "
                    "For events use SAP Event Mesh or Enterprise Event Enablement."
                ),
                extension_tier=3,
            ))
        return findings

    @classmethod
    def _check_missing_btp_layer(cls, solution, footprint: dict, btp_present: bool) -> list:
        findings = []
        has_sap = (footprint["sap_app_count"] + footprint["sap_element_count"]) > 0
        has_custom = footprint["classic_pattern_count"] > 0

        if has_sap and not btp_present:
            sap_names = [a["name"] for a in footprint["sap_apps"][:3]]
            findings.append(CleanCoreFinding(
                severity="HIGH",
                rule="MISSING_BTP_MEDIATION_LAYER",
                description=(
                    "Solution includes SAP components but no SAP BTP / Integration Suite / "
                    "Event Mesh element is modelled. "
                    "Without BTP mediation, custom extensions likely bypass the clean-core boundary."
                ),
                evidence=(
                    f"SAP apps: {', '.join(sap_names) or 'detected via elements'}. "
                    "BTP elements in model: 0."
                ),
                remediation=(
                    "Add an ApplicationComponent or TechnologyService element for "
                    "SAP Integration Suite or SAP BTP Subaccount. "
                    "Route all custom-to-SAP interactions through it. "
                    "For real-time extensions add SAP Build Work Zone or BTP side-by-side app element."
                ),
                extension_tier=2,
            ))
        return findings

    @classmethod
    def _check_blocked_integration_patterns(cls, solution) -> list:
        """Cross-check all integration patterns on this solution vs approval_status."""
        findings = []
        try:
            from app.models.solution_models import SolutionIntegrationPattern
            from app.models.integration_pattern import IntegrationPattern
            rows = SolutionIntegrationPattern.query.filter_by(solution_id=solution.id).all()
            if not rows:
                return []
            ids = [r.pattern_id for r in rows]
            blocked = IntegrationPattern.query.filter(
                IntegrationPattern.id.in_(ids),
                IntegrationPattern.approval_status == "blocked",
            ).all()
            # Already reported in _check_classic_integration; avoid double-counting
        except Exception:
            pass
        return findings

    @classmethod
    def _check_direct_relationships(cls, solution, footprint: dict) -> list:
        """
        Detect ArchiMate ServingRelationships where a custom component
        directly calls a SAP core element with no BTP/API mediator in between.
        """
        findings = []
        if not footprint["sap_elements"]:
            return findings

        try:
            from app.models.archimate_core import ArchiMateRelationship
            from app.models.solution_models import SolutionArchiMateElement
            from app.models.archimate_core import ArchiMateElement

            sap_ids = {e["id"] for e in footprint["sap_elements"]}
            btp_ids = {b["id"] for b in footprint["btp_elements"] if b.get("source") == "element"}

            # All element IDs in this solution
            saes = SolutionArchiMateElement.query.filter_by(solution_id=solution.id).all()
            solution_element_ids = {sae.element_id for sae in saes if sae.element_id}
            non_sap_ids = solution_element_ids - sap_ids - btp_ids

            if not non_sap_ids:
                return findings

            # Find direct ServingRelationship or AssociationRelationship from non-SAP to SAP
            direct_rels = ArchiMateRelationship.query.filter(
                ArchiMateRelationship.source_element_id.in_(non_sap_ids),
                ArchiMateRelationship.target_element_id.in_(sap_ids),
                ArchiMateRelationship.relationship_type.in_(
                    ["ServingRelationship", "serving", "AssociationRelationship", "association",
                     "TriggeringRelationship", "triggering"]
                ),
            ).limit(10).all()

            if direct_rels:
                source_ids = {r.source_element_id for r in direct_rels}
                sources = ArchiMateElement.query.filter(
                    ArchiMateElement.id.in_(source_ids)
                ).all()
                source_names = [e.name for e in sources]
                target_ids = {r.target_element_id for r in direct_rels}
                targets = ArchiMateElement.query.filter(
                    ArchiMateElement.id.in_(target_ids)
                ).all()
                target_names = [e.name for e in targets]

                findings.append(CleanCoreFinding(
                    severity="HIGH",
                    rule="DIRECT_SAP_COUPLING",
                    description=(
                        f"{len(direct_rels)} direct relationship(s) from custom components "
                        "to SAP core elements without BTP/API mediator in the model. "
                        "Direct coupling creates upgrade dependency and violates clean-core isolation."
                    ),
                    evidence=(
                        f"Custom sources: {', '.join(source_names[:3])}. "
                        f"SAP targets: {', '.join(target_names[:3])}."
                    ),
                    remediation=(
                        "Insert SAP Integration Suite (CPI) or BTP API Gateway as mediator element. "
                        "Reroute ServingRelationships: custom → Integration Suite → SAP. "
                        "This achieves decoupling and allows SAP core upgrades without touching custom code."
                    ),
                    extension_tier=3,
                ))
        except Exception as exc:
            logger.debug("_check_direct_relationships failed: %s", exc)
        return findings

    @classmethod
    def _check_upgrade_risk_signals(cls, solution, footprint: dict) -> list:
        """Flag lifecycle-expired SAP systems (ECC, R/3) as upgrade blockers."""
        findings = []
        legacy_keywords = {"sap ecc", "sap r/3", "r3", "ecc 6", "ecc6", "sap erp 6"}
        legacy_apps = [
            a for a in footprint["sap_apps"]
            if cls._matches_keywords((a["name"] or "").lower(), legacy_keywords)
        ]
        if legacy_apps:
            names = ", ".join(a["name"] for a in legacy_apps[:5])
            findings.append(CleanCoreFinding(
                severity="CRITICAL",
                rule="LEGACY_SAP_SYSTEM",
                description=(
                    f"{len(legacy_apps)} legacy SAP system(s) detected (ECC/R/3). "
                    "SAP ECC mainstream maintenance ended 2027 (extended to 2030 with surcharge). "
                    "These are upgrade-blocking systems that require a RISE migration plan."
                ),
                evidence=f"Legacy systems: {names}",
                remediation=(
                    "Initiate RISE with SAP conversion or new implementation. "
                    "Commission a clean-core assessment (ABAP custom code via SAP Custom Code Migration App). "
                    "Define target clean-core architecture in this solution before migration commences."
                ),
                extension_tier=4,
            ))

        # On-premise SAP with no cloud signal
        onprem_sap = [
            a for a in footprint["sap_apps"]
            if a.get("deployment") in ("on-premise", "on_premise", "on_prem", "onpremise", "unknown")
            and a not in legacy_apps
        ]
        if onprem_sap and not footprint["btp_element_count"]:
            names = ", ".join(a["name"] for a in onprem_sap[:3])
            findings.append(CleanCoreFinding(
                severity="MEDIUM",
                rule="ON_PREMISE_SAP_NO_CLOUD_PATH",
                description=(
                    f"{len(onprem_sap)} on-premise SAP application(s) with no cloud migration "
                    "path modelled. RISE with SAP requires cloud deployment."
                ),
                evidence=f"On-premise SAP: {names}",
                remediation=(
                    "Model the target deployment as RISE/cloud. "
                    "Add a SolutionPlateau (TOGAF) for the migration timeline. "
                    "Confirm RISE contract scope covers these systems."
                ),
                extension_tier=3,
            ))
        return findings

    @classmethod
    def _check_documentation_gaps(cls, solution, footprint: dict) -> list:
        """Advisory findings for missing clean-core documentation."""
        findings = []
        has_sap = (footprint["sap_app_count"] + footprint["sap_element_count"]) > 0
        if not has_sap:
            return findings

        # Check for missing description/rationale
        desc = getattr(solution, "description", None) or ""
        if len(desc.strip()) < 50:
            findings.append(CleanCoreFinding(
                severity="INFO",
                rule="MISSING_CLEAN_CORE_RATIONALE",
                description=(
                    "Solution has SAP components but no architecture rationale documented. "
                    "ARB reviewers require a clean-core posture statement before approval."
                ),
                evidence=f"Solution description length: {len(desc.strip())} chars",
                remediation=(
                    "Add a description stating the clean-core extension tier for each "
                    "customisation (Tier 1 in-app, Tier 2 side-by-side, or standard). "
                    "Reference the RISE contract scope."
                ),
                extension_tier=0,
            ))

        # Check for missing ARB submission
        try:
            from app.models.solutions_strategic import ARBReviewItem
            submitted = ARBReviewItem.query.filter_by(solution_id=solution.id).count() > 0
        except Exception:
            try:
                from app.models.architecture_review_board import ARBReviewItem
                submitted = ARBReviewItem.query.filter_by(solution_id=solution.id).count() > 0
            except Exception:
                submitted = False

        if not submitted:
            findings.append(CleanCoreFinding(
                severity="INFO",
                rule="NOT_SUBMITTED_TO_ARB",
                description=(
                    "Solution contains SAP components but has not been submitted to the ARB. "
                    "SAP transformation work requires ARB sign-off on clean-core posture."
                ),
                evidence="ARB submission count: 0",
                remediation=(
                    "Use 'submit_for_arb_review' tool or navigate to the solution's "
                    "ARB tab and submit. Include the clean-core assessment as evidence."
                ),
                extension_tier=0,
            ))
        return findings

    # ── Scoring and classification ─────────────────────────────────────────────

    @classmethod
    def _compute_score(cls, findings: list) -> int:
        deduction = sum(SEVERITY_DEDUCTIONS.get(f.severity, 0) for f in findings)
        return max(0, 100 - deduction)

    @classmethod
    def _score_to_tier(cls, score: int) -> str:
        if score >= 80:
            return "CLEAN_CORE_COMPLIANT"
        if score >= 50:
            return "AT_RISK"
        return "NON_COMPLIANT"

    @classmethod
    def _assess_upgrade_risk(cls, findings: list, footprint: dict) -> str:
        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        if critical >= 2 or (critical >= 1 and high >= 2):
            return "UPGRADE_BLOCKER"
        if critical >= 1 or high >= 2:
            return "HIGH_RISK"
        if high >= 1:
            return "MEDIUM_RISK"
        return "LOW_RISK"

    @classmethod
    def _build_extension_model(cls, footprint: dict, findings: list) -> dict:
        has_btp = footprint["btp_element_count"] > 0
        has_classic = footprint["classic_pattern_count"] > 0
        has_modification = any(f.rule == "SAP_MODIFICATION_DETECTED" for f in findings)
        return {
            "tier_0_standard": True,
            "tier_1_inapp": not has_modification,
            "tier_2_sidebyside": has_btp,
            "tier_3_classic": has_classic,
            "tier_4_modification": has_modification,
            "highest_violation_tier": (
                4 if has_modification else
                3 if has_classic else
                2 if not has_btp and (footprint["sap_app_count"] + footprint["sap_element_count"]) > 0 else
                1
            ),
        }

    @classmethod
    def _build_summary(cls, result: CleanCoreResult) -> str:
        tier_label = {
            "CLEAN_CORE_COMPLIANT": "CLEAN CORE COMPLIANT",
            "AT_RISK": "AT RISK",
            "NON_COMPLIANT": "NON-COMPLIANT",
        }.get(result.compliance_tier, result.compliance_tier)

        critical = sum(1 for f in result.findings if f.severity == "CRITICAL")
        high = sum(1 for f in result.findings if f.severity == "HIGH")
        medium = sum(1 for f in result.findings if f.severity == "MEDIUM")

        fp = result.sap_footprint
        lines = [
            f"SAP Clean-Core Assessment: {result.solution_name}",
            f"Score: {result.score}/100 — {tier_label} | Upgrade risk: {result.upgrade_risk}",
            f"SAP footprint: {fp['sap_app_count']} app(s), {fp['sap_element_count']} element(s), "
            f"{fp['btp_element_count']} BTP element(s)",
            f"Findings: {critical} CRITICAL, {high} HIGH, {medium} MEDIUM",
        ]
        if result.findings:
            lines.append("Top findings:")
            for f in sorted(result.findings, key=lambda x: ("CRITICAL", "HIGH", "MEDIUM", "INFO").index(x.severity))[:3]:
                lines.append(f"  [{f.severity}] {f.rule}: {f.description[:120]}")
        return "\n".join(lines)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _matches_keywords(text: str, keywords: set) -> bool:
        return any(kw in text for kw in keywords)

    @staticmethod
    def _serialise(result: CleanCoreResult) -> dict:
        return {
            "solution_id": result.solution_id,
            "solution_name": result.solution_name,
            "score": result.score,
            "compliance_tier": result.compliance_tier,
            "upgrade_risk": result.upgrade_risk,
            "summary": result.summary,
            "sap_footprint": result.sap_footprint,
            "extension_model": result.extension_model,
            "findings": [
                {
                    "severity": f.severity,
                    "rule": f.rule,
                    "description": f.description,
                    "evidence": f.evidence,
                    "remediation": f.remediation,
                    "extension_tier": f.extension_tier,
                }
                for f in result.findings
            ],
            "findings_summary": {
                "CRITICAL": sum(1 for f in result.findings if f.severity == "CRITICAL"),
                "HIGH": sum(1 for f in result.findings if f.severity == "HIGH"),
                "MEDIUM": sum(1 for f in result.findings if f.severity == "MEDIUM"),
                "INFO": sum(1 for f in result.findings if f.severity == "INFO"),
            },
        }
