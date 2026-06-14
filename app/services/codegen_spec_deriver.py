"""
Codegen Component Spec deriver (increment 2).

Pure function: an Architectural Genome (architectural_genome_schema.json) in,
one Codegen Component Spec (codegen_component_spec_schema.json) per module out.

No app/DB/IO dependency — `genome` dict in, list of spec dicts out — so it is
trivially testable and deterministic. The spec is the contract between genome and
generated code: build target + completeness gate + acceptance-check target.

Design rationale: docs/CODEGEN_COMPONENT_SPEC.md.
Increment 3 will point verify_codegen + verify_generation.sh at the output.
"""

import re
from typing import Any, Dict, List

SPEC_VERSION = "1.0.0"

# kinds/categories must match the enums in codegen_component_spec_schema.json
_DEFAULT_ROLES = ["admin", "user", "viewer"]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def derive_component_specs(genome: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return one component spec per genome module (deterministic order)."""
    language = genome.get("language", "python-fastapi")
    specs = []
    for module_key in genome.get("modules", {}):  # dict preserves insertion order
        module = genome["modules"][module_key]
        specs.append(_derive_module_spec(genome, module_key, module, language))
    return specs


# --------------------------------------------------------------------------- #
# Per-module derivation
# --------------------------------------------------------------------------- #

def _derive_module_spec(genome, module_key, module, language) -> Dict[str, Any]:
    root = module["aggregate_root"]
    base = _route_base(root)

    data_contract = _data_contract(module)
    state_machine = _state_machine(module)
    views = _views(module)
    pii_fields = _pii_fields(module)
    shared_deps = _shared_dependencies(genome, module)
    nfr = _nfr_contract(genome, pii_fields)

    spec: Dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "solution_id": genome["solution_id"],
        "module_key": module_key,
        "language": language,
        "module_type": module.get("module_type", "crud"),
        "archimate_sources": list(module.get("archimate_element_ids", [])),
        "data_contract": data_contract,
        "shared_dependencies": shared_deps,
        "expected_artifacts": _expected_artifacts(module_key, module, bool(state_machine), shared_deps),
        "acceptance_checks": _acceptance_checks(base, root, data_contract, state_machine, views, nfr, pii_fields),
    }
    if "genome_version" in genome:
        spec["genome_version"] = genome["genome_version"]
    if state_machine:
        spec["state_machine"] = state_machine
    if views:
        spec["views"] = views
    if nfr:
        spec["nfr_contract"] = nfr
    spec["completeness_gate"] = _completeness_gate(module, state_machine, pii_fields, shared_deps, data_contract)
    return spec


def _data_contract(module) -> Dict[str, Any]:
    fields_by_entity = module.get("fields", {}) or {}
    entities = []
    for entity_name in module.get("entities", []):
        entity_fields = []
        for f in fields_by_entity.get(entity_name, []):
            entry = {"name": f["name"], "type": f["type"]}
            if "required" in f:
                entry["required"] = f["required"]
            sens = f.get("sensitivity", "none")
            if sens != "none":
                entry["sensitivity"] = sens
            entry["verify"] = _field_verify(_route_base(module["aggregate_root"]), f, sens)
            entity_fields.append(entry)
        entities.append({"name": entity_name, "fields": entity_fields})

    contract: Dict[str, Any] = {
        "aggregate_root": module["aggregate_root"],
        "entities": entities,
    }
    operations = module.get("operations", {}) or {}
    if operations:
        ops = []
        for op_name, op in operations.items():
            authz = list(op.get("authorization", []))
            ops.append({
                "name": op_name,
                "type": op.get("type", "command"),
                "authorization": authz,
                "verify": _operation_verify(_route_base(module["aggregate_root"]), op_name, authz),
            })
        contract["operations"] = ops
    return contract


def _state_machine(module) -> Dict[str, Any]:
    sm = module.get("state_machine")
    if not sm:
        return {}
    states = list(sm.get("states", []))
    transitions = []
    for t in sm.get("transitions", []):
        authz = list(t.get("authorization", []))
        entry = {
            "from": t["from"],
            "to": t["to"],
            "trigger": t["trigger"],
            "verify": _transition_verify(t, states),
        }
        if t.get("guard"):
            entry["guard"] = t["guard"]
        if authz:
            entry["authorization"] = authz
        transitions.append(entry)
    return {"field": sm.get("field", "status"), "states": states, "transitions": transitions}


def _views(module) -> Dict[str, Any]:
    v = module.get("views") or {}
    out: Dict[str, Any] = {}
    if "list" in v:
        lv = v["list"]
        list_spec = {k: lv[k] for k in ("columns", "export_formats", "search_fields", "bulk_actions", "empty_state")
                     if k in lv}
        list_spec["verify"] = _list_verify(lv)
        out["list"] = list_spec
    if "detail" in v:
        out["detail"] = {k: v["detail"][k] for k in ("sections", "show_audit_trail", "related_lists")
                         if k in v["detail"]}
    if "create" in v:
        out["create"] = {k: v["create"][k] for k in ("fields", "wizard_steps") if k in v["create"]}
    return out


def _pii_fields(module) -> List[str]:
    """Dotted Entity.field for fields classified pii/restricted (from fields + sensitive_fields)."""
    out = []
    fields_by_entity = module.get("fields", {}) or {}
    for entity_name, fields in fields_by_entity.items():
        for f in fields:
            if f.get("sensitivity", "none") in ("pii", "restricted"):
                out.append(f"{entity_name}.{f['name']}")
    for sf in module.get("sensitive_fields", []):
        if sf.get("level") in ("pii", "restricted") and sf["field"] not in out:
            out.append(sf["field"])
    return out


def _shared_dependencies(genome, module) -> List[str]:
    deps = []
    views = module.get("views") or {}
    list_view = views.get("list", {})
    if list_view.get("export_formats"):
        deps.append("export_service")
    if list_view.get("search_fields") or genome.get("infrastructure", {}).get("search") == "postgresql_fts":
        deps.append("search_service")
    if genome.get("compliance", {}).get("audit_logging", "none") not in ("none", None):
        deps.append("audit_service")
    if genome.get("notifications", {}).get("channels"):
        deps.append("notification_service")
    if genome.get("file_storage", {}).get("provider", "none") not in ("none", None):
        deps.append("file_storage")
    if genome.get("webhooks", {}).get("enabled"):
        deps.append("webhook_service")
    # dedupe, preserve order
    seen = set()
    return [d for d in deps if not (d in seen or seen.add(d))]


def _nfr_contract(genome, pii_fields) -> Dict[str, Any]:
    security = genome.get("security", {}) or {}
    idp = genome.get("identity_provider", {}) or {}
    roles = idp.get("roles") or _DEFAULT_ROLES
    mt = security.get("multi_tenancy")
    tenant_isolation = bool(mt.get("enabled", True)) if isinstance(mt, dict) else bool(mt)
    rl = security.get("rate_limiting", {}) or {}
    rate_limit = rl.get("authenticated") or rl.get("default")
    audit_logged = genome.get("compliance", {}).get("audit_logging", "none") not in ("none", None)

    nfr: Dict[str, Any] = {
        "rbac_roles": list(roles),
        "tenant_isolation": tenant_isolation,
        "audit_logged": audit_logged,
    }
    if rate_limit:
        nfr["rate_limit"] = rate_limit
    if pii_fields:
        nfr["pii_fields"] = pii_fields
    verify_bits = []
    if tenant_isolation:
        verify_bits.append("cross-tenant GET -> 404")
    if pii_fields:
        verify_bits.append("pii fields masked in logs")
    if verify_bits:
        nfr["verify"] = "; ".join(verify_bits)
    return nfr


def _expected_artifacts(module_key, module, has_sm, shared_deps) -> List[Dict[str, Any]]:
    d = f"app/modules/{module_key}"
    arts = [
        {"path": f"{d}/models.py", "kind": "model"},
        {"path": f"{d}/schemas.py", "kind": "schema"},
        {"path": f"{d}/handler.py", "kind": "handler"},
        {"path": f"tests/test_{module_key}_crud.py", "kind": "test"},
    ]
    if has_sm:
        arts.append({"path": f"{d}/state_machine.py", "kind": "state_machine"})
        arts.append({"path": f"tests/test_{module_key}_state_machine.py", "kind": "test"})
    views = module.get("views") or {}
    if "list" in views:
        ref = ["export_service"] if views["list"].get("export_formats") else []
        art = {"path": f"{d}/ui/list.html", "kind": "view_list"}
        if ref:
            art["must_reference"] = ref
        arts.append(art)
    if "detail" in views:
        arts.append({"path": f"{d}/ui/detail.html", "kind": "view_detail"})
    if "create" in views:
        arts.append({"path": f"{d}/ui/create.html", "kind": "view_create"})
    return arts


def _completeness_gate(module, state_machine, pii_fields, shared_deps, data_contract) -> Dict[str, Any]:
    checks = []

    def check(cid, passed, detail):
        checks.append({"id": cid, "passed": bool(passed), "detail": detail})

    check("has_archimate_source", bool(module.get("archimate_element_ids")),
          "module must trace to >=1 ArchiMateElement (verify_codegen rejects untraced modules)")
    check("data_contract_nonempty",
          bool(data_contract["entities"]) and any(e["fields"] for e in data_contract["entities"]),
          "aggregate must declare at least one entity with fields")
    if state_machine:
        states = state_machine["states"]
        check("state_machine_has_initial_and_terminal", len(states) >= 2,
              "state machine needs >=2 states with a clear initial/terminal")
    if pii_fields:
        check("every_pii_field_has_masking_plan", True,
              f"{len(pii_fields)} pii/restricted field(s) require masking/encryption")
    export_formats = (module.get("views", {}) or {}).get("list", {}).get("export_formats")
    if export_formats:
        check("every_export_format_has_export_service_dep", "export_service" in shared_deps,
              "list declares export_formats -> export_service dependency must be present")
    return {"checks": checks}


def _acceptance_checks(base, root, data_contract, state_machine, views, nfr, pii_fields) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []

    def add(cid, category, assertion, src):
        checks.append({"id": cid, "category": category, "assertion": assertion, "source_genome_path": src})

    mk = f"modules.{base}"  # representative genome path prefix
    # Route checks per view
    if "list" in views:
        add("ac_route_list", "route", f"GET /{base} -> 200", f"{mk}.views.list")
    if "detail" in views:
        add("ac_route_detail", "route", f"GET /{base}/{{id}} -> 200", f"{mk}.views.detail")
    if "create" in views:
        add("ac_route_create", "route", f"POST /{base} -> 201", f"{mk}.views.create")

    # Required-field validation (first entity)
    if data_contract["entities"]:
        e = data_contract["entities"][0]
        for f in e["fields"]:
            if f.get("required"):
                add(f"ac_field_{f['name']}_required", "field_validation",
                    f"POST /{base} without {f['name']} -> 422", f"{mk}.fields.{e['name']}.{f['name']}")

    # State transitions: legal + illegal
    if state_machine:
        for t in state_machine["transitions"]:
            from_states = t["from"] if isinstance(t["from"], list) else [t["from"]]
            add(f"ac_transition_{t['trigger']}", "state_transition",
                f"{t['trigger']} from {from_states[0]} -> 200; illegal transition -> 409",
                f"{mk}.state_machine")
            if t.get("authorization"):
                add(f"ac_rbac_{t['trigger']}", "rbac",
                    f"{t['trigger']} -> 403 for role not in {t['authorization']}", f"{mk}.state_machine")

    # Operation RBAC
    for op in data_contract.get("operations", []):
        if op.get("authorization"):
            add(f"ac_rbac_op_{op['name']}", "rbac",
                f"{op['name']} -> 403 for role not in {op['authorization']}", f"{mk}.operations.{op['name']}")

    # PII masking
    for pf in pii_fields:
        add(f"ac_pii_{pf.replace('.', '_')}", "pii", f"{pf} masked in logs", "security")

    # Tenant isolation
    if nfr.get("tenant_isolation"):
        add("ac_tenant_isolation", "tenant_isolation", "GET other-org record -> 404", "security.multi_tenancy")

    # View behaviours
    lv = views.get("list", {})
    if lv.get("empty_state"):
        cta = lv["empty_state"].get("cta_action", "create")
        add("ac_empty_state", "empty_state", f"list with 0 rows renders cta_action={cta} button",
            f"{mk}.views.list.empty_state")
    if lv.get("export_formats"):
        fmt = lv["export_formats"][0]
        add("ac_export", "export", f"export button downloads {fmt} with the column set", f"{mk}.views.list.export_formats")

    return checks


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _route_base(pascal_name: str) -> str:
    """PascalCase aggregate -> kebab-case plural route base. WorkOrder -> work-orders."""
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", pascal_name).lower()
    return kebab if kebab.endswith("s") else kebab + "s"


def _field_verify(base, field, sensitivity) -> str:
    if field.get("required"):
        return f"POST /{base} without {field['name']} -> 422"
    if sensitivity in ("pii", "restricted"):
        return f"{field['name']} masked in logs; returned only to authorized roles"
    if field.get("unique"):
        return f"POST /{base} with duplicate {field['name']} -> 409"
    return f"{field['name']} round-trips through create/read unchanged"


def _operation_verify(base, op_name, authz) -> str:
    if authz:
        return f"{op_name} on /{base} -> 403 for role not in {authz}; 200 for an allowed role"
    return f"{op_name} on /{base} executes and returns its declared output"


def _transition_verify(t, states) -> str:
    from_states = t["from"] if isinstance(t["from"], list) else [t["from"]]
    base = f"{t['trigger']} from {from_states[0]} -> {t['to']}; an illegal transition is rejected with 409"
    if t.get("authorization"):
        base += f"; -> 403 for role not in {t['authorization']}"
    return base


def _list_verify(lv) -> str:
    bits = []
    if lv.get("empty_state"):
        bits.append("empty-state CTA renders at 0 rows")
    if lv.get("export_formats"):
        bits.append(f"export downloads {lv['export_formats'][0]} with the column set")
    if lv.get("search_fields"):
        bits.append("search bar filters on the declared fields")
    return "; ".join(bits) or "list renders the declared columns"
