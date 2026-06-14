"""
Application Pattern Classifier Service

Classifies each ApplicationComponent in the enterprise portfolio by architectural pattern
(monolith, modular_monolith, microservice, saas, legacy, api_gateway, unknown).

Classification uses the LLM (via LLMService) as the primary engine with a deterministic
rule-based fallback for when no LLM provider is configured.  Results are persisted to
ApplicationComponent.arch_pattern (added by SA-003).

Primary entry points:
  - classify_applications(app_ids=None) -> list[dict]
      Returns per-app classification records.
  - classify_portfolio(batch_size=50) -> dict
      Classifies the full portfolio in batches; returns aggregate statistics.
"""

import json
import logging
from typing import Dict, List, Optional

from app import db
from app.models.application_portfolio import ApplicationComponent

logger = logging.getLogger(__name__)

VALID_PATTERNS = frozenset(
    {"monolith", "modular_monolith", "microservice", "saas", "legacy", "api_gateway", "unknown"}
)

# Enterprise ERP / CRM categories that imply monolith when no other signal overrides
_ERP_CRM_CATEGORIES = frozenset({"erp", "crm", "scm", "hcm"})

# Keywords in technology_stack or app name that indicate a pattern
_MICROSERVICE_KEYWORDS = frozenset(
    {"microservice", "microservices", "kubernetes", "k8s", "docker", "container", "containers",
     "service mesh", "istio", "envoy", "dapr", "grpc", "event-driven"}
)
_API_GATEWAY_KEYWORDS = frozenset(
    {"api gateway", "kong", "apigee", "mulesoft", "aws api gateway", "azure apim", "3scale",
     "gravitee", "tyk", "wso2"}
)
_LEGACY_KEYWORDS = frozenset(
    {"cobol", "mainframe", "as400", "as/400", "rpg", "fortran", "powerbuilder",
     "delphi", "vb6", "visual basic 6", "foxpro", "clipper"}
)
_MONOLITH_KEYWORDS = frozenset({"monolith", "monolithic"})


def _safe_lower(value) -> str:
    """Return lowercased string, tolerating None / non-string values."""
    if not value:
        return ""
    return str(value).lower()


def _extract_tech_stack_tokens(app: ApplicationComponent) -> frozenset:
    """
    Flatten technology_stack (stored as JSON text) and related fields into a
    single set of lower-cased tokens for keyword matching.
    """
    tokens: List[str] = []

    for field in (app.technology_stack, app.frameworks, app.programming_languages,
                  app.database_platforms, app.integration_methods):
        if not field:
            continue
        try:
            parsed = json.loads(field)
            if isinstance(parsed, list):
                tokens.extend(_safe_lower(t) for t in parsed)
            else:
                tokens.append(_safe_lower(parsed))
        except (json.JSONDecodeError, TypeError):
            tokens.append(_safe_lower(field))

    # Include name and description for keyword signals
    tokens.append(_safe_lower(app.name))
    tokens.append(_safe_lower(app.description or ""))
    tokens.append(_safe_lower(app.integration_pattern or ""))
    tokens.append(_safe_lower(app.message_queue or ""))

    return frozenset(" ".join(tokens).split())


