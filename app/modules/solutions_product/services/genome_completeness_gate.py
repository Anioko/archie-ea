"""
Genome Completeness Gate

Validates that a genome (post-inference, post-perfector) has all critical
fields required to generate a production-ready application.

Called immediately before Phase 4 code generation begins.
Returns blocking issues (generation cannot proceed) and warnings (surfaced in UI).
"""
from dataclasses import dataclass, field

from app.modules.codegen.stack_registry import STACK_REGISTRY, validate_language


@dataclass
class CompletenessResult:
    can_generate: bool
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_completeness(genome: dict) -> CompletenessResult:
    """
    Validate genome completeness after inference + perfector pass.

    Args:
        genome: Enriched genome dict (post-infer_genome, post-genome_perfector)

    Returns:
        CompletenessResult with blocking_issues and warnings.
        can_generate is True only when blocking_issues is empty.
    """
    issues = []
    warnings = []

    # ── Language / stack validation — block generation ────────────────────────
    # validate_language returns corrective error strings with explicit "X does
    # not exist" statements so LLMs cannot silently pick a wrong stack slug.
    issues.extend(validate_language(genome.get("language")))

    # Detect stack-composition mismatches (e.g. genome describes a frontend
    # but the chosen language produces none)
    lang = genome.get("language")
    if lang and lang in STACK_REGISTRY:
        stack = STACK_REGISTRY[lang]
        genome_has_frontend = bool(genome.get("frontend") or genome.get("ui_framework"))
        genome_has_mobile = bool(genome.get("mobile", {}).get("platforms"))

        if genome_has_frontend and stack["frontend"] is None:
            warnings.append(
                f"genome.language='{lang}' ({stack['label']}) generates NO frontend code, "
                f"but genome contains frontend/ui_framework config — it will be ignored. "
                f"For a full-stack output with Next.js, use 'react-shadcn' "
                f"(FastAPI + Next.js), 'flask-nextjs' (Flask + Next.js), or 'flask-react' (Flask + React/Vite)."
            )
        if genome_has_mobile and stack["mobile"] is None:
            warnings.append(
                f"genome.language='{lang}' ({stack['label']}) generates NO mobile code, "
                f"but genome contains mobile.platforms config — it will be ignored. "
                f"For a mobile app, use 'react-native-expo'."
            )

    # ── Critical fields — block generation ───────────────────────────────────

    bm = genome.get("business_model", {})
    if not bm.get("type"):
        issues.append(
            "business_model.type is required — "
            "specify one of: saas, marketplace, consumer, internal_tool, api_product"
        )

    comp = genome.get("compliance", {})
    if not isinstance(comp.get("gdpr"), bool):
        issues.append(
            "compliance.gdpr must be explicitly set (true or false) — "
            "determines whether GDPR deletion/export endpoints are generated"
        )

    ops = genome.get("operations", {})
    if not ops.get("error_tracking"):
        issues.append(
            "operations.error_tracking is required — "
            "set to 'sentry' or explicitly 'none' to skip"
        )

    dep = genome.get("deployment", {})
    if not dep.get("ci_cd"):
        issues.append(
            "deployment.ci_cd is required — "
            "set to 'github_actions' or explicitly 'none' to skip"
        )

    infra = genome.get("infrastructure", {})
    if not infra.get("auth", {}).get("provider"):
        issues.append(
            "infrastructure.auth.provider is required — "
            "specify auth type: jwt, oauth2, oidc, saml, api_key, or none"
        )

    if not infra.get("database"):
        issues.append(
            "infrastructure.database is required — "
            "specify database engine: postgresql, mysql, sqlite, mongodb"
        )

    mob = genome.get("mobile", {})
    if mob.get("platforms") and "ios" in mob["platforms"] and not mob.get("minimum_ios"):
        issues.append(
            "mobile.minimum_ios is required when platforms includes ios — "
            "recommended: '16.0'"
        )

    if mob.get("platforms") and "android" in mob["platforms"] and not mob.get("minimum_android"):
        issues.append(
            "mobile.minimum_android is required when platforms includes android — "
            "recommended: 26 (Android 8.0)"
        )

    # ── Warnings — non-blocking ───────────────────────────────────────────────

    if not ops.get("alerting_email"):
        warnings.append(
            "operations.alerting_email not set — "
            "you won't receive email notifications when the app goes down"
        )

    if comp.get("hipaa"):
        warnings.append(
            "HIPAA flagged — generated code is a starting point only. "
            "Engage a compliance consultant and conduct a formal risk assessment before launch."
        )

    if comp.get("pci_dss"):
        warnings.append(
            "PCI-DSS flagged — never store raw card data in your database. "
            "Use Stripe.js to tokenize on the client; your server never sees card numbers."
        )

    if bm.get("billing") not in ("none", None, "") and not bm.get("plans"):
        warnings.append(
            "Billing enabled but no plans defined — "
            "Stripe integration will be generated without plan-level enforcement"
        )

    return CompletenessResult(
        can_generate=len(issues) == 0,
        blocking_issues=issues,
        warnings=warnings,
    )
