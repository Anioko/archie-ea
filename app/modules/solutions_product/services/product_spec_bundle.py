"""
ProductSpecBundle — Parse SolutionSpecGenerator output into structured dataclasses.

Wave 1: 100% deterministic. No LLM calls. Pure transform from existing spec data.
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PathDef:
    path: str
    method: str
    operation_id: str
    summary: str
    request_schema: Optional[str]
    response_schema: str
    archimate_source_id: Optional[int]
    vendor: bool = False  # True for buy/vendor stub paths — skips barrel imports + response_model


@dataclass
class ServiceDef:
    name: str
    tag: str
    paths: list[PathDef] = field(default_factory=list)


@dataclass
class EventDef:
    name: str
    channel: str
    payload_schema: str


@dataclass
class InfraContext:
    nodes: list[dict] = field(default_factory=list)
    tech_services: list[dict] = field(default_factory=list)
    slas: list[dict] = field(default_factory=list)
    nfrs: list[dict] = field(default_factory=list)


@dataclass
class FieldDef:
    name: str
    type: str
    format: Optional[str] = None
    required: bool = False
    readonly: bool = False
    description: str = ""
    constraints: Optional[dict] = None
    enum: Optional[list] = None
    # Data architecture depth — indexes, composite keys, check constraints
    primary_key: bool = False
    unique: bool = False
    max_length: Optional[int] = None
    foreign_key: Optional[str] = None
    index: bool = False
    index_type: Optional[str] = None  # btree, gin, gist, hash
    default_value: Optional[str] = None  # SQL default expression
    check_constraint: Optional[str] = None  # CHECK expression
    enum_values: Optional[list] = None


@dataclass
class IndexDef:
    columns: list[str]
    type: str = "btree"  # btree, gin, gist, hash
    unique: bool = False
    where: Optional[str] = None  # partial index condition
    name: Optional[str] = None


@dataclass
class TableDef:
    name: str
    fields: list[FieldDef] = field(default_factory=list)
    composite_keys: list[list[str]] = field(default_factory=list)
    composite_indexes: list[IndexDef] = field(default_factory=list)
    unique_constraints: list[list[str]] = field(default_factory=list)
    description: str = ""


@dataclass
class ConditionExpr:
    """Structured condition for business rule compilation.

    Supports: eq, neq, in, not_in, gt, gte, lt, lte, between, matches, is_null, is_not_null.
    """
    field_name: str  # "order.total", "entity.status", "user.role"
    operator: str  # eq, neq, in, not_in, gt, gte, lt, lte, between, matches, is_null, is_not_null
    value: object = None  # literal, list (for in/not_in), tuple (for between), regex string (for matches)


@dataclass
class SideEffectDef:
    """Structured side effect for business rule compilation."""
    type: str  # emit_event, call_service, audit_log, send_notification, update_field
    name: str
    payload: dict = field(default_factory=dict)


@dataclass
class TransitionDef:
    from_state: str
    to_state: str
    trigger: str  # method name: "approve", "reject", "submit"
    guard: Optional[ConditionExpr] = None
    actions: list[SideEffectDef] = field(default_factory=list)


@dataclass
class StateMachineDef:
    entity: str
    field_name: str  # "status"
    states: list[str] = field(default_factory=list)  # ["draft", "pending", "approved", "rejected"]
    initial_state: str = ""
    transitions: list[TransitionDef] = field(default_factory=list)


@dataclass
class DecisionRowDef:
    """One row in a decision table (DMN-style)."""
    conditions: dict  # column_name -> value_or_range, e.g. {"amount": ">10000", "region": "EU"}
    outputs: dict     # column_name -> value, e.g. {"approval_required": True, "limit": 50000}
    annotation: str = ""


@dataclass
class DecisionModelDef:
    """DMN-style decision model that compiles to a pure decision service function.

    hit_policy:
      UNIQUE  — exactly one row fires (raises if multiple match)
      FIRST   — first matching row wins (ordered)
      COLLECT — all matching rows returned as list
      ANY     — all matching rows must agree on output (raises on conflict)
    """
    name: str         # function name, e.g. "evaluate_credit_limit"
    entity: str       # entity this decision applies to
    description: str
    inputs: list[str]   # input column names in evaluation order
    outputs: list[str]  # output column names
    rows: list[DecisionRowDef] = field(default_factory=list)
    hit_policy: str = "FIRST"  # UNIQUE, FIRST, COLLECT, ANY
    source: str = "brief_extraction"  # how this was created


@dataclass
class BusinessRuleDef:
    id: str
    type: str  # state_transition, validation, authorization, side_effect, computed_field
    entity: str
    trigger: str  # on_create, on_update, on_delete, before_save, after_save, or method name
    preconditions: list = field(default_factory=list)  # list of ConditionExpr dicts or legacy dicts
    postconditions: list = field(default_factory=list)  # list of ConditionExpr dicts
    side_effects: list = field(default_factory=list)  # list of SideEffectDef dicts
    severity: str = "error"
    priority: int = 1
    error_message: Optional[str] = None  # custom error message for validation rules
    description: Optional[str] = None


@dataclass
class IntegrationEndpointDef:
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    request_schema: Optional[str] = None
    response_schema: Optional[str] = None
    error_codes: list[int] = field(default_factory=list)
    description: str = ""


@dataclass
class IntegrationDef:
    name: str
    protocol: str
    auth_method: str
    sla: dict = field(default_factory=dict)
    retry_policy: dict = field(default_factory=dict)
    circuit_breaker: dict = field(default_factory=dict)
    direction: str = "publish"
    version: int = 0
    base_url: str = ""
    endpoints: list[IntegrationEndpointDef] = field(default_factory=list)
    request_headers: dict = field(default_factory=dict)
    timeout_s: float = 30.0


@dataclass
class NFRDef:
    """Structured non-functional requirement that compiles to middleware/config/code."""
    category: str  # performance, security, reliability, observability, compliance
    name: str  # rate_limit, circuit_breaker, audit_trail, structured_logging, cors, etc.
    target: dict = field(default_factory=dict)  # category-specific structured target
    enforcement: str = "middleware"  # middleware, config, infrastructure, code


@dataclass
class ScreenActionDef:
    label: str  # "Approve", "Delete", "Export"
    type: str  # button, menu_item, bulk_action, link
    api_endpoint: str  # POST /api/orders/:id/approve
    confirmation: bool = False
    permission: Optional[str] = None  # role required


@dataclass
class ComponentDef:
    type: str  # table, form, card, chart, badge, modal, tabs, stat_card
    entity: str
    fields: list[str] = field(default_factory=list)
    editable: bool = False
    config: dict = field(default_factory=dict)


@dataclass
class ScreenDef:
    name: str  # "OrderList", "OrderDetail", "OrderForm"
    type: str  # list, detail, form, dashboard, workflow
    entity: str
    url_path: str  # /orders, /orders/:id, /orders/new
    components: list[ComponentDef] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)  # API endpoints this screen calls
    actions: list[ScreenActionDef] = field(default_factory=list)
    parent_screen: Optional[str] = None  # for navigation hierarchy
    permission: Optional[str] = None


@dataclass
class SequenceDiagramStep:
    """A single step in a UML sequence diagram."""
    source_lifeline: str  # calling service/actor
    target_lifeline: str  # receiving service/actor
    message: str  # method call or description
    return_value: Optional[str] = None
    is_async: bool = False
    method_body_hint: Optional[str] = None


@dataclass
class SequenceDiagramDef:
    """A UML sequence diagram compiled from architecture specs."""
    name: str
    entity: str
    steps: list[SequenceDiagramStep] = field(default_factory=list)
    description: str = ""


@dataclass
class DeploymentDef:
    runtime: str = "python3.11"
    framework: str = "fastapi"
    database: str = "postgresql"
    cache: str = "none"
    messaging: str = "none"
    container_runtime: str = "kubernetes"
    scaling: dict = field(default_factory=lambda: {
        "min_replicas": 1, "max_replicas": 3,
        "metric": "cpu", "threshold": 80,
    })
    secrets_backend: str = "env-vars"
    observability: dict = field(default_factory=lambda: {
        "logging": "stdout", "metrics": "prometheus", "traces": "jaeger",
    })
    version: int = 0
    # Operational model — Phase 7 gap closure
    hpa: Optional[dict] = None  # {min: 2, max: 10, cpu_target: 70}
    pdb: Optional[dict] = None  # {min_available: 1}
    network_policies: list[dict] = field(default_factory=list)
    health_check_dependencies: list[str] = field(default_factory=list)  # ["database", "redis", "kafka"]


@dataclass
class ProductSpecBundle:
    solution_id: int
    solution_name: str
    openapi: dict
    asyncapi: Optional[dict]
    schemas: dict
    services: list[ServiceDef]
    events: list[EventDef]
    infra_context: InfraContext
    contract_tests: list[dict]
    maturity_score: float
    spec_hash: str
    # Confirmed spec data from SolutionArchiMateElement.spec_data
    confirmed_fields: dict = field(default_factory=dict)  # model_name -> [FieldDef]
    business_rules: dict = field(default_factory=dict)  # model_name -> [BusinessRuleDef]
    integrations: dict = field(default_factory=dict)  # integration_name -> IntegrationDef
    deployment: Optional[DeploymentDef] = None
    identity_provider: Optional[dict] = None  # OIDC provider config from spec_data
    ci_cd: Optional[dict] = None  # CI/CD pipeline config (provider, registry, namespaces)
    architecture_style: Optional[dict] = None  # Architecture style config (primary, patterns, service_mesh, api_gateway)
    business_process_flows: dict = field(default_factory=dict)  # service_name -> [{ action, description, method_body_hint, from, to }]
    seed_context: dict = field(default_factory=dict)  # canonical seed/adapters metadata
    provenance: dict = field(default_factory=dict)  # entity/field/rule provenance
    # Phase 1-7 gap closures: behavioral logic, data depth, NFR compilation, screens
    state_machines: dict = field(default_factory=dict)  # entity_name -> StateMachineDef
    tables: dict = field(default_factory=dict)  # table_name -> TableDef (enriched schema with indexes/constraints)
    nfr_specs: list = field(default_factory=list)  # list of NFRDef
    screens: list = field(default_factory=list)  # list of ScreenDef (frontend screen specifications)
    uml_diagrams: list = field(default_factory=list)  # list of SequenceDiagramDef
    mobile_config: dict = field(default_factory=dict)  # genome.mobile section (offline, push, features)
    webhook_config: dict = field(default_factory=dict)  # genome.webhooks section (enabled, delivery, subscriptions)
    product_config: dict = field(default_factory=dict)  # genome.product section (branding, colors, logo)
    multi_tenancy: dict = field(default_factory=dict)  # {enabled, strategy, tenant_field} from genome.security.multi_tenancy
    payment_config: dict = field(default_factory=dict)  # genome.payments section (provider, modes, webhook_secret_env)
    _genome_modules: dict = field(default_factory=dict)  # raw genome.modules dict for template access
    _genome_compliance: dict = field(default_factory=dict)  # raw genome.compliance dict for template access
    _genome_business_model: dict = field(default_factory=dict)  # raw genome.business_model dict for template access
    _genome_operations: dict = field(default_factory=dict)  # raw genome.operations dict for template access
    # Genome v2 fields
    workers: list = field(default_factory=list)  # list of worker dicts (name, trigger, queue, retry_policy)
    api_protocol: str = "rest"  # rest, graphql, both
    graphql_config: dict = field(default_factory=dict)  # genome.graphql section
    feature_flags: dict = field(default_factory=dict)  # genome.feature_flags section (provider, flags[])
    genome_events: dict = field(default_factory=dict)  # module_name -> list of event dicts (event-sourcing)
    genome_projections: dict = field(default_factory=dict)  # module_name -> list of projection dicts
    aggregate_types: dict = field(default_factory=dict)  # module_name -> "crud" or "event_sourced"
    composite_indexes: dict = field(default_factory=dict)  # entity_name -> list of index dicts
    # Decision models (DMN-style) — pure decision service functions
    decision_models: list = field(default_factory=list)  # list of DecisionModelDef
    # Gap-closure: DB model enrichments (all default-empty so old bundles stay valid)
    sla_load_config: dict = field(default_factory=dict)     # SolutionSLA → k6 thresholds/scenarios
    resilience_config: dict = field(default_factory=dict)   # RiskSnapshot → circuit breakers/retries
    compliance_config: dict = field(default_factory=dict)   # SolutionComplianceMapping → framework controls
    rbac_config: dict = field(default_factory=dict)         # SolutionStakeholder → roles/permissions
    adr_constraints: list = field(default_factory=list)     # SolutionADRDirect → tech/arch constraints
    integration_clients: list = field(default_factory=list) # SolutionIntegrationFlow → typed clients
    kpi_metrics: list = field(default_factory=list)         # SolutionGoal.kpis + SolutionOutcome → metrics


def _snake(name):
    """Convert a display name to snake_case."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", (name or "unknown").strip())
    return re.sub(r"_+", "_", s).strip("_").lower()


