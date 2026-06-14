"""Domain seed resolver for seed-first code generation accuracy."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


_CATALOG_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "seed_data",
        "codegen_domain_seed_catalog.json",
    )
)


def _snake(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def _pascal(value: str) -> str:
    words = re.split(r"[\s_\-]+", re.sub(r"[^a-zA-Z0-9\s_\-]", "", value or ""))
    return "".join(w.capitalize() for w in words if w) or "Unknown"


def _normalize_vendor(vendor_name: str) -> str:
    name = (vendor_name or "").lower()
    if "salesforce" in name or "sfdc" in name:
        return "SALESFORCE"
    if "sap" in name:
        return "SAP"
    if "dynamics" in name or "microsoft" in name:
        return "MICROSOFT_DYNAMICS"
    return ""


def _parse_condition(condition: str) -> Dict[str, str]:
    text = (condition or "").strip()
    op_match = re.search(r"(>=|<=|==|!=|>|<)", text)
    if not op_match:
        return {
            "subject": _snake(text.split(" ")[0] if text else "value"),
            "operator": "!=",
            "threshold": "null",
        }
    operator = op_match.group(1)
    parts = text.split(operator, 1)
    left = _snake(parts[0].strip()) or "value"
    right = parts[1].strip().strip("'\"") if len(parts) > 1 else ""
    return {"subject": left, "operator": operator, "threshold": right or "value"}


class DomainSeedResolver:
    """Resolve domain seeds and vendor adapters for a solution."""

    @staticmethod
    def load_catalog() -> Dict[str, Any]:
        try:
            with open(_CATALOG_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {"version": "unknown", "domains": {}, "vendor_adapters": {}}

    @classmethod
    def _infer_vendor_keys(cls, solution) -> List[str]:
        vendor_keys: List[str] = []
        try:
            from app.modules.solutions_strategic.v2.services.vendor_template_service import (
                VendorTemplateService,
            )

            vendor_keys = VendorTemplateService.get_solution_vendor_keys(solution)
            if vendor_keys:
                return vendor_keys
        except Exception as exc:
            logger.debug("suppressed error in DomainSeedResolver._infer_vendor_keys (app/modules/codegen/services/domain_seed_service.py): %s", exc)

        try:
            for vp in (solution.vendor_products or []):
                org = getattr(vp, "vendor_organization", None)
                key = _normalize_vendor(getattr(org, "name", ""))
                if key and key not in vendor_keys:
                    vendor_keys.append(key)
        except Exception as exc:
            logger.debug("suppressed error in DomainSeedResolver._infer_vendor_keys (app/modules/codegen/services/domain_seed_service.py): %s", exc)
        return vendor_keys

    @classmethod
    def _build_seed_index(cls, vendor_keys: List[str], catalog: Dict[str, Any]) -> Dict[str, Any]:
        adapters = catalog.get("vendor_adapters", {})
        domains = catalog.get("domains", {})
        seed_index: Dict[str, Any] = {}
        for key in vendor_keys:
            adapter = adapters.get(key) or {}
            domain_name = adapter.get("domain")
            domain = domains.get(domain_name, {})
            entities = domain.get("entities", {})
            for entity_name, entity_seed in entities.items():
                canonical = _pascal(entity_name)
                aliases = [_snake(a) for a in entity_seed.get("aliases", [])]
                aliases.extend([_snake(entity_name), _snake(canonical)])
                seed_index[canonical] = {
                    "vendor_key": key,
                    "domain": domain_name,
                    "entity": canonical,
                    "aliases": sorted(set(aliases)),
                    "required_fields": entity_seed.get("required_fields", []),
                    "optional_fields": entity_seed.get("optional_fields", []),
                    "rule_patterns": entity_seed.get("rule_patterns", []),
                    "adapter_mapping": (adapter.get("entity_mappings", {}) or {}).get(canonical, {}),
                }
        return seed_index

    @classmethod
    def _apply_seed_fields(cls, classes: List[Dict[str, Any]], seed_index: Dict[str, Any]) -> Dict[str, Any]:
        provenance = {"entities": {}, "fields": {}}
        coverage = {"seeded_entities": 0, "expected_entities": len(seed_index), "missing_required_fields": []}

        for cls_row in classes:
            cls_name = _pascal(cls_row.get("name", ""))
            cls_alias = _snake(cls_name)
            seed = None
            for seed_name, seed_spec in seed_index.items():
                if cls_alias in seed_spec["aliases"] or _snake(seed_name) == cls_alias:
                    seed = seed_spec
                    break
            if not seed:
                provenance["entities"][cls_name] = "inferred"
                continue

            coverage["seeded_entities"] += 1
            provenance["entities"][cls_name] = "seeded"
            provenance["fields"][cls_name] = {}
            existing_fields = cls_row.get("fields", []) or []
            existing_names = {_snake(f.get("name", "")): f for f in existing_fields}

            for req_name in seed.get("required_fields", []):
                req_snake = _snake(req_name)
                if req_snake not in existing_names:
                    existing_fields.append(
                        {
                            "name": req_snake,
                            "type": "string",
                            "nullable": False,
                            "primary_key": False,
                            "foreign_key": None,
                            "description": "Domain-seeded required field",
                            "seeded": True,
                        }
                    )
                    coverage["missing_required_fields"].append(f"{cls_name}.{req_snake}")
                    provenance["fields"][cls_name][req_snake] = "seeded"
                else:
                    existing_names[req_snake]["nullable"] = False
                    existing_names[req_snake]["seeded"] = True
                    provenance["fields"][cls_name][req_snake] = "mapped"

            cls_row["fields"] = existing_fields
            cls_row["seed_context"] = {
                "vendor_key": seed.get("vendor_key"),
                "domain": seed.get("domain"),
                "adapter_mapping": seed.get("adapter_mapping", {}),
            }
        return {"classes": classes, "provenance": provenance, "coverage": coverage}

    @classmethod
    def normalize_rules(cls, rules: List[Dict[str, Any]], seed_index: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for rule in rules or []:
            base = dict(rule)
            parsed = _parse_condition(base.get("condition") or base.get("name", ""))
            base.setdefault("subject", parsed["subject"])
            base.setdefault("operator", parsed["operator"])
            base.setdefault("threshold", parsed["threshold"])
            base.setdefault("effect", "validate")
            base.setdefault("evidence_source", base.get("source", "unknown"))
            base.setdefault("severity", "should")
            normalized.append(base)

        # Add seed-defined rule patterns when missing from authored rules
        if seed_index:
            existing_rule_names = {_snake(r.get("name", "")) for r in normalized}
            for seed in seed_index.values():
                for pattern in seed.get("rule_patterns", []):
                    pname = _snake(pattern.get("name", ""))
                    if pname in existing_rule_names:
                        continue
                    normalized.append(
                        {
                            "name": pattern.get("name", "SeedRule"),
                            "condition": f"{pattern.get('subject', 'value')} {pattern.get('operator', '==')} {pattern.get('threshold', '')}".strip(),
                            "subject": pattern.get("subject", "value"),
                            "operator": pattern.get("operator", "=="),
                            "threshold": pattern.get("threshold", ""),
                            "effect": pattern.get("effect", "validate"),
                            "severity": pattern.get("severity", "must"),
                            "source": "domain_seed",
                            "evidence_source": "domain_seed",
                        }
                    )
        return normalized

    @classmethod
    def resolve(cls, solution, uml_classes: List[Dict[str, Any]], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        catalog = cls.load_catalog()
        vendor_keys = cls._infer_vendor_keys(solution)
        seed_index = cls._build_seed_index(vendor_keys, catalog)
        seeded = cls._apply_seed_fields(uml_classes, seed_index)
        normalized_rules = cls.normalize_rules(rules, seed_index=seed_index)

        adapter_expected = sum(
            1
            for seed in seed_index.values()
            if seed.get("adapter_mapping")
        )
        adapter_mapped = sum(
            1
            for cls_row in seeded["classes"]
            if (cls_row.get("seed_context") or {}).get("adapter_mapping")
        )
        adapter_coverage = round((adapter_mapped / max(adapter_expected, 1)) * 100, 1) if adapter_expected else 100.0

        return {
            "version": catalog.get("version", "unknown"),
            "vendor_keys": vendor_keys,
            "seed_index": seed_index,
            "classes": seeded["classes"],
            "normalized_rules": normalized_rules,
            "provenance": seeded["provenance"],
            "coverage": {
                **seeded["coverage"],
                "adapter_expected": adapter_expected,
                "adapter_mapped": adapter_mapped,
                "adapter_coverage": adapter_coverage,
            },
        }

    @classmethod
    def compute_domain_fidelity(cls, uml: Dict[str, Any], seed_context: Dict[str, Any] | None) -> Dict[str, Any]:
        if not seed_context:
            return {
                "score": 100.0,
                "expected_entities": 0,
                "seeded_entities": 0,
                "required_field_coverage": 100.0,
                "adapter_coverage": 100.0,
                "missing_required_fields": [],
            }

        classes = uml.get("class_diagram", {}).get("classes", []) if uml else []
        class_lookup = {_pascal(c.get("name", "")): c for c in classes}
        seed_index = seed_context.get("seed_index", {})
        expected_entities = len(seed_index)
        seeded_entities = 0
        total_required_fields = 0
        present_required_fields = 0
        missing_required_fields: List[str] = []

        for seed_name, seed in seed_index.items():
            cls_row = class_lookup.get(_pascal(seed_name))
            if not cls_row:
                continue
            seeded_entities += 1
            field_names = {_snake(f.get("name", "")) for f in (cls_row.get("fields") or [])}
            for req_name in seed.get("required_fields", []):
                total_required_fields += 1
                req_snake = _snake(req_name)
                if req_snake in field_names:
                    present_required_fields += 1
                else:
                    missing_required_fields.append(f"{seed_name}.{req_snake}")

        entity_coverage = (seeded_entities / max(expected_entities, 1)) * 100 if expected_entities else 100.0

        # If no seed entities appear in the UML at all, the seed context is for a
        # different domain (e.g. SAP finance seeds applied to a MES/NIS2 solution).
        # Don't penalise: the solution is correct for its domain, the seed is irrelevant.
        if seeded_entities == 0 and expected_entities > 0:
            return {
                "score": 100.0,
                "expected_entities": expected_entities,
                "seeded_entities": 0,
                "required_field_coverage": 100.0,
                "adapter_coverage": 100.0,
                "missing_required_fields": [],
            }

        required_field_coverage = (present_required_fields / max(total_required_fields, 1)) * 100 if total_required_fields else 100.0
        adapter_coverage = float((seed_context.get("coverage") or {}).get("adapter_coverage", 100.0))
        score = round(entity_coverage * 0.4 + required_field_coverage * 0.4 + adapter_coverage * 0.2, 1)

        return {
            "score": score,
            "expected_entities": expected_entities,
            "seeded_entities": seeded_entities,
            "required_field_coverage": round(required_field_coverage, 1),
            "adapter_coverage": round(adapter_coverage, 1),
            "missing_required_fields": missing_required_fields,
        }
