"""Importer that synchronises the TypeScript vendor catalogue into the database."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.capabilities import COBITDomain, COBITProcess, ITILPractice
from app.models.vendor_organization import VendorOrganization, VendorProduct, VendorProductCapability

from .catalogue_loader import (
    DEFAULT_CATALOGUE_PATH,
    DEFAULT_CUSTOM_MODEL_PATH,
    CatalogueParseError,
    load_catalogue,
    load_custom_capability_model,
)


LOGGER = logging.getLogger(__name__)


@dataclass
class ImportSummary:
    capabilities_created: int = 0
    capabilities_existing: int = 0
    custom_capabilities_created: int = 0
    custom_capabilities_updated: int = 0
    cobit_domains_created: int = 0
    cobit_processes_created: int = 0
    cobit_processes_updated: int = 0
    itil_practices_created: int = 0
    itil_practices_updated: int = 0
    vendors_created: int = 0
    vendors_updated: int = 0
    products_created: int = 0
    products_updated: int = 0
    capability_links_created: int = 0
    capability_links_updated: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, int]:
        return {
            "capabilities_created": self.capabilities_created,
            "capabilities_existing": self.capabilities_existing,
            "custom_capabilities_created": self.custom_capabilities_created,
            "custom_capabilities_updated": self.custom_capabilities_updated,
            "cobit_domains_created": self.cobit_domains_created,
            "cobit_processes_created": self.cobit_processes_created,
            "cobit_processes_updated": self.cobit_processes_updated,
            "itil_practices_created": self.itil_practices_created,
            "itil_practices_updated": self.itil_practices_updated,
            "vendors_created": self.vendors_created,
            "vendors_updated": self.vendors_updated,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "capability_links_created": self.capability_links_created,
            "capability_links_updated": self.capability_links_updated,
            "errors": len(self.errors),
        }

    def formatted_report(self) -> str:
        header = "Vendor catalogue import summary"
        divider = "=" * len(header)
        lines = [header, divider]
        for key, value in self.to_dict().items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"  - {err}" for err in self.errors)
        return "\n".join(lines)


DOMAIN_NAMES = {
    "EDM": "Evaluate, Direct and Monitor",
    "APO": "Align, Plan and Organise",
    "BAI": "Build, Acquire and Implement",
    "DSS": "Deliver, Service and Support",
    "MEA": "Monitor, Evaluate and Assess",
}

MARKET_POSITION_COVERAGE = {
    "LEADER": 90,
    "CHALLENGER": 80,
    "VISIONARY": 75,
    "NICHE": 65,
}

PRACTICE_TYPE_DEFAULT = "service"

VENDOR_TYPE_MAP = {
    "SOFTWARE": "software_vendor",
    "SAAS": "saas_platform",
    "CLOUD_SERVICE": "cloud_provider",
    "MANAGED_SERVICE": "managed_service_provider",
    "CONSULTING": "consulting_partner",
}

MARKET_SHARE_MAP = {
    "DOMINANT": Decimal("35.0"),
    "MAJOR": Decimal("20.0"),
    "MODERATE": Decimal("10.0"),
    "EMERGING": Decimal("3.0"),
}


class VendorCatalogueImporter:
    """Coordinates the ingestion of the TypeScript vendor catalogue."""

    def __init__(self, catalogue_path: Optional[Path] = None, custom_model_path: Optional[Path] = None):
        self.catalogue_path = catalogue_path or DEFAULT_CATALOGUE_PATH
        self.custom_model_path = custom_model_path or DEFAULT_CUSTOM_MODEL_PATH
        self.summary = ImportSummary()
        self.logger = LOGGER

    def run(self, commit: bool = True) -> ImportSummary:
        """Execute the import and optionally commit changes."""
        try:
            payload = load_catalogue(self.catalogue_path)
        except (FileNotFoundError, CatalogueParseError) as exc:
            error_message = f"Failed to load catalogue: {exc}"
            self.summary.errors.append(error_message)
            self.logger.error(error_message)
            raise

        # Custom capability model is optional
        custom_capability_model = None
        try:
            custom_capability_model = load_custom_capability_model(self.custom_model_path)
        except (FileNotFoundError, CatalogueParseError):
            self.logger.info("Custom capability model not found, skipping")

        try:
            capability_index = self._ensure_capabilities(payload["capability_taxonomy"])
            self._ensure_cobit(payload["cobit_processes"])
            self._ensure_itil(payload["itil_processes"])
            self._sync_vendors(payload["vendors"], capability_index)
            if custom_capability_model:
                self._sync_custom_capability_model(custom_capability_model)
            if commit:
                db.session.commit()
            else:
                db.session.rollback()
            return self.summary
        except SQLAlchemyError as exc:
            db.session.rollback()
            message = f"Database error during import: {exc}"
            self.summary.errors.append(message)
            self.logger.exception(message)
            raise
        except Exception as exc:
            db.session.rollback()
            message = f"Unexpected error during import: {exc}"
            self.summary.errors.append(message)
            self.logger.exception(message)
            raise

    # ------------------------------------------------------------------
    # Capability scaffolding
    # ------------------------------------------------------------------

    def _ensure_capabilities(self, taxonomy: Dict[str, str]) -> Dict[str, BusinessCapability]:
        slug_to_capability: Dict[str, BusinessCapability] = {}
        for slug, name in taxonomy.items():
            # Use case-insensitive lookup to avoid duplicates
            capability = BusinessCapability.query.filter(
                db.func.lower(BusinessCapability.name) == db.func.lower(name)
            ).first()

            if capability:
                slug_to_capability[slug] = capability
                self.summary.capabilities_existing += 1
                continue

            # Create new capability but guard against race/unique conflicts
            try:
                capability = BusinessCapability(
                    name=name,
                    description=f"Imported from vendor catalogue taxonomy ({slug}).",
                    level=2,
                    business_domain=self._infer_domain(slug),
                    category="supporting",
                    strategic_importance="high",
                )
                db.session.add(capability)
                db.session.flush()
                slug_to_capability[slug] = capability
                self.summary.capabilities_created += 1
            except IntegrityError as exc:
                # Another process or earlier step created it — rollback and re-query
                db.session.rollback()
                capability = BusinessCapability.query.filter(
                    db.func.lower(BusinessCapability.name) == db.func.lower(name)
                ).first()
                if capability:
                    slug_to_capability[slug] = capability
                    self.summary.capabilities_existing += 1
                else:
                    err = f"Failed to create capability '{name}': {exc}"
                    self.summary.errors.append(err)
                    self.logger.exception(err)
                    # skip this capability
                    continue
        return slug_to_capability

    @staticmethod
    def _infer_domain(slug: str) -> str:
        if slug in {
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "release-management",
            "service-request",
            "configuration-management",
            "asset-management",
            "knowledge-management",
            "service-catalog",
        }:
            return "IT Service Management"
        if slug in {
            "governance-framework",
            "risk-management",
            "compliance-management",
            "portfolio-management",
            "architecture-management",
            "vendor-management",
            "security-management",
            "performance-management",
            "resource-optimization",
        }:
            return "Governance & Strategy"
        if slug in {
            "monitoring-alerting",
            "automation",
            "reporting-analytics",
            "workflow-orchestration",
            "integration-platform",
            "ai-ml",
        }:
            return "Platform Engineering"
        if slug in {
            "project-management",
            "financial-management",
            "audit-compliance",
            "business-continuity",
            "capacity-planning",
        }:
            return "Enterprise Operations"
        return "Enterprise IT"

    # ------------------------------------------------------------------
    # COBIT and ITIL reference data
    # ------------------------------------------------------------------

    def _ensure_cobit(self, cobit_processes: Dict[str, str]) -> None:
        domain_cache: Dict[str, COBITDomain] = {
            d.code: d for d in COBITDomain.query.filter(COBITDomain.code.in_(DOMAIN_NAMES.keys())).all()
        }

        for code, name in DOMAIN_NAMES.items():
            if code not in domain_cache:
                domain = COBITDomain(
                    code=code,
                    name=name,
                    description=f"Imported from vendor catalogue for {code} domain.",
                    domain_type="governance" if code == "EDM" else "management",
                )
                db.session.add(domain)
                db.session.flush()
                domain_cache[code] = domain
                self.summary.cobit_domains_created += 1

        for process_code, process_name in cobit_processes.items():
            domain_code = process_code[:3]
            domain = domain_cache.get(domain_code)
            if not domain:
                # Fallback: create domain if not already captured (unexpected but safe)
                domain = COBITDomain(
                    code=domain_code,
                    name=DOMAIN_NAMES.get(domain_code, domain_code),
                    description=f"Auto-created domain for {domain_code} due to missing definition.",
                    domain_type="governance" if domain_code == "EDM" else "management",
                )
                db.session.add(domain)
                db.session.flush()
                domain_cache[domain_code] = domain
                self.summary.cobit_domains_created += 1

            process = COBITProcess.query.filter_by(code=process_code).first()
            if process:
                updated = False
                if process.name != process_name:
                    process.name = process_name
                    updated = True
                if process.domain_id != domain.id:
                    process.domain_id = domain.id
                    updated = True
                if updated:
                    self.summary.cobit_processes_updated += 1
                continue

            process = COBITProcess(
                code=process_code,
                name=process_name,
                description=f"Imported from vendor catalogue ({process_code}).",
                domain_id=domain.id,
            )
            db.session.add(process)
            self.summary.cobit_processes_created += 1

    def _ensure_itil(self, itil_processes: Dict[str, str]) -> None:
        for slug, name in itil_processes.items():
            code = slug.upper().replace("-", "_")[:20]  # Truncate to fit varchar(20)
            practice = ITILPractice.query.filter_by(code=code).first()
            if practice:
                updated = False
                if practice.name != name:
                    practice.name = name
                    updated = True
                if practice.practice_type != PRACTICE_TYPE_DEFAULT:
                    practice.practice_type = PRACTICE_TYPE_DEFAULT
                    updated = True
                if updated:
                    self.summary.itil_practices_updated += 1
                continue

            practice = ITILPractice(
                code=code,
                name=name,
                description=f"Imported from vendor catalogue ({slug}).",
                practice_type=PRACTICE_TYPE_DEFAULT,
            )
            db.session.add(practice)
            self.summary.itil_practices_created += 1

    # ------------------------------------------------------------------
    # Vendor and product ingestion
    # ------------------------------------------------------------------

    def _sync_vendors(self, vendors: List[Dict[str, object]], capability_index: Dict[str, BusinessCapability]) -> None:
        for vendor in vendors:
            try:
                vendor_org = VendorOrganization.query.filter_by(name=vendor["name"]).first()
                if vendor_org:
                    self._update_vendor(vendor_org, vendor)
                    self.summary.vendors_updated += 1
                else:
                    vendor_org = self._create_vendor(vendor)
                    self.summary.vendors_created += 1

                product = self._sync_vendor_product(vendor_org, vendor)
                self._sync_vendor_capabilities(product, vendor, capability_index)
            except IntegrityError as exc:
                db.session.rollback()
                err = f"Integrity error while syncing vendor '{vendor.get('name')}': {exc}"
                self.summary.errors.append(err)
                self.logger.exception(err)
                # continue with next vendor
                continue
            except Exception as exc:
                db.session.rollback()
                err = f"Unexpected error while syncing vendor '{vendor.get('name')}': {exc}"
                self.summary.errors.append(err)
                self.logger.exception(err)
                continue

    def _create_vendor(self, vendor: Dict[str, object]) -> VendorOrganization:
        vendor_org = VendorOrganization(
            name=vendor["name"],
            display_name=vendor["name"],
        )
        db.session.add(vendor_org)
        db.session.flush()
        self._update_vendor(vendor_org, vendor)
        return vendor_org

    def _update_vendor(self, vendor_org: VendorOrganization, vendor: Dict[str, object]) -> None:
        vendor_type = VENDOR_TYPE_MAP.get(str(vendor.get("vendorType", "")).upper())
        if vendor_type:
            vendor_org.vendor_type = vendor_type
        vendor_org.website = vendor.get("website")
        vendor_org.description = vendor.get("description")
        vendor_org.headquarters_location = vendor.get("headquarters")
        vendor_org.year_founded = vendor.get("founded")
        vendor_org.public_company = vendor.get("publicCompany")

        market_position = str(vendor.get("marketPosition", "")).lower() or None
        if market_position:
            vendor_org.gartner_magic_quadrant_position = market_position

        market_share_bucket = str(vendor.get("marketShare", "")).upper()
        if market_share_bucket in MARKET_SHARE_MAP:
            vendor_org.market_share_percentage = MARKET_SHARE_MAP[market_share_bucket]

        compliance = vendor.get("complianceFrameworks") or []
        if isinstance(compliance, list):
            vendor_org.set_compliance_frameworks(compliance)
        else:
            vendor_org.set_compliance_frameworks([])

        risk_level = str(vendor.get("riskLevel", "")).upper()
        if risk_level == "HIGH":
            vendor_org.vendor_lock_in_risk = 8
        elif risk_level == "MEDIUM":
            vendor_org.vendor_lock_in_risk = 5
        elif risk_level == "LOW":
            vendor_org.vendor_lock_in_risk = 2

        notes = []
        if vendor.get("category"):
            notes.append(f"Category: {vendor['category']}")
        if vendor.get("licenseModel"):
            notes.append(f"License: {vendor['licenseModel']}")
        if vendor.get("typicalAnnualCost"):
            notes.append(f"Annual cost: {vendor['typicalAnnualCost']}")
        if vendor.get("deploymentModel"):
            notes.append(f"Deployment: {', '.join(vendor['deploymentModel'])}")
        if notes:
            vendor_org.strategic_notes = "\n".join(notes)

    def _sync_vendor_product(self, vendor_org: VendorOrganization, vendor: Dict[str, object]) -> VendorProduct:
        product_name = vendor["name"]
        # Query the product directly to avoid relationship auto-flush issues
        product = VendorProduct.query.filter_by(vendor_organization_id=vendor_org.id, name=product_name).first()
        if product:
            created = False
        else:
            try:
                product = VendorProduct(vendor_organization_id=vendor_org.id, name=product_name)
                db.session.add(product)
                db.session.flush()
                created = True
            except IntegrityError as exc:
                db.session.rollback()
                # Try to re-query after rollback
                product = VendorProduct.query.filter_by(vendor_organization_id=vendor_org.id, name=product_name).first()
                if product:
                    created = False
                else:
                    err = f"Failed to create product '{product_name}' for vendor '{vendor_org.name}': {exc}"
                    self.summary.errors.append(err)
                    self.logger.exception(err)
                    # Create a placeholder in-memory object to continue
                    product = VendorProduct(vendor_organization_id=vendor_org.id, name=product_name)
                    created = False

        product.deployment_model = ", ".join(vendor.get("deploymentModel", [])) or None
        product.licensing_model = vendor.get("licenseModel")
        product.product_type = str(vendor.get("category", "")).lower() or None
        product.functional_scope = vendor.get("description")
        product.market_position = str(vendor.get("marketPosition", "")).lower() or None
        product.integration_methods = json.dumps(vendor.get("integrations", []))
        product.supported_platforms = json.dumps(vendor.get("deploymentModel", []))
        product.target_market = str(vendor.get("marketShare", "")).lower() or None
        product.description = vendor.get("description")
        product.status = "active"

        if created:
            self.summary.products_created += 1
        else:
            self.summary.products_updated += 1
        return product

    def _sync_vendor_capabilities(
        self,
        product: VendorProduct,
        vendor: Dict[str, object],
        capability_index: Dict[str, BusinessCapability],
    ) -> None:
        capabilities = vendor.get("capabilities", []) or []
        coverage = MARKET_POSITION_COVERAGE.get(str(vendor.get("marketPosition", "")).upper(), 70)
        maturity_level = 4 if str(vendor.get("marketPosition", "")).upper() == "LEADER" else 3

        for capability_slug in capabilities:
            capability = capability_index.get(capability_slug)
            if not capability:
                self.logger.warning("Capability slug '%s' missing from taxonomy; skipping", capability_slug)
                continue
            try:
                mapping = VendorProductCapability.query.filter_by(
                    vendor_product_id=product.id,
                    business_capability_id=capability.id,
                ).first()

                if mapping:
                    mapping.coverage_percentage = coverage
                    mapping.maturity_level = maturity_level
                    mapping.implementation_complexity = 4
                    mapping.fit_score = coverage
                    self.summary.capability_links_updated += 1
                    continue

                mapping = VendorProductCapability(
                    vendor_product_id=product.id,
                    business_capability_id=capability.id,
                    coverage_percentage=coverage,
                    maturity_level=maturity_level,
                    fit_score=coverage,
                    implementation_complexity=4,
                    configuration_required=True,
                )
                db.session.add(mapping)
                self.summary.capability_links_created += 1
            except IntegrityError as exc:
                db.session.rollback()
                # If someone else inserted the mapping, try to re-query and update
                mapping = VendorProductCapability.query.filter_by(
                    vendor_product_id=product.id,
                    business_capability_id=capability.id,
                ).first()
                if mapping:
                    mapping.coverage_percentage = coverage
                    mapping.maturity_level = maturity_level
                    mapping.implementation_complexity = 4
                    mapping.fit_score = coverage
                    self.summary.capability_links_updated += 1
                else:
                    err = f"Failed to create capability mapping for product_id={product.id} cap_id={capability.id}: {exc}"
                    self.summary.errors.append(err)
                    self.logger.exception(err)


    def _sync_custom_capability_model(self, model: List[Dict[str, Any]]) -> None:
        for l1 in model:
            l1_defaults = {
                "description": l1.get("description"),
                "category": "strategic",
                "business_domain": l1.get("name"),
                "strategic_importance": "high",
            }
            l1_capability = self._upsert_custom_capability(l1["name"], 1, None, l1_defaults)

            for l2 in l1.get("level2", []):
                l2_defaults = {
                    "description": f"{l2['name']} within {l1['name']} domain.",
                    "category": "tactical",
                    "business_domain": l1.get("name"),
                    "strategic_importance": "high",
                }
                l2_capability = self._upsert_custom_capability(l2["name"], 2, l1_capability, l2_defaults)

                for l3 in l2.get("level3", []):
                    metadata = {
                        "mapped_vendor_capabilities": l3.get("mappedVendorCapabilities", []),
                        "mapped_vendors": l3.get("mappedVendors") or [],
                    }
                    notes = []
                    if metadata["mapped_vendor_capabilities"]:
                        notes.append(
                            "Vendor capabilities: "
                            + ", ".join(sorted(set(metadata["mapped_vendor_capabilities"])))
                        )
                    if metadata["mapped_vendors"]:
                        notes.append(
                            "Direct vendors: " + ", ".join(sorted(set(metadata["mapped_vendors"])))
                        )

                    l3_description = f"{l3['name']} capability supporting {l2['name']} in {l1['name']} domain."
                    if notes:
                        l3_description += " " + " | ".join(notes)

                    l3_defaults = {
                        "description": l3_description,
                        "category": "operational",
                        "business_domain": l1.get("name"),
                        "strategic_importance": "high",
                    }
                    self._upsert_custom_capability(l3["name"], 3, l2_capability, l3_defaults)

    def _upsert_custom_capability(
        self,
        name: str,
        level: int,
        parent: Optional[BusinessCapability],
        defaults: Dict[str, Optional[str]],
    ) -> BusinessCapability:
        query = BusinessCapability.query.filter_by(name=name, level=level)
        if parent is None:
            query = query.filter(BusinessCapability.parent_capability_id.is_(None))
        else:
            query = query.filter_by(parent_capability_id=parent.id)

        capability = query.first()
        clean_defaults = {key: value for key, value in defaults.items() if value is not None}

        if capability:
            updated = False
            for field, value in clean_defaults.items():
                current_value = getattr(capability, field)
                if isinstance(current_value, str) and isinstance(value, str):
                    if current_value.strip() == value.strip():
                        continue
                if current_value != value:
                    setattr(capability, field, value)
                    updated = True
            if updated:
                self.summary.custom_capabilities_updated += 1
            return capability

        capability = BusinessCapability(
            name=name,
            level=level,
            parent_capability_id=parent.id if parent else None,
            **clean_defaults,
        )
        db.session.add(capability)
        db.session.flush()
        self.summary.custom_capabilities_created += 1
        return capability


def import_vendor_catalogue(link_capabilities: bool = True) -> str:  # pragma: no cover - thin wrapper
    """Convenience entry-point for admin jobs and CLI invocations."""
    importer = VendorCatalogueImporter()
    summary = importer.run(commit=True)
    return summary.formatted_report()


__all__ = ["VendorCatalogueImporter", "import_vendor_catalogue", "ImportSummary"]
