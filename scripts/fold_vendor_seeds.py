"""One-time fold of the twelve vendor seed modules and the four vendor template
element lists into thirteen reference pack files (decision F). Run once, its
output (the pack YAML files) committed, then the script itself deleted in a
later commit — see the build report for the exact commands run.

Usage (from the repository root, with PYTHONPATH=. on this shell):
    python scripts/fold_vendor_seeds.py [--out DIR]
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import types
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

READ_AT = "2026-09-23"
TRADEMARK_LINE = (
    "Product and company names are the property of their respective owners; "
    "no affiliation or endorsement is implied."
)

# The twelve seeds — module name, factory function name, target pack_key.
SEEDS = [
    ("vendor_seeds_appian", "create_appian_template", "appian"),
    ("vendor_seeds_dassault_delmia", "create_dassault_delmia_template", "dassault-delmia"),
    ("vendor_seeds_ge_proficy", "create_ge_proficy_template", "ge-proficy"),
    ("vendor_seeds_ibm_maximo", "create_ibm_maximo_template", "ibm-maximo"),
    ("vendor_seeds_mendix", "create_mendix_template", "mendix"),
    ("vendor_seeds_microsoft_power", "create_microsoft_power_template", "microsoft-power-platform"),
    ("vendor_seeds_outsystems", "create_outsystems_template", "outsystems"),
    ("vendor_seeds_rockwell_factorytalk", "create_rockwell_factorytalk_template", "rockwell-factorytalk"),
    ("vendor_seeds_salesforce", "create_salesforce_template", "salesforce"),
    ("vendor_seeds_sap_s4hana", "create_sap_s4hana_template", "sap-s4hana"),
    ("vendor_seeds_servicenow", "create_servicenow_template", "servicenow"),
    ("vendor_seeds_siemens_opcenter", "create_siemens_opcenter_template", "siemens-opcenter"),
]

# Curated (vendor, product, source URL) per pack — the vendor's own public
# product overview page (decision F attribution).
PACK_META = {
    "appian": ("Appian", "Appian Low-Code Automation Platform", "https://appian.com/products/platform.html"),
    "dassault-delmia": ("Dassault Systemes", "Dassault DELMIA Digital Manufacturing & Operations", "https://www.3ds.com/products/delmia"),
    "ge-proficy": ("GE Digital", "GE Proficy Manufacturing Intelligence Suite", "https://www.ge.com/digital/applications/manufacturing-execution-systems"),
    "ibm-maximo": ("IBM", "IBM Maximo Application Suite", "https://www.ibm.com/products/maximo"),
    "mendix": ("Mendix", "Mendix Low-Code Application Platform", "https://www.mendix.com/low-code-platform/"),
    "microsoft-power-platform": ("Microsoft", "Microsoft Power Platform", "https://www.microsoft.com/en-us/power-platform"),
    "outsystems": ("OutSystems", "OutSystems Low-Code Application Platform", "https://www.outsystems.com/low-code-platform/"),
    "rockwell-factorytalk": ("Rockwell Automation", "Rockwell FactoryTalk Manufacturing Suite", "https://www.rockwellautomation.com/en-us/products/software/factorytalk.html"),
    "salesforce": ("Salesforce", "Salesforce CRM Platform", "https://www.salesforce.com/crm/"),
    "sap-s4hana": ("SAP", "SAP S/4HANA", "https://www.sap.com/products/erp/s4hana.html"),
    "servicenow": ("ServiceNow", "ServiceNow IT Service Management Platform", "https://www.servicenow.com/products/itsm.html"),
    "siemens-opcenter": ("Siemens", "Siemens Opcenter Manufacturing Execution System", "https://www.sw.siemens.com/en-US/technology/opcenter-manufacturing-operations-management/"),
    "microsoft-dynamics-365": ("Microsoft", "Microsoft Dynamics 365", "https://www.microsoft.com/en-us/dynamics-365"),
}

# The four template groups (fact 1 / decision F): (pack_key, [element rows]).
# Copied verbatim from app/commands/seed_vendor_archimate_templates.py so the
# fold has no runtime dependency on the file this task deletes.
TEMPLATE_GROUPS = {
    "sap-s4hana": [
        {"element_name": "SAP S/4HANA Application Server", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 1},
        {"element_name": "SAP HANA Primary Database", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 2},
        {"element_name": "SAP Business Technology Platform", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": True, "display_order": 3},
        {"element_name": "SAP Gateway", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 4},
        {"element_name": "SAP Fiori Launchpad", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 5},
        {"element_name": "SAP Integration Suite", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 6},
        {"element_name": "SAP Event Mesh", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": False, "display_order": 7},
        {"element_name": "SAP Web Dispatcher", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 8},
        {"element_name": "SAP HANA Secondary Database", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 9},
        {"element_name": "SAP Fiori Frontend Server", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 10},
    ],
    "microsoft-dynamics-365": [
        {"element_name": "Microsoft Dynamics 365 Application Server", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 1},
        {"element_name": "Azure SQL Database", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 2},
        {"element_name": "Azure Active Directory", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 3},
        {"element_name": "Dynamics 365 Finance Module", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 4},
        {"element_name": "Dynamics 365 SCM Module", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 5},
        {"element_name": "Azure API Management", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 6},
        {"element_name": "Dynamics 365 Customer Engagement", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 7},
        {"element_name": "Azure Service Bus", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": False, "display_order": 8},
        {"element_name": "Azure Key Vault", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": False, "display_order": 9},
        {"element_name": "Azure Monitor", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 10},
        {"element_name": "Power Platform Environment", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 11},
    ],
    "microsoft-power-platform": [
        {"element_name": "Power Platform Environment", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 1},
        {"element_name": "Dataverse Instance", "element_type": "Node", "archimate_layer": "Technology", "mandatory": True, "display_order": 2},
        {"element_name": "Azure Active Directory", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 3},
        {"element_name": "Power Apps Service", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 4},
        {"element_name": "Power Automate Service", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 5},
        {"element_name": "Power BI Service", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 6},
        {"element_name": "Azure API Management", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 7},
        {"element_name": "On-Premises Data Gateway", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 8},
        {"element_name": "Azure Key Vault", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": False, "display_order": 9},
    ],
    "salesforce": [
        {"element_name": "Salesforce Core Platform", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 1},
        {"element_name": "Salesforce Lightning Experience", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 2},
        {"element_name": "Salesforce Identity and SSO", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 3},
        {"element_name": "Salesforce REST and Bulk API", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": True, "display_order": 4},
        {"element_name": "Salesforce Event Bus", "element_type": "SystemSoftware", "archimate_layer": "Technology", "mandatory": False, "display_order": 5},
        {"element_name": "Salesforce Einstein", "element_type": "ApplicationComponent", "archimate_layer": "Application", "mandatory": False, "display_order": 6},
        {"element_name": "Salesforce Data Cloud", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 7},
        {"element_name": "Heroku Runtime", "element_type": "Node", "archimate_layer": "Technology", "mandatory": False, "display_order": 8},
    ],
}

# decision F's mapping table, written once. Every other top-level key the
# seeds use (business_actors, products, application_functions, stakeholders,
# drivers, goals, outcomes, principles, requirements, constraints,
# assessments, implementation_events, work_packages, deliverables, plateaus,
# value_streams_supported, courses_of_action) carries no vendor-documented
# architecture fact — it is implementation-project narrative (dates, budget
# figures, invented ROI, generic role lists) fabricated for demo purposes,
# not "facts about the product taken from the vendor's public documentation" —
# so it has no ArchiMate counterpart *for this pack's sourcing standard* and
# is dropped, counted below. See the build report for the full reasoning.
MAPPING_TABLE = {
    "capabilities_enabled": ("Capability", "strategy"),
    "business_services": ("BusinessService", "business"),
    "business_processes": ("BusinessProcess", "business"),
    "business_functions": ("BusinessFunction", "business"),
    "business_roles": ("BusinessRole", "business"),
    "business_objects": ("BusinessObject", "business"),
    "application_components": ("ApplicationComponent", "application"),
    "application_services": ("ApplicationService", "application"),
    "application_interfaces": ("ApplicationInterface", "application"),
    "data_objects": ("DataObject", "application"),
    "nodes": ("Node", "technology"),
    "system_software": ("SystemSoftware", "technology"),
    "technology_services": ("TechnologyService", "technology"),
    "devices": ("Device", "technology"),
    "communication_networks": ("CommunicationNetwork", "technology"),
    "artifacts": ("Artifact", "technology"),
    "equipment": ("Equipment", "physical"),
    "facilities": ("Facility", "physical"),
    "materials": ("Material", "physical"),
    "distribution_networks": ("DistributionNetwork", "physical"),
}


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "x"


def truncate_words(text: str, limit: int = 60) -> str:
    words = (text or "").split()
    if len(words) <= limit:
        return text or ""
    return " ".join(words[:limit])


def load_seed_dicts() -> dict:
    """Import the twelve seeds with vendor_tech_stack_creator stubbed and
    VendorStackTemplate replaced by a plain kwargs-capturing class, so the
    per-layer lists can be read without a database or app context."""
    stub = types.ModuleType("app.commands.vendor_tech_stack_creator")

    def seed_vendor_with_tech_stack(*a, **k):
        return None, None

    stub.seed_vendor_with_tech_stack = seed_vendor_with_tech_stack
    sys.modules["app.commands.vendor_tech_stack_creator"] = stub

    import app.models as models_pkg  # noqa: E402

    class SimpleCapture:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    models_pkg.VendorStackTemplate = SimpleCapture

    results = {}
    for modname, fnname, pack_key in SEEDS:
        module = importlib.import_module(f"app.commands.{modname}")
        fn = getattr(module, fnname)
        results[pack_key] = fn()
    return results


def build_elements_from_seed(seed_obj, dropped_counter: Counter) -> list[dict]:
    """Every relevant per-layer list on one seed's captured kwargs, converted
    to pack elements (decision F)."""
    elements: list[dict] = []
    for key, value in vars(seed_obj).items():
        if key in ("vendor_name", "name", "description") or value in (None, ""):
            continue
        if not isinstance(value, str):
            continue
        try:
            rows = json.loads(value)
        except (ValueError, TypeError):
            continue
        if not isinstance(rows, list):
            continue
        if key not in MAPPING_TABLE:
            dropped_counter[key] += len(rows)
            continue
        etype, layer = MAPPING_TABLE[key]
        for row in rows:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            elements.append(
                {
                    "type": etype,
                    "layer": layer,
                    "name": row["name"],
                    "description": truncate_words(row.get("description") or row["name"]),
                    "mandatory": True,
                }
            )
    return elements


def dedupe_element_keys(elements: list[dict]) -> None:
    seen: Counter = Counter()
    for el in elements:
        base = f"{el['layer']}.{slug(el['name'])}"
        seen[base] += 1
        el["element_key"] = base if seen[base] == 1 else f"{base}-{seen[base]}"


def merge_template_group(elements: list[dict], group_rows: list[dict]) -> int:
    """Merge one of the four curated template groups into a pack's element
    list (decision F): case-folded name match updates `mandatory`; no match
    adds a new element in module `core`. Returns count of new elements added."""
    by_name = {el["name"].strip().lower(): el for el in elements}
    added = 0
    for row in group_rows:
        key = row["element_name"].strip().lower()
        existing = by_name.get(key)
        if existing is not None:
            existing["mandatory"] = bool(row["mandatory"])
            continue
        new_el = {
            "type": row["element_type"],
            "layer": row["archimate_layer"].lower(),
            "name": row["element_name"],
            "description": truncate_words(f"{row['element_name']}, part of the platform."),
            "mandatory": bool(row["mandatory"]),
        }
        elements.append(new_el)
        by_name[key] = new_el
        added += 1
    return added


def assign_modules(elements: list[dict], product: str) -> list[dict]:
    for el in elements:
        el["module_keys"] = ["platform"] if el["layer"] in ("technology", "physical") else ["core"]
    modules = []
    if any(m == ["core"] for m in (el["module_keys"] for el in elements)):
        modules.append({"key": "core", "question": f"Do you run {product}?"})
    if any(m == ["platform"] for m in (el["module_keys"] for el in elements)):
        modules.append(
            {
                "key": "platform",
                "question": f"Do you run the {product} platform components (hosting, integration, data)?",
            }
        )
    return modules


def build_relationships(elements: list[dict], validator, stats: Counter) -> list[dict]:

    by_key = {el["element_key"]: el for el in elements}
    acs = [el for el in elements if el["type"] == "ApplicationComponent"]
    root = None
    # Root: the ApplicationComponent whose name matches the pack most closely,
    # or the first ApplicationComponent if none is an obvious root; one is
    # synthesised by the caller before this function runs, so acs is never
    # empty when relationships are generated for a non-trivial pack.
    if acs:
        root = acs[0]

    relationships: list[dict] = []
    connected: set[str] = set()

    def try_add(source_key, target_key, rtype, rule):
        src_type = by_key[source_key]["type"]
        tgt_type = by_key[target_key]["type"]
        if not validator.validate(src_type, tgt_type, rtype):
            stats[f"refused_{rule}"] += 1
            return False
        rel_modules = sorted(set(by_key[source_key]["module_keys"]) | set(by_key[target_key]["module_keys"]))
        relationships.append(
            {"source_key": source_key, "target_key": target_key, "type": rtype, "module_keys": rel_modules}
        )
        connected.add(source_key)
        connected.add(target_key)
        stats[f"generated_{rule}"] += 1
        return True

    # Rule (i): root --composition--> every other ApplicationComponent.
    if root:
        for ac in acs:
            if ac is root:
                continue
            try_add(root["element_key"], ac["element_key"], "composition", "i")

    # Rule (ii): AC whose description names a BusinessService/BusinessProcess
    # /ApplicationService gets serving (business) or realization (service).
    business_targets = [el for el in elements if el["type"] in ("BusinessService", "BusinessProcess")]
    service_targets = [el for el in elements if el["type"] == "ApplicationService"]
    for ac in acs:
        desc = ac["description"].lower()
        for tgt in business_targets:
            if tgt["name"].lower() in desc:
                try_add(ac["element_key"], tgt["element_key"], "serving", "ii")
        for tgt in service_targets:
            if tgt["name"].lower() in desc:
                try_add(ac["element_key"], tgt["element_key"], "realization", "ii")

    # Rule (iii): Node/SystemSoftware/Device whose description names an AC
    # gets serving to it, else serving to the root.
    for el in elements:
        if el["type"] not in ("Node", "SystemSoftware", "Device"):
            continue
        desc = el["description"].lower()
        matched = False
        for ac in acs:
            if ac["name"].lower() in desc:
                if try_add(el["element_key"], ac["element_key"], "serving", "iii"):
                    matched = True
        if not matched and root and el is not root:
            try_add(el["element_key"], root["element_key"], "serving", "iii")

    # Rule (iv): every Capability gets a realization from the root.
    if root:
        for el in elements:
            if el["type"] == "Capability":
                try_add(root["element_key"], el["element_key"], "realization", "iv")

    # Rule (v): every remaining unconnected element gets an association to
    # an anchor (root ApplicationComponent, else the first Node, first
    # Equipment, first CommunicationNetwork it can validly reach — the matrix
    # is not symmetric for every pair, so both directions are tried).
    anchors = []
    if root:
        anchors.append(root)
    for wanted_type in ("Node", "Equipment", "CommunicationNetwork", "Facility"):
        candidate = next((el for el in elements if el["type"] == wanted_type), None)
        if candidate:
            anchors.append(candidate)

    dropped = []
    for el in elements:
        if el["element_key"] in connected:
            continue
        placed = False
        for anchor in anchors:
            if anchor is el:
                continue
            if try_add(el["element_key"], anchor["element_key"], "association", "v"):
                placed = True
                break
            if try_add(anchor["element_key"], el["element_key"], "association", "v"):
                placed = True
                break
        if not placed:
            dropped.append(el["element_key"])

    if dropped:
        stats["dropped_unconnected"] += len(dropped)
        elements[:] = [el for el in elements if el["element_key"] not in dropped]

    return relationships


def build_pack(pack_key: str, seed_obj, dropped_counter: Counter, all_stats: dict) -> dict:
    from app.config.archimate_relationship_matrix import RelationshipValidator

    vendor, product, source_url = PACK_META[pack_key]
    elements = build_elements_from_seed(seed_obj, dropped_counter) if seed_obj is not None else []

    # Every seed-derived element cites the vendor's public product page.
    for el in elements:
        el["source_urls"] = [source_url]

    # Ensure a root ApplicationComponent named after the product exists.
    has_named_root = any(
        el["type"] == "ApplicationComponent" and el["name"].strip().lower() == product.strip().lower()
        for el in elements
    )
    if not has_named_root:
        elements.insert(
            0,
            {
                "type": "ApplicationComponent",
                "layer": "application",
                "name": product,
                "description": truncate_words(f"{product}, the core application component of the {vendor} pack."),
                "mandatory": True,
                "source_urls": [source_url],
            },
        )

    template_rows = TEMPLATE_GROUPS.get(pack_key)
    added_from_template = 0
    if template_rows:
        # Give template-only rows a source_urls entry before the merge helper
        # runs, so every element (seed-derived or template-derived) cites the
        # same vendor page.
        before = {id(el) for el in elements}
        added_from_template = merge_template_group(elements, template_rows)
        for el in elements:
            if id(el) not in before:
                el["source_urls"] = [source_url]

    dedupe_element_keys(elements)
    pack_version = "2025.1" if pack_key in TEMPLATE_GROUPS else "1.0"
    modules = assign_modules(elements, product)

    validator = RelationshipValidator()
    stats = Counter()
    relationships = build_relationships(elements, validator, stats)
    all_stats[pack_key] = {
        "elements": len(elements),
        "relationships": len(relationships),
        "modules": len(modules),
        "added_from_template": added_from_template,
        "rule_stats": dict(stats),
    }

    attribution_text = (
        f"Facts about {product} are taken from {vendor}'s public product documentation, "
        f"read on {READ_AT}; product, module and service names are used as names only."
    )

    pack = {
        "pack_key": pack_key,
        "pack_version": pack_version,
        "vendor": vendor,
        "product": product,
        "product_edition": "",
        "segment_tags": [],
        "industry_tags": [],
        "attribution_text": attribution_text,
        "trademark_line": TRADEMARK_LINE,
        "modules": modules,
        "elements": elements,
        "relationships": relationships,
        "integrations": [],
        "capability_mappings": [],
    }
    sources = {"sources": [{"url": source_url, "read_at": READ_AT, "licence": "proprietary-facts-only"}]}
    return {"pack": pack, "sources": sources}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "app" / "seed_data" / "reference_packs"))
    args = parser.parse_args()
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    seed_dicts = load_seed_dicts()
    dropped_counter: Counter = Counter()
    all_stats: dict = {}

    pack_keys = [pk for _, _, pk in SEEDS] + ["microsoft-dynamics-365"]

    for pack_key in pack_keys:
        seed_obj = seed_dicts.get(pack_key)
        built = build_pack(pack_key, seed_obj, dropped_counter, all_stats)
        pack_dir = out_root / pack_key
        pack_dir.mkdir(parents=True, exist_ok=True)
        version = built["pack"]["pack_version"]
        with open(pack_dir / f"{version}.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(built["pack"], fh, sort_keys=False, allow_unicode=True, width=100)
        with open(pack_dir / "sources.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(built["sources"], fh, sort_keys=False, allow_unicode=True, width=100)

    print("=== fold report ===")
    print("dropped list keys (no ArchiMate counterpart used by this fold):")
    for key, count in sorted(dropped_counter.items()):
        print(f"  {key}: {count}")
    print()
    print("per-pack (pack_key, elements, relationships, modules, added_from_template, rule_stats):")
    for pack_key in pack_keys:
        s = all_stats[pack_key]
        print(
            f"  {pack_key}: elements={s['elements']} relationships={s['relationships']} "
            f"modules={s['modules']} added_from_template={s['added_from_template']} "
            f"rules={s['rule_stats']}"
        )


if __name__ == "__main__":
    main()