def _pascal(name):
    """Convert a display name to PascalCase. Strips non-alphanumeric for valid identifiers."""
    sanitized = re.sub(r"[^a-zA-Z0-9\s_\-]", "", (name or "Unknown").strip())
    words = re.split(r"[\s_\-]+", sanitized)
    result = "".join(w.capitalize() for w in words if w)
    return result or "Unknown"


def _extract_archimate_id(operation):
    """Extract x-archimate-source from an OpenAPI operation extension."""
    return operation.get("x-archimate-source")


def _parse_services(openapi_spec):
    """Parse OpenAPI paths into ServiceDef list, grouped by tag."""
    paths = openapi_spec.get("paths", {})
    tag_map = {}

    for path_str, path_item in paths.items():
        for method in ("get", "post", "put", "delete", "patch"):
            operation = path_item.get(method)
            if not operation:
                continue

            tags = operation.get("tags", ["default"])
            tag = tags[0] if tags else "default"
            op_id = operation.get("operationId", f"{method}_{_snake(path_str)}")
            summary = operation.get("summary", "")

            # Determine request schema
            request_schema = None
            req_body = operation.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                schema_ref = json_content.get("schema", {}).get("$ref", "")
                if schema_ref:
                    request_schema = schema_ref.split("/")[-1]

            # Determine response schema
            response_schema = "dict"
            responses = operation.get("responses", {})
            for code in ("200", "201"):
                resp = responses.get(code, {})
                content = resp.get("content", {})
                json_content = content.get("application/json", {})
                schema_ref = json_content.get("schema", {}).get("$ref", "")
                if schema_ref:
                    response_schema = schema_ref.split("/")[-1]
                    break

            archimate_id = _extract_archimate_id(operation)

            path_def = PathDef(
                path=path_str,
                method=method.upper(),
                operation_id=op_id,
                summary=summary,
                request_schema=request_schema,
                response_schema=response_schema,
                archimate_source_id=archimate_id,
            )

            if tag not in tag_map:
                tag_map[tag] = ServiceDef(
                    name=_pascal(tag) + "Service",
                    tag=tag,
                    paths=[],
                )
            tag_map[tag].paths.append(path_def)

    return list(tag_map.values())


