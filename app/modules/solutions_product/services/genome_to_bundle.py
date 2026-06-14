"""
Genome → ProductSpecBundle Adapter

Converts an Architectural Genome dict into a ProductSpecBundle that the
existing DeterministicCodeGenerator can consume without modification.

This adapter is the bridge between the new genome-based pipeline and the
existing Jinja2 template rendering system. It translates genome concepts
(modules, operations, state machines) into the ProductSpecBundle dataclasses
(ServiceDef, PathDef, BusinessRuleDef, FieldDef, etc.) that templates expect.

Pipeline position:
  Genome → GenomeToBundle → ProductSpecBundle → DeterministicCodeGenerator → Code
"""
import hashlib
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Map genome "language" values to (runtime, framework) tuples.
# Keys must match the enum in architectural_genome_schema.json.
_LANGUAGE_TO_DEPLOY = {
    "python-fastapi": ("python3.12", "fastapi"),
    "python-flask": ("python3.12", "flask"),
    "go-chi": ("go1.22", "chi"),
    "java-spring-boot": ("java17", "spring-boot"),
    "salesforce-apex": ("apex", "salesforce"),
    "react-native-expo": ("node20", "expo"),
    "react-shadcn": ("node20", "react"),
    "sap-cap": ("node20", "sap-cap"),
    "flask-nextjs": ("python3.12", "flask"),
    "flask-react": ("python3.12", "flask"),
}


def _parse_language(genome: dict) -> tuple:
    """Return (runtime, framework) from the genome's language field."""
    lang = genome.get("language", "python-fastapi")
    return _LANGUAGE_TO_DEPLOY.get(lang, ("python3.12", "fastapi"))


