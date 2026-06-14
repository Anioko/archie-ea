"""
-> app.modules.architecture.services.archimate_service

Comprehensive ArchiMate 3.2 Generation Service

Auto-generates ArchiMate elements during application import with:
- Multi-layer element generation (Strategy, Business, Application, Technology, Motivation)
- APQC PCF integration for intelligent element mapping
- ArchiMate 3.2 relationship auto-generation
- Vendor product alignment

Designed for Enterprise, Systems, Solutions, Applications, Business and Integration architecture needs.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.apqc_process import APQCProcess
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.models.archimate_element_types import (
    APQC_RELATIONSHIP_TEMPLATES,
    ArchiMateElementTypes,
    RelationshipPattern,
)

logger = logging.getLogger(__name__)


class ComprehensiveArchiMateService:
    """
    Comprehensive ArchiMate 3.2 element generation service.

    Generates elements across all ArchiMate layers:
    - Strategy Layer: Capability, Resource, CourseOfAction, ValueStream
    - Business Layer: BusinessProcess, BusinessService, BusinessFunction, BusinessRole, BusinessActor
    - Application Layer: ApplicationComponent, ApplicationService, ApplicationInterface, DataObject
    - Technology Layer: Node, SystemSoftware, TechnologyService, Artifact
    - Motivation Layer: Goal, Driver, Principle, Requirement, Constraint
    - Implementation Layer: WorkPackage, Deliverable
    """

    # APQC Category to ArchiMate element type mappings (comprehensive)
    APQC_ELEMENT_GENERATION_MAP = {
        # 1.0 - Develop Vision and Strategy
        "1.0": {
            "strategy": ["Capability", "CourseOfAction", "ValueStream"],
            "business": ["BusinessFunction", "BusinessProcess"],
            "motivation": ["Goal", "Driver", "Principle"],
            "application": ["ApplicationService"],
        },
        # 2.0 - Develop and Manage Products and Services
        "2.0": {
            "strategy": ["Capability", "ValueStream"],
            "business": ["BusinessProcess", "BusinessService", "Product", "BusinessRole"],
            "application": ["ApplicationComponent", "ApplicationService", "DataObject"],
            "motivation": ["Requirement", "Goal"],
        },
        # 3.0 - Market and Sell Products and Services
        "3.0": {
            "business": [
                "BusinessProcess",
                "BusinessService",
                "BusinessInterface",
                "BusinessActor",
                "Contract",
            ],
            "application": ["ApplicationComponent", "ApplicationService", "ApplicationInterface"],
            "motivation": ["Goal", "Outcome"],
        },
        # 4.0 - Deliver Physical Products
        "4.0": {
            "business": ["BusinessProcess", "BusinessService", "BusinessEvent"],
            "physical": ["DistributionNetwork", "Facility", "Material"],
            "application": ["ApplicationComponent", "ApplicationProcess"],
        },
        # 5.0 - Deliver Services
        "5.0": {
            "business": [
                "BusinessProcess",
                "BusinessService",
                "BusinessInterface",
                "BusinessRole",
                "Contract",
            ],
            "application": ["ApplicationComponent", "ApplicationService"],
            "physical": ["Equipment", "Facility"],
        },
        # 6.0 - Manage Customer Service
        "6.0": {
            "business": [
                "BusinessProcess",
                "BusinessService",
                "BusinessRole",
                "BusinessActor",
                "BusinessInterface",
            ],
            "application": ["ApplicationComponent", "ApplicationService", "ApplicationEvent"],
        },
        # 7.0 - Develop and Manage IT
        "7.0": {
            "application": [
                "ApplicationComponent",
                "ApplicationService",
                "ApplicationInterface",
                "ApplicationFunction",
                "DataObject",
            ],
            "technology": [
                "Node",
                "SystemSoftware",
                "TechnologyService",
                "Artifact",
                "CommunicationNetwork",
            ],
            "business": ["BusinessProcess", "BusinessFunction"],
            "motivation": ["Requirement", "Principle"],
        },
        # 8.0 - Manage Enterprise Information
        "8.0": {
            "business": ["BusinessObject", "BusinessProcess", "Representation"],
            "application": ["DataObject", "ApplicationComponent", "ApplicationService"],
            "technology": ["Artifact", "Node"],
            "motivation": ["Meaning", "Principle"],
        },
        # 9.0 - Manage Financial Resources
        "9.0": {
            "business": ["BusinessProcess", "BusinessFunction", "BusinessRole", "Contract"],
            "application": ["ApplicationComponent", "ApplicationService", "DataObject"],
            "physical": ["Facility", "Equipment"],
            "motivation": ["Principle", "Constraint"],
        },
        # 10.0 - Acquire, Construct, and Manage Assets
        "10.0": {
            "strategy": ["Resource", "Capability"],
            "business": ["BusinessProcess", "BusinessFunction", "Contract"],
            "physical": ["Facility", "Equipment"],
            "application": ["ApplicationComponent", "ApplicationService"],
            "motivation": ["Assessment", "Constraint", "Requirement"],
        },
        # 11.0 - Manage Enterprise Risk, Compliance, Remediation, Resiliency
        "11.0": {
            "motivation": [
                "Assessment",
                "Constraint",
                "Requirement",
                "Driver",
                "Stakeholder",
                "Principle",
            ],
            "business": ["BusinessProcess", "BusinessFunction", "BusinessRole"],
            "application": ["ApplicationComponent", "ApplicationService"],
        },
        # 12.0 - Manage External Relationships
        "12.0": {
            "business": [
                "BusinessActor",
                "BusinessCollaboration",
                "BusinessInterface",
                "Contract",
                "BusinessProcess",
            ],
            "motivation": ["Meaning", "Stakeholder"],
            "application": ["ApplicationInterface", "ApplicationService"],
        },
        # 13.0 - Develop and Manage Human Capital
        "13.0": {
            "strategy": ["Resource", "Capability"],
            "business": ["BusinessRole", "BusinessActor", "BusinessProcess", "BusinessFunction"],
            "application": ["ApplicationComponent", "ApplicationService"],
            "motivation": ["Goal", "Requirement"],
        },
    }

    def __init__(self):
        self._model_cache = {}

    def _get_or_create_architecture_model(self, app: ApplicationComponent) -> ArchitectureModel:
        """Get or create an architecture model for the application."""
        model_name = f"{app.name} Architecture"

        # Check cache first
        if model_name in self._model_cache:
            return self._model_cache[model_name]

        model = ArchitectureModel.query.filter_by(name=model_name).first()

        if not model:
            model = ArchitectureModel(
                name=model_name,
                version="1.0",
                model_data=json.dumps(
                    {
                        "source": "ComprehensiveArchiMateService",
                        "application_id": app.id,
                        "application_name": app.name,
                        "generated_at": datetime.utcnow().isoformat(),
                        "archimate_version": "3.2",
                    }
                ),
            )
            db.session.add(model)
            db.session.flush()

        self._model_cache[model_name] = model
        return model

    def _get_apqc_category(self, process_code: str) -> str:
        """Extract APQC category from process code (e.g., '7.1.2' -> '7.0')."""
        if not process_code:
            return None
        parts = process_code.split(".")
        if parts:
            return f"{parts[0]}.0"
        return None

    def _create_element(
        self,
        architecture_model: ArchitectureModel,
        element_type: str,
        name: str,
        layer: str,
        description: str = None,
        scope: str = "application",
        properties: Dict = None,
        source_app_id: int = None,
        apqc_process: APQCProcess = None,
    ) -> ArchiMateElement:
        """Create an ArchiMate element with deduplication."""

        # Check for existing element with same name and type in this architecture
        existing = ArchiMateElement.query.filter_by(
            name=name, type=element_type, architecture_id=architecture_model.id
        ).first()

        if existing:
            return existing

        # Build properties
        props = properties or {}
        props["source"] = "comprehensive_archimate_service"
        props["generated_at"] = datetime.utcnow().isoformat()
        if source_app_id:
            props["source_application_id"] = source_app_id
        if apqc_process:
            props["apqc_process_code"] = apqc_process.process_code
            props["apqc_process_name"] = apqc_process.process_name
            props["apqc_category_1"] = apqc_process.category_level_1
            props["apqc_category_2"] = apqc_process.category_level_2

        element = ArchiMateElement(
            name=name,
            type=element_type,
            layer=layer,
            description=description,
            scope=scope,
            architecture_id=architecture_model.id,
            properties=json.dumps(props) if props else None,
        )
        db.session.add(element)
        db.session.flush()

        return element

    def _create_relationship(
        self,
        architecture_model: ArchitectureModel,
        source_element: ArchiMateElement,
        target_element: ArchiMateElement,
        relationship_type: str,
    ) -> ArchiMateRelationship:
        """Create an ArchiMate relationship with deduplication."""

        # Check for existing relationship
        existing = ArchiMateRelationship.query.filter_by(
            source_id=source_element.id,
            target_id=target_element.id,
            type=relationship_type,
            architecture_id=architecture_model.id,
        ).first()

        if existing:
            return existing

        relationship = ArchiMateRelationship(
            source_id=source_element.id,
            target_id=target_element.id,
            type=relationship_type,
            architecture_id=architecture_model.id,
        )
        db.session.add(relationship)
        db.session.flush()

        return relationship

    def generate_elements_for_application(
        self,
        application: ApplicationComponent,
        apqc_processes: List[APQCProcess] = None,
        include_layers: List[str] = None,
        include_relationships: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive ArchiMate elements for an application.

        Args:
            application: The ApplicationComponent to generate elements for
            apqc_processes: List of linked APQC processes (if None, will fetch from DB)
            include_layers: Specific layers to include (if None, includes all)
            include_relationships: Whether to generate relationships

        Returns:
            Dict with generation statistics and element details
        """
        logger.info(f"Starting comprehensive ArchiMate generation for {application.name}")

        # Default to all layers
        if not include_layers:
            include_layers = [
                "strategy",
                "business",
                "application",
                "technology",
                "physical",
                "motivation",
                "implementation_migration",
            ]

        # Get architecture model
        arch_model = self._get_or_create_architecture_model(application)

        # Fetch APQC processes if not provided
        if apqc_processes is None:
            apqc_processes = self._get_application_apqc_processes(application.id)

        stats = {
            "elements_created": 0,
            "elements_by_layer": {},
            "elements_by_type": {},
            "relationships_created": 0,
            "apqc_processes_used": len(apqc_processes),
            "elements": [],
            "relationships": [],
        }

        created_elements = {}  # Track elements by type for relationship generation

        # 1. Always create core ApplicationComponent element
        app_element = self._create_element(
            architecture_model=arch_model,
            element_type="ApplicationComponent",
            name=application.name,
            layer="application",
            description=application.description or f"Application: {application.name}",
            scope="application",
            source_app_id=application.id,
            properties={
                "component_type": application.component_type,
                "technology_stack": application.technology_stack,
                "deployment_status": application.deployment_status,
                "business_criticality": application.business_criticality,
            },
        )
        created_elements["ApplicationComponent"] = [app_element]
        stats["elements"].append(
            {
                "id": app_element.id,
                "name": app_element.name,
                "type": "ApplicationComponent",
                "layer": "application",
            }
        )
        stats["elements_created"] += 1
        stats["elements_by_layer"]["application"] = (
            stats["elements_by_layer"].get("application", 0) + 1
        )
        stats["elements_by_type"]["ApplicationComponent"] = (
            stats["elements_by_type"].get("ApplicationComponent", 0) + 1
        )

        # 2. Generate elements based on application attributes
        if "application" in include_layers:
            # Create ApplicationService for the app
            service_element = self._create_element(
                architecture_model=arch_model,
                element_type="ApplicationService",
                name=f"{application.name} Service",
                layer="application",
                description=f"Services provided by {application.name}",
                scope="application",
                source_app_id=application.id,
            )
            created_elements.setdefault("ApplicationService", []).append(service_element)
            stats["elements"].append(
                {
                    "id": service_element.id,
                    "name": service_element.name,
                    "type": "ApplicationService",
                    "layer": "application",
                }
            )
            stats["elements_created"] += 1
            stats["elements_by_layer"]["application"] = (
                stats["elements_by_layer"].get("application", 0) + 1
            )
            stats["elements_by_type"]["ApplicationService"] = (
                stats["elements_by_type"].get("ApplicationService", 0) + 1
            )

            # Create ApplicationInterface if app has interfaces
            if application.interfaces_count and application.interfaces_count > 0:
                interface_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="ApplicationInterface",
                    name=f"{application.name} Interface",
                    layer="application",
                    description=f"Integration interfaces for {application.name} ({application.interfaces_count} interfaces)",
                    scope="application",
                    source_app_id=application.id,
                    properties={"interfaces_count": application.interfaces_count},
                )
                created_elements.setdefault("ApplicationInterface", []).append(interface_element)
                stats["elements"].append(
                    {
                        "id": interface_element.id,
                        "name": interface_element.name,
                        "type": "ApplicationInterface",
                        "layer": "application",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["application"] = (
                    stats["elements_by_layer"].get("application", 0) + 1
                )
                stats["elements_by_type"]["ApplicationInterface"] = (
                    stats["elements_by_type"].get("ApplicationInterface", 0) + 1
                )

        # 3. Generate technology layer elements
        if "technology" in include_layers:
            # Node for hosting
            if application.hosting_environment:
                node_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="Node",
                    name=f"{application.hosting_environment} Environment",
                    layer="technology",
                    description=f"Hosting environment for {application.name}",
                    scope="enterprise",
                    source_app_id=application.id,
                )
                created_elements.setdefault("Node", []).append(node_element)
                stats["elements"].append(
                    {
                        "id": node_element.id,
                        "name": node_element.name,
                        "type": "Node",
                        "layer": "technology",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["technology"] = (
                    stats["elements_by_layer"].get("technology", 0) + 1
                )
                stats["elements_by_type"]["Node"] = stats["elements_by_type"].get("Node", 0) + 1

            # SystemSoftware for technology stack
            if application.technology_stack:
                sys_sw_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="SystemSoftware",
                    name=application.technology_stack,
                    layer="technology",
                    description=f"Technology stack for {application.name}",
                    scope="application",
                    source_app_id=application.id,
                )
                created_elements.setdefault("SystemSoftware", []).append(sys_sw_element)
                stats["elements"].append(
                    {
                        "id": sys_sw_element.id,
                        "name": sys_sw_element.name,
                        "type": "SystemSoftware",
                        "layer": "technology",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["technology"] = (
                    stats["elements_by_layer"].get("technology", 0) + 1
                )
                stats["elements_by_type"]["SystemSoftware"] = (
                    stats["elements_by_type"].get("SystemSoftware", 0) + 1
                )

        # 4. Generate business layer elements from application business attributes
        if "business" in include_layers:
            # BusinessFunction from business domain
            if application.business_domain:
                biz_func_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="BusinessFunction",
                    name=f"{application.business_domain} Function",
                    layer="business",
                    description=f"Business function supported by {application.name}",
                    scope="enterprise",
                    source_app_id=application.id,
                )
                created_elements.setdefault("BusinessFunction", []).append(biz_func_element)
                stats["elements"].append(
                    {
                        "id": biz_func_element.id,
                        "name": biz_func_element.name,
                        "type": "BusinessFunction",
                        "layer": "business",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["business"] = (
                    stats["elements_by_layer"].get("business", 0) + 1
                )
                stats["elements_by_type"]["BusinessFunction"] = (
                    stats["elements_by_type"].get("BusinessFunction", 0) + 1
                )

            # BusinessRole from owner
            if application.business_owner:
                biz_role_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="BusinessRole",
                    name=f"Business Owner - {application.business_owner}",
                    layer="business",
                    description=f"Business owner responsible for {application.name}",
                    scope="enterprise",
                    source_app_id=application.id,
                )
                created_elements.setdefault("BusinessRole", []).append(biz_role_element)
                stats["elements"].append(
                    {
                        "id": biz_role_element.id,
                        "name": biz_role_element.name,
                        "type": "BusinessRole",
                        "layer": "business",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["business"] = (
                    stats["elements_by_layer"].get("business", 0) + 1
                )
                stats["elements_by_type"]["BusinessRole"] = (
                    stats["elements_by_type"].get("BusinessRole", 0) + 1
                )

        # 5. Generate motivation layer elements
        if "motivation" in include_layers:
            # Requirement from business criticality
            if application.business_criticality:
                req_element = self._create_element(
                    architecture_model=arch_model,
                    element_type="Requirement",
                    name=f"{application.business_criticality} Criticality Requirement",
                    layer="motivation",
                    description=f"Criticality requirement for {application.name}: {application.business_criticality}",
                    scope="application",
                    source_app_id=application.id,
                )
                created_elements.setdefault("Requirement", []).append(req_element)
                stats["elements"].append(
                    {
                        "id": req_element.id,
                        "name": req_element.name,
                        "type": "Requirement",
                        "layer": "motivation",
                    }
                )
                stats["elements_created"] += 1
                stats["elements_by_layer"]["motivation"] = (
                    stats["elements_by_layer"].get("motivation", 0) + 1
                )
                stats["elements_by_type"]["Requirement"] = (
                    stats["elements_by_type"].get("Requirement", 0) + 1
                )

        # 6. Generate elements from APQC process mappings
        apqc_categories_processed = set()
        for apqc_process in apqc_processes:
            category = self._get_apqc_category(apqc_process.process_code)
            if not category:
                continue

            # Get element types to generate for this category
            element_map = self.APQC_ELEMENT_GENERATION_MAP.get(category, {})

            for layer, element_types in element_map.items():
                if layer not in include_layers:
                    continue

                for element_type in element_types:
                    # Create element based on APQC process
                    element_name = self._generate_element_name(
                        element_type, apqc_process, application
                    )
                    element_desc = self._generate_element_description(
                        element_type, apqc_process, application
                    )

                    element = self._create_element(
                        architecture_model=arch_model,
                        element_type=element_type,
                        name=element_name,
                        layer=layer,
                        description=element_desc,
                        scope="enterprise"
                        if layer in ["strategy", "motivation"]
                        else "application",
                        source_app_id=application.id,
                        apqc_process=apqc_process,
                    )

                    created_elements.setdefault(element_type, []).append(element)
                    stats["elements"].append(
                        {
                            "id": element.id,
                            "name": element.name,
                            "type": element_type,
                            "layer": layer,
                            "apqc_code": apqc_process.process_code,
                        }
                    )
                    stats["elements_created"] += 1
                    stats["elements_by_layer"][layer] = stats["elements_by_layer"].get(layer, 0) + 1
                    stats["elements_by_type"][element_type] = (
                        stats["elements_by_type"].get(element_type, 0) + 1
                    )

            apqc_categories_processed.add(category)

        # 7. Generate relationships
        if include_relationships:
            relationships = self._generate_relationships(
                arch_model, created_elements, apqc_categories_processed, app_element
            )
            stats["relationships_created"] = len(relationships)
            stats["relationships"] = [
                {"source": r.source_id, "target": r.target_id, "type": r.type}
                for r in relationships
            ]

        db.session.commit()

        logger.info(
            f"Completed ArchiMate generation for {application.name}: "
            f"{stats['elements_created']} elements, {stats['relationships_created']} relationships"
        )

        return {
            "success": True,
            "application_id": application.id,
            "application_name": application.name,
            "architecture_model_id": arch_model.id,
            "statistics": stats,
        }

    def _generate_element_name(
        self, element_type: str, apqc_process: APQCProcess, application: ApplicationComponent
    ) -> str:
        """Generate a meaningful name for an element based on APQC process."""

        # Type-specific naming patterns
        naming_patterns = {
            "BusinessProcess": f"[{apqc_process.process_code}] {apqc_process.process_name}",
            "BusinessFunction": f"{apqc_process.category_level_1}",
            "BusinessService": f"{apqc_process.process_name} Service",
            "BusinessRole": f"{apqc_process.process_name} Responsible",
            "Capability": f"Capability: {apqc_process.category_level_1}",
            "ValueStream": f"Value Stream: {apqc_process.category_level_1}",
            "CourseOfAction": f"Initiative: {apqc_process.process_name}",
            "Goal": f"Goal: {apqc_process.category_level_1}",
            "Driver": f"Driver: {apqc_process.category_level_1}",
            "Principle": f"Principle: {apqc_process.category_level_1}",
            "ApplicationService": f"{application.name}: {apqc_process.process_name}",
            "ApplicationProcess": f"{apqc_process.process_name} Process",
            "DataObject": f"{apqc_process.process_name} Data",
            "Node": f"Infrastructure: {apqc_process.category_level_1}",
            "TechnologyService": f"Tech Service: {apqc_process.process_name}",
        }

        return naming_patterns.get(element_type, f"[{apqc_process.process_code}] {element_type}")

    def _generate_element_description(
        self, element_type: str, apqc_process: APQCProcess, application: ApplicationComponent
    ) -> str:
        """Generate a meaningful description for an element."""
        base_desc = f"APQC PCF: {apqc_process.process_code} - {apqc_process.process_name}"
        if apqc_process.process_description:
            base_desc += f"\n\n{apqc_process.process_description}"
        base_desc += f"\n\nLinked Application: {application.name}"
        return base_desc

    def _generate_relationships(
        self,
        arch_model: ArchitectureModel,
        created_elements: Dict[str, List[ArchiMateElement]],
        apqc_categories: set,
        app_element: ArchiMateElement,
    ) -> List[ArchiMateRelationship]:
        """Generate ArchiMate relationships based on APQC templates."""
        relationships = []

        # 1. Connect ApplicationComponent to ApplicationService (composition)
        for service in created_elements.get("ApplicationService", []):
            rel = self._create_relationship(arch_model, app_element, service, "composition")
            if rel:
                relationships.append(rel)

        # 2. Connect ApplicationComponent to ApplicationInterface (composition)
        for interface in created_elements.get("ApplicationInterface", []):
            rel = self._create_relationship(arch_model, app_element, interface, "composition")
            if rel:
                relationships.append(rel)

        # 3. Connect Node to ApplicationComponent (realization)
        for node in created_elements.get("Node", []):
            rel = self._create_relationship(arch_model, node, app_element, "realization")
            if rel:
                relationships.append(rel)

        # 4. Connect SystemSoftware to ApplicationComponent (serving)
        for sys_sw in created_elements.get("SystemSoftware", []):
            rel = self._create_relationship(arch_model, sys_sw, app_element, "serving")
            if rel:
                relationships.append(rel)

        # 5. Connect ApplicationComponent to BusinessProcess (serving)
        for bp in created_elements.get("BusinessProcess", []):
            rel = self._create_relationship(arch_model, app_element, bp, "serving")
            if rel:
                relationships.append(rel)

        # 6. Connect ApplicationService to BusinessProcess (serving)
        for service in created_elements.get("ApplicationService", []):
            for bp in created_elements.get("BusinessProcess", []):
                rel = self._create_relationship(arch_model, service, bp, "serving")
                if rel:
                    relationships.append(rel)

        # 7. Connect BusinessRole to BusinessProcess (assignment)
        for role in created_elements.get("BusinessRole", []):
            for bp in created_elements.get("BusinessProcess", []):
                rel = self._create_relationship(arch_model, role, bp, "assignment")
                if rel:
                    relationships.append(rel)

        # 8. Connect Capability to BusinessFunction (realization)
        for cap in created_elements.get("Capability", []):
            for func in created_elements.get("BusinessFunction", []):
                rel = self._create_relationship(arch_model, cap, func, "realization")
                if rel:
                    relationships.append(rel)

        # 9. Connect Goal to Capability (influence)
        for goal in created_elements.get("Goal", []):
            for cap in created_elements.get("Capability", []):
                rel = self._create_relationship(arch_model, goal, cap, "influence")
                if rel:
                    relationships.append(rel)

        # 10. Connect Requirement to ApplicationComponent (realization)
        for req in created_elements.get("Requirement", []):
            rel = self._create_relationship(arch_model, app_element, req, "realization")
            if rel:
                relationships.append(rel)

        # 11. Use APQC-specific relationship templates
        for category in apqc_categories:
            patterns = ArchiMateElementTypes.get_relationships_for_apqc(category)
            for pattern in patterns:
                source_elements = created_elements.get(pattern.source_type, [])
                target_elements = created_elements.get(pattern.target_type, [])

                for source in source_elements:
                    for target in target_elements:
                        if source.id != target.id:
                            rel = self._create_relationship(
                                arch_model, source, target, pattern.relationship_type
                            )
                            if rel:
                                relationships.append(rel)

        return relationships

    def _get_application_apqc_processes(self, application_id: int) -> List[APQCProcess]:
        """Get APQC processes linked to an application."""
        from app.models.process_data import BusinessProcess
        from app.models.relationship_tables import ApplicationProcessSupport

        apqc_processes = []

        try:
            # Get through ApplicationProcessSupport -> BusinessProcess -> APQCProcess
            supports = ApplicationProcessSupport.query.filter_by(
                application_id=application_id
            ).all()

            for support in supports:
                if support.business_process_id:
                    bp = BusinessProcess.query.get(support.business_process_id)
                    if bp and bp.apqc_process_id:
                        apqc = APQCProcess.query.get(bp.apqc_process_id)
                        if apqc and apqc not in apqc_processes:
                            apqc_processes.append(apqc)
        except Exception as e:
            logger.error(f"Error fetching APQC processes for app {application_id}: {e}")

        return apqc_processes

    def generate_for_import_batch(
        self,
        application_ids: List[int],
        apqc_links_by_app: Dict[int, List[Dict]] = None,
        include_layers: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate ArchiMate elements for a batch of imported applications.

        Args:
            application_ids: List of application IDs to process
            apqc_links_by_app: Pre-computed APQC links from import preview
            include_layers: Specific layers to include

        Returns:
            Batch processing results
        """
        results = {
            "total_applications": len(application_ids),
            "processed": 0,
            "failed": 0,
            "total_elements_created": 0,
            "total_relationships_created": 0,
            "applications": [],
            "errors": [],
        }

        for app_id in application_ids:
            try:
                app = db.session.get(ApplicationComponent, app_id)
                if not app:
                    results["errors"].append(f"Application {app_id} not found")
                    results["failed"] += 1
                    continue

                # Get APQC processes if pre-computed
                apqc_processes = None
                if apqc_links_by_app and app_id in apqc_links_by_app:
                    apqc_ids = [
                        link.get("existing_id")
                        for link in apqc_links_by_app[app_id]
                        if link.get("existing_id")
                    ]
                    if apqc_ids:
                        apqc_processes = APQCProcess.query.filter(
                            APQCProcess.id.in_(apqc_ids)
                        ).all()

                # Generate elements
                result = self.generate_elements_for_application(
                    application=app, apqc_processes=apqc_processes, include_layers=include_layers
                )

                results["processed"] += 1
                results["total_elements_created"] += result["statistics"]["elements_created"]
                results["total_relationships_created"] += result["statistics"][
                    "relationships_created"
                ]
                results["applications"].append(
                    {
                        "id": app_id,
                        "name": app.name,
                        "elements_created": result["statistics"]["elements_created"],
                        "relationships_created": result["statistics"]["relationships_created"],
                        "success": True,
                    }
                )

            except Exception as e:
                logger.error(f"Error generating ArchiMate for app {app_id}: {e}")
                results["failed"] += 1
                results["errors"].append(f"App {app_id}: {str(e)}")
                results["applications"].append({"id": app_id, "success": False, "error": str(e)})

        return results


def get_comprehensive_archimate_service() -> ComprehensiveArchiMateService:
    """Factory function to get ComprehensiveArchiMateService instance."""
    return ComprehensiveArchiMateService()
