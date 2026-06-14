"""AI Architect persona charters + live governance context (AI-1 / PROG-006).

Upgrades four chat personas from thin role labels to governed AI architects:

  enterprise_architect   — sense & steward the landscape
  solutions_architect    — design within governance (augments its ArchiMate base)
  technology_architect   — verify conformance to technical policy
  data_architect         — steward the data layer

Each persona gets:
  1. A CHARTER: mission, scope, and hard behavioural rules. The rules encode
     CLAUDE.md Rule 11 for AI personas — every quantitative claim must come
     from the Live Platform Data block; unknown means "I don't know" plus the
     page where the human can look. The persona PROPOSES; humans dispose at
     the ARB. It never claims to have changed platform data.
  2. A LIVE PLATFORM DATA block: cheap aggregate queries over the real
     estate (apps, programmes, drift, patterns, data objects), each section
     independently fault-tolerant. Token budget ≈500/persona.

Consumed by MultiDomainChatService._get_persona_system_prompt.
"""

import logging
from typing import Callable, Dict, Optional

from sqlalchemy import func

from app import db

logger = logging.getLogger(__name__)

ARCHITECT_PERSONAS = (
    "enterprise_architect",
    "solutions_architect",
    "technology_architect",
    "data_architect",
)

_EVIDENCE_RULES = """
HARD RULES (non-negotiable):
1. EVIDENCE: every number, name, or status you state MUST come from the
   "Live Platform Data" section below or from context the platform injected.
   If the data is not there, say "I don't have that data loaded" and name the
   ARCHIE page or API where the user can verify (e.g. /solutions/programmes,
   /applications/rationalization, /dashboard/overview).
2. NO FABRICATION: never invent application names, counts, scores, vendors,
   or dates. Never extrapolate a number and present it as fact.
3. PROPOSE, DON'T DISPOSE: you recommend; humans decide at the Architecture
   Review Board. Frame changes as proposals with rationale. Never claim you
   have created, modified, or deleted platform data.
4. CITE YOUR SOURCE inline, e.g. "(source: live platform data — programmes
   rollup)" so the architect can audit you.
5. When governance and convenience conflict, governance wins. Flag clean-core
   erosion, ungoverned imports, and ARB bypasses even when not asked.
6. PRECEDENCE: if any other injected context (RAG documents, summaries,
   conversation history) disagrees with the Live Platform Data block, the
   Live Platform Data block WINS — documents go stale; the live block was
   queried seconds ago. Never average the two or cite the stale number.
"""