def _snake(name: str) -> str:
    """Convert PascalCase or spaced name to snake_case.

    Handles acronyms correctly: KPIs → kpis, APIs → apis, SQLQuery → sql_query.
    """
    s = re.sub(r"[^\w\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip())
    # Protect trailing-s plurals on all-caps acronyms before standard conversion:
    # "KPIs" → "Kpis", "APIs" → "Apis" so they don't split as "KP_Is" / "AP_Is"
    s = re.sub(r"([A-Z]{2,})s\b", lambda m: m.group(0).capitalize(), s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def _pascal(name: str) -> str:
    """Convert snake_case or spaced name to PascalCase."""
    return "".join(word.capitalize() for word in re.split(r"[\s_\-]+", name.strip()) if word)


def _pluralize(word: str) -> str:
    """Pluralize an English word for API resource paths."""
    if not word:
        return word
    low = word.lower()
    if low.endswith("s") and not low.endswith(("ss", "us", "is")):
        return word
    if low.endswith("is"):
        return word[:-2] + "es"
    if low.endswith(("ss", "sh", "ch", "x", "z")):
        return word + "es"
    if low.endswith("y") and len(low) > 1 and low[-2] not in "aeiou":
        return word[:-1] + "ies"
    if low.endswith("f"):
        return word[:-1] + "ves"
    if low.endswith("fe"):
        return word[:-2] + "ves"
    return word + "s"


# Genome type → JSON Schema type mapping
_GENOME_TO_JSON_TYPE = {
    "string": ("string", None),
    "integer": ("integer", None),
    "float": ("number", None),
    "decimal": ("number", None),
    "boolean": ("boolean", None),
    "datetime": ("string", "date-time"),
    "date": ("string", "date"),
    "text": ("string", None),
    "json": ("object", None),
    "uuid": ("string", "uuid"),
    "enum": ("string", None),
}


def genome_to_bundle(genome: dict) -> "ProductSpecBundle":
    """
    Convert an Architectural Genome dict into a ProductSpecBundle.

    Args:
        genome: Validated genome dict conforming to architectural_genome_schema.json.

    Returns:
        ProductSpecBundle ready for DeterministicCodeGenerator.generate().
    """
    from app.modules.solutions_product.services.product_spec_bundle import (
        BusinessRuleDef,
        DeploymentDef,
        EventDef,
        FieldDef,
        InfraContext,
        PathDef,
        ProductSpecBundle,
        ServiceDef,
        StateMachineDef,
    )

    modules = genome.get("modules", {})
    infra = genome.get("infrastructure", {})
    security = genome.get("security", {})
    deployment_cfg = genome.get("deployment", {})
    idp = genome.get("identity_provider", {})
    mobile = genome.get("mobile", {})
    webhooks = genome.get("webhooks", {})
    payments = genome.get("payments", {})
    product = genome.get("product", {})
    compliance = genome.get("compliance", {})

    # Genome v2 fields
    workers = genome.get("workers", [])
    api_protocol = genome.get("api_protocol", "rest")
    graphql_config = genome.get("graphql", {})
    feature_flags = genome.get("feature_flags", {})

    # Extract per-module event-sourcing data
    genome_events = {}
    genome_projections = {}
    aggregate_types = {}
    for mod_key, mod_def in modules.items():
        root = mod_def.get("aggregate_root", _pascal(mod_key))
        root_snake = _snake(root)
        agg_type = mod_def.get("aggregate_type", "crud")
        aggregate_types[root_snake] = agg_type
        if mod_def.get("events"):
            genome_events[root_snake] = mod_def["events"]
        if mod_def.get("projections"):
            genome_projections[root_snake] = mod_def["projections"]
    solution_name = genome.get("solution_name", "Generated App")
    solution_id = genome.get("solution_id", 0)

    # Build OpenAPI 3.1 spec
    openapi = _build_openapi(genome)

    # Build JSON schemas from module fields
    schemas = _build_schemas(modules)

    # Build ServiceDef list (one per module)
    services = _build_services(modules)

    # Build confirmed_fields (architect-approved field definitions)
    confirmed_fields = _build_confirmed_fields(modules)

    # Build business rules from state machines + module constraints
    business_rules = _build_business_rules(modules)

    # Build state machines
    state_machines = _build_state_machines(modules)

    # Build integrations from genome (populated by AABL compiler from Step 1 data)
    integrations = {}
    for integ_key, integ_def in genome.get("integrations", {}).items():
        if isinstance(integ_def, dict):
            integrations[integ_key] = integ_def

    # Build deployment def from genome language selection
    _runtime, _framework = _parse_language(genome)
    deploy = DeploymentDef(
        runtime=_runtime,
        framework=_framework,
        database=infra.get("database", "postgresql"),
    )

    # Build identity provider config
    idp_config = {}
    if idp:
        idp_config = {
            "type": idp.get("type", "jwt-local"),
            "preset": idp.get("preset"),
            "roles": idp.get("roles", ["admin", "user", "viewer"]),
        }
        if idp.get("issuer_url"):
            idp_config["issuer_url"] = idp["issuer_url"]
        if idp.get("client_id"):
            idp_config["client_id"] = idp["client_id"]

    # Build CI/CD config
    # genome.deployment.ci_cd may be a dict {"provider": "github_actions"} (inference engine)
    # or a legacy dict with full config. Handle both forms.
    operations = genome.get("operations", {})
    business_model = genome.get("business_model", {})

    ci_cd = None
    ci_cd_cfg = deployment_cfg.get("ci_cd", {})
    if isinstance(ci_cd_cfg, str):
        # Normalise legacy string form → dict (should not occur after inference fix, defensive only)
        ci_cd_cfg = {"provider": ci_cd_cfg}
    if ci_cd_cfg.get("provider") and ci_cd_cfg["provider"] != "none":
        ci_cd = {
            "provider": ci_cd_cfg.get("provider", "github_actions"),
            "registry": ci_cd_cfg.get("registry", "ghcr"),
            # Wire deployment.security_scanning into ci_cd so github_actions.yml.j2 can read it
            "run_security_scan": ci_cd_cfg.get(
                "run_security_scan",
                bool(deployment_cfg.get("security_scanning", True)),
            ),
            "require_manual_approval": ci_cd_cfg.get("require_manual_approval", True),
        }

    # Build InfraContext
    nfrs = []
    if security.get("rate_limiting"):
        nfrs.append({"flag": "rate_limiting", "description": "Rate limiting enabled"})
    if security.get("multi_tenancy"):
        nfrs.append({"flag": "multi_tenancy", "description": "Organization-scoped data isolation"})
    if security.get("encryption_at_rest"):
        nfrs.append({"flag": "encryption_at_rest", "description": "Field-level encryption for sensitive data"})
    if security.get("api_keys"):
        nfrs.append({"flag": "api_keys", "description": "API key management for B2B"})
    if security.get("mfa") and security["mfa"] != "none":
        nfrs.append({"flag": "mfa", "description": f"MFA: {security['mfa']}"})
    nfrs.append({"flag": "audit_trail", "description": "Audit logging on all mutations"})
    nfrs.append({"flag": "pagination", "description": "Paginated list endpoints"})
    if infra.get("observability") == "opentelemetry":
        nfrs.append({"flag": "opentelemetry", "description": "OpenTelemetry tracing and metrics"})
    # Wire genome.operations → nfr flags so templates can emit sentry/monitoring code
    if operations.get("error_tracking") == "sentry":
        nfrs.append({"flag": "sentry", "description": "Sentry error and performance tracking"})
    if operations.get("monitoring"):
        nfrs.append({"flag": "monitoring", "description": f"Monitoring: {operations['monitoring']}"})

    infra_context = InfraContext(
        nodes=[],
        tech_services=[],
        slas=[],
        nfrs=nfrs,
    )

    # Normalize multi_tenancy from genome (can be bool or object)
    _mt_raw = security.get("multi_tenancy")
    if isinstance(_mt_raw, dict):
        multi_tenancy = {
            "enabled": _mt_raw.get("enabled", True),
            "strategy": _mt_raw.get("strategy", "row_level"),
            "tenant_field": _mt_raw.get("tenant_field", "organization_id"),
        }
    elif _mt_raw:
        multi_tenancy = {
            "enabled": True,
            "strategy": "row_level",
            "tenant_field": "organization_id",
        }
    else:
        multi_tenancy = {}

    # Build business process flows from state machines
    bp_flows = _build_process_flows(modules)

    # Compute spec hash for deterministic caching
    spec_hash = hashlib.sha256(
        json.dumps(genome, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    # Build events from state machine transitions
    events = _build_events(modules)

    bundle = ProductSpecBundle(
        solution_id=solution_id,
        solution_name=solution_name,
        openapi=openapi,
        asyncapi=None,
        schemas=schemas,
        services=services,
        events=events,
        infra_context=infra_context,
        contract_tests=[],
        maturity_score=0.0,
        spec_hash=spec_hash,
        confirmed_fields=confirmed_fields,
        business_rules=business_rules,
        integrations=integrations,
        deployment=deploy,
        identity_provider=idp_config,
        ci_cd=ci_cd,
        architecture_style=None,
        business_process_flows=bp_flows,
        seed_context={},
        provenance=_build_provenance(genome),
        state_machines=state_machines,
        tables={},
        nfr_specs=[],
        screens=[],
        uml_diagrams=[],
        mobile_config=mobile,
        webhook_config=webhooks,
        payment_config=payments,
        product_config=product,
        multi_tenancy=multi_tenancy,
        _genome_modules=modules,
        _genome_compliance=compliance,
        _genome_business_model=business_model,
        _genome_operations=operations,
        # Genome v2
        workers=workers,
        api_protocol=api_protocol,
        graphql_config=graphql_config,
        feature_flags=feature_flags,
        genome_events=genome_events,
        genome_projections=genome_projections,
        aggregate_types=aggregate_types,
    )

    return bundle


def _build_openapi(genome: dict) -> dict:
    """Build an OpenAPI 3.1 spec from genome modules."""
    modules = genome.get("modules", {})
    solution_name = genome.get("solution_name", "Generated API")

    paths = {}
    component_schemas = {}

    for mod_key, mod_def in modules.items():
        root = mod_def.get("aggregate_root", _pascal(mod_key))
        root_snake = _snake(root)
        # Use snake_case for schema names so _pascal() in the generator
        # produces correct PascalCase (e.g., "work_order" → "WorkOrder")
        schema_name = root_snake
        resource_plural = _pluralize(root_snake)
        resource_path = f"/api/{resource_plural}"

        # Build schema from fields (v1: "fields", v2: "confirmed_fields")
        _entity_fields = mod_def.get("confirmed_fields", {}) or mod_def.get("fields", {})
        root_fields = _entity_fields.get(root, [])
        properties = {"id": {"type": "string", "format": "uuid"}}
        required = ["id"]

        for field in root_fields:
            # FK fields reference UUID primary keys — override type to string
            if field.get("foreign_key"):
                json_type, json_format = "string", "uuid"
            else:
                json_type, json_format = _GENOME_TO_JSON_TYPE.get(
                    field.get("type", "string"), ("string", None)
                )
            prop = {"type": json_type}
            if json_format:
                prop["format"] = json_format
            if field.get("format"):
                prop["format"] = field["format"]
            if field.get("max_length"):
                prop["maxLength"] = field["max_length"]
            if field.get("min_length"):
                prop["minLength"] = field["min_length"]
            if field.get("minimum") is not None:
                prop["minimum"] = field["minimum"]
            if field.get("maximum") is not None:
                prop["maximum"] = field["maximum"]
            if field.get("enum_values"):
                prop["enum"] = field["enum_values"]
            if field.get("description"):
                prop["description"] = field["description"]
            properties[field["name"]] = prop
            if field.get("required", True):
                required.append(field["name"])

        # Add state machine field to the aggregate root's schema
        sm = mod_def.get("state_machine")
        if sm:
            sm_field = sm.get("field", "status")
            # If sm_field is generic "status" but a *_status field already exists, reuse it
            if sm_field == "status" and sm_field not in properties:
                existing_status = next(
                    (k for k in properties if k.endswith("_status") or k.endswith("_state")),
                    None,
                )
                if existing_status:
                    sm_field = existing_status
                    sm["field"] = existing_status  # propagate to downstream consumers
            if sm_field not in properties:
                properties[sm_field] = {
                    "type": "string",
                    "enum": sm.get("states", []),
                    "default": sm.get("initial_state", sm.get("states", ["draft"])[0]),
                }
            else:
                # Merge state machine enum into existing field if it has no enum
                existing = properties[sm_field]
                if not existing.get("enum") and sm.get("states"):
                    existing["enum"] = sm.get("states", [])
                if not existing.get("default") and sm.get("initial_state"):
                    existing["default"] = sm["initial_state"]

        component_schemas[schema_name] = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        # Track archimate source if available
        element_ids = mod_def.get("archimate_element_ids", [])
        x_source = element_ids[0] if element_ids else None

        # CRUD paths — tags use schema_name so template _pascal() produces correct class name
        paths[resource_path] = {
            "get": {
                "operationId": f"list_{root_snake}s",
                "summary": f"List {root}s",
                "tags": [schema_name],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": f"create_{root_snake}",
                "summary": f"Create {root}",
                "tags": [schema_name],
                "requestBody": {
                    "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}"}}}
                },
                "responses": {"201": {"description": "Created"}},
            },
        }
        if x_source:
            paths[resource_path]["get"]["x-archimate-source"] = x_source
            paths[resource_path]["post"]["x-archimate-source"] = x_source

        paths[f"{resource_path}/{{id}}"] = {
            "get": {
                "operationId": f"get_{root_snake}",
                "summary": f"Get {root} by ID",
                "tags": [schema_name],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "OK"}},
            },
            "put": {
                "operationId": f"update_{root_snake}",
                "summary": f"Update {root}",
                "tags": [schema_name],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_name}"}}}
                },
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "operationId": f"delete_{root_snake}",
                "summary": f"Delete {root}",
                "tags": [schema_name],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"204": {"description": "Deleted"}},
            },
        }

        # State machine transition endpoints
        sm = mod_def.get("state_machine")
        if sm:
            for trans in sm.get("transitions", []):
                trigger = trans.get("trigger")
                if not trigger:
                    continue
                trigger_snake = _snake(trigger)
                trans_path = f"{resource_path}/{{id}}/{trigger_snake}"
                paths[trans_path] = {
                    "post": {
                        "operationId": f"{root_snake}_{trigger_snake}",
                        "summary": f"{trigger.replace('_', ' ').title()} {root}",
                        "tags": [schema_name],
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                        ],
                        "responses": {"200": {"description": "Transition applied"}},
                    }
                }

    return {
        "openapi": "3.1.0",
        "info": {"title": solution_name, "version": "1.0.0"},
        "paths": paths,
        "components": {"schemas": component_schemas},
    }


