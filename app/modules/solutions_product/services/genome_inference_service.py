"""
Genome Inference Engine

Deterministically populates missing genome sections from signals already
present in the genome and problem statement.

Design constraints:
- Pure functions only — no LLM, no DB access, no I/O
- Non-destructive — never overwrites an existing value
- Every inferred value is logged in genome["_inference_log"] with its reason
- Inference order: business_model → compliance → operations → deployment → mobile
  (compliance reads from business_model, so order matters)
"""
import copy
import logging
import re

logger = logging.getLogger(__name__)

_SAAS_KEYWORDS = ["saas", "subscription", "per seat", "monthly plan", "pricing tier", "pricing page"]
_MARKETPLACE_KEYWORDS = ["marketplace", "commission", "take rate", "buyer", "seller", "vendor listing"]
_INTERNAL_KEYWORDS = ["internal", "internal only", "employees only", "internal tool", "intranet"]
_API_KEYWORDS = ["api product", "developer platform", "sdk", "developer tool", "api-first"]
_EU_KEYWORDS = ["eu", "europe", "gdpr", "international", "global users", "worldwide"]
_HEALTH_KEYWORDS = ["health", "medical", "patient", "phi", "hipaa", "clinical", "ehr", "emr", "hospital"]
_PCI_KEYWORDS = ["payment card", "credit card", "pci", "card number", "debit card"]
_LOCATION_KEYWORDS = ["location", "field service", "map", "gps", "nearby", "distance", "geofence", "route"]
# Include common inflected forms explicitly (plural, gerund) since word-boundary
# matching uses strict \b...\b and won't match "photos" from "photo" or "scanning" from "scan".
_CAMERA_KEYWORDS = ["photo", "photos", "scan", "scanning", "camera", "cameras",
                    "image capture", "qr code", "barcode", "selfie"]
_NOTIFICATION_KEYWORDS = ["notify", "notification", "alert", "reminder", "push notification", "sms alert"]


def infer_genome(genome: dict, problem_text: str = "") -> dict:
    """
    Populate missing genome sections from signals in the existing genome.

    Args:
        genome: Existing genome dict from CodegenGeneration.genome
        problem_text: Solution's Step 1 problem statement (from
                      Solution.journey_state["steps"]["1"]["problem_statement"]
                      or Solution.problem_clarification)
    Returns:
        New genome dict with inferred sections merged in. Original is not mutated.
    """
    result = copy.deepcopy(genome)
    log = result.setdefault("_inference_log", {})

    corpus = _build_corpus(result, problem_text)

    _infer_business_model(result, corpus, log)
    _infer_compliance(result, corpus, log)
    _infer_operations(result, log)
    _infer_deployment(result, log)
    _infer_mobile_permissions(result, corpus, log)

    return result


def _infer_business_model(genome: dict, corpus: str, log: dict) -> None:
    bm = genome.setdefault("business_model", {})

    if "type" not in bm:
        if _kw_match(corpus, _SAAS_KEYWORDS):
            _set(bm, log, "business_model.type", "saas",
                 "inferred from: SaaS/subscription keywords in problem statement")
        elif _kw_match(corpus, _MARKETPLACE_KEYWORDS):
            _set(bm, log, "business_model.type", "marketplace",
                 "inferred from: marketplace keywords")
        elif _kw_match(corpus, _INTERNAL_KEYWORDS):
            _set(bm, log, "business_model.type", "internal_tool",
                 "inferred from: internal tool keywords")
        elif _kw_match(corpus, _API_KEYWORDS):
            _set(bm, log, "business_model.type", "api_product",
                 "inferred from: API/developer platform keywords")
        elif genome.get("security", {}).get("multi_tenancy"):
            _set(bm, log, "business_model.type", "saas",
                 "inferred from: multi_tenancy enabled — strong SaaS signal")
        else:
            # Backwards-compatibility fallback: old solutions with vague problem text
            # would be blocked by the completeness gate if type stays unset.
            # internal_tool is the safe default — no billing, no multi-tenancy,
            # no Stripe dependencies. Correct via wizard if wrong.
            _set(bm, log, "business_model.type", "internal_tool",
                 "default fallback: no business model signals detected — "
                 "defaulting to internal_tool to unblock generation. "
                 "Review and correct in wizard if this is a customer-facing product.")

    if "billing" not in bm:
        bm_type = bm.get("type")
        if bm_type == "internal_tool":
            _set(bm, log, "business_model.billing", "none",
                 "unconditional: internal tools do not bill users")
        elif _kw_match(corpus, ["subscription", "monthly", "annual plan", "per seat"]):
            _set(bm, log, "business_model.billing", "stripe_subscription",
                 "inferred from: subscription/billing keywords")
        elif _kw_match(corpus, ["usage", "pay per use", "metered", "credits"]):
            _set(bm, log, "business_model.billing", "usage_based",
                 "inferred from: usage-based keywords")
        elif bm_type in ("consumer", "marketplace"):
            _set(bm, log, "business_model.billing", "stripe_subscription",
                 f"inferred from: business_model.type={bm_type}")

    if "trial_days" not in bm and bm.get("billing") in ("stripe_subscription", "usage_based"):
        _set(bm, log, "business_model.trial_days", 14,
             "default: 14-day trial for subscription products")