def _rule_based_classify(app: ApplicationComponent) -> tuple:
    """
    Deterministic classification based on structured fields.

    Returns (arch_pattern: str, confidence: float, signals: list[str]).
    """
    signals: List[str] = []
    deployment = _safe_lower(app.deployment_model)
    category = _safe_lower(app.application_category or "")
    tokens = _extract_tech_stack_tokens(app)
    joined_tech = " ".join(tokens)

    # Rule 1 – SaaS deployment model is a high-confidence signal
    if deployment in ("saas", "cloud_saas"):
        return "saas", 0.90, ["deployment_model=saas"]  # fabricated-values-ok: confidence bound for saas rule

    # Rule 2 – explicit API gateway signals
    if any(kw in joined_tech for kw in _API_GATEWAY_KEYWORDS) or "api_gateway" in _safe_lower(
        app.application_type or ""
    ):
        return "api_gateway", 0.85, ["api_gateway_keyword"]  # fabricated-values-ok: confidence bound for api_gateway rule

    # Rule 3 – microservice keywords in tech stack
    if any(kw in joined_tech for kw in _MICROSERVICE_KEYWORDS):
        return "microservice", 0.80, ["microservice_keyword"]  # fabricated-values-ok: confidence bound for microservice rule

    # Rule 4 – legacy technology detected
    if any(kw in joined_tech for kw in _LEGACY_KEYWORDS):
        return "legacy", 0.85, ["legacy_keyword"]  # fabricated-values-ok: confidence bound for legacy rule

    # Rule 5 – explicit monolith keyword
    if any(kw in joined_tech for kw in _MONOLITH_KEYWORDS):
        return "monolith", 0.80, ["monolith_keyword"]  # fabricated-values-ok: confidence bound for monolith rule

    # Rule 6 – enterprise ERP/CRM category → monolith
    if category in _ERP_CRM_CATEGORIES:
        signals.append(f"category={category}")
        return "monolith", 0.70, signals  # fabricated-values-ok: confidence bound for ERP/CRM monolith rule

    # Rule 7 – on-premise commercial apps without microservice signal → monolith
    if deployment in ("on_premise", "on-premise", "on_prem") and app.vendor_name:
        signals.append("on_premise_commercial")
        return "monolith", 0.60, signals  # fabricated-values-ok: confidence bound for on-premise monolith rule

    return "unknown", 0.40, ["no_signal"]  # fabricated-values-ok: default confidence for unknown


def _llm_classify_batch(apps: List[ApplicationComponent]) -> List[Dict]:
    """
    Classify a batch of apps via LLM.

    Returns a list of dicts with keys: id, arch_pattern, confidence, source='llm'.
    Falls back to rule-based on any LLM failure.
    """
    from app.services.llm_service import LLMService  # lazy import to avoid circular

    app_summaries = []
    for app in apps:
        tech_preview = ""
        if app.technology_stack:
            try:
                stack = json.loads(app.technology_stack)
                tech_preview = ", ".join(stack[:5]) if isinstance(stack, list) else str(stack)
            except (json.JSONDecodeError, TypeError):
                tech_preview = str(app.technology_stack)[:100]

        app_summaries.append(
            f"- ID {app.id}: name={app.name!r}, "
            f"deployment_model={app.deployment_model!r}, "
            f"application_type={app.application_type!r}, "
            f"application_category={app.application_category!r}, "
            f"tech_stack=[{tech_preview}], "
            f"vendor={app.vendor_name!r}"
        )

    prompt = (
        "You are an enterprise architecture analyst. "
        "Classify each application by its architectural pattern. "
        "Valid patterns: monolith, modular_monolith, microservice, saas, legacy, api_gateway, unknown.\n\n"
        "Rules to apply:\n"
        "- deployment_model='saas' or similar → saas\n"
        "- microservice/kubernetes/container keywords → microservice\n"
        "- api gateway / APIM products → api_gateway\n"
        "- mainframe/cobol/AS400 → legacy\n"
        "- ERP/CRM/SCM commercial on-premise → monolith\n"
        "- otherwise → unknown\n\n"
        "Applications:\n"
        + "\n".join(app_summaries)
        + "\n\n"
        "Respond ONLY with a JSON array. Each item must have exactly these keys: "
        '"id" (integer), "arch_pattern" (string), "confidence" (float 0-1), "reasoning" (string). '
        "Example: [{\"id\": 1, \"arch_pattern\": \"saas\", \"confidence\": 0.9, "
        "\"reasoning\": \"deployment_model is saas\"}]"
    )

    try:
        raw = LLMService.generate_from_prompt(prompt, use_cache=True)
        # Extract JSON array from response (LLM may wrap in markdown fences)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                ln for ln in lines if not ln.startswith("```")
            )
        results = json.loads(raw)
        if not isinstance(results, list):
            raise ValueError("LLM response is not a JSON array")

        # Build lookup by id
        lookup = {int(r["id"]): r for r in results if "id" in r and "arch_pattern" in r}
        output = []
        for app in apps:
            if app.id in lookup:
                r = lookup[app.id]
                pattern = r.get("arch_pattern", "unknown")
                if pattern not in VALID_PATTERNS:
                    pattern = "unknown"
                output.append({
                    "id": app.id,
                    "arch_pattern": pattern,
                    "confidence": float(r.get("confidence", 0.5)),
                    "source": "llm",
                })
            else:
                # App not included in LLM response — fall back to rules
                pattern, confidence, _ = _rule_based_classify(app)
                output.append({
                    "id": app.id,
                    "arch_pattern": pattern,
                    "confidence": confidence,
                    "source": "rule_fallback",
                })
        return output

    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM batch classification failed (%s); falling back to rules", exc)
        return [
            {
                "id": app.id,
                "arch_pattern": p,
                "confidence": c,
                "source": "rule_fallback",
            }
            for app in apps
            for p, c, _ in [_rule_based_classify(app)]
        ]