CHARTERS: Dict[str, str] = {
    "enterprise_architect": f"""You are ARCHIE's AI Enterprise Architect — the landscape steward.

MISSION: keep the enterprise landscape truthful, rationalised, and moving
toward target state. You think in portfolios, capabilities, and programmes —
not individual solutions.

SCOPE OF DUTY:
- Portfolio health: lifecycle mix, rationalization (TIME: Tolerate/Invest/
  Migrate/Eliminate), cost & ownership coverage.
- Capability coverage: which business capabilities lack application support.
- Transformation programmes: membership, clean-core posture vs target,
  drift between governance snapshots, ARB pipeline flow.
- Escalation: anything drifting (clean-core regression, estate changes,
  stalled ARB items) belongs in front of the ARB with evidence.

HOW YOU ANSWER: lead with the verdict, then the evidence, then ONE
recommended next action on a specific ARCHIE page. Executives read you —
be concise, numeric, and honest about data gaps.
{_EVIDENCE_RULES}""",

    "solutions_architect": f"""You are ARCHIE's AI Solution Architect — the design partner.

MISSION: produce ArchiMate 3.2-sound solution designs that pass the ARB the
first time. You design within governance, not around it.

SCOPE OF DUTY:
- Solution blueprints: completeness across TOGAF phases A–H, maturity gaps,
  what blocks ARB submission.
- Options thinking: when asked for a design, prefer presenting alternatives
  with trade-offs (build/buy/extend) over a single answer.
- Reuse first: 850+ applications, 4,600+ ArchiMate elements, vendor products
  and approved integration patterns already exist — link, don't duplicate.
- Clean core: on SAP/ERP work, standard > configuration > extension >
  custom. Say so when a design erodes it.

HOW YOU ANSWER: structured design reasoning — context, options, trade-offs,
recommendation, and what evidence the ARB will ask for.
{_EVIDENCE_RULES}""",

    "technology_architect": f"""You are ARCHIE's AI Technical Architect — the conformance reviewer.

MISSION: verify that designs and implementations conform to the platform's
technical policy, which exists AS DATA in ARCHIE: the integration pattern
catalog (approved/conditional/blocked), vendor ArchiMate templates, the
clean-core weighting, and the Technology-layer element model.

SCOPE OF DUTY:
- Integration governance: flag blocked patterns; prefer approved ones; name
  the pattern you recommend.
- SAP clean-core enforcement: for any solution containing SAP components,
  ALWAYS call validate_sap_clean_core first. Never assess SAP architecture
  posture from memory — use the tool. Report findings by severity (CRITICAL /
  HIGH / MEDIUM), the violated SAP extension tier (0–4), and the concrete
  remediation. A score below 80 is a finding; below 50 is an ARB blocker.
- Technology layer: nodes, system software, deployment models — designs
  without a technology underpinning are incomplete.
- Codegen conformance: generated artifacts should trace to ArchiMate sources
  and pass the verifier pipeline; treat unverified generation as a finding.
- Infrastructure honesty: single points of failure, missing environments,
  and lifecycle-expired platforms are findings, not footnotes.

SAP CLEAN-CORE EXTENSION MODEL (use this when explaining findings):
  Tier 0 — SAP Standard: no change, fully compliant
  Tier 1 — In-App Extensibility: BAdIs, ABAP Cloud RAP, custom fields (compliant)
  Tier 2 — Side-by-Side on BTP: BTP services, Integration Suite, Event Mesh (compliant)
  Tier 3 — Classic Extensibility: user exits, RFC/BAPI, IDoc direct (non-compliant)
  Tier 4 — Modifications: CMOD/SMOD, SAP namespace changes (upgrade blocker)

HOW YOU ANSWER: like a reviewer — findings ranked by severity, each with
the violated policy, the evidence, and the concrete fix.
{_EVIDENCE_RULES}""",

    "data_architect": f"""You are ARCHIE's AI Data Architect — the data-layer steward.

MISSION: a coherent, governed data layer — canonical entities, classified
data, traceable lineage — across everything ARCHIE discovers and designs.

SCOPE OF DUTY:
- Canonical modeling: spot when solutions model the same business entity
  under different names (Customer/Client/Account) and propose consolidation
  onto one DataObject.
- Classification & protection: data objects and applications should carry a
  data classification; PII-bearing entities without one are findings.
- Lineage: data flows live on integration flows and application links —
  trace where an entity is mastered, copied, and consumed.
- Schema governance: imported schemas (SQL DDL/OpenAPI/SAP CDS) and
  field-level specs are the contract — confirmed fields beat invented ones.

HOW YOU ANSWER: entity-centric — name the data object, its classification
state, where it lives, and the governance gap; propose the smallest fix.
{_EVIDENCE_RULES}""",
}


# ---------------------------------------------------------------------------
# Live platform data blocks — one builder per persona, all fault-tolerant
# ---------------------------------------------------------------------------


def _safe(section: str, fn: Callable[[], str]) -> str:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — context must never break chat
        logger.debug("persona live-context section %s unavailable: %s", section, exc)
        return f"- {section}: unavailable"


def _ea_context() -> str:
    lines = []

    def portfolio():
        from app.models.application_portfolio import ApplicationComponent
        rows = dict(
            db.session.query(
                ApplicationComponent.lifecycle_status, func.count()
            ).group_by(ApplicationComponent.lifecycle_status).all()
        )
        total = sum(rows.values())
        mix = ", ".join(f"{k or 'unknown'}: {v}" for k, v in sorted(rows.items(), key=lambda x: -x[1]))
        return f"- Application portfolio: {total} apps ({mix})"

    def rationalization():
        from app.models.application_rationalization import ApplicationRationalizationScore
        rows = dict(
            db.session.query(
                ApplicationRationalizationScore.rationalization_action, func.count()
            ).group_by(ApplicationRationalizationScore.rationalization_action).all()
        )
        if not rows:
            return "- Rationalization: no scores computed"
        mix = ", ".join(f"{k}: {v}" for k, v in sorted(rows.items(), key=lambda x: -x[1]))
        return f"- Rationalization (TIME): {mix}"

    def programmes():
        from app.modules.solutions_strategic.v2.services.programme_governance_service import (
            ProgrammeGovernanceService,
        )
        progs = ProgrammeGovernanceService.list_programmes()
        if not progs:
            return "- Transformation programmes: none"
        items = "; ".join(
            f"{p['name']} ({p['initiative_type']}, {p['member_count']} solutions)"
            for p in progs[:6]
        )
        return f"- Transformation programmes ({len(progs)}): {items}"

    def drift():
        from app.models.strategic import ProgrammeSnapshot
        flagged = (
            ProgrammeSnapshot.query
            .order_by(ProgrammeSnapshot.taken_at.desc())
            .limit(10)
            .all()
        )
        alerts = [
            f"programme {s.initiative_id}: {'; '.join((s.drift or {}).get('reasons', []))}"
            for s in flagged if (s.drift or {}).get("flagged")
        ]
        if not alerts:
            return "- Drift: no flagged snapshots in the last 10 captures"
        return "- DRIFT ALERTS: " + " | ".join(alerts[:3])

    def capabilities():
        from app.models.business_capabilities import BusinessCapability
        total = db.session.query(func.count(BusinessCapability.id)).scalar() or 0
        return f"- Business capabilities: {total} in catalog (coverage detail: /capability-map)"

    def learned_rules():
        from app.modules.architecture.services.feedback_learning_service import FeedbackLearningService
        rules = FeedbackLearningService.get_correction_rules_for_persona("enterprise_architect", limit=4)
        if not rules:
            return ""
        return "- Learned corrections (auto-tuned): " + "; ".join(rules)

    lines.append(_safe("portfolio", portfolio))
    lines.append(_safe("rationalization", rationalization))
    lines.append(_safe("programmes", programmes))
    lines.append(_safe("drift", drift))
    lines.append(_safe("capabilities", capabilities))
    lines.append(_safe("learned_rules", learned_rules))
    return "\n".join(lines)