def _infer_compliance(genome: dict, corpus: str, log: dict) -> None:
    comp = genome.setdefault("compliance", {})

    if "audit_log_all_mutations" not in comp:
        _set(comp, log, "compliance.audit_log_all_mutations", True,
             "unconditional: all mutations must be audited for security and debugging")

    if "privacy_policy_required" not in comp:
        _set(comp, log, "compliance.privacy_policy_required", True,
             "unconditional: App Store and SaaS legal requirements demand a privacy policy")

    if "gdpr" not in comp:
        has_email = _has_field_format(genome, "email")
        bm_type = genome.get("business_model", {}).get("type")

        if _kw_match(corpus, _EU_KEYWORDS):
            _set(comp, log, "compliance.gdpr", True,
                 "inferred from: EU/GDPR keywords in problem statement")
        elif has_email:
            _set(comp, log, "compliance.gdpr", True,
                 "inferred from: email field detected — PII collected requires GDPR consideration")
        elif bm_type in ("saas", "consumer", "marketplace"):
            _set(comp, log, "compliance.gdpr", True,
                 f"inferred from: business_model.type={bm_type} — likely serves EU users")
        else:
            _set(comp, log, "compliance.gdpr", False,
                 "no GDPR signals detected — set explicitly if EU users are expected")

    if comp.get("gdpr"):
        _gdpr_derived = [
            ("cookie_consent", "required when gdpr=true — EU cookie law"),
            ("data_deletion_endpoint", "GDPR Article 17 — right to erasure"),
            ("data_export_endpoint", "GDPR Article 20 — right to data portability"),
            ("terms_of_service_required", "required for data processing agreements with EU users"),
        ]
        for key, reason in _gdpr_derived:
            if key not in comp:
                _set(comp, log, f"compliance.{key}", True, reason)

    if "hipaa" not in comp:
        if _kw_match(corpus, _HEALTH_KEYWORDS):
            _set(comp, log, "compliance.hipaa", True,
                 "inferred from: healthcare keywords — human compliance review required before launch")
        else:
            _set(comp, log, "compliance.hipaa", False, "no healthcare keywords detected")

    if "pci_dss" not in comp:
        if _kw_match(corpus, _PCI_KEYWORDS):
            _set(comp, log, "compliance.pci_dss", True,
                 "inferred from: payment card keywords — use Stripe, never store raw card data")
        else:
            _set(comp, log, "compliance.pci_dss", False, "no payment card keywords detected")


def _infer_operations(genome: dict, log: dict) -> None:
    ops = genome.setdefault("operations", {})

    unconditional = [
        ("error_tracking", "sentry",
         "unconditional: all apps require error tracking — you learn about outages from Sentry, not users"),
        ("structured_logging", True,
         "unconditional: structured logs are queryable; print statements are not"),
        ("log_pii_scrubbing", True,
         "unconditional: PII must never appear in logs — compliance and security requirement"),
        ("backup_schedule", "daily",
         "unconditional: data loss is not recoverable without backups"),
        ("monitoring", "uptime_robot",
         "unconditional: you must know before your users do when the app is down"),
    ]
    for key, value, reason in unconditional:
        if key not in ops:
            _set(ops, log, f"operations.{key}", value, reason)

    if "log_retention_days" not in ops:
        if genome.get("compliance", {}).get("hipaa") or genome.get("compliance", {}).get("gdpr"):
            _set(ops, log, "operations.log_retention_days", 365,
                 "365 days: HIPAA/GDPR compliance requirement for audit log retention")
        else:
            _set(ops, log, "operations.log_retention_days", 90,
                 "default: 90 days log retention")


def _infer_deployment(genome: dict, log: dict) -> None:
    dep = genome.setdefault("deployment", {})

    unconditional = [
        ("ci_cd", {"provider": "github_actions"},
         "unconditional: GitHub integration is present — all apps get CI/CD pipeline"),
        ("environments", ["development", "staging", "production"],
         "unconditional: environment parity prevents prod-only bugs"),
        ("zero_downtime", True,
         "unconditional: production deploys must not drop in-flight requests"),
        ("branch_protection", True,
         "unconditional: direct pushes to main bypass CI and are dangerous"),
        ("security_scanning", True,
         "unconditional: bandit + safety scan catches vulnerabilities before deploy"),
        ("dependency_auditing", True,
         "unconditional: pip-audit catches known CVEs in dependencies"),
    ]
    for key, value, reason in unconditional:
        if key not in dep:
            _set(dep, log, f"deployment.{key}", value, reason)

    if "platform" not in dep:
        if genome.get("mobile", {}).get("platforms"):
            _set(dep, log, "deployment.platform", "expo_eas",
                 "inferred from: mobile platforms configured")
        else:
            _set(dep, log, "deployment.platform", "docker",
                 "default: Docker for web/API applications")


