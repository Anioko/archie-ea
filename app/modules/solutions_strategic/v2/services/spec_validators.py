"""
Spec Validators — schema, business rule, integration, deployment, cross-component.

Each validator returns a list of error dicts: [{"code": "VAL-XXX", "message": "...", "severity": "error|warning"}]
Empty list = valid.
"""
import logging

logger = logging.getLogger(__name__)

ALLOWED_FIELD_TYPES = {
    "string", "integer", "number", "boolean", "array", "object",
    "uuid", "decimal", "timestamp", "enum", "json",
}

ALLOWED_FIELD_FORMATS = {
    "uuid", "email", "date-time", "date", "uri", "ipv4", "ipv6",
    "hostname", "enum", None,
}

ALLOWED_RULE_TYPES = {"state_transition", "validation", "authorization", "side_effect"}
ALLOWED_SEVERITIES = {"error", "warning"}
ALLOWED_OPERATORS = {">", "<", ">=", "<=", "==", "!=", "in", "not_in", "contains", "matches"}

ALLOWED_PROTOCOLS = {"REST", "gRPC", "GraphQL", "async", "batch", "WebSocket", "SOAP", "SFTP"}
ALLOWED_AUTH_METHODS = {"OAuth2", "API Key", "mTLS", "Service Token", "bearer", "none"}
ALLOWED_BACKOFF_STRATEGIES = {"linear", "exponential", "jitter"}

ALLOWED_RUNTIMES = {"python3.11", "java17", "node20", "dotnet8", "go1.22"}
ALLOWED_FRAMEWORKS = {"fastapi", "spring-boot", "express", "aspnet", "gin"}
ALLOWED_DATABASES = {"postgresql", "mysql", "mongodb", "dynamodb", "none"}
ALLOWED_CACHES = {"redis", "memcached", "none"}
ALLOWED_MESSAGING = {"rabbitmq", "kafka", "sqs", "none"}
ALLOWED_CONTAINER_RUNTIMES = {"kubernetes", "ecs", "docker-compose", "vm"}

# Framework -> compatible runtimes
FRAMEWORK_RUNTIME_MAP = {
    "fastapi": {"python3.11"},
    "spring-boot": {"java17"},
    "express": {"node20"},
    "aspnet": {"dotnet8"},
    "gin": {"go1.22"},
}

# Database -> required driver runtimes (all runtimes have drivers for these DBs)
DATABASE_DRIVER_MAP = {
    "postgresql": ALLOWED_RUNTIMES,
    "mysql": ALLOWED_RUNTIMES,
    "mongodb": ALLOWED_RUNTIMES,
    "dynamodb": ALLOWED_RUNTIMES,
    "none": ALLOWED_RUNTIMES,
}

# Forbidden integration combinations
FORBIDDEN_INTEGRATION_COMBOS = [
    {
        "condition": lambda c: c.get("auth_method") == "mTLS" and c.get("endpoint_type") == "public",
        "message": "mTLS cannot be used with public endpoints — mTLS requires mutual certificate trust",
    },
    {
        "condition": lambda c: (
            c.get("protocol") == "async"
            and c.get("sla", {}).get("max_latency_ms") is not None
            and c.get("sla", {}).get("max_latency_ms", 999) < 100
        ),
        "message": "Async protocol with synchronous SLA (<100ms) is contradictory — use REST or gRPC for low-latency requirements",
    },
]

# Forbidden deployment combinations
FORBIDDEN_DEPLOYMENT_COMBOS = [
    {
        "condition": lambda d: d.get("database") == "mongodb" and d.get("consistency") == "strong" and not d.get("replica_set"),
        "message": "MongoDB with strong consistency requires a replica set configuration",
    },
]


def validate_fields_schema(fields):
    """Validate field definitions against allowed types and required properties.

    Returns list of error dicts.
    """
    errors = []
    if not isinstance(fields, list):
        return [{"code": "FIELD-001", "message": "Fields must be a list", "severity": "error"}]

    seen_names = set()
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append({"code": "FIELD-002", "message": f"Field {i} must be a dict", "severity": "error"})
            continue

        name = field.get("name")
        if not name or not isinstance(name, str):
            errors.append({"code": "FIELD-003", "message": f"Field {i} missing 'name'", "severity": "error"})
            continue

        if name in seen_names:
            errors.append({"code": "FIELD-004", "message": f"Duplicate field name: {name}", "severity": "error"})
        seen_names.add(name)

        field_type = field.get("type")
        if not field_type or field_type not in ALLOWED_FIELD_TYPES:
            errors.append({
                "code": "FIELD-005",
                "message": f"Field '{name}' has invalid type '{field_type}'. Allowed: {sorted(ALLOWED_FIELD_TYPES)}",
                "severity": "error",
            })

        fmt = field.get("format")
        if fmt and fmt not in ALLOWED_FIELD_FORMATS:
            errors.append({
                "code": "FIELD-006",
                "message": f"Field '{name}' has invalid format '{fmt}'. Allowed: {sorted(f for f in ALLOWED_FIELD_FORMATS if f)}",
                "severity": "warning",
            })

        if field_type == "enum" and not field.get("enum"):
            errors.append({
                "code": "FIELD-007",
                "message": f"Enum field '{name}' must have 'enum' list of allowed values",
                "severity": "error",
            })

    return errors


