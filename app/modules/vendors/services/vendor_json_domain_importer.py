"""
-> app.modules.vendors.services.seeder_service

Vendor Domain JSON Importer

Imports vendors, products, and capability mappings from domain-specific JSON
files in the ``vendor json/`` directory. Each JSON file covers one IT domain
(e.g. Cybersecurity, Enterprise Applications) with L1/L2/L3 tiered vendors.

Idempotent: safe to re-run as new JSON files are added.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.capability_to_vendor_mapping import TechnicalCapabilityVendorMapping
from app.models.technical_capability import TechnicalCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_JSON_DIR = PROJECT_ROOT / "vendor json"

TIER_RANK = {"L1": 1, "L2": 2, "L3": 3}
TIER_TO_STRATEGIC = {
    "L1": "tier_1_strategic",
    "L2": "tier_2_preferred",
    "L3": "tier_3_approved",
}
TIER_COVERAGE = {"L1": 85, "L2": 75, "L3": 65}

VENDOR_TYPE_MAP = {
    "product": "software_vendor",
    "saas": "saas_platform",
    "managed": "managed_service_provider",
    "consulting": "consulting_partner",
    "mdr": "managed_service_provider",
    "services": "systems_integrator",
}

SECURITY_SCORE_MAP = {
    "very high": 95,
    "high": 85,
    "enterprise": 85,
    "medium-high": 75,
    "medium": 65,
    "low": 45,
}

MATURITY_MAP = {
    "enterprise": "mature",
    "established": "mature",
    "growing": "growth",
    "emerging": "emerging",
}


@dataclass
class DomainImportSummary:
    files_loaded: int = 0
    vendors_created: int = 0
    vendors_updated: int = 0
    products_created: int = 0
    products_updated: int = 0
    biz_cap_links_created: int = 0
    tech_cap_links_created: int = 0
    capabilities_unmatched: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_loaded": self.files_loaded,
            "vendors_created": self.vendors_created,
            "vendors_updated": self.vendors_updated,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "biz_cap_links_created": self.biz_cap_links_created,
            "tech_cap_links_created": self.tech_cap_links_created,
            "capabilities_unmatched": self.capabilities_unmatched,
            "errors": len(self.errors),
        }


# ── Helpers ──────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Normalise a vendor name to a slug (strip parentheticals, special chars)."""
    clean = re.sub(r"\s*\([^)]*\)", "", name)  # Remove (parentheticals)
    clean = re.sub(r"[^A-Za-z0-9]+", "-", clean).strip("-")
    return re.sub(r"-+", "-", clean)


def _generate_code(vendor_name: str) -> str:
    return f"VEND-{_slugify(vendor_name).upper()[:45]}"


def _generate_seed_source_id(vendor_name: str) -> str:
    return f"vjson-{_slugify(vendor_name).lower()}"


def _safe_str(value: Any, max_len: int) -> Optional[str]:
    """Truncate a string to fit a VARCHAR column, normalise unicode dashes."""
    if value is None:
        return None
    s = str(value)
    # Replace non-breaking hyphens, en-dashes, em-dashes with ASCII hyphen
    s = s.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return s[:max_len] if len(s) > max_len else s


def _parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else default


def _map_vendor_type(service_model: Optional[str]) -> str:
    if not service_model:
        return "software_vendor"
    lower = service_model.lower()
    for keyword, vtype in VENDOR_TYPE_MAP.items():
        if keyword in lower:
            return vtype
    return "software_vendor"


# ── Main Importer ────────────────────────────────────────────────────────