def _build_schemas(modules: dict) -> dict:
    """Build JSON schemas dict from genome module fields.

    Keys use snake_case to match confirmed_fields convention.
    """
    schemas = {}
    for mod_key, mod_def in modules.items():
        for entity_name, fields in mod_def.get("fields", {}).items():
            # Always include id field — models use UUID primary keys
            properties = {"id": {"type": "string", "format": "uuid"}}
            for field in fields:
                if field.get("foreign_key"):
                    json_type, json_format = "string", "uuid"
                else:
                    json_type, json_format = _GENOME_TO_JSON_TYPE.get(
                        field.get("type", "string"), ("string", None)
                    )
                prop = {"type": json_type}
                if json_format:
                    prop["format"] = json_format
                if field.get("enum_values"):
                    prop["enum"] = field["enum_values"]
                properties[field["name"]] = prop
            # Add state machine field for aggregate root
            sm = mod_def.get("state_machine")
            if sm and entity_name == mod_def.get("aggregate_root"):
                sm_field = sm.get("field", "status")
                if sm_field == "status" and sm_field not in properties:
                    existing = next((k for k in properties if k.endswith("_status") or k.endswith("_state")), None)
                    if existing:
                        sm_field = existing
                        sm["field"] = existing
                if sm_field not in properties:
                    _sm_states = sm.get("states", [])
                    properties[sm_field] = {
                        "type": "string",
                        "enum": _sm_states,
                        # Default to the initial state so Create schema doesn't
                        # require the caller to send status in the POST body.
                        "default": _sm_states[0] if _sm_states else None,
                    }
            # Add auto-generated timestamp fields
            properties["created_at"] = {"type": "string", "format": "date-time"}
            properties["updated_at"] = {"type": "string", "format": "date-time"}
            # Build required list from genome field definitions
            required = ["id"]
            for field in fields:
                if field.get("required", False):
                    required.append(field["name"])
            schemas[_snake(entity_name)] = {
                "type": "object",
                "properties": properties,
                "required": required,
            }
    return schemas