def validate_business_rules(rules, known_entities=None, known_fields=None):
    """Validate business rules against metamodel.

    Args:
        rules: list of rule dicts
        known_entities: list of known entity names (from component specs)
        known_fields: dict of entity_name -> list of field names

    Returns list of error dicts.
    """
    errors = []
    known_entities = known_entities or []
    known_fields = known_fields or {}

    if not isinstance(rules, list):
        return [{"code": "RULE-001", "message": "Rules must be a list", "severity": "error"}]

    seen_ids = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append({"code": "RULE-002", "message": f"Rule {i} must be a dict", "severity": "error"})
            continue

        rule_id = rule.get("id")
        if rule_id and rule_id in seen_ids:
            errors.append({"code": "RULE-003", "message": f"Duplicate rule ID: {rule_id}", "severity": "error"})
        if rule_id:
            seen_ids.add(rule_id)

        rule_type = rule.get("type")
        if rule_type not in ALLOWED_RULE_TYPES:
            errors.append({
                "code": "RULE-004",
                "message": f"Rule '{rule_id or i}' has invalid type '{rule_type}'. Allowed: {sorted(ALLOWED_RULE_TYPES)}",
                "severity": "error",
            })

        entity = rule.get("entity")
        if entity and known_entities and entity not in known_entities:
            errors.append({
                "code": "RULE-005",
                "message": f"Rule '{rule_id or i}' references unknown entity '{entity}'. Known: {known_entities}",
                "severity": "warning",
            })

        # Validate precondition field references
        entity_fields = known_fields.get(entity, [])
        for pc in rule.get("preconditions", []):
            if isinstance(pc, dict):
                field_name = pc.get("field", "")
                # Handle nested field references like "items.length"
                base_field = field_name.split(".")[0] if "." in field_name else field_name
                if entity_fields and base_field not in entity_fields:
                    errors.append({
                        "code": "RULE-006",
                        "message": f"Rule '{rule_id or i}' precondition references unknown field '{field_name}' on entity '{entity}'",
                        "severity": "warning",
                    })
                op = pc.get("operator")
                if op and op not in ALLOWED_OPERATORS:
                    errors.append({
                        "code": "RULE-007",
                        "message": f"Rule '{rule_id or i}' precondition has invalid operator '{op}'",
                        "severity": "error",
                    })

        severity = rule.get("severity")
        if severity and severity not in ALLOWED_SEVERITIES:
            errors.append({
                "code": "RULE-008",
                "message": f"Rule '{rule_id or i}' has invalid severity '{severity}'. Allowed: {sorted(ALLOWED_SEVERITIES)}",
                "severity": "warning",
            })

    return errors


def validate_integration_contract(contract):
    """Validate an integration contract against allowed values and forbidden combinations.

    Returns list of error dicts.
    """
    errors = []
    if not isinstance(contract, dict):
        return [{"code": "INT-001", "message": "Contract must be a dict", "severity": "error"}]

    protocol = contract.get("protocol")
    if protocol and protocol not in ALLOWED_PROTOCOLS:
        errors.append({
            "code": "INT-002",
            "message": f"Invalid protocol '{protocol}'. Allowed: {sorted(ALLOWED_PROTOCOLS)}",
            "severity": "error",
        })

    auth = contract.get("auth_method")
    if auth and auth not in ALLOWED_AUTH_METHODS:
        errors.append({
            "code": "INT-003",
            "message": f"Invalid auth method '{auth}'. Allowed: {sorted(ALLOWED_AUTH_METHODS)}",
            "severity": "error",
        })

    retry = contract.get("retry_policy", {})
    if isinstance(retry, dict) and retry.get("backoff"):
        if retry["backoff"] not in ALLOWED_BACKOFF_STRATEGIES:
            errors.append({
                "code": "INT-004",
                "message": f"Invalid backoff strategy '{retry['backoff']}'. Allowed: {sorted(ALLOWED_BACKOFF_STRATEGIES)}",
                "severity": "error",
            })

    # Check forbidden combinations
    for combo in FORBIDDEN_INTEGRATION_COMBOS:
        try:
            if combo["condition"](contract):
                errors.append({"code": "INT-010", "message": combo["message"], "severity": "error"})
        except Exception as e:
            logger.warning("Integration combo check failed: %s", e)

    return errors


