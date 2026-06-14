"""
-> app.modules.vendors.services.integration_service

Service to generate comprehensive ArchiMate elements for VendorProduct from catalogue data.
Creates multiple elements per vendor based on capabilities, modules, and services.
"""
import logging

from app import db

# Configure logger
logger = logging.getLogger(__name__)
from datetime import datetime

from sqlalchemy import text

from app.models.models import ArchiMateElement
from app.models.vendor.vendor_organization import VendorProduct


class VendorProductArchiMateGenerator:
    """Generate ArchiMate 3.2 elements from vendor catalogue data."""

    def __init__(self, vendor_data, vendor_org, product):
        """
        Initialize generator with vendor catalogue data.

        Args:
            vendor_data: Dictionary from VENDOR_CATALOGUE
            vendor_org: VendorOrganization instance
            product: VendorProduct instance
        """
        self.vendor_data = vendor_data
        self.vendor_org = vendor_org
        self.product = product
        self.vendor_name = vendor_data["name"]
        self.created_elements = []

    def generate_all(self):
        """Generate comprehensive ArchiMate elements for this vendor product."""
        logger.info(f"\n*** Generating ArchiMate elements for {self.vendor_name}...")

        # 1. Main application component (platform/system)
        self._generate_main_component()

        # 2. Business capabilities from vendor capabilities
        self._generate_capabilities()

        # 3. Application services from ITIL processes
        self._generate_itil_application_services()

        # 4. Application services from COBIT processes
        self._generate_cobit_application_services()

        # 5. Application components for each capability
        self._generate_capability_components()

        # 6. Application interfaces (APIs and integrations)
        self._generate_application_interfaces()

        # 7. Technology services (deployment, hosting, infrastructure)
        self._generate_technology_services()

        # 8. Data objects (key entities managed by the system)
        self._generate_data_objects()

        # 9. Business processes supported
        self._generate_business_processes()

        return self.created_elements

    def _generate_main_component(self):
        """Generate main ApplicationComponent for the vendor platform."""
        element = self._create_or_update_element(
            name=f"{self.vendor_name} Platform",
            element_type="ApplicationComponent",
            layer="application",
            description=self.vendor_data.get("description", ""),
            documentation=f"Primary application platform for {self.vendor_name}",
        )
        self._link_to_product(element)
        logger.info(f"  [PLATFORM] {element.name}")

    def _generate_capabilities(self):
        """Generate Capability elements from vendor capabilities (ALL of them)."""
        capabilities = self.vendor_data.get("capabilities", [])
        if not capabilities:
            return

        logger.info(f"  [CAPABILITIES] Generating {len(capabilities)} business capabilities...")
        for cap_code in capabilities:  # Generate ALL capabilities
            cap_name = self._get_capability_name(cap_code)
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {cap_name}",
                element_type="Capability",
                layer="strategy",
                description=f"{cap_name} business capability provided by {self.vendor_name}",
                documentation=f"Business capability code: {cap_code}",
            )
            self._link_to_product(element)

    def _generate_itil_application_services(self):
        """Generate ApplicationService elements from ITIL processes."""
        itil_processes = self.vendor_data.get("itilProcesses", [])
        if not itil_processes:
            return

        logger.info(
            f"  [ITIL SERVICES] Generating {len(itil_processes)} ITIL application services..."
        )
        for process_code in itil_processes:
            process_name = self._get_itil_process_name(process_code)
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {process_name}",
                element_type="ApplicationService",
                layer="application",
                description=f"ITIL {process_name} service provided by {self.vendor_name}",
                documentation=f"ITIL process: {process_code}",
            )
            self._link_to_product(element)

    def _generate_cobit_application_services(self):
        """Generate ApplicationService elements from COBIT processes."""
        cobit_processes = self.vendor_data.get("cobitProcesses", [])
        if not cobit_processes:
            return

        logger.info(
            f"  [COBIT SERVICES] Generating {len(cobit_processes)} COBIT application services..."
        )
        for process_code in cobit_processes[:15]:  # Top 15 COBIT processes
            process_name = self._get_cobit_process_name(process_code)
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {process_name}",
                element_type="ApplicationService",
                layer="application",
                description=f"COBIT {process_code}: {process_name}",
                documentation=f"COBIT process: {process_code}",
            )
            self._link_to_product(element)

    def _generate_capability_components(self):
        """Generate ApplicationComponent for each major capability."""
        capabilities = self.vendor_data.get("capabilities", [])[
            :12
        ]  # Top 12 capabilities as components
        if not capabilities:
            return

        logger.info(f"  [COMPONENTS] Generating {len(capabilities)} capability components...")
        for cap_code in capabilities:
            cap_name = self._get_capability_name(cap_code)
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {cap_name} Module",
                element_type="ApplicationComponent",
                layer="application",
                description=f"{cap_name} application module within {self.vendor_name}",
                documentation=f"Application component for: {cap_code}",
            )
            self._link_to_product(element)

    def _generate_application_interfaces(self):
        """Generate ApplicationInterface elements for integrations and APIs."""
        integrations = self.vendor_data.get("integrations", [])
        if not integrations:
            return

        logger.info(f"  [INTERFACES] Generating {len(integrations)} application interfaces...")

        # REST API
        api_element = self._create_or_update_element(
            name=f"{self.vendor_name} REST API",
            element_type="ApplicationInterface",
            layer="application",
            description=f"RESTful API for {self.vendor_name} integration",
            documentation="Standard REST API interface",
        )
        self._link_to_product(api_element)

        # Integration interfaces
        for integration in integrations[:10]:  # Top 10 integrations
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {integration} Integration",
                element_type="ApplicationInterface",
                layer="application",
                description=f"Integration interface with {integration}",
                documentation=f"Pre-built integration: {integration}",
            )
            self._link_to_product(element)

    def _generate_technology_services(self):
        """Generate TechnologyService elements for deployment, hosting, and infrastructure."""
        # Deployment models
        deployment_models = self.vendor_data.get("deploymentModel", [])
        if deployment_models:
            logger.info(
                f"  [DEPLOYMENT] Generating {len(deployment_models)} deployment technology services..."
            )
            for model in deployment_models:
                element = self._create_or_update_element(
                    name=f"{self.vendor_name} - {model} Deployment",
                    element_type="TechnologyService",
                    layer="technology",
                    description=f"{model} deployment option for {self.vendor_name}",
                    documentation=f"Deployment model: {model}",
                )
                self._link_to_product(element)

        # Infrastructure services based on deployment
        if "CLOUD" in deployment_models or "HYBRID" in deployment_models:
            services = [
                ("Cloud Hosting", "Multi-tenant cloud infrastructure"),
                ("Backup & Recovery", "Automated backup and disaster recovery"),
                ("Monitoring & Alerting", "Cloud-based monitoring infrastructure"),
                ("Security Services", "Cloud security and encryption services"),
            ]
            logger.info(f"  [INFRASTRUCTURE] Generating {len(services)} infrastructure services...")
            for svc_name, svc_desc in services:
                element = self._create_or_update_element(
                    name=f"{self.vendor_name} - {svc_name}",
                    element_type="TechnologyService",
                    layer="technology",
                    description=svc_desc,
                    documentation=f"Technology service: {svc_name}",
                )
                self._link_to_product(element)

    def _generate_data_objects(self):
        """Generate DataObject elements for key entities managed by the system."""
        category = self.vendor_data.get("category", "ITSM")

        data_object_map = {
            "ITSM": [
                ("Incident Record", "Incident management records and history"),
                ("Change Record", "Change request and approval records"),
                ("Configuration Item", "Configuration management database records"),
                ("Service Catalog Item", "Service catalog definitions"),
                ("Knowledge Article", "Knowledge base articles"),
                ("User Profile", "User and technician profiles"),
                ("SLA Definition", "Service level agreement definitions"),
                ("Asset Record", "IT asset inventory records"),
            ],
            "EA_TOOLS": [
                ("Architecture Model", "Enterprise architecture models and diagrams"),
                ("Application Portfolio", "Application inventory and relationships"),
                ("Technology Stack", "Technology standards and stacks"),
                ("Business Capability", "Business capability model"),
                ("Roadmap Item", "Architecture roadmap items"),
                ("Stakeholder", "Architecture stakeholder registry"),
            ],
            "GRC": [
                ("Risk Assessment", "Risk assessment records"),
                ("Control Definition", "Control framework definitions"),
                ("Policy Document", "Policy and procedure documents"),
                ("Audit Report", "Audit findings and reports"),
                ("Compliance Record", "Compliance status tracking"),
                ("Incident Report", "Security incident records"),
            ],
            "ITAM": [
                ("Software License", "Software license entitlements"),
                ("Hardware Asset", "Hardware inventory records"),
                ("Contract", "Vendor contract records"),
                ("License Metric", "License usage metrics"),
                ("Cost Center", "Cost allocation records"),
            ],
            "APM": [
                ("Performance Metric", "Application performance metrics"),
                ("Transaction Trace", "Transaction tracing data"),
                ("Alert Definition", "Alert rules and thresholds"),
                ("Topology Map", "Application topology data"),
            ],
            "SECURITY": [
                ("Security Event", "Security event logs"),
                ("Threat Intelligence", "Threat intelligence feeds"),
                ("Vulnerability", "Vulnerability scan results"),
                ("Security Policy", "Security policy definitions"),
            ],
            "CLOUD_PLATFORM": [
                ("Compute Instance", "Virtual machine instances"),
                ("Storage Bucket", "Object storage containers"),
                ("Network Config", "Network configuration"),
                ("IAM Policy", "Identity and access policies"),
            ],
            "DEVOPS": [
                ("Build Pipeline", "CI/CD pipeline definitions"),
                ("Container Image", "Container registry images"),
                ("Deployment Config", "Deployment configurations"),
                ("Test Result", "Automated test results"),
            ],
            "DATA_GOVERNANCE": [
                ("Data Asset", "Data asset catalog entries"),
                ("Data Lineage", "Data lineage tracking"),
                ("Data Quality Rule", "Data quality definitions"),
                ("Business Glossary", "Business term definitions"),
            ],
            "BPM": [
                ("Process Definition", "Business process models"),
                ("Workflow Instance", "Active workflow instances"),
                ("Process Metric", "Process performance metrics"),
                ("Case Record", "Case management records"),
            ],
        }

        data_objects = data_object_map.get(
            category,
            [
                ("Record", "System records"),
                ("Configuration", "System configuration"),
                ("User Data", "User information"),
            ],
        )

        logger.info(f"  [DATA OBJECTS] Generating {len(data_objects)} data objects...")
        for obj_name, obj_desc in data_objects:
            element = self._create_or_update_element(
                name=f"{self.vendor_name} - {obj_name}",
                element_type="DataObject",
                layer="application",
                description=obj_desc,
                documentation=f"Data entity: {obj_name}",
            )
            self._link_to_product(element)

    def _generate_business_processes(self):
        """Generate BusinessProcess elements for key processes supported."""
        itil_processes = self.vendor_data.get("itilProcesses", [])[
            :8
        ]  # Top 8 ITIL processes as business processes
        if not itil_processes:
            return

        logger.info(
            f"  [BUSINESS PROCESSES] Generating {len(itil_processes)} business processes..."
        )
        for process_code in itil_processes:
            process_name = self._get_itil_process_name(process_code)
            element = self._create_or_update_element(
                name=f"{process_name} Process",
                element_type="BusinessProcess",
                layer="business",
                description=f"Business process: {process_name}",
                documentation=f"ITIL process supported by {self.vendor_name}",
            )
            self._link_to_product(element)

    def _create_or_update_element(self, name, element_type, layer, description, documentation):
        """Create or update an ArchiMate element."""
        # Check if element already exists
        element = ArchiMateElement.query.filter_by(name=name, type=element_type).first()

        if element:
            # Update existing
            element.description = description
            element.documentation = documentation
            element.status = "active"
            element.updated_at = datetime.utcnow()
        else:
            # Create new
            element = ArchiMateElement(
                name=name,
                type=element_type,
                layer=layer,
                description=description,
                documentation=documentation,
                status="active",
            )
            db.session.add(element)
            db.session.flush()
            self.created_elements.append(element)

        return element

    def _link_to_product(self, element):
        """Link ArchiMate element to vendor product."""
        # Check if link already exists
        existing = db.session.execute(  # tenant-filtered: scoped via product FK
            text(
                "SELECT 1 FROM application_vendor_products WHERE archimate_element_id = :elem_id AND vendor_product_id = :prod_id"
            ),
            {"elem_id": element.id, "prod_id": self.product.id},
        ).first()

        if not existing:
            db.session.execute(  # tenant-filtered: scoped via product FK
                text(
                    "INSERT INTO application_vendor_products (archimate_element_id, vendor_product_id, deployment_type, criticality) VALUES (:elem_id, :prod_id, :deploy, :crit)"
                ),
                {
                    "elem_id": element.id,
                    "prod_id": self.product.id,
                    "deploy": "primary_system",
                    "crit": "business_critical",
                },
            )

    def _get_capability_name(self, cap_code):
        """Get human-readable capability name from code."""
        capability_names = {
            "service-desk": "Service Desk",
            "incident-management": "Incident Management",
            "problem-management": "Problem Management",
            "change-management": "Change Management",
            "release-management": "Release Management",
            "service-request": "Service Request Management",
            "configuration-management": "Configuration Management",
            "asset-management": "Asset Management",
            "knowledge-management": "Knowledge Management",
            "service-catalog": "Service Catalog",
            "workflow-orchestration": "Workflow Orchestration",
            "automation": "Process Automation",
            "ai-ml": "AI/ML Capabilities",
            "reporting-analytics": "Reporting & Analytics",
            "integration-platform": "Integration Platform",
            "risk-management": "Risk Management",
            "compliance-management": "Compliance Management",
            "audit-management": "Audit Management",
            "license-management": "License Management",
            "contract-management": "Contract Management",
            "monitoring-alerting": "Monitoring & Alerting",
            "threat-detection": "Threat Detection",
            "vulnerability-management": "Vulnerability Management",
            "data-catalog": "Data Catalog",
            "data-governance": "Data Governance",
            "data-quality": "Data Quality Management",
            "business-process": "Business Process Management",
        }
        return capability_names.get(cap_code, cap_code.replace("-", " ").title())

    def _get_itil_process_name(self, process_code):
        """Get ITIL process name from code."""
        itil_names = {
            "incident-management": "Incident Management",
            "problem-management": "Problem Management",
            "change-management": "Change Management",
            "release-deployment": "Release and Deployment Management",
            "service-asset-config": "Service Asset and Configuration Management",
            "knowledge-management": "Knowledge Management",
            "request-fulfillment": "Request Fulfillment",
            "event-management": "Event Management",
            "service-catalog-mgmt": "Service Catalog Management",
            "service-level": "Service Level Management",
            "availability-management": "Availability Management",
            "capacity-management": "Capacity Management",
            "it-service-continuity": "IT Service Continuity Management",
            "information-security": "Information Security Management",
            "supplier-management": "Supplier Management",
            "transition-planning": "Transition Planning and Support",
            "change-evaluation": "Change Evaluation",
            "service-validation": "Service Validation and Testing",
        }
        return itil_names.get(process_code, process_code.replace("-", " ").title())

    def _get_cobit_process_name(self, process_code):
        """Get COBIT process name from code."""
        cobit_names = {
            "DSS01": "Manage Operations",
            "DSS02": "Manage Service Requests and Incidents",
            "DSS03": "Manage Problems",
            "DSS04": "Manage Continuity",
            "DSS05": "Manage Security Services",
            "DSS06": "Manage Business Process Controls",
            "BAI01": "Manage Programmes and Projects",
            "BAI02": "Manage Requirements Definition",
            "BAI03": "Manage Solutions Identification and Build",
            "BAI04": "Manage Availability and Capacity",
            "BAI05": "Manage Organisational Change",
            "BAI06": "Manage IT Changes",
            "BAI07": "Manage IT Change Acceptance and Transitioning",
            "BAI08": "Manage Knowledge",
            "BAI09": "Manage Assets",
            "BAI10": "Manage Configuration",
            "APO01": "Manage the IT Management Framework",
            "APO02": "Manage Strategy",
            "APO03": "Manage Enterprise Architecture",
            "APO04": "Manage Innovation",
            "APO05": "Manage Portfolio",
            "APO06": "Manage Budget and Costs",
            "APO07": "Manage Human Resources",
            "APO08": "Manage Relationships",
            "APO09": "Manage Service Agreements",
            "APO10": "Manage Suppliers",
            "APO11": "Manage Quality",
            "APO12": "Manage Risk",
            "APO13": "Manage Security",
            "EDM01": "Ensure Governance Framework Setting and Maintenance",
            "EDM02": "Ensure Benefits Delivery",
            "EDM03": "Ensure Risk Optimisation",
            "EDM04": "Ensure Resource Optimisation",
            "EDM05": "Ensure Stakeholder Transparency",
            "MEA01": "Monitor, Evaluate and Assess Performance",
            "MEA02": "Monitor, Evaluate and Assess Internal Control",
            "MEA03": "Monitor, Evaluate and Assess Compliance",
        }
        return cobit_names.get(process_code, process_code)