class VendorJsonDomainImporter:
    """Imports vendor domain JSON files into VendorOrganization / VendorProduct."""

    def __init__(self, json_dir: Optional[Path] = None):
        self.json_dir = json_dir or DEFAULT_JSON_DIR
        self.summary = DomainImportSummary()
        self._biz_cap_index: Dict[str, BusinessCapability] = {}
        self._tech_cap_index: Dict[str, TechnicalCapability] = {}

    def run(self, commit: bool = True) -> Dict[str, Any]:
        """Load all JSON files and import vendors/products/mappings."""
        try:
            merged = self._load_and_merge()
            if not merged:
                return {
                    "success": True,
                    "message": "No vendor JSON files found",
                    "data": self.summary.to_dict(),
                }

            self._build_capability_indexes()

            for vendor_name, vdata in merged.items():
                try:
                    self._import_vendor(vendor_name, vdata)
                except IntegrityError as exc:
                    db.session.rollback()
                    err = f"Integrity error for '{vendor_name}': {exc}"
                    self.summary.errors.append(err)
                    logger.warning(err)
                except Exception as exc:
                    db.session.rollback()
                    err = f"Error importing '{vendor_name}': {exc}"
                    self.summary.errors.append(err)
                    logger.warning(err)

            if commit:
                db.session.commit()
            else:
                db.session.rollback()

            total = self.summary.vendors_created + self.summary.vendors_updated
            msg = (
                f"Imported {self.summary.files_loaded} files: "
                f"{self.summary.vendors_created} vendors created, "
                f"{self.summary.vendors_updated} updated, "
                f"{self.summary.products_created} products created, "
                f"{self.summary.biz_cap_links_created + self.summary.tech_cap_links_created} "
                f"capability links"
            )
            if self.summary.errors:
                msg += f" ({len(self.summary.errors)} errors)"

            return {"success": True, "message": msg, "data": self.summary.to_dict()}

        except Exception as exc:
            db.session.rollback()
            logger.exception("Vendor JSON import failed: %s", exc)
            return {
                "success": False,
                "message": f"Import failed: {exc}",
                "data": self.summary.to_dict(),
            }

    # ── Phase 1: Load & Merge ────────────────────────────────────────────

    def _load_and_merge(self) -> Dict[str, Dict]:
        """Load all JSON files and merge vendors appearing in multiple files."""
        json_dir = Path(self.json_dir)
        if not json_dir.exists():
            logger.warning("Vendor JSON directory not found: %s", json_dir)
            return {}

        merged: Dict[str, Dict] = {}

        for json_file in sorted(json_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                # Normalise problematic Unicode characters before parsing
                raw = raw.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                raw = raw.replace("\u2018", "'").replace("\u2019", "'")
                raw = raw.replace("\u201c", '"').replace("\u201d", '"')
                data = json.loads(raw)
            except (json.JSONDecodeError, OSError) as exc:
                self.summary.errors.append(f"Failed to read {json_file.name}: {exc}")
                continue

            self.summary.files_loaded += 1
            domain = data.get("domain", json_file.stem)
            tiers = data.get("tiers", {})

            for tier_key, entries in tiers.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    name = (entry.get("vendor_name") or "").strip()
                    # Normalise unicode dashes to ASCII
                    name = name.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                    if not name:
                        continue

                    if name not in merged:
                        merged[name] = {
                            "vendor_data": entry,
                            "domains": [domain],
                            "tiers": {domain: tier_key},
                            "all_products": list(entry.get("products") or []),
                            "all_capabilities": list(entry.get("capabilities") or []),
                            "best_tier": tier_key,
                        }
                    else:
                        existing = merged[name]
                        existing["domains"].append(domain)
                        existing["tiers"][domain] = tier_key

                        # Accumulate products (dedupe by product_name)
                        seen_products = {p["product_name"] for p in existing["all_products"]
                                         if "product_name" in p}
                        for product in entry.get("products") or []:
                            pname = product.get("product_name")
                            if pname and pname not in seen_products:
                                existing["all_products"].append(product)
                                seen_products.add(pname)

                        # Accumulate capabilities (dedupe)
                        seen_caps = set(existing["all_capabilities"])
                        for cap in entry.get("capabilities") or []:
                            if cap not in seen_caps:
                                existing["all_capabilities"].append(cap)
                                seen_caps.add(cap)

                        # Best tier wins (L1 > L2 > L3)
                        if TIER_RANK.get(tier_key, 99) < TIER_RANK.get(existing["best_tier"], 99):
                            existing["best_tier"] = tier_key
                            existing["vendor_data"] = entry

        logger.info(
            "Loaded %d JSON files, %d unique vendors",
            self.summary.files_loaded,
            len(merged),
        )
        return merged

    # ── Phase 2: Capability indexes ──────────────────────────────────────

    def _build_capability_indexes(self) -> None:
        """Pre-load business and technical capabilities for fuzzy matching."""
        for bc in BusinessCapability.query.all():  # model-safety-ok  bulk index load
            self._biz_cap_index[bc.name.lower()] = bc
        for tc in TechnicalCapability.query.all():  # model-safety-ok  bulk index load
            self._tech_cap_index[tc.name.lower()] = tc
        logger.info(
            "Capability indexes: %d business, %d technical",
            len(self._biz_cap_index),
            len(self._tech_cap_index),
        )

    # ── Phase 3: Vendor upsert ───────────────────────────────────────────

    def _import_vendor(self, vendor_name: str, vdata: Dict) -> None:
        entry = vdata["vendor_data"]
        best_tier = vdata["best_tier"]
        code = _generate_code(vendor_name)
        ssid = _generate_seed_source_id(vendor_name)

        # Upsert: try name lookup first (merges with existing catalogue vendors)
        with db.session.no_autoflush:
            vendor_org = VendorOrganization.query.filter_by(name=vendor_name).first()

            if not vendor_org:
                # Try seed_source_id lookup (for re-runs of this importer)
                vendor_org = VendorOrganization.query.filter_by(seed_source_id=ssid).first()

        created = False
        if not vendor_org:
            vendor_org = VendorOrganization(name=vendor_name, display_name=vendor_name)
            # Set required seed fields
            try:
                vendor_org.code = code
                vendor_org.seed_source_id = ssid
                vendor_org.is_seed_data = True
                vendor_org.seeded_by = "VendorJsonDomainImporter"
                vendor_org.seed_version = "vjson-1.0"
            except Exception as e:
                logger.debug("Seed metadata columns not available: %s", e)
            db.session.add(vendor_org)
            db.session.flush()
            created = True

        # Update fields from JSON data
        self._update_vendor_fields(vendor_org, entry, vdata, best_tier)

        if created:
            self.summary.vendors_created += 1
        else:
            self.summary.vendors_updated += 1

        # Upsert products
        for product_data in vdata["all_products"]:
            product = self._upsert_product(vendor_org, product_data)
            if product:
                # Link capabilities to this product
                self._link_capabilities(product, vdata["all_capabilities"], best_tier)

    def _update_vendor_fields(
        self,
        vendor_org: VendorOrganization,
        entry: Dict,
        vdata: Dict,
        best_tier: str,
    ) -> None:
        vendor_org.display_name = vendor_org.display_name or entry.get("vendor_name")
        vendor_org.website = entry.get("website") or vendor_org.website
        vendor_org.headquarters_location = entry.get("hq_country") or vendor_org.headquarters_location

        year = _parse_int(entry.get("founded_year"))
        if year > 1800:
            vendor_org.year_founded = year

        emp = _parse_int(entry.get("company_size"))
        if emp > 0:
            vendor_org.employee_count = emp

        vendor_org.vendor_type = _map_vendor_type(entry.get("service_model")) or vendor_org.vendor_type

        security = entry.get("security_posture", "")
        if security:
            score = SECURITY_SCORE_MAP.get(security.lower().strip())
            if score:
                vendor_org.enterprise_readiness_score = score

        vendor_org.strategic_tier = TIER_TO_STRATEGIC.get(best_tier) or vendor_org.strategic_tier

        # JSON array fields
        certs = entry.get("certifications")
        if certs:
            vendor_org.iso_certifications = json.dumps(certs)
        compliance = entry.get("compliance_domains")
        if compliance:
            vendor_org.compliance_frameworks = json.dumps(compliance)
        strengths = entry.get("strengths")
        if strengths:
            vendor_org.strengths = json.dumps(strengths)
        limitations = entry.get("limitations")
        if limitations:
            vendor_org.weaknesses = json.dumps(limitations)

        # Build strategic notes
        notes_parts = []
        domains = vdata.get("domains", [])
        if domains:
            notes_parts.append(f"Domains: {', '.join(domains)}")
        tiers = vdata.get("tiers", {})
        if tiers:
            tier_strs = [f"{d}: {t}" for d, t in tiers.items()]
            notes_parts.append(f"Tiers: {', '.join(tier_strs)}")
        if entry.get("delivery_model"):
            notes_parts.append(f"Delivery: {entry['delivery_model']}")
        if entry.get("pricing_model"):
            notes_parts.append(f"Pricing: {entry['pricing_model']}")
        if entry.get("pricing_tier"):
            notes_parts.append(f"Price tier: {entry['pricing_tier']}")
        industries = entry.get("industries_served")
        if industries:
            notes_parts.append(f"Industries: {', '.join(industries)}")
        hidden = entry.get("hidden_cost_risks")
        if hidden:
            notes_parts.append(f"Cost risks: {', '.join(hidden)}")

        if notes_parts:
            vendor_org.strategic_notes = "\n".join(notes_parts)

        vendor_org.status = "active"

    # ── Phase 4: Product upsert ──────────────────────────────────────────

    def _upsert_product(
        self, vendor_org: VendorOrganization, product_data: Dict
    ) -> Optional[VendorProduct]:
        pname = product_data.get("product_name")
        if not pname:
            return None

        with db.session.no_autoflush:
            product = VendorProduct.query.filter_by(
                vendor_organization_id=vendor_org.id, name=pname
            ).first()

        created = False
        if not product:
            try:
                product = VendorProduct(
                    vendor_organization_id=vendor_org.id, name=pname
                )
                db.session.add(product)
                db.session.flush()
                created = True
            except IntegrityError:
                db.session.rollback()
                product = VendorProduct.query.filter_by(
                    vendor_organization_id=vendor_org.id, name=pname
                ).first()
                if not product:
                    return None

        # Update product fields (truncate to fit VARCHAR limits)
        product.product_type = _safe_str(product_data.get("product_type"), 50) or product.product_type
        product.description = product_data.get("product_description") or product.description
        product.functional_scope = product_data.get("product_description") or product.functional_scope
        product.version = _safe_str(product_data.get("product_version"), 50) or product.version
        product.licensing_model = _safe_str(product_data.get("licensing_model"), 50) or product.licensing_model

        deploy = product_data.get("deployment_options")
        if deploy and isinstance(deploy, list):
            product.deployment_model = ", ".join(deploy)

        platforms = product_data.get("supported_platforms")
        if platforms and isinstance(platforms, list):
            product.supported_platforms = json.dumps(platforms)

        integrations = product_data.get("integrations")
        if integrations and isinstance(integrations, list):
            product.integration_methods = json.dumps(integrations)

        product.documentation_url = product_data.get("product_docs_url") or product.documentation_url
        product.support_portal = product_data.get("product_page_url") or product.support_portal

        maturity = product_data.get("product_maturity")
        if maturity:
            product.product_maturity = _safe_str(MATURITY_MAP.get(maturity.lower(), maturity), 30)

        # Build implementation notes from pricing/SLA info
        impl_notes = []
        if product_data.get("sla_offering"):
            impl_notes.append(f"SLA: {product_data['sla_offering']}")
        if product_data.get("pricing_notes"):
            impl_notes.append(f"Pricing: {product_data['pricing_notes']}")
        if product_data.get("per_unit_metric"):
            impl_notes.append(f"Unit: {product_data['per_unit_metric']}")
        support = product_data.get("support_levels")
        if support and isinstance(support, list):
            impl_notes.append(f"Support: {', '.join(support)}")
        if impl_notes:
            product.implementation_notes = "\n".join(impl_notes)

        product.status = "active"

        if created:
            self.summary.products_created += 1
        else:
            self.summary.products_updated += 1

        return product

    # ── Phase 5: Capability matching & linking ───────────────────────────

    def _link_capabilities(
        self, product: VendorProduct, capabilities: List[str], tier: str
    ) -> None:
        base_coverage = TIER_COVERAGE.get(tier, 70)

        for cap_text in capabilities:
            cap_lower = cap_text.strip().lower()
            if not cap_lower:
                continue

            biz_match = self._find_biz_cap(cap_lower)
            tech_match = self._find_tech_cap(cap_lower)

            if biz_match:
                bc, score = biz_match
                coverage = int(base_coverage * score)
                self._create_biz_cap_link(product, bc, coverage, tier)

            if tech_match:
                tc, score = tech_match
                coverage = int(base_coverage * score)
                self._create_tech_cap_link(product, tc, coverage, tier)

            if not biz_match and not tech_match:
                self.summary.capabilities_unmatched += 1

    def _find_biz_cap(self, cap_lower: str) -> Optional[Tuple[BusinessCapability, float]]:
        # Exact match
        if cap_lower in self._biz_cap_index:
            return (self._biz_cap_index[cap_lower], 1.0)

        # Substring containment
        for name, bc in self._biz_cap_index.items():
            if cap_lower in name or name in cap_lower:
                return (bc, 0.9)

        # Fuzzy match
        best_score = 0.0
        best_cap = None
        for name, bc in self._biz_cap_index.items():
            score = SequenceMatcher(None, cap_lower, name).ratio()
            if score > best_score:
                best_score = score
                best_cap = bc

        if best_score >= 0.6 and best_cap:
            return (best_cap, best_score)
        return None

    def _find_tech_cap(self, cap_lower: str) -> Optional[Tuple[TechnicalCapability, float]]:
        # Exact match
        if cap_lower in self._tech_cap_index:
            return (self._tech_cap_index[cap_lower], 1.0)

        # Substring containment
        for name, tc in self._tech_cap_index.items():
            if cap_lower in name or name in cap_lower:
                return (tc, 0.9)

        # Fuzzy match
        best_score = 0.0
        best_cap = None
        for name, tc in self._tech_cap_index.items():
            score = SequenceMatcher(None, cap_lower, name).ratio()
            if score > best_score:
                best_score = score
                best_cap = tc

        if best_score >= 0.6 and best_cap:
            return (best_cap, best_score)
        return None

    def _create_biz_cap_link(
        self, product: VendorProduct, bc: BusinessCapability, coverage: int, tier: str
    ) -> None:
        with db.session.no_autoflush:
            existing = VendorProductCapability.query.filter_by(
                vendor_product_id=product.id,
                business_capability_id=bc.id,
            ).first()
        if existing:
            existing.coverage_percentage = max(existing.coverage_percentage or 0, coverage)
            return

        try:
            mapping = VendorProductCapability(
                vendor_product_id=product.id,
                business_capability_id=bc.id,
                coverage_percentage=coverage,
                maturity_level=4 if tier == "L1" else 3,
                fit_score=coverage,
                implementation_complexity=4,
                configuration_required=True,
            )
            db.session.add(mapping)
            db.session.flush()
            self.summary.biz_cap_links_created += 1
        except IntegrityError:
            db.session.rollback()

    def _create_tech_cap_link(
        self, product: VendorProduct, tc: TechnicalCapability, coverage: int, tier: str
    ) -> None:
        with db.session.no_autoflush:
            existing = TechnicalCapabilityVendorMapping.query.filter_by(
                technical_capability_id=tc.id,
                vendor_product_id=product.id,
            ).first()
        if existing:
            existing.coverage_percentage = max(existing.coverage_percentage or 0, coverage)
            return

        try:
            mapping = TechnicalCapabilityVendorMapping(
                technical_capability_id=tc.id,
                vendor_product_id=product.id,
                coverage_percentage=coverage,
                maturity_level=4 if tier == "L1" else 3,
                fit_score=coverage,
            )
            db.session.add(mapping)
            db.session.flush()
            self.summary.tech_cap_links_created += 1
        except IntegrityError:
            db.session.rollback()


__all__ = ["VendorJsonDomainImporter", "DomainImportSummary"]