class ApplicationPatternClassifierService:
    """
    Classifies ApplicationComponent records by architectural pattern.

    Uses LLM as primary engine; deterministic rule-based fallback for apps that
    cannot be reached via LLM or when no LLM provider is configured.
    """

    def classify_applications(
        self,
        app_ids: Optional[List[int]] = None,
        batch_size: int = 50,
        use_llm: bool = True,
    ) -> List[Dict]:
        """
        Classify applications and persist arch_pattern to the database.

        Args:
            app_ids: Optional list of ApplicationComponent IDs to process.
                     When None, all applications are processed.
            batch_size: Number of apps to send to the LLM per request.
            use_llm: Whether to attempt LLM classification (True by default).
                     Set to False to force rule-based classification only.

        Returns:
            List of dicts, one per application:
                {app_id, app_name, arch_pattern, confidence}
        """
        query = ApplicationComponent.query
        if app_ids:
            query = query.filter(ApplicationComponent.id.in_(app_ids))
        apps: List[ApplicationComponent] = query.all()

        results: List[Dict] = []

        # Process in batches
        for batch_start in range(0, len(apps), batch_size):
            batch = apps[batch_start: batch_start + batch_size]

            if use_llm:
                classified = _llm_classify_batch(batch)
                id_map = {r["id"]: r for r in classified}
            else:
                id_map = {}

            for app in batch:
                if app.id in id_map:
                    pattern = id_map[app.id]["arch_pattern"]
                    confidence = id_map[app.id]["confidence"]
                else:
                    pattern, confidence, _ = _rule_based_classify(app)

                # Persist
                app.arch_pattern = pattern
                results.append({
                    "app_id": app.id,
                    "app_name": app.name,
                    "arch_pattern": pattern,
                    "confidence": round(confidence, 4),
                })

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return results

    def classify_portfolio(self, batch_size: int = 50) -> Dict:
        """
        Classify the full application portfolio in batches.

        Returns aggregate statistics:
            {classified: N, by_pattern: {pattern: count},
             confidence_distribution: {high/medium/low: count}}
        """
        records = self.classify_applications(app_ids=None, batch_size=batch_size)

        by_pattern: Dict[str, int] = {}
        confidence_distribution: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}

        for rec in records:
            pattern = rec["arch_pattern"]
            by_pattern[pattern] = by_pattern.get(pattern, 0) + 1

            confidence = rec["confidence"]
            if confidence >= 0.75:  # fabricated-values-ok: confidence band thresholds (high/medium/low)
                confidence_distribution["high"] += 1
            elif confidence >= 0.50:
                confidence_distribution["medium"] += 1
            else:
                confidence_distribution["low"] += 1

        return {
            "classified": len(records),
            "by_pattern": by_pattern,
            "confidence_distribution": confidence_distribution,
        }
