"""
Unified ArchiMate Derivation Service - Phase 5.1

Orchestrator service that derives complete ArchiMate 3.2 models from APQC processes.
This is the main entry point for APQC-to-ArchiMate derivation, coordinating all
layer-specific services to generate complete, validated architecture models.

Coordinates:
- Business Layer derivation (from APQC directly)
- Application Layer derivation (via ApplicationLayerService)
- Technology Layer derivation (via TechnologyLayerService + keyword mapping)
- Relationship derivation (via RelationshipService)
- Strategy/Motivation Layer derivation (from APQC 1.0, 10.0)

ArchiMate 3.2 Layer Structure:
1. Strategy Layer: Resource, Capability, CourseOfAction, ValueStream
2. Motivation Layer: Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Requirement, Constraint
3. Business Layer: BusinessActor, BusinessRole, BusinessProcess, BusinessFunction, BusinessService, BusinessObject
4. Application Layer: ApplicationComponent, ApplicationFunction, ApplicationService, DataObject
5. Technology Layer: Node, Device, SystemSoftware, TechnologyService, Artifact, CommunicationNetwork

APQC Mapping Rules:
- APQC 1.0 (Develop Vision and Strategy) -> Strategy Layer + Motivation Layer
- APQC 2.0 - 9.0 (Operating Processes) -> Business Layer
- APQC 10.0 - 13.0 (Management & Support) -> Business Layer + supporting elements
- Level 1 - 2 (Category, Process Group) -> BusinessFunction
- Level 3 (Process) -> BusinessProcess
- Level 4 - 5 (Activity, Task) -> Skipped for main elements (too granular)
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.models.apqc_process import APQCProcess
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# =============================================================================
# Supporting Dataclasses
# =============================================================================


@dataclass
class DerivationOptions:
    """Options for controlling the derivation process."""

    include_strategy_layer: bool = True
    include_motivation_layer: bool = True
    include_technology_layer: bool = True
    min_confidence_threshold: float = 0.5
    max_apqc_level: int = 3  # Don't derive from Level 4 - 5
    auto_create_relationships: bool = True
    use_ai_inference: bool = True  # Use LLM for intelligent inference
    create_cross_layer_relationships: bool = True
    validate_on_completion: bool = True


@dataclass
class ValidationIssue:
    """Represents a validation issue found in the derived model."""

    severity: str  # 'error', 'warning', 'info'
    issue_type: str
    message: str
    affected_elements: List[int] = field(default_factory=list)


@dataclass
class DerivationSummary:
    """Summary statistics for a derivation operation."""

    total_elements: int = 0
    elements_by_layer: Dict[str, int] = field(default_factory=dict)
    total_relationships: int = 0
    avg_confidence: float = 0.0
    low_confidence_count: int = 0
    apqc_coverage: Dict[str, bool] = field(default_factory=dict)
    derivation_duration_seconds: float = 0.0


@dataclass
class DerivedArchitectureModel:
    """
    Complete derived ArchiMate model from APQC processes.

    Contains all derived elements, relationships, summary, and validation results.
    """

    model_id: str
    source_apqc_codes: List[str]
    elements: Dict[str, List[ArchiMateElement]]  # Grouped by layer
    relationships: List[ArchiMateRelationship]
    derivation_summary: DerivationSummary
    validation_issues: List[ValidationIssue]
    created_at: datetime = field(default_factory=datetime.utcnow)
    options_used: DerivationOptions = None


# =============================================================================
# Unified Derivation Service
# =============================================================================


class UnifiedDerivationService:
    """
    Orchestrator service that derives complete ArchiMate 3.2 models from APQC processes.

    This service coordinates all layer-specific derivation services to generate
    complete, validated ArchiMate architecture models from APQC Process Classification
    Framework processes.

    Derivation Flow:
    1. Load and filter APQC processes by level
    2. Derive Strategy Layer elements (from APQC 1.0)
    3. Derive Motivation Layer elements (from APQC 1.0, 10.0)
    4. Derive Business Layer elements (from all APQC processes)
    5. Derive Application Layer elements (using business context)
    6. Derive Technology Layer elements (using application metadata)
    7. Generate all cross-layer relationships
    8. Validate model consistency
    9. Return complete derived model

    Example usage:
        >>> service = UnifiedDerivationService(architecture_id=1)
        >>> model = service.derive_complete_model_from_apqc([1, 2, 3])
        >>> print(f"Derived {model.derivation_summary.total_elements} elements")
    """

    # APQC code prefixes for Strategy/Motivation layer derivation
    STRATEGY_APQC_PREFIXES = ["1.0", "1.1", "1.2", "1.3"]
    MOTIVATION_APQC_PREFIXES = ["1.0", "1.1", "1.2", "1.3", "10.0", "10.1", "10.2"]

    # Technology keyword mappings for technology layer inference
    TECHNOLOGY_KEYWORDS = {
        "cloud": ["Node", "cloud infrastructure"],
        "aws": ["Node", "AWS cloud platform"],
        "azure": ["Node", "Microsoft Azure platform"],
        "gcp": ["Node", "Google Cloud Platform"],
        "kubernetes": ["Node", "Kubernetes container orchestration"],
        "docker": ["SystemSoftware", "Docker container runtime"],
        "database": ["SystemSoftware", "Database management system"],
        "postgresql": ["SystemSoftware", "PostgreSQL database"],
        "mysql": ["SystemSoftware", "MySQL database"],
        "oracle": ["SystemSoftware", "Oracle database"],
        "mongodb": ["SystemSoftware", "MongoDB NoSQL database"],
        "redis": ["SystemSoftware", "Redis in-memory cache"],
        "nginx": ["SystemSoftware", "Nginx web server"],
        "apache": ["SystemSoftware", "Apache HTTP server"],
        "api": ["TechnologyService", "API gateway service"],
        "rest": ["TechnologyService", "RESTful API service"],
        "graphql": ["TechnologyService", "GraphQL API service"],
        "message": ["SystemSoftware", "Message broker"],
        "kafka": ["SystemSoftware", "Apache Kafka messaging"],
        "rabbitmq": ["SystemSoftware", "RabbitMQ message broker"],
        "server": ["Node", "Application server"],
        "network": ["CommunicationNetwork", "Network infrastructure"],
        "firewall": ["Device", "Network firewall"],
        "load balancer": ["Device", "Load balancer"],
    }

    def __init__(self, architecture_id: Optional[int] = None):
        """
        Initialize the UnifiedDerivationService.

        Args:
            architecture_id: Optional ID of existing ArchitectureModel to add elements to.
                           If None, a new ArchitectureModel will be created.
        """
        self.architecture_id = architecture_id
        self.llm_service = LLMService()
        self._derived_elements: Dict[str, List[ArchiMateElement]] = {
            "strategy": [],
            "motivation": [],
            "business": [],
            "application": [],
            "technology": [],
        }
        self._derived_relationships: List[ArchiMateRelationship] = []
        self._element_mapping: Dict[int, ArchiMateElement] = {}  # APQC ID -> ArchiMate Element
        self._validation_issues: List[ValidationIssue] = []

        logger.info(f"UnifiedDerivationService initialized for architecture_id={architecture_id}")

    # =========================================================================
    # Main Entry Point
    # =========================================================================

    def derive_complete_model_from_apqc(
        self, apqc_process_ids: List[int], options: DerivationOptions = None
    ) -> DerivedArchitectureModel:
        """
        Main entry point: derive complete ArchiMate model from APQC processes.

        Orchestrates the complete derivation pipeline from APQC processes to
        a fully populated ArchiMate 3.2 architecture model.

        Args:
            apqc_process_ids: List of APQC Process IDs to derive from
            options: DerivationOptions controlling the derivation behavior

        Returns:
            DerivedArchitectureModel containing all derived elements and relationships

        Raises:
            ValueError: If no APQC processes found for given IDs
        """
        start_time = datetime.utcnow()
        options = options or DerivationOptions()

        logger.info(
            f"Starting complete model derivation for {len(apqc_process_ids)} APQC processes"
        )
        logger.info(
            f"Options: strategy={options.include_strategy_layer}, "
            f"motivation={options.include_motivation_layer}, "
            f"technology={options.include_technology_layer}, "
            f"max_level={options.max_apqc_level}"
        )

        # Generate unique model ID
        model_id = f"derived-{uuid.uuid4().hex[:8]}"

        try:
            # Step 1: Load APQC processes
            apqc_processes = self._load_apqc_processes(apqc_process_ids)
            if not apqc_processes:
                raise ValueError(f"No APQC processes found for IDs: {apqc_process_ids}")

            logger.info(f"Loaded {len(apqc_processes)} APQC processes")

            # Step 2: Filter by level (skip Level 4 - 5 for main elements)
            filtered_processes = self._filter_by_level(apqc_processes, options.max_apqc_level)
            logger.info(
                f"After level filtering: {len(filtered_processes)} processes (max level {options.max_apqc_level})"
            )

            # Step 3: Ensure architecture model exists
            self._ensure_architecture_model()

            # Step 4: Derive Strategy Layer (from APQC 1.0 context)
            if options.include_strategy_layer:
                strategy_processes = self._filter_by_prefix(
                    filtered_processes, self.STRATEGY_APQC_PREFIXES
                )
                strategy_elements = self.derive_strategy_layer(strategy_processes)
                logger.info(f"Derived {len(strategy_elements)} Strategy Layer elements")

            # Step 5: Derive Motivation Layer (from APQC 1.0, 10.0 context)
            if options.include_motivation_layer:
                motivation_processes = self._filter_by_prefix(
                    filtered_processes, self.MOTIVATION_APQC_PREFIXES
                )
                motivation_elements = self.derive_motivation_layer(motivation_processes)
                logger.info(f"Derived {len(motivation_elements)} Motivation Layer elements")

            # Step 6: Derive Business Layer (from all APQC processes)
            business_elements = self.derive_business_layer(filtered_processes)
            logger.info(f"Derived {len(business_elements)} Business Layer elements")

            # Step 7: Derive Application Layer (using business context)
            if options.use_ai_inference:
                application_elements = self.derive_application_layer(
                    filtered_processes, business_elements
                )
                logger.info(f"Derived {len(application_elements)} Application Layer elements")

            # Step 8: Derive Technology Layer (using application metadata)
            if options.include_technology_layer and options.use_ai_inference:
                technology_elements = self.derive_technology_layer(
                    self._derived_elements["application"]
                )
                logger.info(f"Derived {len(technology_elements)} Technology Layer elements")

            # Step 9: Generate relationships
            if options.auto_create_relationships:
                self._generate_all_relationships(options.create_cross_layer_relationships)
                logger.info(f"Generated {len(self._derived_relationships)} relationships")

            # Step 10: Commit all changes
            db.session.commit()

            # Step 11: Validate cross-layer consistency
            if options.validate_on_completion:
                self._validation_issues = self.validate_cross_layer_consistency(
                    self._build_derived_model_for_validation()
                )
                logger.info(f"Validation complete: {len(self._validation_issues)} issues found")

            # Calculate duration
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            # Build summary
            summary = self._build_derivation_summary(apqc_processes, duration)

            # Build final model
            derived_model = DerivedArchitectureModel(
                model_id=model_id,
                source_apqc_codes=[p.process_code for p in apqc_processes],
                elements=self._derived_elements.copy(),
                relationships=self._derived_relationships.copy(),
                derivation_summary=summary,
                validation_issues=self._validation_issues.copy(),
                created_at=start_time,
                options_used=options,
            )

            logger.info(f"Complete model derivation finished in {duration:.2f}s")
            logger.info(
                f"Total elements: {summary.total_elements}, "
                f"Total relationships: {summary.total_relationships}"
            )

            return derived_model

        except Exception as e:
            db.session.rollback()
            logger.error(f"Model derivation failed: {str(e)}", exc_info=True)
            raise

    # =========================================================================
    # Layer-Specific Derivation Methods
    # =========================================================================

    def derive_business_layer(self, apqc_processes: List[APQCProcess]) -> List[ArchiMateElement]:
        """
        Derive Business Layer elements from APQC processes.

        Maps APQC hierarchy to ArchiMate Business Layer:
        - Level 1 (Category) -> BusinessFunction
        - Level 2 (Process Group) -> BusinessFunction
        - Level 3 (Process) -> BusinessProcess

        Args:
            apqc_processes: List of APQCProcess objects to derive from

        Returns:
            List of created ArchiMateElement objects (business layer)
        """
        logger.info(f"Deriving Business Layer from {len(apqc_processes)} APQC processes")

        elements = []

        for apqc in apqc_processes:
            # Determine ArchiMate element type based on APQC level
            element_type = apqc.archimate_mapping_level
            if not element_type:
                logger.debug(f"Skipping APQC {apqc.process_code} - no mapping level")
                continue

            # Check if element already exists for this APQC
            existing = self._find_existing_element(apqc.process_name, element_type)
            if existing:
                self._element_mapping[apqc.id] = existing
                elements.append(existing)
                continue

            # Create new ArchiMate element
            element = ArchiMateElement(
                name=apqc.process_name,
                type=element_type,
                layer="business",
                description=apqc.process_description
                or f"Business {element_type.lower()} derived from APQC {apqc.process_code}",
                documentation=self._build_apqc_documentation(apqc),
                properties=json.dumps(
                    {
                        "source": "apqc_derivation",
                        "apqc_code": apqc.process_code,
                        "apqc_level": apqc.apqc_level,
                        "process_category": apqc.process_category,
                        "process_type": apqc.process_type,
                        "derived_at": datetime.utcnow().isoformat(),
                        "confidence": 1.0,  # Direct APQC mapping has high confidence
                    }
                ),
                architecture_id=self.architecture_id,
            )

            db.session.add(element)
            db.session.flush()  # Get the ID

            self._element_mapping[apqc.id] = element
            elements.append(element)
            self._derived_elements["business"].append(element)

            logger.debug(f"Created {element_type} '{element.name}' from APQC {apqc.process_code}")

        return elements

    def derive_application_layer(
        self, apqc_processes: List[APQCProcess], business_elements: List[ArchiMateElement]
    ) -> List[ArchiMateElement]:
        """
        Derive Application Layer elements using business context.

        Uses AI inference to suggest ApplicationComponent and ApplicationService
        elements that would typically support the derived business processes.

        Args:
            apqc_processes: Source APQC processes for context
            business_elements: Previously derived business layer elements

        Returns:
            List of created ArchiMateElement objects (application layer)
        """
        logger.info(f"Deriving Application Layer from {len(business_elements)} business elements")

        elements = []

        # Group business processes by domain for better inference
        domain_groups = self._group_processes_by_domain(apqc_processes)

        for domain, processes in domain_groups.items():
            # Use AI to infer application components for this domain
            inferred_apps = self._infer_application_components(domain, processes)

            for app_info in inferred_apps:
                # Check for existing
                existing = self._find_existing_element(app_info["name"], "ApplicationComponent")
                if existing:
                    elements.append(existing)
                    continue

                # Create ApplicationComponent
                element = ArchiMateElement(
                    name=app_info["name"],
                    type="ApplicationComponent",
                    layer="application",
                    description=app_info.get(
                        "description", f"Application supporting {domain} domain"
                    ),
                    properties=json.dumps(
                        {
                            "source": "apqc_derivation",
                            "inferred_for_domain": domain,
                            "supported_processes": [p.process_code for p in processes[:5]],
                            "derived_at": datetime.utcnow().isoformat(),
                            "confidence": app_info.get("confidence", 0.7),
                        }
                    ),
                    architecture_id=self.architecture_id,
                )

                db.session.add(element)
                db.session.flush()

                elements.append(element)
                self._derived_elements["application"].append(element)

                # Also create ApplicationService if applicable
                if app_info.get("services"):
                    for svc in app_info["services"]:
                        svc_element = ArchiMateElement(
                            name=svc["name"],
                            type="ApplicationService",
                            layer="application",
                            description=svc.get(
                                "description", f"Service provided by {app_info['name']}"
                            ),
                            properties=json.dumps(
                                {
                                    "source": "apqc_derivation",
                                    "parent_component": app_info["name"],
                                    "derived_at": datetime.utcnow().isoformat(),
                                    "confidence": svc.get("confidence", 0.6),
                                }
                            ),
                            architecture_id=self.architecture_id,
                        )
                        db.session.add(svc_element)
                        elements.append(svc_element)
                        self._derived_elements["application"].append(svc_element)

        return elements

    def derive_technology_layer(
        self, application_elements: List[ArchiMateElement]
    ) -> List[ArchiMateElement]:
        """
        Derive Technology Layer elements from application metadata.

        Uses keyword mapping and AI inference to suggest infrastructure
        components that would typically support the derived applications.

        Args:
            application_elements: Previously derived application layer elements

        Returns:
            List of created ArchiMateElement objects (technology layer)
        """
        logger.info(
            f"Deriving Technology Layer from {len(application_elements)} application elements"
        )

        elements = []
        seen_tech = set()  # Avoid duplicates

        for app_element in application_elements:
            # Extract technology hints from application name and description
            tech_hints = self._extract_technology_hints(app_element)

            for tech_type, tech_name, tech_desc in tech_hints:
                if tech_name in seen_tech:
                    continue
                seen_tech.add(tech_name)

                # Check for existing
                existing = self._find_existing_element(tech_name, tech_type)
                if existing:
                    elements.append(existing)
                    continue

                # Create technology element
                element = ArchiMateElement(
                    name=tech_name,
                    type=tech_type,
                    layer="technology",
                    description=tech_desc,
                    properties=json.dumps(
                        {
                            "source": "apqc_derivation",
                            "inferred_from": app_element.name,
                            "derived_at": datetime.utcnow().isoformat(),
                            "confidence": 0.6,
                        }
                    ),
                    architecture_id=self.architecture_id,
                )

                db.session.add(element)
                db.session.flush()

                elements.append(element)
                self._derived_elements["technology"].append(element)

        # Add default infrastructure if no technology inferred
        if not elements:
            default_tech = self._create_default_technology_elements()
            elements.extend(default_tech)

        return elements

    def derive_strategy_layer(self, apqc_processes: List[APQCProcess]) -> List[ArchiMateElement]:
        """
        Derive Strategy Layer elements from APQC 1.0 processes.

        Maps APQC Category 1.0 "Develop Vision and Strategy" to:
        - Capability: Strategic capabilities
        - ValueStream: End-to-end value delivery flows
        - CourseOfAction: Strategic initiatives
        - Resource: Strategic resources

        Args:
            apqc_processes: APQC processes from Category 1.0

        Returns:
            List of created ArchiMateElement objects (strategy layer)
        """
        logger.info(f"Deriving Strategy Layer from {len(apqc_processes)} APQC processes")

        elements = []

        for apqc in apqc_processes:
            # Determine appropriate Strategy element type
            strategy_type = self._map_apqc_to_strategy_type(apqc)
            if not strategy_type:
                continue

            # Check for existing
            existing = self._find_existing_element(apqc.process_name, strategy_type)
            if existing:
                elements.append(existing)
                self._derived_elements["strategy"].append(existing)
                continue

            # Create strategy element
            element = ArchiMateElement(
                name=apqc.process_name,
                type=strategy_type,
                layer="strategy",
                description=apqc.process_description
                or f"Strategic {strategy_type.lower()} derived from APQC {apqc.process_code}",
                properties=json.dumps(
                    {
                        "source": "apqc_derivation",
                        "apqc_code": apqc.process_code,
                        "apqc_level": apqc.apqc_level,
                        "derived_at": datetime.utcnow().isoformat(),
                        "confidence": 0.9,
                    }
                ),
                architecture_id=self.architecture_id,
            )

            db.session.add(element)
            db.session.flush()

            elements.append(element)
            self._derived_elements["strategy"].append(element)

        return elements

    def derive_motivation_layer(self, apqc_processes: List[APQCProcess]) -> List[ArchiMateElement]:
        """
        Derive Motivation Layer elements from APQC 1.0 and 10.0 processes.

        Maps strategic/governance APQC processes to:
        - Goal: Business objectives
        - Driver: External/internal motivators
        - Outcome: Expected results
        - Principle: Guiding principles

        Args:
            apqc_processes: APQC processes from Category 1.0 and 10.0

        Returns:
            List of created ArchiMateElement objects (motivation layer)
        """
        logger.info(f"Deriving Motivation Layer from {len(apqc_processes)} APQC processes")

        elements = []

        for apqc in apqc_processes:
            # Determine appropriate Motivation element type
            motivation_type = self._map_apqc_to_motivation_type(apqc)
            if not motivation_type:
                continue

            # Check for existing
            existing = self._find_existing_element(apqc.process_name, motivation_type)
            if existing:
                elements.append(existing)
                self._derived_elements["motivation"].append(existing)
                continue

            # Create motivation element
            element = ArchiMateElement(
                name=self._transform_to_motivation_name(apqc.process_name, motivation_type),
                type=motivation_type,
                layer="motivation",
                description=apqc.process_description
                or f"Motivation element derived from APQC {apqc.process_code}",
                properties=json.dumps(
                    {
                        "source": "apqc_derivation",
                        "apqc_code": apqc.process_code,
                        "apqc_level": apqc.apqc_level,
                        "derived_at": datetime.utcnow().isoformat(),
                        "confidence": 0.85,
                    }
                ),
                architecture_id=self.architecture_id,
            )

            db.session.add(element)
            db.session.flush()

            elements.append(element)
            self._derived_elements["motivation"].append(element)

        return elements

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def validate_cross_layer_consistency(
        self, model: DerivedArchitectureModel
    ) -> List[ValidationIssue]:
        """
        Validate that derived model is internally consistent.

        Checks:
        - All elements have required fields
        - Relationships reference valid elements
        - Layer assignments are correct
        - Cross-layer relationships follow ArchiMate rules
        - No orphan elements (elements without relationships)

        Args:
            model: The derived architecture model to validate

        Returns:
            List of ValidationIssue objects describing any problems found
        """
        logger.info("Validating cross-layer consistency")
        issues = []

        all_element_ids = set()
        for layer_elements in model.elements.values():
            for elem in layer_elements:
                all_element_ids.add(elem.id)

        # Check 1: All elements have required fields
        for layer_name, layer_elements in model.elements.items():
            for elem in layer_elements:
                if not elem.name:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            issue_type="missing_name",
                            message=f"Element ID {elem.id} has no name",
                            affected_elements=[elem.id],
                        )
                    )
                if not elem.type:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            issue_type="missing_type",
                            message=f"Element '{elem.name}' has no type",
                            affected_elements=[elem.id],
                        )
                    )
                if elem.layer != layer_name:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            issue_type="layer_mismatch",
                            message=f"Element '{elem.name}' has layer '{elem.layer}' but is in '{layer_name}' group",
                            affected_elements=[elem.id],
                        )
                    )

        # Check 2: Relationships reference valid elements
        for rel in model.relationships:
            if rel.source_id not in all_element_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        issue_type="invalid_relationship_source",
                        message=f"Relationship {rel.id} references non-existent source {rel.source_id}",
                        affected_elements=[rel.source_id],
                    )
                )
            if rel.target_id not in all_element_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        issue_type="invalid_relationship_target",
                        message=f"Relationship {rel.id} references non-existent target {rel.target_id}",
                        affected_elements=[rel.target_id],
                    )
                )

        # Check 3: Orphan elements (warning only)
        connected_elements = set()
        for rel in model.relationships:
            connected_elements.add(rel.source_id)
            connected_elements.add(rel.target_id)

        orphans = all_element_ids - connected_elements
        if orphans:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    issue_type="orphan_elements",
                    message=f"Found {len(orphans)} elements without relationships",
                    affected_elements=list(orphans),
                )
            )

        # Check 4: Cross-layer relationship validity
        cross_layer_issues = self._validate_cross_layer_relationships(model)
        issues.extend(cross_layer_issues)

        logger.info(f"Validation complete: {len(issues)} issues found")
        return issues

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _load_apqc_processes(self, process_ids: List[int]) -> List[APQCProcess]:
        """Load APQC processes by IDs."""
        return APQCProcess.query.filter(APQCProcess.id.in_(process_ids)).all()

    def _filter_by_level(self, processes: List[APQCProcess], max_level: int) -> List[APQCProcess]:
        """Filter processes by APQC level (1 - 5)."""
        return [p for p in processes if p.apqc_level and p.apqc_level <= max_level]

    def _filter_by_prefix(
        self, processes: List[APQCProcess], prefixes: List[str]
    ) -> List[APQCProcess]:
        """Filter processes by APQC code prefix."""
        filtered = []
        for p in processes:
            if any(p.process_code.startswith(prefix.rstrip(".")) for prefix in prefixes):
                filtered.append(p)
        return filtered

    def _ensure_architecture_model(self):
        """Ensure an ArchitectureModel exists for derived elements."""
        if self.architecture_id:
            arch = db.session.get(ArchitectureModel, self.architecture_id)
            if arch:
                return arch

        # Create new architecture model
        arch = ArchitectureModel(
            name=f"APQC Derived Model {datetime.utcnow().strftime('%Y%m%d')}",
            version="1.0",
            model_data='{"source": "APQC PCF derivation", "type": "auto-generated"}',
        )
        db.session.add(arch)
        db.session.flush()

        self.architecture_id = arch.id
        logger.info(f"Created new ArchitectureModel with ID {arch.id}")
        return arch

    def _find_existing_element(self, name: str, element_type: str) -> Optional[ArchiMateElement]:
        """Find existing element by name and type."""
        return ArchiMateElement.query.filter_by(
            name=name, type=element_type, architecture_id=self.architecture_id
        ).first()

    def _build_apqc_documentation(self, apqc: APQCProcess) -> str:
        """Build documentation string from APQC process metadata."""
        docs = [f"Derived from APQC Process: {apqc.process_code}"]

        if apqc.category_level_1:
            docs.append(f"Category L1: {apqc.category_level_1}")
        if apqc.category_level_2:
            docs.append(f"Category L2: {apqc.category_level_2}")
        if apqc.category_level_3:
            docs.append(f"Category L3: {apqc.category_level_3}")
        if apqc.process_category:
            docs.append(f"Process Category: {apqc.process_category}")
        if apqc.industry_domain:
            docs.append(f"Industry: {apqc.industry_domain}")

        return "\n".join(docs)

    def _group_processes_by_domain(
        self, processes: List[APQCProcess]
    ) -> Dict[str, List[APQCProcess]]:
        """Group APQC processes by their top-level category/domain."""
        groups = {}
        for p in processes:
            # Use the first segment of process_code as domain
            domain = p.category_level_1 or p.process_code.split(".")[0]
            if domain not in groups:
                groups[domain] = []
            groups[domain].append(p)
        return groups

    def _infer_application_components(
        self, domain: str, processes: List[APQCProcess]
    ) -> List[Dict[str, Any]]:
        """
        Use AI to infer application components for a business domain.

        Returns list of dicts with: name, description, confidence, services
        """
        # Build context for inference
        process_names = [p.process_name for p in processes[:10]]
        process_codes = [p.process_code for p in processes[:10]]

        # Use domain keywords to suggest typical applications
        domain_apps = self._get_domain_typical_applications(domain)

        if domain_apps:
            return domain_apps

        # Fallback: create generic applications based on processes
        return [
            {
                "name": f"{domain} System",
                "description": f"Application system supporting {domain} processes",
                "confidence": 0.5,
                "services": [
                    {
                        "name": f"{domain} Service",
                        "description": f"Core service for {domain}",
                        "confidence": 0.5,
                    }
                ],
            }
        ]

    def _get_domain_typical_applications(self, domain: str) -> List[Dict[str, Any]]:
        """Map APQC domains to typical enterprise applications."""
        domain_lower = domain.lower() if domain else ""

        # Common enterprise application patterns by APQC domain
        mappings = {
            "1": [  # Develop Vision and Strategy
                {
                    "name": "Strategic Planning System",
                    "description": "Enterprise strategy and planning platform",
                    "confidence": 0.8,
                }
            ],
            "2": [  # Develop and Manage Products
                {
                    "name": "Product Lifecycle Management (PLM)",
                    "description": "Product development and management system",
                    "confidence": 0.85,
                },
                {
                    "name": "R&D Management System",
                    "description": "Research and development tracking",
                    "confidence": 0.7,
                },
            ],
            "3": [  # Market and Sell
                {
                    "name": "CRM System",
                    "description": "Customer relationship management",
                    "confidence": 0.9,
                },
                {
                    "name": "Marketing Automation Platform",
                    "description": "Digital marketing and campaign management",
                    "confidence": 0.8,
                },
            ],
            "4": [  # Deliver Products and Services
                {
                    "name": "Order Management System",
                    "description": "Order processing and fulfillment",
                    "confidence": 0.85,
                },
                {
                    "name": "Supply Chain Management",
                    "description": "Supply chain planning and execution",
                    "confidence": 0.8,
                },
            ],
            "5": [  # Manage Customer Service
                {
                    "name": "Customer Service Platform",
                    "description": "Customer support and service management",
                    "confidence": 0.85,
                },
                {
                    "name": "Case Management System",
                    "description": "Service request and case handling",
                    "confidence": 0.75,
                },
            ],
            "6": [  # Develop and Manage Human Capital
                {
                    "name": "Human Capital Management (HCM)",
                    "description": "HR and workforce management",
                    "confidence": 0.9,
                },
                {
                    "name": "Learning Management System (LMS)",
                    "description": "Training and development platform",
                    "confidence": 0.8,
                },
            ],
            "7": [  # Manage Information Technology
                {
                    "name": "IT Service Management (ITSM)",
                    "description": "IT operations and service desk",
                    "confidence": 0.9,
                },
                {
                    "name": "Enterprise Architecture Repository",
                    "description": "Architecture modeling and management",
                    "confidence": 0.85,
                },
            ],
            "8": [  # Manage Financial Resources
                {
                    "name": "Enterprise Resource Planning (ERP)",
                    "description": "Financial and accounting system",
                    "confidence": 0.9,
                },
                {
                    "name": "Financial Planning & Analysis",
                    "description": "Budgeting and financial planning",
                    "confidence": 0.8,
                },
            ],
            "9": [  # Acquire, Construct, and Manage Assets
                {
                    "name": "Asset Management System",
                    "description": "Enterprise asset management",
                    "confidence": 0.85,
                },
                {
                    "name": "Facilities Management System",
                    "description": "Property and facilities management",
                    "confidence": 0.75,
                },
            ],
            "10": [  # Manage Enterprise Risk, Compliance, Remediation, Resiliency
                {
                    "name": "Governance Risk & Compliance (GRC)",
                    "description": "Enterprise risk and compliance management",
                    "confidence": 0.9,
                },
                {
                    "name": "Audit Management System",
                    "description": "Internal audit and control tracking",
                    "confidence": 0.8,
                },
            ],
            "11": [  # Manage External Relationships
                {
                    "name": "Vendor Management System",
                    "description": "Supplier and vendor relationship management",
                    "confidence": 0.8,
                },
                {
                    "name": "Partnership Portal",
                    "description": "External partner collaboration",
                    "confidence": 0.7,
                },
            ],
            "12": [  # Develop and Manage Business Capabilities
                {
                    "name": "Business Process Management (BPM)",
                    "description": "Process modeling and automation",
                    "confidence": 0.85,
                },
                {
                    "name": "Performance Management System",
                    "description": "KPI tracking and analytics",
                    "confidence": 0.8,
                },
            ],
        }

        # Try to match domain to APQC category
        for key, apps in mappings.items():
            if domain.startswith(key) or key in domain_lower:
                return apps

        return []

    def _extract_technology_hints(self, app_element: ArchiMateElement) -> List[tuple]:
        """Extract technology hints from application element."""
        hints = []

        # Check element name and description for technology keywords
        text_to_search = f"{app_element.name} {app_element.description or ''}".lower()

        for keyword, (tech_type, tech_desc) in self.TECHNOLOGY_KEYWORDS.items():
            if keyword in text_to_search:
                tech_name = f"{keyword.title()} Infrastructure"
                hints.append((tech_type, tech_name, tech_desc))

        return hints

    def _create_default_technology_elements(self) -> List[ArchiMateElement]:
        """Create default technology infrastructure elements."""
        defaults = [
            ("Node", "Application Server Cluster", "Primary application hosting infrastructure"),
            ("Node", "Database Server", "Database hosting infrastructure"),
            ("SystemSoftware", "Operating System", "Server operating system layer"),
            ("CommunicationNetwork", "Enterprise Network", "Corporate network infrastructure"),
        ]

        elements = []
        for tech_type, name, desc in defaults:
            existing = self._find_existing_element(name, tech_type)
            if existing:
                elements.append(existing)
                continue

            element = ArchiMateElement(
                name=name,
                type=tech_type,
                layer="technology",
                description=desc,
                properties=json.dumps(
                    {
                        "source": "apqc_derivation",
                        "is_default": True,
                        "derived_at": datetime.utcnow().isoformat(),
                        "confidence": 0.5,
                    }
                ),
                architecture_id=self.architecture_id,
            )
            db.session.add(element)
            db.session.flush()

            elements.append(element)
            self._derived_elements["technology"].append(element)

        return elements

    def _map_apqc_to_strategy_type(self, apqc: APQCProcess) -> Optional[str]:
        """Map APQC process to Strategy layer element type."""
        code = apqc.process_code
        name_lower = apqc.process_name.lower()

        # 1.1.x - Vision/Strategy development -> Capability
        if code.startswith("1.1"):
            return "Capability"

        # 1.2.x - Strategic planning -> CourseOfAction
        if code.startswith("1.2"):
            return "CourseOfAction"

        # 1.3.x - Resource management -> Resource
        if code.startswith("1.3"):
            return "Resource"

        # Check keywords in name
        if "value" in name_lower or "stream" in name_lower:
            return "ValueStream"
        if "capability" in name_lower:
            return "Capability"
        if "resource" in name_lower or "asset" in name_lower:
            return "Resource"
        if "initiative" in name_lower or "program" in name_lower or "strategy" in name_lower:
            return "CourseOfAction"

        return None

    def _map_apqc_to_motivation_type(self, apqc: APQCProcess) -> Optional[str]:
        """Map APQC process to Motivation layer element type."""
        code = apqc.process_code
        name_lower = apqc.process_name.lower()

        # APQC 1.0 -> Goals and Drivers
        if code.startswith("1."):
            if "goal" in name_lower or "objective" in name_lower:
                return "Goal"
            if "vision" in name_lower or "mission" in name_lower:
                return "Goal"
            return "Driver"

        # APQC 10.0 -> Principles and Constraints
        if code.startswith("10."):
            if "compliance" in name_lower or "regulation" in name_lower:
                return "Constraint"
            if "policy" in name_lower or "standard" in name_lower:
                return "Principle"
            if "risk" in name_lower:
                return "Assessment"
            return "Principle"

        # General keyword matching
        if "goal" in name_lower or "objective" in name_lower:
            return "Goal"
        if "outcome" in name_lower or "result" in name_lower:
            return "Outcome"
        if "driver" in name_lower or "motivation" in name_lower:
            return "Driver"
        if "principle" in name_lower or "policy" in name_lower:
            return "Principle"
        if "constraint" in name_lower or "restriction" in name_lower:
            return "Constraint"

        return None

    def _transform_to_motivation_name(self, process_name: str, motivation_type: str) -> str:
        """Transform process name to appropriate motivation element name."""
        # Add appropriate prefix/suffix based on type
        if motivation_type == "Goal":
            if not process_name.lower().startswith(("achieve", "ensure", "establish", "improve")):
                return f"Achieve {process_name}"
        elif motivation_type == "Driver":
            if not process_name.lower().endswith(("driver", "motivation", "force")):
                return f"{process_name} Driver"
        elif motivation_type == "Outcome":
            if not process_name.lower().endswith(("outcome", "result")):
                return f"{process_name} Outcome"
        elif motivation_type == "Principle":
            if not process_name.lower().endswith(("principle", "policy")):
                return f"{process_name} Principle"

        return process_name

    def _generate_all_relationships(self, include_cross_layer: bool = True):
        """Generate relationships between derived elements."""
        logger.info("Generating relationships between derived elements")

        # Intra-layer relationships
        self._generate_business_layer_relationships()
        self._generate_application_layer_relationships()
        self._generate_technology_layer_relationships()

        # Cross-layer relationships
        if include_cross_layer:
            self._generate_cross_layer_relationships()

    def _generate_business_layer_relationships(self):
        """Generate relationships within business layer."""
        business_elements = self._derived_elements.get("business", [])

        # Create composition relationships for parent-child APQC mappings
        for apqc_id, element in self._element_mapping.items():
            apqc = APQCProcess.query.get(apqc_id)
            if apqc and apqc.parent_process_id:
                parent_element = self._element_mapping.get(apqc.parent_process_id)
                if parent_element:
                    rel = ArchiMateRelationship(
                        type="composition",
                        source_id=parent_element.id,
                        target_id=element.id,
                        architecture_id=self.architecture_id,
                        properties=json.dumps(
                            {
                                "source": "apqc_derivation",
                                "derived_at": datetime.utcnow().isoformat(),
                            }
                        ),
                    )
                    db.session.add(rel)
                    self._derived_relationships.append(rel)

    def _generate_application_layer_relationships(self):
        """Generate relationships within application layer."""
        app_components = [
            e
            for e in self._derived_elements.get("application", [])
            if e.type == "ApplicationComponent"
        ]
        app_services = [
            e
            for e in self._derived_elements.get("application", [])
            if e.type == "ApplicationService"
        ]

        # Create realization relationships (component realizes service)
        for service in app_services:
            props = json.loads(service.properties) if service.properties else {}
            parent_name = props.get("parent_component")

            if parent_name:
                component = next((c for c in app_components if c.name == parent_name), None)
                if component:
                    rel = ArchiMateRelationship(
                        type="realization",
                        source_id=component.id,
                        target_id=service.id,
                        architecture_id=self.architecture_id,
                    )
                    db.session.add(rel)
                    self._derived_relationships.append(rel)

    def _generate_technology_layer_relationships(self):
        """Generate relationships within technology layer."""
        nodes = [e for e in self._derived_elements.get("technology", []) if e.type == "Node"]
        software = [
            e for e in self._derived_elements.get("technology", []) if e.type == "SystemSoftware"
        ]

        # Create assignment relationships (node assigned to software)
        for sw in software:
            if nodes:
                rel = ArchiMateRelationship(
                    type="assignment",
                    source_id=nodes[0].id,  # Assign to first node
                    target_id=sw.id,
                    architecture_id=self.architecture_id,
                )
                db.session.add(rel)
                self._derived_relationships.append(rel)

    def _generate_cross_layer_relationships(self):
        """Generate relationships between layers."""
        # Strategy -> Business (realization)
        strategy_elements = self._derived_elements.get("strategy", [])
        business_elements = self._derived_elements.get("business", [])

        for strategy in strategy_elements:
            if strategy.type == "Capability":
                # Find related business functions
                for business in business_elements:
                    if business.type == "BusinessFunction":
                        rel = ArchiMateRelationship(
                            type="realization",
                            source_id=business.id,
                            target_id=strategy.id,
                            architecture_id=self.architecture_id,
                        )
                        db.session.add(rel)
                        self._derived_relationships.append(rel)
                        break  # One relationship per capability

        # Motivation -> Strategy (realization)
        motivation_elements = self._derived_elements.get("motivation", [])

        for motivation in motivation_elements:
            if motivation.type == "Goal":
                for strategy in strategy_elements:
                    if strategy.type == "CourseOfAction":
                        rel = ArchiMateRelationship(
                            type="realization",
                            source_id=strategy.id,
                            target_id=motivation.id,
                            architecture_id=self.architecture_id,
                        )
                        db.session.add(rel)
                        self._derived_relationships.append(rel)
                        break

        # Business -> Application (serving)
        app_elements = self._derived_elements.get("application", [])

        for app in app_elements:
            if app.type == "ApplicationComponent":
                for business in business_elements[:3]:  # Limit relationships
                    if business.type == "BusinessProcess":
                        rel = ArchiMateRelationship(
                            type="serving",
                            source_id=app.id,
                            target_id=business.id,
                            architecture_id=self.architecture_id,
                        )
                        db.session.add(rel)
                        self._derived_relationships.append(rel)

        # Application -> Technology (assignment/serving)
        tech_elements = self._derived_elements.get("technology", [])
        nodes = [e for e in tech_elements if e.type == "Node"]

        for app in app_elements:
            if app.type == "ApplicationComponent" and nodes:
                rel = ArchiMateRelationship(
                    type="assignment",
                    source_id=nodes[0].id,
                    target_id=app.id,
                    architecture_id=self.architecture_id,
                )
                db.session.add(rel)
                self._derived_relationships.append(rel)

    def _validate_cross_layer_relationships(
        self, model: DerivedArchitectureModel
    ) -> List[ValidationIssue]:
        """Validate cross-layer relationship rules."""
        issues = []

        # Build element lookup
        element_lookup = {}
        for layer_elements in model.elements.values():
            for elem in layer_elements:
                element_lookup[elem.id] = elem

        # Define valid cross-layer relationship patterns
        # Format: (source_layer, target_layer, allowed_types)
        valid_patterns = [
            ("motivation", "motivation", ["influence", "association", "realization"]),
            ("strategy", "motivation", ["realization"]),
            ("strategy", "business", ["realization"]),
            ("business", "business", ["composition", "aggregation", "flow", "triggering"]),
            ("business", "motivation", ["realization"]),
            ("application", "business", ["serving", "realization"]),
            ("application", "application", ["composition", "serving", "flow", "realization"]),
            ("technology", "application", ["assignment", "serving", "realization"]),
            ("technology", "technology", ["composition", "assignment", "serving", "flow"]),
        ]

        for rel in model.relationships:
            source = element_lookup.get(rel.source_id)
            target = element_lookup.get(rel.target_id)

            if not source or not target:
                continue

            # Check if relationship pattern is valid
            pattern_valid = False
            for src_layer, tgt_layer, allowed_types in valid_patterns:
                if (
                    source.layer == src_layer
                    and target.layer == tgt_layer
                    and rel.type in allowed_types
                ):
                    pattern_valid = True
                    break
                # Also check reverse direction
                if (
                    source.layer == tgt_layer
                    and target.layer == src_layer
                    and rel.type in allowed_types
                ):
                    pattern_valid = True
                    break

            if not pattern_valid and source.layer != target.layer:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        issue_type="unusual_cross_layer_relationship",
                        message=f"Unusual relationship: {source.layer}.{source.type} --[{rel.type}]--> {target.layer}.{target.type}",
                        affected_elements=[rel.source_id, rel.target_id],
                    )
                )

        return issues

    def _build_derived_model_for_validation(self) -> DerivedArchitectureModel:
        """Build a DerivedArchitectureModel for validation purposes."""
        return DerivedArchitectureModel(
            model_id="validation-temp",
            source_apqc_codes=[],
            elements=self._derived_elements,
            relationships=self._derived_relationships,
            derivation_summary=DerivationSummary(),
            validation_issues=[],
        )

    def _build_derivation_summary(
        self, source_processes: List[APQCProcess], duration_seconds: float
    ) -> DerivationSummary:
        """Build summary statistics for the derivation."""
        # Count elements by layer
        elements_by_layer = {}
        total_elements = 0
        total_confidence = 0.0
        low_confidence_count = 0

        for layer_name, layer_elements in self._derived_elements.items():
            elements_by_layer[layer_name] = len(layer_elements)
            total_elements += len(layer_elements)

            for elem in layer_elements:
                props = json.loads(elem.properties) if elem.properties else {}
                confidence = props.get("confidence", 1.0)
                total_confidence += confidence
                if confidence < 0.5:
                    low_confidence_count += 1

        # Calculate APQC coverage
        apqc_coverage = {}
        for p in source_processes:
            apqc_coverage[p.process_code] = p.id in self._element_mapping

        return DerivationSummary(
            total_elements=total_elements,
            elements_by_layer=elements_by_layer,
            total_relationships=len(self._derived_relationships),
            avg_confidence=total_confidence / total_elements if total_elements > 0 else 0.0,
            low_confidence_count=low_confidence_count,
            apqc_coverage=apqc_coverage,
            derivation_duration_seconds=duration_seconds,
        )