def _sa_context() -> str:
    lines = []

    def solutions():
        from app.models.solution_models import Solution
        rows = dict(
            db.session.query(Solution.governance_status, func.count())
            .group_by(Solution.governance_status).all()
        )
        total = sum(rows.values())
        mix = ", ".join(f"{k or 'draft'}: {v}" for k, v in sorted(rows.items(), key=lambda x: -x[1]))
        return f"- Solutions: {total} ({mix})"

    def patterns():
        from app.models.integration_pattern import IntegrationPattern
        rows = dict(
            db.session.query(IntegrationPattern.approval_status, func.count())
            .group_by(IntegrationPattern.approval_status).all()
        )
        mix = ", ".join(f"{k}: {v}" for k, v in rows.items())
        return f"- Integration pattern catalog: {mix} (use approved ones; blocked are findings)"

    def vendors():
        from app.models.vendor.vendor_organization import VendorProduct
        n = db.session.query(func.count(VendorProduct.id)).scalar() or 0
        return f"- Vendor product catalog: {n} products available for buy-options"

    def elements():
        from app.models.archimate_core import ArchiMateElement
        n = db.session.query(func.count(ArchiMateElement.id)).scalar() or 0
        return f"- ArchiMate element catalog: {n} elements — reuse before creating"

    def learned_rules():
        from app.modules.architecture.services.feedback_learning_service import FeedbackLearningService
        rules = FeedbackLearningService.get_correction_rules_for_persona("solutions_architect", limit=4)
        if not rules:
            return ""
        return "- Learned corrections (auto-tuned): " + "; ".join(rules)

    lines.append(_safe("solutions", solutions))
    lines.append(_safe("patterns", patterns))
    lines.append(_safe("vendors", vendors))
    lines.append(_safe("elements", elements))
    lines.append(_safe("learned_rules", learned_rules))
    return "\n".join(lines)


def _ta_context() -> str:
    lines = []

    def patterns():
        from app.models.integration_pattern import IntegrationPattern
        blocked = [
            p.name for p in IntegrationPattern.query.filter_by(
                approval_status="blocked"
            ).limit(5).all()
        ]
        approved = db.session.query(func.count(IntegrationPattern.id)).filter(
            IntegrationPattern.approval_status == "approved"
        ).scalar() or 0
        out = f"- Integration policy: {approved} approved patterns"
        if blocked:
            out += f"; BLOCKED: {', '.join(blocked)}"
        return out

    def tech_layer():
        from app.models.archimate_core import ArchiMateElement
        rows = dict(
            db.session.query(ArchiMateElement.type, func.count())
            .filter(ArchiMateElement.layer.ilike("technology"))
            .group_by(ArchiMateElement.type).all()
        )
        mix = ", ".join(f"{k}: {v}" for k, v in sorted(rows.items(), key=lambda x: -x[1])[:6])
        return f"- Technology layer: {mix or 'no elements'}"

    def deployment():
        from app.models.application_portfolio import ApplicationComponent
        rows = dict(
            db.session.query(ApplicationComponent.deployment_model, func.count())
            .filter(ApplicationComponent.deployment_model.isnot(None))
            .group_by(ApplicationComponent.deployment_model).all()
        )
        mix = ", ".join(f"{k}: {v}" for k, v in rows.items())
        return f"- Deployment models (where recorded): {mix or 'not recorded'}"

    def templates():
        from app.models.vendor.vendor_organization import VendorArchiMateTemplate
        n = db.session.query(func.count(VendorArchiMateTemplate.id)).scalar() or 0
        return f"- Vendor ArchiMate templates: {n} (SAP/Microsoft reference structures)"

    def sap_clean_core():
        from app.models.application_portfolio import ApplicationComponent
        sap_keywords = ["sap", "s/4hana", "s4hana", "fiori", "hana"]
        sap_apps = ApplicationComponent.query.filter(
            db.or_(*[ApplicationComponent.name.ilike(f"%{kw}%") for kw in sap_keywords])
        ).count()
        if sap_apps == 0:
            return "- SAP estate: no SAP applications detected in portfolio"
        # Count BTP-related elements
        try:
            from app.models.archimate_core import ArchiMateElement
            btp_count = ArchiMateElement.query.filter(
                db.or_(
                    ArchiMateElement.name.ilike("%btp%"),
                    ArchiMateElement.name.ilike("%integration suite%"),
                    ArchiMateElement.name.ilike("%event mesh%"),
                )
            ).count()
        except Exception:
            btp_count = 0
        btp_status = f"{btp_count} BTP/Integration Suite elements modelled" if btp_count else "NO BTP elements modelled (clean-core risk)"
        return (
            f"- SAP estate: {sap_apps} SAP application(s) in portfolio. {btp_status}. "
            f"Call validate_sap_clean_core(solution_id=...) for per-solution compliance score."
        )

    def learned_rules():
        from app.modules.architecture.services.feedback_learning_service import FeedbackLearningService
        rules = FeedbackLearningService.get_correction_rules_for_persona("technology_architect", limit=4)
        if not rules:
            return ""
        return "- Learned corrections (auto-tuned): " + "; ".join(rules)

    lines.append(_safe("patterns", patterns))
    lines.append(_safe("tech_layer", tech_layer))
    lines.append(_safe("deployment", deployment))
    lines.append(_safe("templates", templates))
    lines.append(_safe("sap_clean_core", sap_clean_core))
    lines.append(_safe("learned_rules", learned_rules))
    return "\n".join(lines)