def _generator_pascal(name: str) -> str:
    """Mirror the generator's _pascal() function exactly.

    The DeterministicCodeGenerator uses this to convert confirmed_fields keys
    to class names. We must use the same function to ensure response_schema
    in PathDef matches the generated class names.

    Handles snake_case, space-separated, AND existing PascalCase/camelCase.
    """
    import re as _re
    sanitized = _re.sub(r"[^a-zA-Z0-9\s_\-]", "", (name or "Unknown").strip())
    segments = _re.split(r"[\s_\-]+", sanitized)
    words = []
    for seg in segments:
        if not seg:
            continue
        parts = _re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", seg)
        parts = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parts)
        words.extend(parts.split("_"))
    result = "".join(w.capitalize() for w in words if w)
    return result or "Unknown"


def _build_services(modules: dict) -> list:
    """Build ServiceDef list from genome modules.

    Service names use the _generator_pascal() result of the snake_case key
    to match the class names that the model/schema templates will produce.
    """
    from app.modules.solutions_product.services.product_spec_bundle import PathDef, ServiceDef

    services = []
    for mod_key, mod_def in modules.items():
        root = mod_def.get("aggregate_root", _pascal(mod_key))
        root_snake = _snake(root)
        # Service name must match the class name the generator will produce
        # from the confirmed_fields key (snake_case → _pascal → PascalCase)
        svc_name = _generator_pascal(root_snake)
        resource_plural = _pluralize(root_snake)
        resource_path = f"/api/{resource_plural}"

        element_ids = mod_def.get("archimate_element_ids", [])
        x_source = element_ids[0] if element_ids else None

        # Vendor/buy modules have externally-owned schemas — mark paths so the
        # route template skips barrel imports and response_model bindings.
        is_vendor = mod_def.get("type") in ("vendor", "buy") or bool(mod_def.get("vendor"))

        # response_schema/request_schema use snake_case (same as confirmed_fields key)
        # — the generator's _pascal() converts to PascalCase for class names in templates
        paths = [
            PathDef(
                path=resource_path, method="GET",
                operation_id=f"list_{root_snake}s",
                summary=f"List {root}s",
                request_schema=None,
                response_schema=svc_name,
                archimate_source_id=x_source,
                vendor=is_vendor,
            ),
            PathDef(
                path=resource_path, method="POST",
                operation_id=f"create_{root_snake}",
                summary=f"Create {root}",
                request_schema=svc_name,
                response_schema=svc_name,
                archimate_source_id=x_source,
                vendor=is_vendor,
            ),
            PathDef(
                path=f"{resource_path}/{{id}}", method="GET",
                operation_id=f"get_{root_snake}",
                summary=f"Get {root} by ID",
                request_schema=None,
                response_schema=svc_name,
                archimate_source_id=x_source,
                vendor=is_vendor,
            ),
            PathDef(
                path=f"{resource_path}/{{id}}", method="PUT",
                operation_id=f"update_{root_snake}",
                summary=f"Update {root}",
                request_schema=svc_name,
                response_schema=svc_name,
                archimate_source_id=x_source,
                vendor=is_vendor,
            ),
            PathDef(
                path=f"{resource_path}/{{id}}", method="DELETE",
                operation_id=f"delete_{root_snake}",
                summary=f"Delete {root}",
                request_schema=None,
                response_schema=svc_name,
                archimate_source_id=x_source,
                vendor=is_vendor,
            ),
        ]

        # State machine transition paths are NOT added to PathDef list.
        # The route template generates them from state_machine_transitions context
        # variable, with proper state machine handler logic (lookup entity, call
        # sm.transition(), handle errors). Adding them as PathDef would cause the
        # template to generate generic CRUD POST handlers instead.

        services.append(ServiceDef(name=svc_name, tag=svc_name, paths=paths))

    return services