def _infer_mobile_permissions(genome: dict, corpus: str, log: dict) -> None:
    mob = genome.setdefault("mobile", {})
    if not mob.get("platforms"):
        return

    perms = set(mob.get("permissions", []))

    if "camera" not in perms:
        if _kw_match(corpus, _CAMERA_KEYWORDS) or _has_field_format(genome, "image"):
            perms.add("camera")
            log["mobile.permissions.camera"] = "inferred from: photo/scan/camera keywords or image field type"

    if "location" not in perms:
        if _kw_match(corpus, _LOCATION_KEYWORDS) or _has_field_name(
            genome, ["latitude", "longitude", "location", "address", "geo"]
        ):
            perms.add("location")
            log["mobile.permissions.location"] = "inferred from: location keywords or geolocation fields"

    # notifications: unconditional default for mobile apps — most apps benefit from push notifications.
    # Mirrors the pattern of audit_log_all_mutations (compliance) and error_tracking (operations).
    if "notifications" not in perms:
        perms.add("notifications")
        log["mobile.permissions.notifications"] = (
            "inferred from: notification keywords" if _kw_match(corpus, _NOTIFICATION_KEYWORDS)
            else "default: unconditional — mobile apps require push notification capability"
        )

    mob["permissions"] = sorted(perms)

    if "ios" in mob.get("platforms", []) and "privacy_manifest_required" not in mob:
        _set(mob, log, "mobile.privacy_manifest_required", True,
             "unconditional: Apple requires PrivacyInfo.xcprivacy for all iOS apps")

    if "minimum_ios" not in mob and "ios" in mob.get("platforms", []):
        _set(mob, log, "mobile.minimum_ios", "16.0",
             "default: iOS 16.0 covers 95%+ of active iOS devices")

    if "minimum_android" not in mob and "android" in mob.get("platforms", []):
        _set(mob, log, "mobile.minimum_android", 26,
             "default: Android 8.0 (API 26) covers 95%+ of active Android devices")

    if "deep_link_scheme" not in mob:
        solution_name = genome.get("solution_name", "app")
        scheme = re.sub(r"[^a-z0-9]", "", solution_name.lower())[:20] or "app"
        _set(mob, log, "mobile.deep_link_scheme", scheme,
             f"derived from solution name: {scheme}://")


def _set(target: dict, log: dict, log_key: str, value, reason: str) -> None:
    field_key = log_key.split(".")[-1]
    target[field_key] = value
    log[log_key] = reason


def _kw_match(corpus: str, keywords: list) -> bool:
    """Match keywords against corpus using strict word boundaries (\\bkw\\b).

    Prevents substring false positives:
    - 'eu' does NOT match 'queue'
    - 'internal' does NOT match 'international'

    Note: inflected forms (plural, gerund) must be listed explicitly in the
    keyword list, since '\\bphoto\\b' does NOT match 'photos' and '\\bscan\\b'
    does NOT match 'scanning'. Add 'photos' alongside 'photo', 'scanning'
    alongside 'scan', etc. See _CAMERA_KEYWORDS for the established convention.
    """
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, corpus):
            return True
    return False


def _build_corpus(genome: dict, problem_text: str) -> str:
    parts = [problem_text]
    prob = genome.get("problem", {})
    if isinstance(prob, dict):
        parts.append(prob.get("statement", ""))
        parts.extend(prob.get("success_metrics", []))
        parts.extend(str(c) for c in prob.get("constraints", []))
    elif isinstance(prob, str):
        parts.append(prob)
    return " ".join(str(p) for p in parts).lower()


def _has_field_format(genome: dict, fmt: str) -> bool:
    for mod_def in genome.get("modules", {}).values():
        fields_map = mod_def.get("fields", {})
        if not fields_map:
            fields_map = mod_def.get("confirmed_fields", {})
        for fields in fields_map.values():
            if not isinstance(fields, list):
                continue
            for field in fields:
                if field.get("type") == fmt or field.get("format") == fmt:
                    return True
    return False


def _has_field_name(genome: dict, names: list) -> bool:
    for mod_def in genome.get("modules", {}).values():
        fields_map = mod_def.get("fields", {})
        if not fields_map:
            fields_map = mod_def.get("confirmed_fields", {})
        for fields in fields_map.values():
            if not isinstance(fields, list):
                continue
            for field in fields:
                fname = field.get("name", "").lower()
                if any(n in fname for n in names):
                    return True
    return False