def generate_vendor_archimate_portfolio():
    """
    Generate comprehensive ArchiMate elements for all vendor products.
    Uses vendor catalogue data to create rich ArchiMate models.
    """
    from app.models.vendor.vendor_organization import VendorOrganization
    from app.seed_data.simple_vendor_catalogue import VENDOR_CATALOGUE

    logger.info("\n" + "=" * 70)
    logger.info("GENERATING COMPREHENSIVE ARCHIMATE PORTFOLIO FOR VENDORS")
    logger.info("=" * 70)

    total_elements = 0

    for vendor_data in VENDOR_CATALOGUE:
        vendor = VendorOrganization.query.filter_by(name=vendor_data["name"]).first()
        if not vendor:
            logger.info(f"⚠️  Vendor not found: {vendor_data['name']}")
            continue

        product = VendorProduct.query.filter_by(vendor_organization_id=vendor.id).first()
        if not product:
            logger.info(f"⚠️  No product found for: {vendor_data['name']}")
            continue

        generator = VendorProductArchiMateGenerator(vendor_data, vendor, product)
        elements = generator.generate_all()
        total_elements += len(elements)

    db.session.commit()

    logger.info("\n" + "=" * 70)
    logger.info(f"\n*** COMPLETE: Generated {total_elements} ArchiMate elements")
    logger.info("=" * 70 + "\n")

    return total_elements