def _build_confirmed_fields(modules: dict) -> dict:
    """Build confirmed_fields dict from genome module field definitions.

    Returns dicts (not FieldDef dataclasses) because the DeterministicCodeGenerator
    and its Jinja2 templates use dict-style access (f.get("name"), f["type"]).

    Keys use snake_case so the generator's _pascal() produces correct PascalCase.
    _pascal("work_order") → "WorkOrder" (correct)
    _pascal("WorkOrder") → "Workorder" (wrong — capitalize() lowercases after first char)
    """
    confirmed = {}
    for mod_key, mod_def in modules.items():
        # v1 uses "fields", v2 uses "confirmed_fields" — check both
        entity_fields = mod_def.get("confirmed_fields", {}) or mod_def.get("fields", {})
        for entity_name, fields in entity_fields.items():
            key = _snake(entity_name)
            field_defs = []
            for f in fields:
                # FK columns must match the referenced PK type (UUID string)
                ftype = f.get("type", "string")
                if f.get("foreign_key"):
                    ftype = "string"
                # Infer referential_actions for FK columns when not explicitly set.
                # RESTRICT: prevent deletion of parent if children exist (for required FKs).
                # SET NULL: null out the column when parent is deleted (for optional FKs).
                _ref_actions = f.get("referential_actions")
                if not _ref_actions and f.get("foreign_key"):
                    _ref_actions = {
                        "ondelete": "RESTRICT" if f.get("required", True) else "SET NULL",
                        "onupdate": "CASCADE",
                    }
                fd = {
                    "name": f["name"],
                    "type": ftype,
                    "format": f.get("format"),
                    "required": f.get("required", True),
                    "readonly": False,
                    "description": f.get("description", ""),
                    "primary_key": (f["name"] == "id"),
                    "unique": f.get("unique", False),
                    "max_length": f.get("max_length"),
                    "foreign_key": f.get("foreign_key"),
                    "referential_actions": _ref_actions,
                    "index": f.get("index", False),
                    "index_type": None,
                    "default_value": f.get("default_value"),
                    "check_constraint": None,
                    "enum_values": f.get("enum_values"),
                }
                field_defs.append(fd)

            # Inject state machine field if module has one
            sm = mod_def.get("state_machine")
            if sm and entity_name == mod_def.get("aggregate_root"):
                sm_field = sm.get("field", "status")
                # If generic "status" but a *_status field exists, reuse it
                if sm_field == "status" and not any(f["name"] == "status" for f in field_defs):
                    existing = next((f["name"] for f in field_defs if f["name"].endswith("_status") or f["name"].endswith("_state")), None)
                    if existing:
                        sm_field = existing
                        sm["field"] = existing
                # Don't duplicate if field already defined
                if not any(f["name"] == sm_field for f in field_defs):
                    field_defs.append({
                        "name": sm_field,
                        "type": "enum",
                        "format": None,
                        "required": False,
                        "readonly": False,
                        "description": f"State machine field ({sm.get('initial_state', 'draft')} → ...)",
                        "primary_key": False,
                        "unique": False,
                        "max_length": None,
                        "foreign_key": None,
                        "index": True,
                        "index_type": None,
                        "default_value": sm.get("initial_state", sm.get("states", ["draft"])[0]),
                        "check_constraint": None,
                        "enum_values": sm.get("states", []),
                    })

            confirmed[key] = field_defs
    return confirmed


