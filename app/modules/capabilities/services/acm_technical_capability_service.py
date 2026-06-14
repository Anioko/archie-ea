"""
DEPRECATED: Import from app.modules.capabilities.services instead.
-> app.modules.capabilities.services.seeder_service

ACM Technical Capability Service

Service layer for managing Application Capability Model (ACM) technical capabilities.
Provides CRUD operations, hierarchy management, and mapping to business capabilities,
APQC processes, and applications.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload, selectinload  # dead-code-ok

from app import db
from app.models.technical_capability import (
    ACMDomain,
    TechnicalCapability,
    application_technical_capability_mapping,
    technical_capability_apqc_mapping,
    technical_capability_business_mapping,
    technical_capability_vendor_mapping,
)
from app.seed_data.acm_seed_data import get_domain_list, get_flat_capabilities

logger = logging.getLogger(__name__)


class ACMTechnicalCapabilityService:
    """Service for managing ACM technical capabilities."""

    @staticmethod
    def seed_capabilities() -> Dict[str, Any]:
        """
        Seed the database with ACM technical capabilities.
        Returns summary of seeded capabilities.
        """
        capabilities = get_flat_capabilities()
        created_count = 0
        updated_count = 0
        code_to_id = {}  # Map codes to IDs for parent relationships

        # First pass: Create all capabilities without parent relationships
        for cap_data in capabilities:
            existing = TechnicalCapability.query.filter_by(code=cap_data["code"]).first()

            if existing:
                # Update existing
                for key, value in cap_data.items():
                    if key not in ["parent_code", "technology_patterns"] and hasattr(existing, key):
                        setattr(existing, key, value)
                if "technology_patterns" in cap_data and cap_data["technology_patterns"]:
                    existing.technology_patterns = json.dumps(cap_data["technology_patterns"])
                existing.updated_at = datetime.utcnow()
                updated_count += 1
                code_to_id[existing.code] = existing.id
            else:
                # Create new
                new_cap = TechnicalCapability(
                    name=cap_data["name"],
                    code=cap_data["code"],
                    description=cap_data.get("description"),
                    acm_domain=cap_data["acm_domain"],
                    level=cap_data["level"],
                    level_number=cap_data["level_number"],
                    capability_type=cap_data.get("capability_type"),
                    is_foundational=cap_data.get("is_foundational", False),
                )
                if "technology_patterns" in cap_data and cap_data["technology_patterns"]:
                    new_cap.technology_patterns = json.dumps(cap_data["technology_patterns"])
                db.session.add(new_cap)
                db.session.flush()  # Get the ID
                code_to_id[new_cap.code] = new_cap.id
                created_count += 1

        db.session.commit()

        # Second pass: Set parent relationships
        for cap_data in capabilities:
            if cap_data.get("parent_code"):
                child = TechnicalCapability.query.filter_by(code=cap_data["code"]).first()
                parent_id = code_to_id.get(cap_data["parent_code"])
                if child and parent_id:
                    child.parent_id = parent_id

        db.session.commit()

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(capabilities),
            "domains": len(ACMDomain.ALL_DOMAINS),
        }

    @staticmethod
    def get_all_capabilities(
        domain: Optional[str] = None,
        level: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[TechnicalCapability], int]:
        """
        Get all technical capabilities with optional filtering.
        Returns tuple of (capabilities, total_count).
        """
        query = TechnicalCapability.query

        if domain:
            query = query.filter(TechnicalCapability.acm_domain == domain)
        if level:
            query = query.filter(TechnicalCapability.level == level)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    TechnicalCapability.name.ilike(search_term),
                    TechnicalCapability.code.ilike(search_term),
                    TechnicalCapability.description.ilike(search_term),
                )
            )

        total = query.count()
        capabilities = (
            query.order_by(TechnicalCapability.acm_domain, TechnicalCapability.code)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return capabilities, total

    @staticmethod
    def get_capability_by_id(capability_id: int) -> Optional[TechnicalCapability]:
        """Get a single capability by ID."""
        return TechnicalCapability.query.get(capability_id)

    @staticmethod
    def get_capability_by_code(code: str) -> Optional[TechnicalCapability]:
        """Get a single capability by code."""
        return TechnicalCapability.query.filter_by(code=code).first()

    @staticmethod
    def get_hierarchy(domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get hierarchical structure of capabilities for tree view."""
        return TechnicalCapability.get_hierarchy(domain)

    @staticmethod
    def get_domain_summary() -> Dict[str, Dict[str, Any]]:
        """Get summary statistics for each ACM domain."""
        return TechnicalCapability.get_domain_summary()

    @staticmethod
    def get_domains() -> List[Dict[str, str]]:
        """Get list of all ACM domains."""
        return get_domain_list()

    # Business Capability Mapping
    @staticmethod
    def map_to_business_capability(
        technical_capability_id: int,
        business_capability_id: int,
        relationship_type: str = "supports",
        strength: str = "medium",
    ) -> bool:
        """Map a technical capability to a business capability."""
        try:
            stmt = technical_capability_business_mapping.insert().values(
                technical_capability_id=technical_capability_id,
                business_capability_id=business_capability_id,
                relationship_type=relationship_type,
                strength=strength,
                created_at=datetime.utcnow(),
            )
            db.session.execute(stmt)  # tenant-filtered: scoped via parent FK (technical_capability_id, business_capability_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error mapping capabilities: {e}")
            return False

    @staticmethod
    def get_business_capability_mappings(
        technical_capability_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all business capabilities mapped to a technical capability."""
        from app.models.business_capabilities import BusinessCapability

        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return []

        return [
            {
                "id": bc.id,
                "name": bc.name,
                "code": getattr(bc, "code", None),
                "level": getattr(bc, "level", None),
            }
            for bc in tech_cap.business_capabilities
        ]

    # Application Mapping
    @staticmethod
    def map_to_application(
        technical_capability_id: int,
        application_id: int,
        capability_coverage: str = "partial",
        maturity_level: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Map a technical capability to an application."""
        try:
            stmt = application_technical_capability_mapping.insert().values(
                application_id=application_id,
                technical_capability_id=technical_capability_id,
                capability_coverage=capability_coverage,
                maturity_level=maturity_level,
                notes=notes,
                created_at=datetime.utcnow(),
            )
            db.session.execute(stmt)  # tenant-filtered: scoped via parent FK (application_id, technical_capability_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error mapping to application: {e}")
            return False

    @staticmethod
    def get_application_mappings(
        technical_capability_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all applications mapped to a technical capability."""
        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return []

        return [
            {
                "id": app.id,
                "name": app.name,
                "application_type": getattr(app, "application_type", None),
                "deployment_model": getattr(app, "deployment_model", None),
            }
            for app in tech_cap.applications
        ]

    @staticmethod
    def get_capabilities_for_application(
        application_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all technical capabilities for an application."""
        from app.models.application_portfolio import ApplicationComponent

        app = ApplicationComponent.query.get(application_id)
        if not app:
            return []

        return [
            {
                "id": tc.id,
                "name": tc.name,
                "code": tc.code,
                "acm_domain": tc.acm_domain,
                "level": tc.level,
            }
            for tc in app.technical_capabilities
        ]

    # APQC Process Mapping
    @staticmethod
    def map_to_apqc_process(
        technical_capability_id: int,
        apqc_process_id: int,
        relationship_type: str = "implements",
    ) -> bool:
        """Map a technical capability to an APQC process."""
        try:
            stmt = technical_capability_apqc_mapping.insert().values(
                technical_capability_id=technical_capability_id,
                apqc_process_id=apqc_process_id,
                relationship_type=relationship_type,
                created_at=datetime.utcnow(),
            )
            db.session.execute(stmt)  # tenant-filtered: scoped via parent FK (technical_capability_id, apqc_process_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error mapping to APQC process: {e}")
            return False

    @staticmethod
    def get_apqc_mappings(
        technical_capability_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all APQC processes mapped to a technical capability."""
        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return []

        return [
            {
                "id": proc.id,
                "name": proc.name,
                "process_id": getattr(proc, "process_id", None),
                "level": getattr(proc, "level", None),
            }
            for proc in tech_cap.apqc_processes
        ]

    # Vendor Product Mapping
    @staticmethod
    def map_to_vendor_product(
        technical_capability_id: int,
        vendor_product_id: int,
        capability_coverage: str = "partial",
    ) -> bool:
        """Map a technical capability to a vendor product."""
        try:
            stmt = technical_capability_vendor_mapping.insert().values(
                technical_capability_id=technical_capability_id,
                vendor_product_id=vendor_product_id,
                capability_coverage=capability_coverage,
                created_at=datetime.utcnow(),
            )
            db.session.execute(stmt)  # tenant-filtered: scoped via parent FK (technical_capability_id, vendor_product_id)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error mapping to vendor product: {e}")
            return False

    @staticmethod
    def get_vendor_mappings(
        technical_capability_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all vendor products mapped to a technical capability."""
        tech_cap = TechnicalCapability.query.get(technical_capability_id)
        if not tech_cap:
            return []

        return [
            {
                "id": vp.id,
                "name": vp.name,
                "vendor_name": getattr(vp, "vendor_name", None),
            }
            for vp in tech_cap.vendor_products
        ]

    # Gap Analysis
    @staticmethod
    def analyze_capability_gaps(
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze technical capability gaps.
        Returns domains/capabilities without application coverage.
        """
        query = TechnicalCapability.query

        if domain:
            query = query.filter(TechnicalCapability.acm_domain == domain)

        all_caps = query.all()

        # Batch-load app counts and vendor names to avoid N+1 queries
        from app.models.application_portfolio import ApplicationComponent

        atcm = application_technical_capability_mapping
        # 1) Count of applications per capability
        app_count_rows = (
            db.session.query(
                atcm.c.technical_capability_id,
                func.count(atcm.c.application_id),
            )
            .group_by(atcm.c.technical_capability_id)
            .all()
        )
        app_counts = dict(app_count_rows)

        # 2) Vendor names of mapped applications per capability
        vendor_name_rows = (
            db.session.query(
                atcm.c.technical_capability_id,
                ApplicationComponent.vendor_name,
            )
            .join(ApplicationComponent, ApplicationComponent.id == atcm.c.application_id)
            .filter(ApplicationComponent.vendor_name.isnot(None))
            .distinct()
            .all()
        )
        app_vendors_by_cap = {}
        for cap_id, vname in vendor_name_rows:
            app_vendors_by_cap.setdefault(cap_id, set()).add(vname)

        # 3) Vendor products per capability (for market data on uncovered caps)
        from app.models.vendor.vendor_organization import VendorProduct, VendorOrganization
        tcvm = technical_capability_vendor_mapping
        market_vendor_rows = (
            db.session.query(
                tcvm.c.technical_capability_id,
                VendorOrganization.name,
            )
            .join(VendorProduct, VendorProduct.id == tcvm.c.vendor_product_id)
            .join(VendorOrganization, VendorOrganization.id == VendorProduct.vendor_organization_id)
            .filter(VendorOrganization.name.isnot(None))
            .distinct()
            .all()
        )
        market_vendors_by_cap = {}
        for cap_id, vname in market_vendor_rows:
            market_vendors_by_cap.setdefault(cap_id, set()).add(vname)

        gaps = {
            "total_capabilities": len(all_caps),
            "covered": 0,
            "uncovered": 0,
            "by_domain": {},
            "uncovered_capabilities": [],
        }

        for cap in all_caps:
            domain_key = cap.acm_domain
            if domain_key not in gaps["by_domain"]:
                gaps["by_domain"][domain_key] = {"total": 0, "covered": 0, "uncovered": 0}

            gaps["by_domain"][domain_key]["total"] += 1

            cap_app_count = app_counts.get(cap.id, 0)

            if cap_app_count > 0:
                gaps["covered"] += 1
                gaps["by_domain"][domain_key]["covered"] += 1

                # Get vendors of mapped applications (from preloaded dict)
                vendors = sorted(app_vendors_by_cap.get(cap.id, set()))
                is_market_data = False
            else:
                gaps["uncovered"] += 1
                gaps["by_domain"][domain_key]["uncovered"] += 1

                # Get vendors that could fill this gap (market data, from preloaded dict)
                vendors = sorted(market_vendors_by_cap.get(cap.id, set()))
                is_market_data = len(vendors) > 0

            gaps["uncovered_capabilities"].append(
                {
                    "id": cap.id,
                    "name": cap.name,
                    "code": cap.code,
                    "domain": cap.acm_domain,
                    "level": cap.level,
                    "applications_count": cap_app_count,
                    "vendors_count": len(vendors),
                    "vendors": vendors,
                    "is_market_data": is_market_data,
                }
            )

        # Calculate coverage percentages
        if gaps["total_capabilities"] > 0:
            gaps["coverage_percentage"] = round(
                (gaps["covered"] / gaps["total_capabilities"]) * 100, 1
            )
        else:
            gaps["coverage_percentage"] = 0

        for domain_key, domain_stats in gaps["by_domain"].items():
            if domain_stats["total"] > 0:
                domain_stats["coverage_percentage"] = round(
                    (domain_stats["covered"] / domain_stats["total"]) * 100, 1
                )
            else:
                domain_stats["coverage_percentage"] = 0

        return gaps

    # Auto-classification
    @staticmethod
    def classify_application_domains(application_id: int) -> List[str]:
        """
        Auto-classify an application's ACM domains based on its technology stack.
        Returns list of suggested ACM domains.
        """
        from app.models.application_portfolio import ApplicationComponent

        app = ApplicationComponent.query.get(application_id)
        if not app:
            return []

        suggested_domains = set()

        # Parse technology stack
        tech_stack = []
        if app.technology_stack:
            try:
                tech_stack = (
                    json.loads(app.technology_stack)
                    if isinstance(app.technology_stack, str)
                    else app.technology_stack
                )
            except (ValueError, KeyError, TypeError):
                tech_stack = [app.technology_stack]

        # Add frameworks and languages
        if app.frameworks:
            try:
                frameworks = (
                    json.loads(app.frameworks)
                    if isinstance(app.frameworks, str)
                    else app.frameworks
                )
                tech_stack.extend(frameworks)
            except (ValueError, KeyError, TypeError):
                tech_stack.append(app.frameworks)

        if app.programming_languages:
            try:
                languages = (
                    json.loads(app.programming_languages)
                    if isinstance(app.programming_languages, str)
                    else app.programming_languages
                )
                tech_stack.extend(languages)
            except (ValueError, KeyError, TypeError):
                tech_stack.append(app.programming_languages)

        tech_stack_lower = [t.lower() for t in tech_stack if t]

        # Classification rules
        ux_keywords = [
            "react",
            "angular",
            "vue",
            "flutter",
            "swift",
            "kotlin",
            "ui",
            "frontend",
            "mobile",
            "css",
            "html",
        ]
        app_services_keywords = [
            "api",
            "rest",
            "graphql",
            "grpc",
            "microservice",
            "backend",
            "spring",
            "django",
            "flask",
            "express",
            "node",
        ]
        data_keywords = [
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "elasticsearch",
            "sql",
            "database",
            "snowflake",
            "bigquery",
        ]
        security_keywords = [
            "oauth",
            "saml",
            "auth",
            "identity",
            "okta",
            "azure ad",
            "security",
            "vault",
            "encryption",
        ]
        devops_keywords = [
            "kubernetes",
            "docker",
            "terraform",
            "jenkins",
            "github actions",
            "aws",
            "azure",
            "gcp",
            "ci/cd",
        ]
        ai_keywords = [
            "tensorflow",
            "pytorch",
            "ml",
            "ai",
            "machine learning",
            "pandas",
            "numpy",
            "analytics",
            "data science",
        ]
        comm_keywords = [
            "kafka",
            "rabbitmq",
            "websocket",
            "socket.io",
            "notification",
            "email",
            "sms",
            "twilio",
        ]

        for tech in tech_stack_lower:
            if any(kw in tech for kw in ux_keywords):
                suggested_domains.add(ACMDomain.USER_EXPERIENCE)
            if any(kw in tech for kw in app_services_keywords):
                suggested_domains.add(ACMDomain.APPLICATION_SERVICES)
            if any(kw in tech for kw in data_keywords):
                suggested_domains.add(ACMDomain.DATA_STORAGE)
            if any(kw in tech for kw in security_keywords):
                suggested_domains.add(ACMDomain.SECURITY_IDENTITY)
            if any(kw in tech for kw in devops_keywords):
                suggested_domains.add(ACMDomain.DEVOPS_PLATFORM)
            if any(kw in tech for kw in ai_keywords):
                suggested_domains.add(ACMDomain.AI_ANALYTICS)
            if any(kw in tech for kw in comm_keywords):
                suggested_domains.add(ACMDomain.COMMUNICATION)

        # Check application type for additional hints
        if app.application_type:
            app_type_lower = app.application_type.lower()
            if "mobile" in app_type_lower or "web" in app_type_lower:
                suggested_domains.add(ACMDomain.USER_EXPERIENCE)
            if "api" in app_type_lower or "service" in app_type_lower:
                suggested_domains.add(ACMDomain.APPLICATION_SERVICES)
            if "data" in app_type_lower or "analytics" in app_type_lower:
                suggested_domains.add(ACMDomain.DATA_STORAGE)
                suggested_domains.add(ACMDomain.AI_ANALYTICS)

        return list(suggested_domains)

    @staticmethod
    def auto_map_application_capabilities(
        application_id: int,
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Automatically map an application to technical capabilities based on its tech stack.
        Returns mapping results.
        """
        from app.models.application_portfolio import ApplicationComponent

        app = ApplicationComponent.query.get(application_id)
        if not app:
            return {"error": "Application not found", "mappings": []}

        # Get suggested domains
        suggested_domains = ACMTechnicalCapabilityService.classify_application_domains(
            application_id
        )

        # Update application's ACM fields
        app.acm_domains = json.dumps(suggested_domains)
        if suggested_domains:
            app.acm_primary_domain = suggested_domains[0]

        mappings = []
        # Map to L1 capabilities for each suggested domain
        for domain in suggested_domains:
            l1_caps = TechnicalCapability.query.filter_by(acm_domain=domain, level="L1").all()

            for cap in l1_caps:
                # Check if mapping already exists
                existing = db.session.execute(  # tenant-filtered: scoped via parent FK (application_id, technical_capability_id)
                    application_technical_capability_mapping.select().where(
                        and_(
                            application_technical_capability_mapping.c.application_id
                            == application_id,
                            application_technical_capability_mapping.c.technical_capability_id
                            == cap.id,
                        )
                    )
                ).fetchone()

                if not existing:
                    ACMTechnicalCapabilityService.map_to_application(
                        cap.id, application_id, "partial"
                    )
                    mappings.append(
                        {
                            "capability_id": cap.id,
                            "capability_name": cap.name,
                            "domain": domain,
                        }
                    )

        if commit:
            db.session.commit()

        return {
            "application_id": application_id,
            "application_name": app.name,
            "suggested_domains": suggested_domains,
            "mappings_created": len(mappings),
            "mappings": mappings,
        }