def validate_deployment_spec(spec):
    """Validate a deployment spec for runtime/framework compatibility.

    Returns list of error dicts.
    """
    errors = []
    if not isinstance(spec, dict):
        return [{"code": "DEP-001", "message": "Deployment spec must be a dict", "severity": "error"}]

    runtime = spec.get("runtime")
    framework = spec.get("framework")
    database = spec.get("database")
    cache = spec.get("cache")
    messaging = spec.get("messaging")
    container_runtime = spec.get("container_runtime")

    if runtime and runtime not in ALLOWED_RUNTIMES:
        errors.append({
            "code": "DEP-002",
            "message": f"Invalid runtime '{runtime}'. Allowed: {sorted(ALLOWED_RUNTIMES)}",
            "severity": "error",
        })

    if framework and framework not in ALLOWED_FRAMEWORKS:
        errors.append({
            "code": "DEP-003",
            "message": f"Invalid framework '{framework}'. Allowed: {sorted(ALLOWED_FRAMEWORKS)}",
            "severity": "error",
        })

    # Runtime-framework compatibility
    if framework and runtime and framework in FRAMEWORK_RUNTIME_MAP:
        compatible = FRAMEWORK_RUNTIME_MAP[framework]
        if runtime not in compatible:
            errors.append({
                "code": "DEP-004",
                "message": f"Framework '{framework}' requires runtime in {sorted(compatible)}, got '{runtime}'",
                "severity": "error",
            })

    if database and database not in ALLOWED_DATABASES:
        errors.append({
            "code": "DEP-005",
            "message": f"Invalid database '{database}'. Allowed: {sorted(ALLOWED_DATABASES)}",
            "severity": "error",
        })

    if cache and cache not in ALLOWED_CACHES:
        errors.append({
            "code": "DEP-006",
            "message": f"Invalid cache '{cache}'. Allowed: {sorted(ALLOWED_CACHES)}",
            "severity": "error",
        })

    if messaging and messaging not in ALLOWED_MESSAGING:
        errors.append({
            "code": "DEP-007",
            "message": f"Invalid messaging '{messaging}'. Allowed: {sorted(ALLOWED_MESSAGING)}",
            "severity": "error",
        })

    if container_runtime and container_runtime not in ALLOWED_CONTAINER_RUNTIMES:
        errors.append({
            "code": "DEP-008",
            "message": f"Invalid container runtime '{container_runtime}'. Allowed: {sorted(ALLOWED_CONTAINER_RUNTIMES)}",
            "severity": "error",
        })

    # Scaling validation
    scaling = spec.get("scaling", {})
    if isinstance(scaling, dict):
        min_r = scaling.get("min_replicas", 1)
        max_r = scaling.get("max_replicas", 1)
        if min_r > max_r:
            errors.append({
                "code": "DEP-009",
                "message": f"min_replicas ({min_r}) cannot exceed max_replicas ({max_r})",
                "severity": "error",
            })

    # Forbidden deployment combinations
    for combo in FORBIDDEN_DEPLOYMENT_COMBOS:
        try:
            if combo["condition"](spec):
                errors.append({"code": "DEP-010", "message": combo["message"], "severity": "error"})
        except Exception as e:
            logger.warning("Deployment combo check failed: %s", e)

    return errors


def validate_cross_component_consistency(components, integrations):
    """Validate shared schema consistency across integration boundaries.

    Args:
        components: dict of component_name -> {"fields": [...]}
        integrations: dict of "source->target" -> {"payload_schema_ref": "EntityName"}

    Returns list of error dicts.
    """
    errors = []

    # Build field type index: entity_name -> field_name -> type
    field_types = {}
    for comp_name, comp_data in components.items():
        for field in comp_data.get("fields", []):
            key = field.get("name")
            if key:
                if comp_name not in field_types:
                    field_types[comp_name] = {}
                field_types[comp_name][key] = {
                    "type": field.get("type"),
                    "format": field.get("format"),
                }

    # Check cross-references: if OrderService has customer_id:uuid but CustomerService has id:integer, flag it
    for integration_key, integration_data in integrations.items():
        parts = integration_key.split("->")
        if len(parts) != 2:
            continue
        source_name = parts[0].strip()
        target_name = parts[1].strip()

        source_fields = field_types.get(source_name, {})
        target_fields = field_types.get(target_name, {})

        # Check for FK-like references (fields ending in _id that reference target)
        for fname, finfo in source_fields.items():
            if fname.endswith("_id"):
                # Check if target has matching "id" field
                target_id = target_fields.get("id")
                if target_id:
                    source_type = f"{finfo.get('type')}:{finfo.get('format', '')}"
                    target_type = f"{target_id.get('type')}:{target_id.get('format', '')}"
                    if source_type != target_type:
                        errors.append({
                            "code": "XCOMP-001",
                            "message": (
                                f"Type mismatch: {source_name}.{fname} is {finfo.get('type')}"
                                f"({finfo.get('format', '')}) but {target_name}.id is "
                                f"{target_id.get('type')}({target_id.get('format', '')})"
                            ),
                            "severity": "error",
                        })

    return errors