def _build_business_rules(modules: dict) -> dict:
    """Build BusinessRuleDef dict from genome state machine guards and validation rules."""
    from app.modules.solutions_product.services.product_spec_bundle import BusinessRuleDef

    rules = {}
    for mod_key, mod_def in modules.items():
        root = mod_def.get("aggregate_root", _pascal(mod_key))
        rule_key = _snake(root)  # snake_case — generator _pascal's it
        mod_rules = []

        # Extract validation rules from operations
        for op_name, op_def in mod_def.get("operations", {}).items():
            for i, val in enumerate(op_def.get("validation", [])):
                rule_id = f"{_snake(mod_key)}_val_{i}"
                mod_rules.append(BusinessRuleDef(
                    id=rule_id,
                    type="validation",
                    entity=root,
                    trigger=f"validate_{_snake(val.get('field', 'unknown'))}",
                    preconditions=[{
                        "field": val.get("field", ""),
                        "operator": "satisfies",
                        "value": val.get("rule", ""),
                    }],
                    postconditions=[],
                    side_effects=[],
                    severity="error",
                    priority=1,
                    error_message=val.get("rule"),
                    description=val.get("rule"),
                ))

        # Extract rules from state machine guards
        sm = mod_def.get("state_machine")
        if sm:
            for i, trans in enumerate(sm.get("transitions", [])):
                guard = trans.get("guard")
                if guard:
                    rule_id = f"{_snake(mod_key)}_guard_{i}"
                    mod_rules.append(BusinessRuleDef(
                        id=rule_id,
                        type="state_transition",
                        entity=root,
                        trigger=f"guard_{_snake(trans.get('trigger', 'unknown'))}",
                        preconditions=[{
                            "field": "state",
                            "operator": "guard",
                            "value": guard,
                        }],
                        postconditions=[],
                        side_effects=[],
                        severity="error",
                        priority=1,
                        error_message=f"Guard failed: {guard}",
                        description=f"Guard for {trans.get('trigger')}: {guard}",
                    ))

        if mod_rules:
            rules[rule_key] = mod_rules

    return rules


