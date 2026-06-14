"""ADM-to-Composer Bridge Service

Transforms TOGAF ADM Phase A Architecture Vision outputs into
Solution Composer canvas elements for visual architecture composition.

Key Features:
- Converts ADM Phase A deliverables into CanvasNode objects
- Generates ArchiMate-compliant element mappings
- Creates initial solution canvas with stakeholders, capabilities, constraints
- Provides visual layout suggestions for architecture vision elements
- Links ADM workflow instances to Solution Composer canvases

Reuses:
- SolutionComposerService for canvas operations
- CanvasNode, CanvasConnection, CanvasState dataclasses
- ADM Phase A workflow outputs from EAWorkflowEngine
- ArchiMate 3.2 element types for proper visualization
"""

import json  # dead-code-ok — used in downstream methods
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok — type hints in method signatures
from uuid import uuid4

from app import db  # dead-code-ok — used in downstream methods
from app.modules.solutions_strategic.v2.services.solution_composer_service import (
    CanvasNode,
    CanvasConnection,
    CanvasState,
    SolutionComposerService,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ArchiMate Element Mappings for ADM Artifacts
# =============================================================================

# Map ADM stakeholder categories to ArchiMate Business Actors
STAKEHOLDER_ARCHIMATE_MAP = {
    "executive": {"type": "business_actor", "layer": "business", "icon": "👔"},
    "architect": {"type": "business_role", "layer": "business", "icon": "🏗️"},
    "business_owner": {"type": "business_role", "layer": "business", "icon": "💼"},
    "technical": {"type": "business_role", "layer": "business", "icon": "⚙️"},
    "other": {"type": "business_actor", "layer": "business", "icon": "👤"},
}

# Map business goal types to ArchiMate motivational elements
GOAL_ARCHIMATE_MAP = {
    "strategic": {"type": "goal", "layer": "motivation"},
    "operational": {"type": "outcome", "layer": "motivation"},
    "financial": {"type": "goal", "layer": "motivation"},
    "customer": {"type": "goal", "layer": "motivation"},
    "compliance": {"type": "principle", "layer": "motivation"},
}

# Map capability maturity to visual styling
CAPABILITY_MATURITY_STYLES = {
    "high": {"color": "#10b981", "border": "#059669", "badge": "mature"},
    "medium": {"color": "#f59e0b", "border": "#d97706", "badge": "developing"},
    "low": {"color": "#ef4444", "border": "#dc2626", "badge": "gap"},
    "unknown": {"color": "#6b7280", "border": "#4b5563", "badge": "unknown"},
}

# Constraint visualization mapping
CONSTRAINT_TYPE_STYLES = {
    "budget": {"icon": "💰", "color": "#f59e0b"},
    "timeline": {"icon": "⏱️", "color": "#3b82f6"},
    "regulatory": {"icon": "⚖️", "color": "#8b5cf6"},
    "technical": {"icon": "🔧", "color": "#10b981"},
    "resource": {"icon": "👥", "color": "#ef4444"},
}


class ADMToComposerBridgeService:
    """Bridge service connecting ADM Phase A outputs to Solution Composer."""

    def __init__(self):
        self.composer_service = SolutionComposerService()

    # =========================================================================
    # Main Bridge Methods
    # =========================================================================

    def create_canvas_from_adm_workflow(
        self,
        workflow_instance_id: int,
        adm_outputs: Dict[str, Any],
        user_id: int,
    ) -> CanvasState:
        """Create a new Solution Composer canvas from ADM Phase A workflow outputs.
        
        Args:
            workflow_instance_id: The ADM workflow instance ID
            adm_outputs: Dictionary containing all ADM Phase A step outputs
            user_id: User creating the canvas
            
        Returns:
            CanvasState: Populated canvas ready for editing in Solution Composer
        """
        scope = adm_outputs.get("scope", {})
        stakeholders = adm_outputs.get("stakeholders", {})
        goals = adm_outputs.get("goals", {})
        constraints = adm_outputs.get("constraints", {})
        capabilities = adm_outputs.get("capabilities", {})

        project_name = scope.get("project_name", "Architecture Vision")

        # Initialize canvas
        canvas = CanvasState(
            name=f"ADM Vision: {project_name}",
            description=self._generate_canvas_description(adm_outputs),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

        # Generate nodes with auto-layout positioning
        nodes = []

        # 1. Create stakeholder nodes (left side)
        stakeholder_nodes = self._create_stakeholder_nodes(stakeholders)
        nodes.extend(self._position_nodes(stakeholder_nodes, row=0, start_x=50))

        # 2. Create business goal nodes (motivation layer, top)
        goal_nodes = self._create_goal_nodes(goals)
        nodes.extend(self._position_nodes(goal_nodes, row=1, start_x=50, y_offset=200))

        # 3. Create capability nodes (business layer, center)
        capability_nodes = self._create_capability_nodes(capabilities)
        nodes.extend(self._position_nodes(capability_nodes, row=2, start_x=50, y_offset=450))

        # 4. Create constraint nodes (bottom)
        constraint_nodes = self._create_constraint_nodes(constraints)
        nodes.extend(self._position_nodes(constraint_nodes, row=3, start_x=50, y_offset=750))

        canvas.nodes = nodes

        # Generate connections between related elements
        canvas.connections = self._create_adm_connections(nodes, adm_outputs)

        logger.info(
            f"Created ADM canvas '{canvas.name}' with {len(nodes)} nodes "
            f"and {len(canvas.connections)} connections"
        )

        return canvas

    def import_adm_to_existing_canvas(
        self,
        canvas_id: int,
        adm_outputs: Dict[str, Any],
        merge_strategy: str = "append",
    ) -> CanvasState:
        """Import ADM Phase A elements into an existing Solution Composer canvas.
        
        Args:
            canvas_id: Existing canvas ID to import into
            adm_outputs: ADM Phase A workflow outputs
            merge_strategy: How to handle conflicts - "append", "replace", or "merge"
            
        Returns:
            CanvasState: Updated canvas with ADM elements integrated
        """
        # Load existing canvas
        existing_canvas = self.composer_service.load_canvas(canvas_id)
        if not existing_canvas:
            raise ValueError(f"Canvas {canvas_id} not found")

        # Generate ADM nodes with positioning to avoid overlap
        adm_canvas = self.create_canvas_from_adm_workflow(0, adm_outputs, 0)

        # Offset ADM nodes to right of existing content
        max_x = max(
            (n.position_x + n.width for n in existing_canvas.nodes),
            default=0
        )
        offset_x = max_x + 100 if max_x > 0 else 50

        for node in adm_canvas.nodes:
            node.position_x += offset_x

        if merge_strategy == "append":
            existing_canvas.nodes.extend(adm_canvas.nodes)
            existing_canvas.connections.extend(adm_canvas.connections)
        elif merge_strategy == "replace":
            # Replace motivation/business layer elements only
            existing_canvas.nodes = [
                n for n in existing_canvas.nodes
                if n.layer not in ["business", "motivation"]
            ]
            existing_canvas.nodes.extend(adm_canvas.nodes)
            # Regenerate connections
            existing_canvas.connections = self._create_adm_connections(
                existing_canvas.nodes, adm_outputs
            )

        existing_canvas.updated_at = datetime.utcnow().isoformat()

        logger.info(
            f"Imported ADM elements to canvas {canvas_id} using {merge_strategy} strategy"
        )

        return existing_canvas

    # =========================================================================
    # Node Generation Methods
    # =========================================================================

    def _create_stakeholder_nodes(self, stakeholders_data: Dict) -> List[CanvasNode]:
        """Convert stakeholder analysis into CanvasNode objects."""
        nodes = []
        stakeholder_list = stakeholders_data.get("stakeholders", [])

        for idx, stakeholder in enumerate(stakeholder_list):
            category = stakeholder.get("category", "other")
            mapping = STAKEHOLDER_ARCHIMATE_MAP.get(category, STAKEHOLDER_ARCHIMATE_MAP["other"])

            node = CanvasNode(
                id=f"stakeholder_{uuid4().hex[:8]}",
                type=mapping["type"],
                layer=mapping["layer"],
                name=stakeholder.get("name", f"Stakeholder {idx + 1}"),
                source_type="stakeholder",
                source_id=stakeholder.get("id"),
                properties={
                    "role": stakeholder.get("role", "Unknown"),
                    "email": stakeholder.get("email", ""),
                    "category": category,
                    "concerns": stakeholder.get("concerns", []),
                    "icon": mapping["icon"],
                    "adm_source": "stakeholder_analysis",
                },
            )
            nodes.append(node)

        return nodes

    def _create_goal_nodes(self, goals_data: Dict) -> List[CanvasNode]:
        """Convert business goals into ArchiMate motivational element nodes."""
        nodes = []
        goal_list = goals_data.get("business_goals", [])

        for idx, goal in enumerate(goal_list):
            goal_type = self._categorize_goal(goal.get("statement", ""))
            mapping = GOAL_ARCHIMATE_MAP.get(goal_type, GOAL_ARCHIMATE_MAP["strategic"])

            node = CanvasNode(
                id=f"goal_{uuid4().hex[:8]}",
                type=mapping["type"],
                layer=mapping["layer"],
                name=goal.get("statement", f"Goal {idx + 1}")[:50],  # Truncate long names
                source_type="business_goal",
                properties={
                    "full_statement": goal.get("statement", ""),
                    "measurable_outcome": goal.get("measurable_outcome", ""),
                    "goal_type": goal_type,
                    "target_date": goal.get("target_date", ""),
                    "adm_source": "business_goals",
                },
            )
            nodes.append(node)

        return nodes

    def _create_capability_nodes(self, capabilities_data: Dict) -> List[CanvasNode]:
        """Convert capability assessment into CanvasNode objects with maturity styling."""
        nodes = []
        capability_list = capabilities_data.get("capabilities", [])

        for idx, capability in enumerate(capability_list):
            maturity = capability.get("maturity", "unknown").lower()
            style = CAPABILITY_MATURITY_STYLES.get(maturity, CAPABILITY_MATURITY_STYLES["unknown"])

            node = CanvasNode(
                id=f"capability_{uuid4().hex[:8]}",
                type="capability",
                layer="business",
                name=capability.get("name", f"Capability {idx + 1}"),
                source_type="business_capability",
                source_id=capability.get("id"),
                properties={
                    "code": capability.get("code", ""),
                    "level": capability.get("level", 1),
                    "maturity": maturity,
                    "gap_assessment": capability.get("gap_assessment", ""),
                    "style": style,
                    "badge": style["badge"],
                    "adm_source": "capability_assessment",
                },
            )
            nodes.append(node)

        return nodes

    def _create_constraint_nodes(self, constraints_data: Dict) -> List[CanvasNode]:
        """Convert constraints into visual constraint nodes."""
        nodes = []

        # Process different constraint types
        all_constraints = []
        all_constraints.extend(
            constraints_data.get("business_constraints", [])
        )
        all_constraints.extend(
            constraints_data.get("technical_constraints", [])
        )

        # Add policy constraints with special handling
        policy_constraints = constraints_data.get("policy_constraints", [])
        for policy in policy_constraints:
            all_constraints.append({
                "description": f"Policy: {policy.get('name', 'Unknown Policy')}",
                "type": "regulatory",
                "severity": policy.get("severity", "medium"),
                "impact": "Policy compliance required",
            })

        for idx, constraint in enumerate(all_constraints):
            constraint_type = self._categorize_constraint(
                constraint.get("description", "")
            )
            style = CONSTRAINT_TYPE_STYLES.get(
                constraint_type, CONSTRAINT_TYPE_STYLES["technical"]
            )

            node = CanvasNode(
                id=f"constraint_{uuid4().hex[:8]}",
                type="constraint",
                layer="motivation",
                name=constraint.get("description", f"Constraint {idx + 1}")[:50],
                source_type="constraint",
                properties={
                    "full_description": constraint.get("description", ""),
                    "constraint_type": constraint_type,
                    "severity": constraint.get("severity", "medium"),
                    "impact": constraint.get("impact", ""),
                    "icon": style["icon"],
                    "style": {"color": style["color"]},
                    "adm_source": "constraints_assessment",
                },
            )
            nodes.append(node)

        return nodes

    # =========================================================================
    # Auto-Layout and Positioning
    # =========================================================================

    def _position_nodes(
        self,
        nodes: List[CanvasNode],
        row: int,
        start_x: float = 50,
        y_offset: float = None,
    ) -> List[CanvasNode]:
        """Position nodes in a grid layout with automatic spacing."""
        if not nodes:
            return nodes

        # Default Y positions by row
        row_y_positions = {0: 50, 1: 250, 2: 500, 3: 800}
        base_y = y_offset if y_offset is not None else row_y_positions.get(row, 50)

        # Grid spacing
        node_width = 220
        node_height = 120
        gap_x = 40
        gap_y = 60

        # Arrange in rows of max 4 nodes
        cols = min(4, len(nodes))

        for idx, node in enumerate(nodes):
            col = idx % cols
            sub_row = idx // cols

            node.position_x = start_x + (col * (node_width + gap_x))
            node.position_y = base_y + (sub_row * (node_height + gap_y))
            node.width = node_width
            node.height = node_height

        return nodes

    # =========================================================================
    # Connection Generation
    # =========================================================================

    def _create_adm_connections(
        self,
        nodes: List[CanvasNode],
        adm_outputs: Dict[str, Any],
    ) -> List[CanvasConnection]:
        """Generate ArchiMate connections between ADM elements."""
        connections = []

        # Group nodes by type for connection logic
        stakeholder_nodes = [n for n in nodes if n.source_type == "stakeholder"]
        goal_nodes = [n for n in nodes if n.source_type == "business_goal"]
        capability_nodes = [n for n in nodes if n.source_type == "business_capability"]
        constraint_nodes = [n for n in nodes if n.source_type == "constraint"]

        # 1. Connect stakeholders to goals (stakeholders influence goals)
        for stakeholder in stakeholder_nodes:
            concerns = stakeholder.properties.get("concerns", [])
            for goal in goal_nodes:
                # Link if concerns align with goal type
                if self._concerns_match_goal(concerns, goal.properties.get("goal_type")):
                    conn = CanvasConnection(
                        id=f"conn_{uuid4().hex[:8]}",
                        source_node_id=stakeholder.id,
                        target_node_id=goal.id,
                        relationship_type="influence",
                        label="influences",
                    )
                    connections.append(conn)

        # 2. Connect goals to capabilities (goals drive capability needs)
        for goal in goal_nodes:
            for cap in capability_nodes:
                if self._goal_matches_capability(goal, cap):
                    conn = CanvasConnection(
                        id=f"conn_{uuid4().hex[:8]}",
                        source_node_id=goal.id,
                        target_node_id=cap.id,
                        relationship_type="realization",
                        label="realized by",
                    )
                    connections.append(conn)

        # 3. Connect constraints to capabilities (constraints limit capabilities)
        for constraint in constraint_nodes:
            for cap in capability_nodes:
                if self._constraint_affects_capability(constraint, cap):
                    conn = CanvasConnection(
                        id=f"conn_{uuid4().hex[:8]}",
                        source_node_id=constraint.id,
                        target_node_id=cap.id,
                        relationship_type="association",
                        label="constrains",
                        properties={"dashed": True, "color": "#ef4444"},
                    )
                    connections.append(conn)

        return connections

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_canvas_description(self, adm_outputs: Dict) -> str:
        """Generate a description for the canvas based on ADM outputs."""
        scope = adm_outputs.get("scope", {})
        project_name = scope.get("project_name", "Architecture Initiative")
        scope_boundaries = scope.get("scope_boundaries", "Enterprise scope")

        description = (
            f"Architecture Vision canvas for '{project_name}'.\n\n"
            f"Scope: {scope_boundaries}\n\n"
            f"This canvas contains:\n"
            f"- Stakeholders identified during Phase A\n"
            f"- Business goals and drivers\n"
            f"- Current capability assessment\n"
            f"- Constraints and limitations\n\n"
            f"Generated from TOGAF ADM Phase A workflow."
        )

        return description

    def _categorize_goal(self, statement: str) -> str:
        """Categorize a business goal by analyzing its statement."""
        statement_lower = statement.lower()

        keywords = {
            "financial": ["revenue", "cost", "profit", "roi", "budget", "expense"],
            "customer": ["customer", "user", "experience", "satisfaction", "cx"],
            "operational": ["efficiency", "process", "operation", "automation", "speed"],
            "compliance": ["compliance", "regulatory", "audit", "security", "legal"],
        }

        for category, words in keywords.items():
            if any(word in statement_lower for word in words):
                return category

        return "strategic"

    def _categorize_constraint(self, description: str) -> str:
        """Categorize a constraint by analyzing its description."""
        desc_lower = description.lower()

        keywords = {
            "budget": ["budget", "cost", "funding", "financial", "money", "expense"],
            "timeline": ["time", "deadline", "schedule", "milestone", "date", "duration", "complete by", "finish by"],
            "regulatory": ["compliance", "comply", "regulation", "legal", "law", "policy", "standard"],
            "resource": ["resource", "staff", "team", "personnel", "headcount"],
        }

        for category, words in keywords.items():
            if any(word in desc_lower for word in words):
                return category

        return "technical"

    def _concerns_match_goal(self, concerns: List[str], goal_type: str) -> bool:
        """Determine if stakeholder concerns align with a goal type."""
        concern_mapping = {
            "executive": ["financial", "strategic"],
            "architect": ["strategic", "operational"],
            "business_owner": ["customer", "operational"],
            "technical": ["operational", "compliance"],
        }

        return goal_type in concern_mapping.get("executive", [])

    def _goal_matches_capability(self, goal_node: CanvasNode, cap_node: CanvasNode) -> bool:
        """Determine if a goal relates to a capability."""
        goal_text = goal_node.properties.get("full_statement", "").lower()
        cap_name = cap_node.name.lower()

        # Simple keyword matching - can be enhanced with NLP
        cap_words = cap_name.split()
        return any(word in goal_text for word in cap_words if len(word) > 3)

    def _constraint_affects_capability(
        self, constraint_node: CanvasNode, cap_node: CanvasNode
    ) -> bool:
        """Determine if a constraint affects a capability."""
        # By default, link constraints to low-maturity capabilities
        return cap_node.properties.get("maturity") in ["low", "unknown"]

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_canvas_to_json(self, canvas: CanvasState) -> Dict:
        """Export canvas to JSON format for persistence or API transfer."""
        return {
            "name": canvas.name,
            "description": canvas.description,
            "nodes": [asdict(node) for node in canvas.nodes],
            "connections": [asdict(conn) for conn in canvas.connections],
            "viewport": canvas.viewport,
            "created_at": canvas.created_at,
            "updated_at": canvas.updated_at,
        }

    def import_canvas_from_json(self, data: Dict) -> CanvasState:
        """Import canvas from JSON format."""
        nodes = [CanvasNode(**node_data) for node_data in data.get("nodes", [])]
        connections = [
            CanvasConnection(**conn_data) for conn_data in data.get("connections", [])
        ]

        return CanvasState(
            name=data.get("name", "Imported Canvas"),
            description=data.get("description"),
            nodes=nodes,
            connections=connections,
            viewport=data.get("viewport", {"x": 0, "y": 0, "zoom": 1.0}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


# Singleton instance for global access
adm_to_composer_bridge = ADMToComposerBridgeService()