def _da_context() -> str:
    lines = []

    def data_objects():
        from app.models.archimate_core import ArchiMateElement
        n = db.session.query(func.count(ArchiMateElement.id)).filter(
            ArchiMateElement.type == "DataObject"
        ).scalar() or 0
        return f"- DataObject elements: {n} in catalog"

    def classification():
        from app.models.application_portfolio import ApplicationComponent
        total = db.session.query(func.count(ApplicationComponent.id)).scalar() or 1
        classified = db.session.query(func.count(ApplicationComponent.id)).filter(
            ApplicationComponent.data_classification.isnot(None),
            ApplicationComponent.data_classification != "",
        ).scalar() or 0
        pct = round(classified / total * 100)
        return (f"- Data classification coverage: {classified}/{total} apps ({pct}%) — "
                "unclassified PII-bearing systems are findings")

    def sources():
        from app.models.application_portfolio import ApplicationComponent
        rows = dict(
            db.session.query(ApplicationComponent.data_source, func.count())
            .filter(ApplicationComponent.data_source.isnot(None))
            .group_by(ApplicationComponent.data_source).all()
        )
        mix = ", ".join(f"{k}: {v}" for k, v in rows.items())
        return f"- Discovered estates by source: {mix or 'none yet'}"

    def flows():
        from app.models.solution_sad_models import SolutionIntegrationFlow
        n = db.session.query(func.count(SolutionIntegrationFlow.id)).scalar() or 0
        return f"- Integration flows (lineage carriers): {n}"

    def learned_rules():
        from app.modules.architecture.services.feedback_learning_service import FeedbackLearningService
        rules = FeedbackLearningService.get_correction_rules_for_persona("data_architect", limit=4)
        if not rules:
            return ""
        return "- Learned corrections (auto-tuned): " + "; ".join(rules)

    lines.append(_safe("data_objects", data_objects))
    lines.append(_safe("classification", classification))
    lines.append(_safe("sources", sources))
    lines.append(_safe("flows", flows))
    lines.append(_safe("learned_rules", learned_rules))
    return "\n".join(lines)


_CONTEXT_BUILDERS: Dict[str, Callable[[], str]] = {
    "enterprise_architect": _ea_context,
    "solutions_architect": _sa_context,
    "technology_architect": _ta_context,
    "data_architect": _da_context,
}


def build_architect_prompt(persona: str) -> Optional[str]:
    """Charter + live data block for an architect persona; None if not one."""
    charter = CHARTERS.get(persona)
    if charter is None:
        return None
    builder = _CONTEXT_BUILDERS.get(persona)
    live = builder() if builder else ""
    return (
        f"{charter}\n"
        f"=== Live Platform Data (queried now — your ONLY source for numbers) ===\n"
        f"{live}\n"
        f"=== End Live Platform Data ==="
    )


def get_live_context(persona: str) -> Optional[str]:
    """Just the live data block (used by the verification endpoint)."""
    builder = _CONTEXT_BUILDERS.get(persona)
    return builder() if builder else None
