"""
-> app.modules.architecture.services.modeling_service

ArchiMate Open Exchange Format 3.2 Import/Export Service

Provides import and export capabilities for ArchiMate models in the Open Exchange Format 3.2 specification.

Capabilities:
- Export solutions to ArchiMate XML
- Export analysis sessions with motivational elements
- Import ArchiMate XML and create corresponding models
- Validate ArchiMate XML against schema

Complies with:
- ArchiMate 3.2 Specification
- Open Exchange Format 3.2 (http://www.opengroup.org/xsd/archimate/3.0/)

Reference:
- https://pubs.opengroup.org/architecture/archimate3 - doc/
"""

import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import db

logger = logging.getLogger(__name__)


class ArchiMateExchangeService:
    """
    Import/Export ArchiMate models in Open Exchange Format 3.2.

    Provides comprehensive support for ArchiMate model exchange including
    elements, relationships, views, and properties.
    """

    # ArchiMate 3.2 XML namespace
    ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

    # Namespace map for XML creation
    NAMESPACES = {"": ARCHIMATE_NS, "xsi": XSI_NS}

    # ArchiMate 3.2 Element Types by Layer
    MOTIVATION_ELEMENTS = [
        "Stakeholder",
        "Driver",
        "Assessment",
        "Goal",
        "Outcome",
        "Principle",
        "Requirement",
        "Constraint",
        "Meaning",
        "Value",
    ]

    STRATEGY_ELEMENTS = ["Resource", "Capability", "CourseOfAction", "ValueStream"]

    BUSINESS_ELEMENTS = [
        "BusinessActor",
        "BusinessRole",
        "BusinessCollaboration",
        "BusinessInterface",
        "BusinessProcess",
        "BusinessFunction",
        "BusinessInteraction",
        "BusinessEvent",
        "BusinessService",
        "BusinessObject",
        "Contract",
        "Representation",
        "Product",
    ]

    APPLICATION_ELEMENTS = [
        "ApplicationComponent",
        "ApplicationCollaboration",
        "ApplicationInterface",
        "ApplicationFunction",
        "ApplicationInteraction",
        "ApplicationProcess",
        "ApplicationEvent",
        "ApplicationService",
        "DataObject",
    ]

    TECHNOLOGY_ELEMENTS = [
        "Node",
        "Device",
        "SystemSoftware",
        "TechnologyCollaboration",
        "TechnologyInterface",
        "Path",
        "CommunicationNetwork",
        "TechnologyFunction",
        "TechnologyProcess",
        "TechnologyInteraction",
        "TechnologyEvent",
        "TechnologyService",
        "Artifact",
    ]

    PHYSICAL_ELEMENTS = ["Equipment", "Facility", "DistributionNetwork", "Material"]

    IMPLEMENTATION_ELEMENTS = [
        "WorkPackage",
        "Deliverable",
        "ImplementationEvent",
        "Plateau",
        "Gap",
    ]

    COMPOSITE_ELEMENTS = ["Grouping", "Location"]

    # All valid element types
    ALL_ELEMENT_TYPES = (
        MOTIVATION_ELEMENTS
        + STRATEGY_ELEMENTS
        + BUSINESS_ELEMENTS
        + APPLICATION_ELEMENTS
        + TECHNOLOGY_ELEMENTS
        + PHYSICAL_ELEMENTS
        + IMPLEMENTATION_ELEMENTS
        + COMPOSITE_ELEMENTS
    )

    # ArchiMate 3.2 Relationship Types
    RELATIONSHIP_TYPES = [
        "Composition",
        "Aggregation",
        "Assignment",
        "Realization",
        "Serving",
        "Access",
        "Influence",
        "Triggering",
        "Flow",
        "Specialization",
        "Association",
    ]

    # Layer mapping for elements
    ELEMENT_LAYER_MAP = {
        **{e: "Motivation" for e in MOTIVATION_ELEMENTS},
        **{e: "Strategy" for e in STRATEGY_ELEMENTS},
        **{e: "Business" for e in BUSINESS_ELEMENTS},
        **{e: "Application" for e in APPLICATION_ELEMENTS},
        **{e: "Technology" for e in TECHNOLOGY_ELEMENTS},
        **{e: "Physical" for e in PHYSICAL_ELEMENTS},
        **{e: "Implementation" for e in IMPLEMENTATION_ELEMENTS},
        **{e: "Composite" for e in COMPOSITE_ELEMENTS},
    }

    def __init__(self):
        """Initialize the ArchiMate Exchange Service."""
        self.logger = logger
        # Register namespaces for XML output
        for prefix, uri in self.NAMESPACES.items():
            if prefix:
                ET.register_namespace(prefix, uri)
            else:
                ET.register_namespace("", uri)

    # =========================================================================
    # EXPORT METHODS
    # =========================================================================

    def export_solution_to_archimate_xml(self, solution_id: int) -> str:
        """
        Export a solution and all its elements to ArchiMate XML.

        Args:
            solution_id: ID of the Solution to export

        Returns:
            ArchiMate XML string in Open Exchange Format 3.2
        """
        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
        from app.models.truly_missing_models import Solution

        try:
            # Query solution with relationships
            solution = Solution.query.get(solution_id)
            if not solution:
                raise ValueError(f"Solution with ID {solution_id} not found")

            self.logger.info(
                f"Exporting solution {solution.name} (ID: {solution_id}) to ArchiMate XML"
            )

            # Create root model element
            root = self._create_model_root(
                name=solution.name,
                identifier=f"id-solution-{solution_id}",
                documentation=solution.description,
            )

            # Create elements container
            elements_container = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}elements")

            # Track exported element IDs for relationship building
            exported_elements = {}

            # Export solution as a Grouping element
            solution_elem = self._create_element_xml(
                element_type="Grouping",
                identifier=f"id-solution-{solution_id}",
                name=solution.name,
                documentation=solution.description,
            )
            elements_container.append(solution_elem)
            exported_elements[f"solution-{solution_id}"] = f"id-solution-{solution_id}"

            # Export associated applications
            if hasattr(solution, "applications"):
                for app in solution.applications:
                    app_id = f"id-app-{app.id}"
                    app_elem = self._create_element_xml(
                        element_type="ApplicationComponent",
                        identifier=app_id,
                        name=app.name,
                        documentation=getattr(app, "description", None),
                    )
                    elements_container.append(app_elem)
                    exported_elements[f"app-{app.id}"] = app_id

            # Export ArchiMate elements linked to solution
            if solution.archimate_element_id:
                archimate_elem = ArchiMateElement.query.get(solution.archimate_element_id)
                if archimate_elem:
                    elem_id = f"id-archimate-{archimate_elem.id}"
                    elem = self._create_element_xml(
                        element_type=archimate_elem.type or "Grouping",
                        identifier=elem_id,
                        name=archimate_elem.name,
                        documentation=archimate_elem.description,
                    )
                    elements_container.append(elem)
                    exported_elements[f"archimate-{archimate_elem.id}"] = elem_id

            # Create relationships container
            relationships_container = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}relationships")

            # Add composition relationships from solution to applications
            for app in getattr(solution, "applications", []):
                app_id = exported_elements.get(f"app-{app.id}")
                if app_id:
                    rel_elem = self._build_relationship_xml(
                        relationship_type="Composition",
                        identifier=f"id-rel-solution-app-{app.id}",
                        source=f"id-solution-{solution_id}",
                        target=app_id,
                    )
                    relationships_container.append(rel_elem)

            # Add properties
            self._add_properties_to_element(
                root,
                {
                    "exportDate": datetime.utcnow().isoformat(),
                    "exportSource": "ArchiMate Exchange Service",
                    "solutionStatus": solution.status,
                    "solutionType": solution.solution_type,
                    "businessDomain": solution.business_domain,
                },
            )

            # Generate XML string
            return self._element_to_string(root)

        except Exception as e:
            self.logger.error(f"Error exporting solution {solution_id} to ArchiMate XML: {e}")
            raise

    def export_session_to_archimate_xml(self, session_id: int) -> str:
        """
        Export analysis session with motivational elements.

        Args:
            session_id: ID of the SolutionAnalysisSession to export

        Returns:
            ArchiMate XML string with motivation layer elements
        """
        from app.models.solution_architect_models import (
            SolutionAnalysisSession,
            SolutionAssessment,
            SolutionConstraint,
            SolutionDriver,
            SolutionGoal,
            SolutionPrinciple,
            SolutionRequirement,
        )

        try:
            # Query session with relationships
            session = SolutionAnalysisSession.query.get(session_id)
            if not session:
                raise ValueError(f"Session with ID {session_id} not found")

            self.logger.info(
                f"Exporting session {session.name} (ID: {session_id}) to ArchiMate XML"
            )

            # Create root model element
            root = self._create_model_root(
                name=f"Analysis Session: {session.name}",
                identifier=f"id-session-{session_id}",
                documentation=session.description,
            )

            # Create elements container
            elements_container = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}elements")

            # Track exported element IDs
            exported_elements = {}

            # Get problem definition
            problem = session.problem_definition

            if problem:
                # Export Drivers
                for driver in problem.drivers:
                    driver_id = f"id-driver-{driver.id}"
                    driver_elem = self._create_element_xml(
                        element_type="Driver",
                        identifier=driver_id,
                        name=driver.name,
                        documentation=driver.description,
                    )
                    # Add driver-specific properties
                    self._add_properties_to_element(
                        driver_elem,
                        {
                            "driverType": driver.driver_type.value if driver.driver_type else None,
                            "impactLevel": str(driver.impact_level)
                            if driver.impact_level
                            else None,
                            "urgency": str(driver.urgency) if driver.urgency else None,
                            "source": driver.source,
                        },
                    )
                    elements_container.append(driver_elem)
                    exported_elements[f"driver-{driver.id}"] = driver_id

                # Export Goals
                for goal in problem.goals:
                    goal_id = f"id-goal-{goal.id}"
                    goal_elem = self._create_element_xml(
                        element_type="Goal",
                        identifier=goal_id,
                        name=goal.name,
                        documentation=goal.description,
                    )
                    self._add_properties_to_element(
                        goal_elem,
                        {
                            "targetDate": goal.target_date.isoformat()
                            if goal.target_date
                            else None,
                            "measurementCriteria": goal.measurement_criteria,
                            "priority": str(goal.priority) if goal.priority else None,
                        },
                    )
                    elements_container.append(goal_elem)
                    exported_elements[f"goal-{goal.id}"] = goal_id

                # Export Requirements
                for req in problem.requirements:
                    req_id = f"id-requirement-{req.id}"
                    req_elem = self._create_element_xml(
                        element_type="Requirement",
                        identifier=req_id,
                        name=req.name,
                        documentation=req.description,
                    )
                    self._add_properties_to_element(
                        req_elem,
                        {
                            "requirementType": req.requirement_type.value
                            if req.requirement_type
                            else None,
                            "priority": str(req.priority) if req.priority else None,
                            "isMandatory": str(req.is_mandatory),
                            "acceptanceCriteria": req.acceptance_criteria,
                        },
                    )
                    elements_container.append(req_elem)
                    exported_elements[f"requirement-{req.id}"] = req_id

                # Export Constraints
                for constraint in problem.constraints:
                    constraint_id = f"id-constraint-{constraint.id}"
                    constraint_elem = self._create_element_xml(
                        element_type="Constraint",
                        identifier=constraint_id,
                        name=constraint.name,
                        documentation=constraint.description,
                    )
                    self._add_properties_to_element(
                        constraint_elem,
                        {
                            "constraintType": constraint.constraint_type.value
                            if constraint.constraint_type
                            else None,
                            "value": constraint.value,
                            "unit": constraint.unit,
                            "severity": str(constraint.severity) if constraint.severity else None,
                        },
                    )
                    elements_container.append(constraint_elem)
                    exported_elements[f"constraint-{constraint.id}"] = constraint_id

                # Export Principles
                for principle in problem.principles:
                    principle_id = f"id-principle-{principle.id}"
                    principle_elem = self._create_element_xml(
                        element_type="Principle",
                        identifier=principle_id,
                        name=principle.name,
                        documentation=principle.statement,
                    )
                    self._add_properties_to_element(
                        principle_elem,
                        {
                            "rationale": principle.rationale,
                            "implications": principle.implications,
                            "priority": str(principle.priority) if principle.priority else None,
                        },
                    )
                    elements_container.append(principle_elem)
                    exported_elements[f"principle-{principle.id}"] = principle_id

                # Export Assessments
                for assessment in problem.assessments:
                    assessment_id = f"id-assessment-{assessment.id}"
                    assessment_elem = self._create_element_xml(
                        element_type="Assessment",
                        identifier=assessment_id,
                        name=assessment.aspect,
                        documentation=f"Current: {assessment.current_state}\nTarget: {assessment.target_state}",
                    )
                    self._add_properties_to_element(
                        assessment_elem,
                        {
                            "currentState": assessment.current_state,
                            "targetState": assessment.target_state,
                            "gapAnalysis": assessment.gap_analysis,
                            "gapSeverity": str(assessment.gap_severity)
                            if assessment.gap_severity
                            else None,
                        },
                    )
                    elements_container.append(assessment_elem)
                    exported_elements[f"assessment-{assessment.id}"] = assessment_id

            # Create relationships container
            relationships_container = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}relationships")

            # Build relationships: Driver -> Goal (Association)
            if problem:
                for goal in problem.goals:
                    for driver in problem.drivers:
                        rel_elem = self._build_relationship_xml(
                            relationship_type="Association",
                            identifier=f"id-rel-driver-goal-{driver.id}-{goal.id}",
                            source=exported_elements.get(f"driver-{driver.id}"),
                            target=exported_elements.get(f"goal-{goal.id}"),
                        )
                        if rel_elem is not None:
                            relationships_container.append(rel_elem)

                # Goal -> Requirement (Realization)
                for req in problem.requirements:
                    for goal in problem.goals:
                        rel_elem = self._build_relationship_xml(
                            relationship_type="Realization",
                            identifier=f"id-rel-goal-req-{goal.id}-{req.id}",
                            source=exported_elements.get(f"requirement-{req.id}"),
                            target=exported_elements.get(f"goal-{goal.id}"),
                        )
                        if rel_elem is not None:
                            relationships_container.append(rel_elem)

                # Constraint -> Goal (Influence)
                for constraint in problem.constraints:
                    for goal in problem.goals:
                        rel_elem = self._build_relationship_xml(
                            relationship_type="Influence",
                            identifier=f"id-rel-constraint-goal-{constraint.id}-{goal.id}",
                            source=exported_elements.get(f"constraint-{constraint.id}"),
                            target=exported_elements.get(f"goal-{goal.id}"),
                        )
                        if rel_elem is not None:
                            relationships_container.append(rel_elem)

            # Add export metadata
            self._add_properties_to_element(
                root,
                {
                    "exportDate": datetime.utcnow().isoformat(),
                    "exportSource": "ArchiMate Exchange Service",
                    "sessionStatus": session.status.value if session.status else None,
                    "sessionVersion": str(session.current_version),
                },
            )

            return self._element_to_string(root)

        except Exception as e:
            self.logger.error(f"Error exporting session {session_id} to ArchiMate XML: {e}")
            raise

    # =========================================================================
    # IMPORT METHODS
    # =========================================================================

    def import_archimate_xml(self, xml_content: str, user_id: int) -> Dict[str, Any]:
        """
        Import ArchiMate XML and create corresponding models.

        Args:
            xml_content: ArchiMate XML content string
            user_id: ID of the user performing the import

        Returns:
            Import summary with counts of created, skipped, and error items
        """
        from app.models.archimate_core import (
            ArchiMateElement,
            ArchiMateRelationship,
            ArchitectureModel,
        )

        result = {
            "success": True,
            "model_id": None,
            "elements_created": 0,
            "elements_skipped": 0,
            "relationships_created": 0,
            "relationships_skipped": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Validate XML first
            validation = self.validate_archimate_xml(xml_content)
            if not validation["valid"]:
                result["success"] = False
                result["errors"] = validation["errors"]
                return result

            result["warnings"] = validation.get("warnings", [])

            # Parse XML
            root = ET.fromstring(xml_content)

            # Extract model info
            model_name = root.get(
                "name", f'Imported Model {datetime.utcnow().strftime("%Y%m%d_%H%M%S")}'
            )
            model_identifier = root.get("identifier", str(uuid.uuid4()))

            # Create ArchitectureModel
            arch_model = ArchitectureModel(name=model_name, version="1.0", model_data=xml_content)
            db.session.add(arch_model)
            db.session.flush()
            result["model_id"] = arch_model.id

            self.logger.info(f"Creating architecture model: {model_name} (ID: {arch_model.id})")

            # Map of imported element identifiers to database IDs
            element_id_map = {}

            # Process elements
            elements_container = root.find(f".//{{{self.ARCHIMATE_NS}}}elements")
            if elements_container is None:
                # Try without namespace
                elements_container = root.find(".//elements")

            if elements_container is not None:
                for elem in elements_container:
                    try:
                        elem_result = self._import_element(elem, arch_model.id, user_id)
                        if elem_result["created"]:
                            result["elements_created"] += 1
                            element_id_map[elem_result["identifier"]] = elem_result["db_id"]
                        else:
                            result["elements_skipped"] += 1
                            if elem_result.get("warning"):
                                result["warnings"].append(elem_result["warning"])
                    except Exception as e:
                        result["errors"].append(f"Error importing element: {e}")
                        result["elements_skipped"] += 1

            # Process relationships
            relationships_container = root.find(f".//{{{self.ARCHIMATE_NS}}}relationships")
            if relationships_container is None:
                relationships_container = root.find(".//relationships")

            if relationships_container is not None:
                for rel in relationships_container:
                    try:
                        rel_result = self._import_relationship(rel, arch_model.id, element_id_map)
                        if rel_result["created"]:
                            result["relationships_created"] += 1
                        else:
                            result["relationships_skipped"] += 1
                            if rel_result.get("warning"):
                                result["warnings"].append(rel_result["warning"])
                    except Exception as e:
                        result["errors"].append(f"Error importing relationship: {e}")
                        result["relationships_skipped"] += 1

            # Commit all changes
            db.session.commit()

            self.logger.info(
                f"Import complete: {result['elements_created']} elements, "
                f"{result['relationships_created']} relationships created"
            )

        except ET.ParseError as e:
            db.session.rollback()
            result["success"] = False
            result["errors"].append(f"XML parsing error: {e}")
            self.logger.error(f"XML parsing error during import: {e}")

        except SQLAlchemyError as e:
            db.session.rollback()
            result["success"] = False
            result["errors"].append(f"Database error: {e}")
            self.logger.error(f"Database error during import: {e}")

        except Exception as e:
            db.session.rollback()
            result["success"] = False
            result["errors"].append(f"Import error: {e}")
            self.logger.error(f"Error during ArchiMate import: {e}")

        return result

    def _import_element(
        self, elem: ET.Element, architecture_id: int, user_id: int
    ) -> Dict[str, Any]:
        """
        Import a single ArchiMate element.

        Args:
            elem: XML element to import
            architecture_id: ID of the parent ArchitectureModel
            user_id: ID of the importing user

        Returns:
            Dict with import result
        """
        from app.models.archimate_core import ArchiMateElement

        result = {"created": False, "identifier": None, "db_id": None, "warning": None}

        # Get element attributes
        identifier = elem.get("identifier", str(uuid.uuid4()))
        result["identifier"] = identifier

        # Get element type from tag or xsi:type
        elem_type = elem.get(f"{{{self.XSI_NS}}}type")
        if not elem_type:
            # Try tag name
            tag = elem.tag
            if "{" in tag:
                elem_type = tag.split("}")[1]
            else:
                elem_type = tag

        # Map type to valid ArchiMate type
        archimate_type = self._map_archimate_type_to_internal(elem_type)
        if not archimate_type:
            result["warning"] = f"Unknown element type: {elem_type}, defaulting to Grouping"
            archimate_type = "Grouping"

        # Get name and documentation
        name_elem = elem.find(f".//{{{self.ARCHIMATE_NS}}}name")
        if name_elem is None:
            name_elem = elem.find(".//name")
        name = (
            name_elem.text
            if name_elem is not None and name_elem.text
            else elem.get("name", "Unnamed Element")
        )

        doc_elem = elem.find(f".//{{{self.ARCHIMATE_NS}}}documentation")
        if doc_elem is None:
            doc_elem = elem.find(".//documentation")
        documentation = doc_elem.text if doc_elem is not None else None

        # Get layer from element type
        layer = self.ELEMENT_LAYER_MAP.get(archimate_type, "Other")

        # Create ArchiMateElement
        archimate_element = ArchiMateElement(
            name=name,
            type=archimate_type,
            layer=layer,
            description=documentation,
            architecture_id=architecture_id,
        )

        db.session.add(archimate_element)
        db.session.flush()

        result["created"] = True
        result["db_id"] = archimate_element.id

        # Import to domain-specific model if applicable
        self._create_domain_model(archimate_element, elem, user_id)

        return result

    def _import_relationship(
        self, rel: ET.Element, architecture_id: int, element_id_map: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Import a single ArchiMate relationship.

        Args:
            rel: XML relationship element
            architecture_id: ID of the parent ArchitectureModel
            element_id_map: Map of element identifiers to database IDs

        Returns:
            Dict with import result
        """
        from app.models.archimate_core import ArchiMateRelationship

        result = {"created": False, "warning": None}

        # Get relationship type
        rel_type = rel.get(f"{{{self.XSI_NS}}}type")
        if not rel_type:
            tag = rel.tag
            if "{" in tag:
                rel_type = tag.split("}")[1]
            else:
                rel_type = tag

        # Validate relationship type
        if rel_type not in self.RELATIONSHIP_TYPES:
            # Try to map common variations
            rel_type = self._normalize_relationship_type(rel_type)
            if rel_type not in self.RELATIONSHIP_TYPES:
                result[
                    "warning"
                ] = f"Unknown relationship type: {rel_type}, defaulting to Association"
                rel_type = "Association"

        # Get source and target
        source_id = rel.get("source")
        target_id = rel.get("target")

        if not source_id or not target_id:
            result["warning"] = "Relationship missing source or target"
            return result

        # Map to database IDs
        source_db_id = element_id_map.get(source_id)
        target_db_id = element_id_map.get(target_id)

        if not source_db_id or not target_db_id:
            result[
                "warning"
            ] = f"Could not resolve source ({source_id}) or target ({target_id}) element"
            return result

        # Create relationship
        relationship = ArchiMateRelationship(
            type=rel_type,
            architecture_id=architecture_id,
            source_id=source_db_id,
            target_id=target_db_id,
        )

        db.session.add(relationship)
        result["created"] = True

        return result

    def _create_domain_model(self, archimate_element, xml_elem: ET.Element, user_id: int) -> None:
        """
        Create domain-specific model based on ArchiMate element type.

        This maps ArchiMate elements to the rich domain models in the application.
        """
        elem_type = archimate_element.type

        # Import domain models lazily to avoid circular imports
        try:
            if elem_type == "Driver":
                from app.models.motivation import Driver

                driver = Driver(
                    name=archimate_element.name,
                    description=archimate_element.description,
                    archimate_element_id=archimate_element.id,
                    architecture_id=archimate_element.architecture_id,
                    status="active",
                )
                db.session.add(driver)

            elif elem_type == "Goal":
                from app.models.motivation import Goal

                goal = Goal(
                    name=archimate_element.name,
                    description=archimate_element.description,
                    archimate_element_id=archimate_element.id,
                    architecture_id=archimate_element.architecture_id,
                    status="active",
                )
                db.session.add(goal)

            elif elem_type == "ApplicationComponent":
                from app.models.application_portfolio import ApplicationComponent

                app = ApplicationComponent(
                    name=archimate_element.name,
                    description=archimate_element.description,
                    archimate_element_id=archimate_element.id,
                )
                db.session.add(app)

            # Add more type mappings as needed

        except Exception as e:
            self.logger.warning(f"Could not create domain model for {elem_type}: {e}")

    # =========================================================================
    # VALIDATION METHODS
    # =========================================================================

    def validate_archimate_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Validate XML without importing.

        Args:
            xml_content: ArchiMate XML content string

        Returns:
            Validation result with errors and warnings
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "element_count": 0,
            "relationship_count": 0,
            "element_types": [],
            "relationship_types": [],
        }

        try:
            # Parse XML
            root = ET.fromstring(xml_content)

            # Check for model element
            if "model" not in root.tag.lower():
                result["warnings"].append("Root element is not 'model'")

            # Validate elements
            elements_container = root.find(f".//{{{self.ARCHIMATE_NS}}}elements")
            if elements_container is None:
                elements_container = root.find(".//elements")

            element_types_found = set()
            if elements_container is not None:
                for elem in elements_container:
                    result["element_count"] += 1

                    # Get element type
                    elem_type = elem.get(f"{{{self.XSI_NS}}}type")
                    if not elem_type:
                        tag = elem.tag
                        if "{" in tag:
                            elem_type = tag.split("}")[1]
                        else:
                            elem_type = tag

                    element_types_found.add(elem_type)

                    # Validate element type
                    if elem_type and elem_type not in self.ALL_ELEMENT_TYPES:
                        # Check if it's a known variant
                        normalized = self._map_archimate_type_to_internal(elem_type)
                        if not normalized:
                            result["warnings"].append(f"Unknown element type: {elem_type}")

                    # Check for required name
                    name_elem = elem.find(f".//{{{self.ARCHIMATE_NS}}}name")
                    if name_elem is None:
                        name_elem = elem.find(".//name")
                    if name_elem is None and not elem.get("name"):
                        result["warnings"].append(
                            f"Element {elem.get('identifier', 'unknown')} has no name"
                        )

            result["element_types"] = list(element_types_found)

            # Validate relationships
            relationships_container = root.find(f".//{{{self.ARCHIMATE_NS}}}relationships")
            if relationships_container is None:
                relationships_container = root.find(".//relationships")

            relationship_types_found = set()
            if relationships_container is not None:
                for rel in relationships_container:
                    result["relationship_count"] += 1

                    # Get relationship type
                    rel_type = rel.get(f"{{{self.XSI_NS}}}type")
                    if not rel_type:
                        tag = rel.tag
                        if "{" in tag:
                            rel_type = tag.split("}")[1]
                        else:
                            rel_type = tag

                    relationship_types_found.add(rel_type)

                    # Validate relationship type
                    if rel_type and rel_type not in self.RELATIONSHIP_TYPES:
                        normalized = self._normalize_relationship_type(rel_type)
                        if normalized not in self.RELATIONSHIP_TYPES:
                            result["warnings"].append(f"Unknown relationship type: {rel_type}")

                    # Check for source and target
                    if not rel.get("source"):
                        result["errors"].append(
                            f"Relationship {rel.get('identifier', 'unknown')} has no source"
                        )
                        result["valid"] = False
                    if not rel.get("target"):
                        result["errors"].append(
                            f"Relationship {rel.get('identifier', 'unknown')} has no target"
                        )
                        result["valid"] = False

            result["relationship_types"] = list(relationship_types_found)

        except ET.ParseError as e:
            result["valid"] = False
            result["errors"].append(f"XML parsing error: {e}")

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Validation error: {e}")

        return result

    # =========================================================================
    # MAPPING HELPERS
    # =========================================================================

    def _map_element_to_archimate_type(self, element) -> str:
        """
        Map internal element to ArchiMate type.

        Args:
            element: Database model instance

        Returns:
            ArchiMate element type string
        """
        # Get class name and map to ArchiMate type
        class_name = element.__class__.__name__

        # Direct mappings
        type_map = {
            "Driver": "Driver",
            "Goal": "Goal",
            "Requirement": "Requirement",
            "Constraint": "Constraint",
            "Principle": "Principle",
            "Assessment": "Assessment",
            "ApplicationComponent": "ApplicationComponent",
            "ApplicationInterface": "ApplicationInterface",
            "ApplicationFunction": "ApplicationFunction",
            "ApplicationProcess": "ApplicationProcess",
            "ApplicationEvent": "ApplicationEvent",
            "ApplicationService": "ApplicationService",
            "DataObject": "DataObject",
            "BusinessActor": "BusinessActor",
            "BusinessRole": "BusinessRole",
            "BusinessProcess": "BusinessProcess",
            "BusinessFunction": "BusinessFunction",
            "BusinessService": "BusinessService",
            "BusinessObject": "BusinessObject",
            "Node": "Node",
            "Device": "Device",
            "SystemSoftware": "SystemSoftware",
            "Artifact": "Artifact",
            "TechnologyService": "TechnologyService",
            "Solution": "Grouping",
            "Capability": "Capability",
            "Resource": "Resource",
        }

        return type_map.get(class_name, "Grouping")

    def _map_archimate_type_to_internal(self, archimate_type: str) -> Optional[str]:
        """
        Map ArchiMate type to valid internal type.

        Handles common variations and aliases.
        """
        if archimate_type in self.ALL_ELEMENT_TYPES:
            return archimate_type

        # Handle common variations
        type_aliases = {
            "Business Actor": "BusinessActor",
            "Business Role": "BusinessRole",
            "Business Process": "BusinessProcess",
            "Business Function": "BusinessFunction",
            "Business Service": "BusinessService",
            "Business Object": "BusinessObject",
            "Business Event": "BusinessEvent",
            "Business Interface": "BusinessInterface",
            "Business Collaboration": "BusinessCollaboration",
            "Business Interaction": "BusinessInteraction",
            "Application Component": "ApplicationComponent",
            "Application Interface": "ApplicationInterface",
            "Application Function": "ApplicationFunction",
            "Application Process": "ApplicationProcess",
            "Application Event": "ApplicationEvent",
            "Application Service": "ApplicationService",
            "Application Collaboration": "ApplicationCollaboration",
            "Application Interaction": "ApplicationInteraction",
            "Data Object": "DataObject",
            "Technology Service": "TechnologyService",
            "Technology Function": "TechnologyFunction",
            "Technology Process": "TechnologyProcess",
            "Technology Event": "TechnologyEvent",
            "Technology Interface": "TechnologyInterface",
            "Technology Collaboration": "TechnologyCollaboration",
            "Technology Interaction": "TechnologyInteraction",
            "System Software": "SystemSoftware",
            "Communication Network": "CommunicationNetwork",
            "Distribution Network": "DistributionNetwork",
            "Course of Action": "CourseOfAction",
            "Value Stream": "ValueStream",
            "Work Package": "WorkPackage",
            "Implementation Event": "ImplementationEvent",
        }

        return type_aliases.get(archimate_type)

    def _map_archimate_type_to_model(self, archimate_type: str) -> Optional[Type]:
        """
        Map ArchiMate type to internal model class.

        Args:
            archimate_type: ArchiMate element type string

        Returns:
            Model class or None
        """
        # Import models lazily
        from app.models.application_layer import (
            ApplicationCollaboration,
            ApplicationEvent,
            ApplicationFunction,
            ApplicationInteraction,
            ApplicationInterface,
            ApplicationProcess,
            ApplicationService,
            DataObject,
        )
        from app.models.archimate_core import ArchiMateElement
        from app.models.motivation import Assessment, Driver, Goal, Meaning, Value

        type_model_map = {
            "Driver": Driver,
            "Goal": Goal,
            "Assessment": Assessment,
            "Value": Value,
            "Meaning": Meaning,
            "ApplicationInterface": ApplicationInterface,
            "ApplicationEvent": ApplicationEvent,
            "ApplicationCollaboration": ApplicationCollaboration,
            "ApplicationFunction": ApplicationFunction,
            "ApplicationProcess": ApplicationProcess,
            "ApplicationInteraction": ApplicationInteraction,
            "DataObject": DataObject,
            "ApplicationService": ApplicationService,
        }

        return type_model_map.get(archimate_type)

    def _normalize_relationship_type(self, rel_type: str) -> str:
        """
        Normalize relationship type to standard ArchiMate type.
        """
        type_aliases = {
            "Serves": "Serving",
            "ServingRelationship": "Serving",
            "Uses": "Serving",
            "Accesses": "Access",
            "AccessRelationship": "Access",
            "Influences": "Influence",
            "InfluenceRelationship": "Influence",
            "Triggers": "Triggering",
            "TriggeringRelationship": "Triggering",
            "Flows": "Flow",
            "FlowRelationship": "Flow",
            "Composes": "Composition",
            "CompositionRelationship": "Composition",
            "Aggregates": "Aggregation",
            "AggregationRelationship": "Aggregation",
            "Assigns": "Assignment",
            "AssignmentRelationship": "Assignment",
            "Realizes": "Realization",
            "RealizationRelationship": "Realization",
            "Specializes": "Specialization",
            "SpecializationRelationship": "Specialization",
            "Associates": "Association",
            "AssociationRelationship": "Association",
        }

        return type_aliases.get(rel_type, rel_type)

    def _build_relationship_xml(
        self,
        relationship_type: str,
        identifier: str,
        source: str,
        target: str,
        name: Optional[str] = None,
        documentation: Optional[str] = None,
    ) -> Optional[ET.Element]:
        """
        Build XML element for relationship.

        Args:
            relationship_type: ArchiMate relationship type
            identifier: Unique identifier for the relationship
            source: Source element identifier
            target: Target element identifier
            name: Optional relationship name
            documentation: Optional documentation

        Returns:
            XML Element for the relationship
        """
        if not source or not target:
            return None

        rel_elem = ET.Element(f"{{{self.ARCHIMATE_NS}}}relationship")
        rel_elem.set("identifier", identifier)
        rel_elem.set(f"{{{self.XSI_NS}}}type", relationship_type)
        rel_elem.set("source", source)
        rel_elem.set("target", target)

        if name:
            name_elem = ET.SubElement(rel_elem, f"{{{self.ARCHIMATE_NS}}}name")
            name_elem.text = name

        if documentation:
            doc_elem = ET.SubElement(rel_elem, f"{{{self.ARCHIMATE_NS}}}documentation")
            doc_elem.text = documentation

        return rel_elem

    # =========================================================================
    # XML BUILDING HELPERS
    # =========================================================================

    def _create_model_root(
        self, name: str, identifier: str, documentation: Optional[str] = None
    ) -> ET.Element:
        """
        Create the root model element for ArchiMate XML.

        Args:
            name: Model name
            identifier: Model identifier
            documentation: Optional model documentation

        Returns:
            Root XML Element
        """
        root = ET.Element(f"{{{self.ARCHIMATE_NS}}}model")
        root.set("identifier", identifier)
        root.set("name", name)
        root.set(
            f"{{{self.XSI_NS}}}schemaLocation",
            f"{self.ARCHIMATE_NS} http://www.opengroup.org/xsd/archimate/3.0/archimate3_Model.xsd",
        )

        # Add name element
        name_elem = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}name")
        name_elem.text = name

        # Add documentation if provided
        if documentation:
            doc_elem = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}documentation")
            doc_elem.text = documentation

        return root

    def _create_element_xml(
        self, element_type: str, identifier: str, name: str, documentation: Optional[str] = None
    ) -> ET.Element:
        """
        Create an ArchiMate element XML node.

        Args:
            element_type: ArchiMate element type
            identifier: Unique identifier
            name: Element name
            documentation: Optional documentation

        Returns:
            XML Element
        """
        elem = ET.Element(f"{{{self.ARCHIMATE_NS}}}element")
        elem.set("identifier", identifier)
        elem.set(f"{{{self.XSI_NS}}}type", element_type)

        # Add name
        name_elem = ET.SubElement(elem, f"{{{self.ARCHIMATE_NS}}}name")
        name_elem.text = name

        # Add documentation if provided
        if documentation:
            doc_elem = ET.SubElement(elem, f"{{{self.ARCHIMATE_NS}}}documentation")
            doc_elem.text = documentation

        return elem

    def _add_properties_to_element(
        self, element: ET.Element, properties: Dict[str, Optional[str]]
    ) -> None:
        """
        Add property elements to an ArchiMate element.

        Args:
            element: XML Element to add properties to
            properties: Dictionary of property key-value pairs
        """
        if not properties:
            return

        # Find or create properties container
        props_container = element.find(f".//{{{self.ARCHIMATE_NS}}}properties")
        if props_container is None:
            props_container = ET.SubElement(element, f"{{{self.ARCHIMATE_NS}}}properties")

        for key, value in properties.items():
            if value is not None:
                prop_elem = ET.SubElement(props_container, f"{{{self.ARCHIMATE_NS}}}property")
                prop_elem.set("propertyDefinitionRef", key)

                value_elem = ET.SubElement(prop_elem, f"{{{self.ARCHIMATE_NS}}}value")
                value_elem.text = str(value)

    def _element_to_string(self, element: ET.Element) -> str:
        """
        Convert XML Element to formatted string.

        Args:
            element: XML Element

        Returns:
            Formatted XML string
        """
        # Add XML declaration
        xml_declaration = '<?xml version="1.0" encoding="UTF - 8"?>\n'

        # Convert to string with indentation
        self._indent_xml(element)
        xml_string = ET.tostring(element, encoding="unicode")

        return xml_declaration + xml_string

    def _indent_xml(self, elem: ET.Element, level: int = 0) -> None:
        """
        Add indentation to XML element for pretty printing.

        Args:
            elem: XML Element to indent
            level: Current indentation level
        """
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent


# Singleton instance
_archimate_exchange_service = None


def get_archimate_exchange_service() -> ArchiMateExchangeService:
    """
    Get singleton instance of ArchiMateExchangeService.

    Returns:
        ArchiMateExchangeService instance
    """
    global _archimate_exchange_service
    if _archimate_exchange_service is None:
        _archimate_exchange_service = ArchiMateExchangeService()
    return _archimate_exchange_service