def _parse_events(asyncapi_spec):
    """Parse AsyncAPI channels into EventDef list."""
    if not asyncapi_spec:
        return []

    events = []
    channels = asyncapi_spec.get("channels", {})
    for channel_name, channel_def in channels.items():
        # Extract from publish or subscribe
        for op_type in ("publish", "subscribe"):
            op = channel_def.get(op_type)
            if not op:
                continue
            msg = op.get("message", {})
            payload_ref = msg.get("payload", {}).get("$ref", "")
            payload_schema = payload_ref.split("/")[-1] if payload_ref else "dict"
            event_name = _pascal(channel_name.replace(".", "_"))
            events.append(EventDef(
                name=event_name,
                channel=channel_name,
                payload_schema=payload_schema,
            ))
    return events


def _build_infra_context(solution_id):
    """Query ArchiMate technology-layer elements for infrastructure context."""
    try:
        from app.models.solution_models import SolutionArchiMateElement
        tech_elements = SolutionArchiMateElement.query.filter_by(
            solution_id=solution_id,
            layer_type="technology",
        ).all()

        nodes = []
        tech_services = []
        for elem in tech_elements:
            entry = {
                "id": elem.element_id,
                "name": elem.element_name,
                "type": elem.element_type,
            }
            if elem.element_type and "node" in elem.element_type.lower():
                nodes.append(entry)
            else:
                tech_services.append(entry)

        # Pull SLAs
        slas = []
        try:
            from app.models.solution_sad_models import SolutionSLA
            sla_rows = SolutionSLA.query.filter_by(solution_id=solution_id).all()
            for s in sla_rows:
                slas.append({
                    "name": s.sla_name,
                    "availability": getattr(s, "availability_target", None),
                    "response_time_ms": getattr(s, "response_time_ms", None),
                })
        except Exception as e:
            logger.debug("Could not load SLAs for infra context: %s", e)

        # Pull NFRs (quality attributes)
        nfrs = []
        try:
            from app.models.solution_sad_models import SolutionQualityAttribute
            qa_rows = SolutionQualityAttribute.query.filter_by(solution_id=solution_id).all()
            for qa in qa_rows:
                nfrs.append({
                    "name": getattr(qa, "attribute_name", ""),
                    "category": getattr(qa, "category", ""),
                    "target": getattr(qa, "target_value", ""),
                })
        except Exception as e:
            logger.debug("Could not load quality attributes for infra context: %s", e)

        return InfraContext(nodes=nodes, tech_services=tech_services, slas=slas, nfrs=nfrs)
    except Exception:
        return InfraContext()