def _build_state_machines(modules: dict) -> dict:
    """Build StateMachineDef dict from genome modules.

    Converts genome state machine format (dicts with 'from'/'to' keys) into
    proper StateMachineDef/TransitionDef dataclass instances that the Jinja2
    state_machine.py.j2 template expects.
    """
    from app.modules.solutions_product.services.product_spec_bundle import (
        ConditionExpr,
        SideEffectDef,
        StateMachineDef,
        TransitionDef,
    )

    machines = {}
    for mod_key, mod_def in modules.items():
        sm = mod_def.get("state_machine")
        if not sm:
            continue
        root = mod_def.get("aggregate_root", _pascal(mod_key))

        transitions = []
        for trans in sm.get("transitions", []):
            froms = trans.get("from", [])
            if isinstance(froms, str):
                froms = [froms]
            to = trans.get("to", "")
            trigger = trans.get("trigger", "")

            # Convert guard string to ConditionExpr if present
            guard = None
            guard_str = trans.get("guard")
            if guard_str:
                # Guard is a free-form string expression from the genome.
                # Wrap it as a ConditionExpr with 'is_not_null' style for the template.
                guard = ConditionExpr(
                    field_name=guard_str,
                    operator="is_not_null",
                    value=None,
                )

            # Convert effects to SideEffectDef list
            actions = []
            effects = trans.get("effect", [])
            if isinstance(effects, str):
                effects = [effects]
            for effect in effects:
                actions.append(SideEffectDef(
                    type="emit_event",
                    name=effect,
                    payload={},
                ))

            # Authorization as actions
            for role in trans.get("authorization", []):
                actions.append(SideEffectDef(
                    type="audit_log",
                    name=f"{trigger}_by_{role}",
                    payload={"role": role},
                ))

            # Create one TransitionDef per source state (template expects single from_state)
            for from_state in froms:
                transitions.append(TransitionDef(
                    from_state=from_state,
                    to_state=to,
                    trigger=trigger,
                    guard=guard,
                    actions=actions,
                ))

        machines[_generator_pascal(_snake(root))] = StateMachineDef(
            entity=root,
            field_name=sm.get("field", "status"),
            states=sm.get("states", []),
            initial_state=sm.get("initial_state", sm.get("states", [""])[0]),
            transitions=transitions,
        )

    return machines


