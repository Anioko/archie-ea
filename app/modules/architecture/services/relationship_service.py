"""
AI-Powered Cross-Layer Relationship Service for ArchiMate 3.2

This service provides comprehensive cross-layer relationship modeling and analysis:
- Realization relationships (implementation links)
- Flow relationships (data/control flow)
- Triggering relationships (event-driven)
- Serving relationships (service provision)
- Assignment relationships (resource allocation)
- Influence relationships (motivation impact)
- Dependency analysis across layers
- Traceability and impact analysis

ArchiMate 3.2 Relationship Types:
Structural:
- Composition: Whole-part relationship
- Aggregation: Group relationship
- Assignment: Resource allocation
- Realization: Implementation relationship

Dependency:
- Serving: Service provision
- Access: Data access
- Influence: Motivation impact

Dynamic:
- Triggering: Temporal/causal relationship
- Flow: Transfer of information/value

Other:
- Specialization: Inheritance
- Association: Generic relationship
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
from app.services.llm_service import LLMService


class RelationshipService:
    """
    AI-powered service for ArchiMate 3.2 cross-layer relationship modeling.

    Capabilities:
    - Auto-discover relationships between elements
    - Create realization chains (motivation -> business -> application -> technology)
    - Model data flows across layers
    - Analyze triggering sequences
    - Perform impact analysis
    - Generate traceability matrices
    - Validate relationship consistency
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Realization Chain Methods
    # ========================================================================

    def create_realization_chain(
        self,
        goal_id: int,
        outcome_id: int,
        business_process_id: int,
        application_component_id: int,
        node_id: int,
    ) -> List[ArchiMateRelationship]:
        """
        Create complete realization chain from goal to infrastructure.

        Realization Chain:
        Goal -> realized by -> Outcome
        Outcome -> realized by -> BusinessProcess
        BusinessProcess -> realized by -> ApplicationComponent
        ApplicationComponent -> realized by -> Node (assigned to)

        Args:
            goal_id: ID of Goal (Motivation)
            outcome_id: ID of Outcome (Motivation)
            business_process_id: ID of BusinessProcess (Business)
            application_component_id: ID of ApplicationComponent (Application)
            node_id: ID of Node (Technology)

        Returns:
            List of ArchiMateRelationships forming the chain
        """
        # Validate all elements exist
        goal = db.session.get(ArchiMateElement, goal_id)
        outcome = db.session.get(ArchiMateElement, outcome_id)
        business_process = db.session.get(ArchiMateElement, business_process_id)
        app_component = db.session.get(ArchiMateElement, application_component_id)
        node = db.session.get(ArchiMateElement, node_id)

        if not all([goal, outcome, business_process, app_component, node]):
            raise ValueError("One or more elements in realization chain not found")

        relationships = []

        # Goal -> Outcome (realization)
        rel1 = ArchiMateRelationship(
            type="realization",
            source_id=outcome_id,
            target_id=goal_id,
            architecture_id=goal.architecture_id,
        )
        db.session.add(rel1)
        relationships.append(rel1)

        # Outcome -> BusinessProcess (realization)
        rel2 = ArchiMateRelationship(
            type="realization",
            source_id=business_process_id,
            target_id=outcome_id,
            architecture_id=goal.architecture_id,
        )
        db.session.add(rel2)
        relationships.append(rel2)

        # BusinessProcess <- ApplicationComponent (serving)
        rel3 = ArchiMateRelationship(
            type="serving",
            source_id=application_component_id,
            target_id=business_process_id,
            architecture_id=goal.architecture_id,
        )
        db.session.add(rel3)
        relationships.append(rel3)

        # ApplicationComponent <- Node (assignment)
        rel4 = ArchiMateRelationship(
            type="assignment",
            source_id=node_id,
            target_id=application_component_id,
            architecture_id=goal.architecture_id,
        )
        db.session.add(rel4)
        relationships.append(rel4)

        db.session.commit()
        return relationships

    def discover_realization_relationships(
        self, architecture_id: int, context_description: str
    ) -> List[ArchiMateRelationship]:
        """
        Use AI to discover potential realization relationships.

        Args:
            architecture_id: ID of the ArchitectureModel
            context_description: Description of architecture context

        Returns:
            List of discovered realization relationships
        """
        # Get all elements in architecture
        elements = ArchiMateElement.query.filter_by(architecture_id=architecture_id).all()

        # Build element context for LLM
        elements_context = []
        for elem in elements:
            elements_context.append(
                {
                    "id": elem.id,
                    "name": elem.name,
                    "type": elem.type,
                    "layer": elem.layer,
                    "description": elem.description,
                }
            )

        prompt = self._build_realization_discovery_prompt(elements_context, context_description)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            relationships_data = json.loads(response)

            relationships = []
            for rel_info in relationships_data.get("realization_relationships", []):
                # Verify elements exist
                source = db.session.get(ArchiMateElement, rel_info["source_id"])
                target = db.session.get(ArchiMateElement, rel_info["target_id"])

                if source and target:
                    relationship = ArchiMateRelationship(
                        type="realization",
                        source_id=rel_info["source_id"],
                        target_id=rel_info["target_id"],
                        architecture_id=architecture_id,
                        properties=json.dumps(
                            {
                                "rationale": rel_info.get("rationale", ""),
                                "discovered_at": datetime.utcnow().isoformat(),
                            }
                        ),
                    )
                    db.session.add(relationship)
                    relationships.append(relationship)

            db.session.commit()
            return relationships

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Realization relationship discovery failed: {str(e)}")

    # ========================================================================
    # Flow Relationship Methods
    # ========================================================================

    def model_data_flow(
        self, source_element_id: int, target_element_id: int, flow_description: str
    ) -> ArchiMateRelationship:
        """
        Model data or control flow between elements.

        Args:
            source_element_id: Source element ID
            target_element_id: Target element ID
            flow_description: Description of what flows

        Returns:
            Flow relationship
        """
        source = db.session.get(ArchiMateElement, source_element_id)
        target = db.session.get(ArchiMateElement, target_element_id)

        if not source or not target:
            raise ValueError("Source or target element not found")

        # Analyze flow with AI to determine type and metadata
        prompt = self._build_flow_analysis_prompt(source, target, flow_description)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            flow_data = json.loads(response)

            relationship = ArchiMateRelationship(
                type="flow",
                source_id=source_element_id,
                target_id=target_element_id,
                architecture_id=source.architecture_id,
                properties=json.dumps(
                    {
                        "flow_type": flow_data.get("flow_type", "data"),
                        "description": flow_description,
                        "protocol": flow_data.get("protocol", ""),
                        "frequency": flow_data.get("frequency", ""),
                        "data_volume": flow_data.get("data_volume", ""),
                        "latency_requirement": flow_data.get("latency_requirement", ""),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                ),
            )

            db.session.add(relationship)
            db.session.commit()

            return relationship

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Flow modeling failed: {str(e)}")

    def discover_flow_relationships(
        self, architecture_id: int, context_description: str
    ) -> List[ArchiMateRelationship]:
        """
        Use AI to discover potential flow relationships.

        Args:
            architecture_id: ID of the ArchitectureModel
            context_description: Description of data flows and integrations

        Returns:
            List of discovered flow relationships
        """
        # Get all application and technology elements
        elements = (
            ArchiMateElement.query.filter_by(architecture_id=architecture_id)
            .filter(ArchiMateElement.layer.in_(["application", "technology", "business"]))
            .all()
        )

        # Build element context
        elements_context = []
        for elem in elements:
            elements_context.append(
                {
                    "id": elem.id,
                    "name": elem.name,
                    "type": elem.type,
                    "layer": elem.layer,
                    "description": elem.description,
                }
            )

        prompt = self._build_flow_discovery_prompt(elements_context, context_description)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            relationships_data = json.loads(response)

            relationships = []
            for rel_info in relationships_data.get("flow_relationships", []):
                source = db.session.get(ArchiMateElement, rel_info["source_id"])
                target = db.session.get(ArchiMateElement, rel_info["target_id"])

                if source and target:
                    relationship = ArchiMateRelationship(
                        type="flow",
                        source_id=rel_info["source_id"],
                        target_id=rel_info["target_id"],
                        architecture_id=architecture_id,
                        properties=json.dumps(rel_info.get("properties", {})),
                    )
                    db.session.add(relationship)
                    relationships.append(relationship)

            db.session.commit()
            return relationships

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Flow relationship discovery failed: {str(e)}")

    # ========================================================================
    # Triggering Relationship Methods
    # ========================================================================

    def model_event_chain(
        self, event_sequence: List[Tuple[int, int]], chain_description: str
    ) -> List[ArchiMateRelationship]:
        """
        Model event-driven triggering sequence.

        Args:
            event_sequence: List of (source_id, target_id) tuples representing sequence
            chain_description: Description of the event chain

        Returns:
            List of triggering relationships
        """
        relationships = []

        for source_id, target_id in event_sequence:
            source = db.session.get(ArchiMateElement, source_id)
            target = db.session.get(ArchiMateElement, target_id)

            if not source or not target:
                continue

            relationship = ArchiMateRelationship(
                type="triggering",
                source_id=source_id,
                target_id=target_id,
                architecture_id=source.architecture_id,
                properties=json.dumps(
                    {
                        "chain_description": chain_description,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                ),
            )

            db.session.add(relationship)
            relationships.append(relationship)

        db.session.commit()
        return relationships

    # ========================================================================
    # Influence Relationship Methods (Motivation -> Other Layers)
    # ========================================================================

    def create_influence_relationships(
        self, driver_id: int, influenced_element_ids: List[int], influence_description: str
    ) -> List[ArchiMateRelationship]:
        """
        Create influence relationships from drivers to architecture elements.

        Args:
            driver_id: ID of Driver (Motivation)
            influenced_element_ids: List of element IDs influenced by driver
            influence_description: Description of influence

        Returns:
            List of influence relationships
        """
        driver = db.session.get(ArchiMateElement, driver_id)
        if not driver or driver.type != "Driver":
            raise ValueError(f"Driver {driver_id} not found")

        relationships = []

        for element_id in influenced_element_ids:
            element = db.session.get(ArchiMateElement, element_id)
            if not element:
                continue

            relationship = ArchiMateRelationship(
                type="influence",
                source_id=driver_id,
                target_id=element_id,
                architecture_id=driver.architecture_id,
                properties=json.dumps(
                    {
                        "description": influence_description,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                ),
            )

            db.session.add(relationship)
            relationships.append(relationship)

        db.session.commit()
        return relationships

    # ========================================================================
    # Impact Analysis Methods
    # ========================================================================

    def analyze_impact(self, element_id: int, change_description: str, max_hops: int = 5) -> Dict:
        """
        Analyze TRANSITIVE impact of changes to an element across all layers.

        Performs multi-hop dependency analysis to find:
        - Direct impacts (1 - hop)
        - Indirect impacts (2+ hops)
        - Affected goals (motivation layer)
        - Blast radius per layer
        - Compliance risks

        Args:
            element_id: ID of element being changed
            change_description: Description of the change
            max_hops: Maximum relationship hops to traverse (default: 5)

        Returns:
            Dict with comprehensive impact analysis:
            {
                'direct_impacts': [...],  # 1 - hop impacts
                'indirect_impacts': {2: [...], 3: [...], ...},  # Multi-hop impacts
                'affected_goals': [...],  # Impacted business goals
                'affected_principles': [...],  # Violated principles
                'blast_radius': {layer: count},  # Elements affected per layer
                'critical_path': [...],  # Elements blocking change
                'risk_level': 'high|medium|low',
                'compliance_impact': {...}
            }
        """
        element = db.session.get(ArchiMateElement, element_id)
        if not element:
            raise ValueError(f"Element {element_id} not found")

        # Perform TRANSITIVE dependency traversal
        direct_impacts = []  # 1 - hop
        indirect_impacts = {hop: [] for hop in range(2, max_hops + 1)}  # 2 - 5 hops
        visited = set()
        blast_radius = {}

        def traverse_dependencies(current_id, hop_level, path):
            """Recursively traverse dependencies."""
            if hop_level > max_hops or current_id in visited:
                return

            visited.add(current_id)
            current = db.session.get(ArchiMateElement, current_id)

            if not current or current.id == element_id:
                return

            # Track blast radius per layer
            layer = current.layer
            blast_radius[layer] = blast_radius.get(layer, 0) + 1

            # Categorize by hop level
            impact_entry = {
                "id": current.id,
                "name": current.name,
                "type": current.type,
                "layer": current.layer,
                "description": current.description,
                "path": path,
            }

            if hop_level == 1:
                direct_impacts.append(impact_entry)
            elif hop_level in indirect_impacts:
                indirect_impacts[hop_level].append(impact_entry)

            # Get outgoing relationships (downstream dependencies)
            outgoing_rels = ArchiMateRelationship.query.filter_by(source_id=current_id).all()

            for rel in outgoing_rels:
                new_path = path + [
                    f"{current.name} --[{rel.type}]--> {rel.target.name if rel.target else '?'}"
                ]
                traverse_dependencies(rel.target_id, hop_level + 1, new_path)

            # Get incoming relationships (upstream dependencies)
            incoming_rels = ArchiMateRelationship.query.filter_by(target_id=current_id).all()

            for rel in incoming_rels:
                new_path = path + [
                    f"{rel.source.name if rel.source else '?'} --[{rel.type}]--> {current.name}"
                ]
                traverse_dependencies(rel.source_id, hop_level + 1, new_path)

        # Start traversal from changed element
        initial_rels = ArchiMateRelationship.query.filter(
            (ArchiMateRelationship.source_id == element_id)
            | (ArchiMateRelationship.target_id == element_id)
        ).all()

        for rel in initial_rels:
            if rel.source_id == element_id:
                traverse_dependencies(rel.target_id, 1, [f"{element.name} --[{rel.type}]-->"])
            else:
                traverse_dependencies(rel.source_id, 1, [f"--[{rel.type}]--> {element.name}"])

        # Identify affected goals (trace to motivation layer)
        affected_goals = []
        affected_principles = []

        for impact_list in [direct_impacts] + list(indirect_impacts.values()):
            for impact in impact_list:
                if impact["layer"] == "motivation":
                    if impact["type"] == "Goal":
                        affected_goals.append(impact)
                    elif impact["type"] == "Principle":
                        affected_principles.append(impact)

        # Calculate risk level based on blast radius
        total_affected = sum(blast_radius.values())
        has_goal_impact = len(affected_goals) > 0
        has_principle_violation = len(affected_principles) > 0

        if total_affected > 20 or has_principle_violation:
            risk_level = "high"
        elif total_affected > 10 or has_goal_impact:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Use AI for semantic analysis
        impact_context = {
            "changed_element": {
                "id": element.id,
                "name": element.name,
                "type": element.type,
                "layer": element.layer,
                "description": element.description,
            },
            "change_description": change_description,
            "direct_impacts": direct_impacts[:10],  # Limit for prompt size
            "indirect_impacts": {k: v[:5] for k, v in indirect_impacts.items() if v},
            "blast_radius": blast_radius,
            "affected_goals": affected_goals,
            "affected_principles": affected_principles,
        }

        prompt = self._build_impact_analysis_prompt(impact_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            ai_analysis = json.loads(response)

            # Merge calculated data with AI analysis
            return {
                "direct_impacts": direct_impacts,
                "indirect_impacts": {k: v for k, v in indirect_impacts.items() if v},
                "affected_goals": affected_goals,
                "affected_principles": affected_principles,
                "blast_radius": blast_radius,
                "total_affected_elements": total_affected,
                "risk_level": risk_level,
                "critical_path": ai_analysis.get("critical_path", []),
                "compliance_impact": ai_analysis.get("compliance_impact", {}),
                "mitigation_recommendations": ai_analysis.get("mitigation_recommendations", []),
                "estimated_effort": ai_analysis.get("estimated_effort", "Unknown"),
            }

        except Exception as e:
            # Return calculated data even if AI fails
            return {
                "direct_impacts": direct_impacts,
                "indirect_impacts": {k: v for k, v in indirect_impacts.items() if v},
                "affected_goals": affected_goals,
                "affected_principles": affected_principles,
                "blast_radius": blast_radius,
                "total_affected_elements": total_affected,
                "risk_level": risk_level,
                "ai_error": str(e),
            }

    def trace_to_motivation(self, element_id: int) -> List[Dict]:
        """
        Trace element back to motivation layer (goals, drivers).

        Args:
            element_id: ID of element to trace

        Returns:
            List of traceability paths to motivation elements
        """
        element = db.session.get(ArchiMateElement, element_id)
        if not element:
            raise ValueError(f"Element {element_id} not found")

        # Perform graph traversal to find paths to motivation layer
        paths = []
        visited = set()

        def traverse(current_id, path):
            if current_id in visited:
                return

            visited.add(current_id)
            current = db.session.get(ArchiMateElement, current_id)

            if not current:
                return

            # If we reached motivation layer, save path
            if current.layer == "motivation":
                paths.append(path + [current])
                return

            # Find incoming realization/serving relationships
            incoming_rels = (
                ArchiMateRelationship.query.filter_by(target_id=current_id)
                .filter(ArchiMateRelationship.type.in_(["realization", "serving", "influence"]))
                .all()
            )

            for rel in incoming_rels:
                traverse(rel.source_id, path + [current])

        traverse(element_id, [])

        # Format paths
        formatted_paths = []
        for path in paths:
            formatted_paths.append(
                [
                    {"id": elem.id, "name": elem.name, "type": elem.type, "layer": elem.layer}
                    for elem in path
                ]
            )

        return formatted_paths

    # ========================================================================
    # Traceability Matrix Methods
    # ========================================================================

    def generate_traceability_matrix(
        self, architecture_id: int, source_layer: str, target_layer: str
    ) -> Dict:
        """
        Generate traceability matrix between two layers.

        Args:
            architecture_id: ID of the ArchitectureModel
            source_layer: Source layer (e.g., 'motivation')
            target_layer: Target layer (e.g., 'application')

        Returns:
            Dict with traceability matrix:
            {
                'source_elements': [...],
                'target_elements': [...],
                'matrix': [[bool]] # source x target
            }
        """
        source_elements = ArchiMateElement.query.filter_by(
            architecture_id=architecture_id, layer=source_layer
        ).all()

        target_elements = ArchiMateElement.query.filter_by(
            architecture_id=architecture_id, layer=target_layer
        ).all()

        # Build traceability matrix
        matrix = []
        for source in source_elements:
            row = []
            for target in target_elements:
                # Check if path exists from source to target
                has_path = self._has_relationship_path(source.id, target.id)
                row.append(has_path)
            matrix.append(row)

        return {
            "source_elements": [
                {"id": e.id, "name": e.name, "type": e.type} for e in source_elements
            ],
            "target_elements": [
                {"id": e.id, "name": e.name, "type": e.type} for e in target_elements
            ],
            "matrix": matrix,
        }

    # ========================================================================
    # Validation Methods
    # ========================================================================

    def validate_relationship_consistency(self, architecture_id: int) -> Dict:
        """
        Validate relationship consistency across architecture.

        Returns:
            Dict with validation results:
            {
                'valid': bool,
                'errors': [...],
                'warnings': [...]
            }
        """
        relationships = ArchiMateRelationship.query.filter_by(architecture_id=architecture_id).all()

        errors = []
        warnings = []

        for rel in relationships:
            source = db.session.get(ArchiMateElement, rel.source_id)
            target = db.session.get(ArchiMateElement, rel.target_id)

            if not source or not target:
                errors.append(f"Relationship {rel.id}: Missing source or target element")
                continue

            # Validate relationship type allowed between element types
            is_valid = self._is_valid_relationship(source.type, target.type, rel.type)

            if not is_valid:
                warnings.append(
                    f"Relationship {rel.id}: {rel.type} between {source.type} "
                    f"and {target.type} may not be valid per ArchiMate spec"
                )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _has_relationship_path(self, source_id: int, target_id: int, max_depth: int = 10) -> bool:
        """Check if relationship path exists from source to target."""
        if source_id == target_id:
            return True

        visited = set()

        def dfs(current_id, depth):
            if depth > max_depth:
                return False

            if current_id == target_id:
                return True

            if current_id in visited:
                return False

            visited.add(current_id)

            # Find outgoing relationships
            outgoing = ArchiMateRelationship.query.filter_by(source_id=current_id).all()

            for rel in outgoing:
                if dfs(rel.target_id, depth + 1):
                    return True

            return False

        return dfs(source_id, 0)

    def _is_valid_relationship(
        self, source_type: str, target_type: str, relationship_type: str
    ) -> bool:
        """
        Validate if relationship type is allowed between element types.

        This is a simplified validation. Full ArchiMate validation is complex.
        """
        # Allow all for now - full validation would require complete metamodel
        return True

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_realization_discovery_prompt(
        self, elements_context: List[Dict], context_description: str
    ) -> str:
        """Build realization relationship discovery prompt."""
        return f"""Discover REALIZATION RELATIONSHIPS between architecture elements.

Elements:
{json.dumps(elements_context, indent=2)}

Context:
{context_description}

A Realization relationship indicates that an entity plays a critical role
in the creation, achievement, or implementation of another entity.

Common patterns:
- Outcome realizes Goal
- BusinessProcess realizes Outcome
- ApplicationComponent realizes BusinessProcess (via serving)
- ApplicationService realizes BusinessService
- TechnologyService realizes ApplicationService
- Node realizes ApplicationComponent (via assignment)

For each potential realization relationship:
- source_id: Element that realizes
- target_id: Element being realized
- rationale: Why this realization exists

Return JSON:
{{
  "realization_relationships": [
    {{
      "source_id": 5,
      "target_id": 2,
      "rationale": "Order Processing application component realizes the Order Management business process by automating order creation, validation, and fulfillment"
    }}
  ]
}}
"""

    def _build_flow_analysis_prompt(
        self, source: ArchiMateElement, target: ArchiMateElement, flow_description: str
    ) -> str:
        """Build flow analysis prompt."""
        return f"""Analyze this DATA/CONTROL FLOW between elements.

Source: {source.name} ({source.type})
{source.description}

Target: {target.name} ({target.type})
{target.description}

Flow Description:
{flow_description}

Determine:
- flow_type: data | control | information
- protocol: HTTP/REST | SOAP | MQ | File | Database | etc.
- frequency: real-time | hourly | daily | batch | event-driven
- data_volume: Approximate volume
- latency_requirement: Required latency

Return JSON:
{{
  "flow_type": "data",
  "protocol": "HTTP/REST",
  "frequency": "real-time",
  "data_volume": "~1000 transactions/hour",
  "latency_requirement": "<100ms"
}}
"""

    def _build_flow_discovery_prompt(
        self, elements_context: List[Dict], context_description: str
    ) -> str:
        """Build flow relationship discovery prompt."""
        return f"""Discover FLOW RELATIONSHIPS (data/control flows) between elements.

Elements:
{json.dumps(elements_context, indent=2)}

Context:
{context_description}

A Flow relationship represents transfer of information, data, or control.

Common patterns:
- BusinessProcess -> BusinessProcess (process flow)
- ApplicationComponent -> ApplicationComponent (data exchange)
- ApplicationService -> ApplicationService (service orchestration)
- Node -> Node (network traffic)

For each flow relationship:
- source_id: Source element
- target_id: Target element
- properties: {{flow_type, protocol, frequency, data_volume}}

Return JSON:
{{
  "flow_relationships": [
    {{
      "source_id": 10,
      "target_id": 12,
      "properties": {{
        "flow_type": "data",
        "protocol": "REST API",
        "frequency": "real-time",
        "data_volume": "100 requests/sec"
      }}
    }}
  ]
}}
"""

    def _build_impact_analysis_prompt(self, impact_context: Dict) -> str:
        """Build impact analysis prompt."""
        return f"""Analyze IMPACT of this change across architecture layers.

Change Context:
{json.dumps(impact_context, indent=2)}

Identify:
1. **Direct Impacts**: Elements directly affected by the change
2. **Indirect Impacts**: Elements affected through dependency chains
3. **Affected Goals**: Business goals/outcomes impacted
4. **Risk Level**: Overall risk (high/medium/low)

Return JSON:
{{
  "direct_impacts": [
    {{
      "element_id": 5,
      "element_name": "Order Processing Service",
      "impact_type": "breaking_change",
      "impact_description": "API contract change requires client updates"
    }}
  ],
  "indirect_impacts": [
    {{
      "element_id": 8,
      "element_name": "Mobile App",
      "impact_type": "downstream_dependency",
      "impact_description": "Mobile app depends on Order Processing Service API"
    }}
  ],
  "affected_goals": [
    {{
      "goal_id": 1,
      "goal_name": "Improve customer satisfaction",
      "impact": "Temporary service disruption may affect customer satisfaction during migration"
    }}
  ],
  "risk_level": "medium",
  "risk_rationale": "Breaking change but controlled rollout possible, limited blast radius",
  "mitigation_recommendations": [
    "Use API versioning to support both old and new contracts",
    "Phased rollout with canary deployment",
    "Comprehensive testing of dependent systems"
  ]
}}
"""