def _compute_spec_hash(openapi, asyncapi, schemas):
    """SHA256 of normalized bundle for drift detection.

    Strips volatile fields (timestamps in OpenAPI description) so the hash
    is deterministic for the same architecture input.
    """
    # Deep-copy openapi to avoid mutating the original
    stable_openapi = json.loads(json.dumps(openapi, sort_keys=True, default=str))
    # Remove timestamp from info.description (SolutionSpecGenerator embeds datetime.utcnow)
    info = stable_openapi.get("info", {})
    if "description" in info:
        del info["description"]
    canonical = json.dumps({
        "openapi": stable_openapi,
        "asyncapi": asyncapi,
        "schemas": schemas,
    }, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_product_spec_bundle(solution_id):
    """Build a ProductSpecBundle from an existing solution.

    Calls SolutionSpecGenerator.generate() and parses the result into
    structured dataclasses. 100% deterministic — no LLM, no network.
    """
    from app.modules.solutions_strategic.v2.services.spec_generator import (
        SolutionSpecGenerator,
    )
    from app.models.solution_models import Solution

    solution = Solution.query.get(solution_id)
    if not solution:
        raise ValueError(f"Solution {solution_id} not found")

    gen = SolutionSpecGenerator(solution_id)
    result = gen.generate()

    if not result.get("success"):
        errors = result.get("errors", [])
        raise ValueError(
            f"Spec generation failed: {'; '.join(e.get('message', '') for e in errors)}"
        )

    openapi = result.get("openapi", {})
    asyncapi = result.get("asyncapi")
    schemas = result.get("schemas", {})
    contract_tests = result.get("contract_tests", [])
    maturity_score = result.get("maturity_score", 0.0)

    services = _parse_services(openapi)
    events = _parse_events(asyncapi)
    infra_context = _build_infra_context(solution_id)
    spec_hash = _compute_spec_hash(openapi, asyncapi, schemas)

    # ── Read confirmed specs from SolutionArchiMateElement.spec_data ──
    # These are populated by the platform LLM via /infer endpoints and
    # confirmed by the architect on the blueprint page.
    confirmed_fields = {}
    business_rules = {}
    integrations = {}
    state_machines = {}
    tables = {}
    nfr_specs = []
    screens = []
    uml_diagrams = []
    deployment_spec = None
    identity_provider_config = None
    ci_cd_config = None
    try:
        from app.models.solution_archimate_element import SolutionArchiMateElement
        links = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()
        for link in links:
            sd = link.spec_data or {}
            elem_name = getattr(link, "element_name", None) or f"element_{link.element_id}"

            # Confirmed fields → model definitions
            if sd.get("fields") and sd.get("fields_status") == "confirmed":
                confirmed_fields[elem_name] = sd["fields"]

            # Business rules
            if sd.get("business_rules") and sd.get("business_rules_status") == "confirmed":
                business_rules[elem_name] = sd["business_rules"]

            # State machines — extract from confirmed spec_data
            if sd.get("state_machine") and sd.get("state_machine_status") == "confirmed":
                sm_data = sd["state_machine"]
                state_machines[elem_name] = sm_data

            # Table-level constraints — indexes, composite keys
            if sd.get("table_constraints"):
                tables[elem_name] = sd["table_constraints"]

            # Structured NFRs
            if sd.get("nfr_specs"):
                for nfr in sd["nfr_specs"]:
                    nfr_specs.append(nfr)

            # Screen definitions
            if sd.get("screens"):
                for screen in sd["screens"]:
                    screens.append(screen)

            # UML sequence diagrams
            if sd.get("sequence_diagrams"):
                for diag in sd["sequence_diagrams"]:
                    steps = []
                    for step in (diag.get("steps") or []):
                        steps.append(SequenceDiagramStep(
                            source_lifeline=step.get("source_lifeline", ""),
                            target_lifeline=step.get("target_lifeline", ""),
                            message=step.get("message", ""),
                            return_value=step.get("return_value"),
                            is_async=step.get("is_async", False),
                            method_body_hint=step.get("method_body_hint"),
                        ))
                    uml_diagrams.append(SequenceDiagramDef(
                        name=diag.get("name", f"sequence_{len(uml_diagrams)}"),
                        entity=elem_name,
                        steps=steps,
                        description=diag.get("description", ""),
                    ))

            # Integration contracts
            if sd.get("integrations"):
                for target_id, contract in sd["integrations"].items():
                    if contract.get("status") == "confirmed":
                        key = f"{elem_name}_to_{target_id}"
                        # Strip operations with no name to prevent invalid Python generation
                        if isinstance(contract.get("operations"), list):
                            contract = dict(contract)
                            contract["operations"] = [
                                op for op in contract["operations"]
                                if isinstance(op, dict) and op.get("name")
                            ]
                        integrations[key] = contract

            # Deployment (take the first confirmed one)
            if not deployment_spec and sd.get("deployment") and sd.get("deployment_status") == "confirmed":
                deployment_spec = sd["deployment"]

            # Identity provider (take the first one found)
            if not identity_provider_config and sd.get("identity_provider"):
                identity_provider_config = sd["identity_provider"]

            # CI/CD config (take the first one found)
            if not ci_cd_config and sd.get("ci_cd"):
                ci_cd_config = sd["ci_cd"]
    except Exception as e:
        logger.warning("build_product_spec_bundle: could not read spec_data: %s", e)

    # ── Infer state machines from business rules ──
    # If business_rules contain state_transition type rules but no explicit state machine
    # was defined, auto-derive a state machine from the transition rules.
    for entity_name, rules in business_rules.items():
        if entity_name in state_machines:
            continue  # explicit definition takes priority
        transition_rules = [r for r in (rules if isinstance(rules, list) else [])
                           if isinstance(r, dict) and r.get("type") == "state_transition"]
        if not transition_rules:
            continue
        states = set()
        transitions = []
        status_field = "status"  # default
        for rule in transition_rules:
            for pc in (rule.get("preconditions") or []):
                if isinstance(pc, dict):
                    if pc.get("operator") in ("==", "eq") and pc.get("field", "").endswith("status"):
                        states.add(pc["value"])
                        status_field = pc["field"].split(".")[-1] if "." in pc.get("field", "") else pc.get("field", "status")
            for post in (rule.get("postconditions") or []):
                if isinstance(post, dict) and post.get("field", "").endswith("status"):
                    states.add(post["value"])
            transitions.append({
                "trigger": rule.get("trigger", ""),
                "from_state": next((pc["value"] for pc in (rule.get("preconditions") or [])
                                    if isinstance(pc, dict) and pc.get("operator") in ("==", "eq")
                                    and pc.get("field", "").endswith("status")), ""),
                "to_state": next((post["value"] for post in (rule.get("postconditions") or [])
                                  if isinstance(post, dict) and post.get("field", "").endswith("status")), ""),
                "guard": None,
                "actions": rule.get("side_effects", []),
            })
        if states:
            state_machines[entity_name] = {
                "entity": entity_name,
                "field_name": status_field,
                "states": sorted(states),
                "initial_state": sorted(states)[0] if states else "",
                "transitions": transitions,
            }

    # ── Infer NFRs from InfraContext.nfrs if no structured nfr_specs exist ──
    if not nfr_specs and infra_context.nfrs:
        for qa in infra_context.nfrs:
            name = qa.get("name", "").lower().replace(" ", "_")
            category = qa.get("category", "").lower()
            target_str = qa.get("target", "")
            nfr_specs.append({
                "category": category or "general",
                "name": name,
                "target": {"description": target_str} if isinstance(target_str, str) else target_str,
                "enforcement": "middleware",
            })

    # ── RUNTIME-02: Enrich integrations with real IntegrationContract data ──
    # For each integration flow, check if the target application has an
    # IntegrationContract registered. If so, override placeholder URLs, auth,
    # and SLA with real values from the contract registry.
    try:
        from app.models.integration_contract import IntegrationContract
        from app.models.solution_sad_models import SolutionIntegrationFlow

        flows = SolutionIntegrationFlow.query.filter_by(solution_id=solution_id).all()
        for flow in flows:
            target_app_id = flow.target_app_id
            if not target_app_id:
                continue

            # Find the best contract for this target application
            contract = (
                IntegrationContract.query
                .filter_by(application_id=target_app_id)
                .order_by(IntegrationContract.updated_at.desc())
                .first()
            )
            if not contract:
                continue

            flow_key = f"flow_{flow.id}_{flow.flow_name or 'unnamed'}"

            # Build enriched integration entry from real contract
            enriched = {
                "protocol": contract.protocol or flow.protocol or "rest",
                "auth_method": contract.auth_method or "none",
                "auth_config": contract.auth_config or {},
                "base_url": contract.base_url,
                "environments": contract.environments or {},
                "sla": {},
                "retry_policy": {"max_retries": 3, "backoff": "exponential"},
                "circuit_breaker": {},
                "status": "confirmed",
                "contract_id": contract.id,
                "contract_name": contract.name,
                "version": contract.version,
            }

            if contract.sla_latency_ms:
                enriched["sla"]["max_latency_ms"] = contract.sla_latency_ms
                enriched["circuit_breaker"] = {
                    "failure_threshold": 5,
                    "timeout_ms": contract.sla_latency_ms * 3,
                }

            if contract.sla_availability:
                enriched["sla"]["availability"] = contract.sla_availability

            if contract.rate_limit:
                enriched["sla"]["rate_limit"] = contract.rate_limit

            integrations[flow_key] = enriched
            logger.debug(
                "Enriched integration %s with contract id=%d (%s)",
                flow_key, contract.id, contract.name,
            )
    except Exception as e:
        logger.debug("RUNTIME-02 contract enrichment skipped: %s", e)

    # ── RUNTIME-03: Inject enterprise registry contracts ──────────────────────
    # Add IntegrationContract rows with no application_id (platform-level enterprise
    # systems like SAP ECC, ServiceNow, MS Graph, etc.) so client.py is generated
    # with real auth_config and base_url even when no explicit linkage exists.
    # Also enrich any existing spec_data integrations by name-matching against the registry.
    try:
        from app.models.integration_contract import IntegrationContract as _IC
        import re as _re

        def _snake(s):
            return _re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")

        # Enrich existing integrations by name-matching against registry
        all_contracts = _IC.query.all()
        name_to_contract = {_snake(c.name): c for c in all_contracts}
        for ikey in list(integrations.keys()):
            iname = _snake(ikey)
            matched = name_to_contract.get(iname)
            if not matched:
                # Try substring match (e.g. "sap_ecc" matches "sap_ecc_odata")
                for cname, c in name_to_contract.items():
                    if iname in cname or cname in iname:
                        matched = c
                        break
            if matched:
                integrations[ikey].update({
                    "base_url": matched.base_url or integrations[ikey].get("base_url", ""),
                    "auth_config": matched.auth_config or integrations[ikey].get("auth_config", {}),
                    "environments": matched.environments or integrations[ikey].get("environments", {}),
                    "contract_id": matched.id,
                })

        # Inject enterprise contracts (no application_id) not already in the dict
        for contract in all_contracts:
            if contract.application_id is not None:
                continue  # skip app-specific contracts; RUNTIME-02 handles those
            ckey = _snake(contract.name)
            if ckey in integrations:
                continue  # already present; enriched above
            sla: dict = {}
            if contract.sla_latency_ms:
                sla["max_latency_ms"] = contract.sla_latency_ms
            if contract.sla_availability:
                sla["availability"] = contract.sla_availability
            if contract.rate_limit:
                sla["rate_limit"] = contract.rate_limit
            integrations[ckey] = {
                "protocol": (contract.protocol or "rest").upper(),
                "auth_method": contract.auth_method or "none",
                "auth_config": contract.auth_config or {},
                "base_url": contract.base_url or "",
                "environments": contract.environments or {},
                "sla": sla,
                "retry_policy": {"max_retries": 3, "backoff": "exponential"},
                "circuit_breaker": {"failure_threshold": 5, "timeout_ms": (contract.sla_latency_ms or 30000) * 3},
                "status": "confirmed",
                "contract_id": contract.id,
                "version": contract.version or "v1",
                "direction": "consume",
            }
            logger.debug("RUNTIME-03: injected enterprise contract %s (id=%d)", contract.name, contract.id)
    except Exception as e:
        logger.warning("RUNTIME-03 enterprise contract injection skipped (non-fatal): %s", e)

    # Also check solution-level metadata for identity_provider, ci_cd, architecture_style
    architecture_style_config = None
    if not identity_provider_config:
        try:
            sol_meta = getattr(solution, "metadata_json", None) or {}
            if isinstance(sol_meta, str):
                sol_meta = json.loads(sol_meta)
            if sol_meta.get("identity_provider"):
                identity_provider_config = sol_meta["identity_provider"]
            if not ci_cd_config and sol_meta.get("ci_cd"):
                ci_cd_config = sol_meta["ci_cd"]
        except Exception as e:
            logger.debug("Could not read identity_provider/ci_cd from solution metadata: %s", e)
    else:
        try:
            sol_meta = getattr(solution, "metadata_json", None) or {}
            if isinstance(sol_meta, str):
                sol_meta = json.loads(sol_meta)
        except Exception:
            sol_meta = {}

    # Read architecture_style from solution metadata
    try:
        if not sol_meta:
            sol_meta = getattr(solution, "metadata_json", None) or {}
            if isinstance(sol_meta, str):
                sol_meta = json.loads(sol_meta)
        if sol_meta.get("architecture_style"):
            architecture_style_config = sol_meta["architecture_style"]
    except Exception as e:
        logger.debug("Could not read architecture_style from solution metadata: %s", e)

    return ProductSpecBundle(
        solution_id=solution_id,
        solution_name=solution.name,
        openapi=openapi,
        asyncapi=asyncapi,
        schemas=schemas,
        services=services,
        events=events,
        infra_context=infra_context,
        contract_tests=contract_tests,
        maturity_score=maturity_score,
        spec_hash=spec_hash,
        confirmed_fields=confirmed_fields,
        business_rules=business_rules,
        integrations=integrations,
        deployment=deployment_spec,
        identity_provider=identity_provider_config,
        ci_cd=ci_cd_config,
        architecture_style=architecture_style_config,
        state_machines=state_machines,
        tables=tables,
        nfr_specs=nfr_specs,
        screens=screens,
        uml_diagrams=uml_diagrams,
    )