def _build_process_flows(modules: dict) -> dict:
    """Build business process flows from state machine transitions."""
    flows = {}
    for mod_key, mod_def in modules.items():
        sm = mod_def.get("state_machine")
        if not sm:
            continue
        root = mod_def.get("aggregate_root", _pascal(mod_key))
        steps = []
        for trans in sm.get("transitions", []):
            trigger = trans.get("trigger", "unknown")
            froms = trans.get("from", [])
            if isinstance(froms, str):
                froms = [froms]
            to = trans.get("to", "unknown")
            steps.append({
                "action": _snake(trigger),
                "description": f"Transition from {', '.join(froms)} to {to}",
                "method_body_hint": trans.get("guard", ""),
            })
        if steps:
            flows[root] = steps
    return flows


def _build_events(modules: dict) -> list:
    """Build EventDef list from state machine transitions that emit events."""
    from app.modules.solutions_product.services.product_spec_bundle import EventDef

    events = []
    for mod_key, mod_def in modules.items():
        for op_name, op_def in mod_def.get("operations", {}).items():
            for event_name in op_def.get("emits", []):
                events.append(EventDef(
                    name=event_name,
                    channel=f"{_snake(mod_key)}.events",
                    payload_schema=event_name,
                ))
    return events


def _build_provenance(genome: dict) -> dict:
    """Build provenance dict from genome archimate sources."""
    sources = genome.get("_archimate_sources", {})
    return {
        "entities": {k: v for k, v in sources.items() if ".fields." not in k},
        "fields": {k: v for k, v in sources.items() if ".fields." in k},
        "rules": {},
        "genome_version": genome.get("genome_version", "unknown"),
    }
