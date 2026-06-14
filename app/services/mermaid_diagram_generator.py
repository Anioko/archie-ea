"""
Mermaid Diagram Generator for ArchiMate Viewpoints

Converts ArchiMate viewpoint data structures into Mermaid.js diagram syntax.
Supports flowcharts and graph diagrams with ArchiMate-inspired styling.
"""

from typing import Dict, List


class MermaidDiagramGenerator:
    """Generate Mermaid.js diagrams from ArchiMate viewpoint data."""

    # ArchiMate layer colors (approximated for Mermaid)
    LAYER_COLORS = {
        "strategy": "#FFFFB5",  # Light yellow
        "business": "#FFFFB5",  # Light yellow
        "application": "#B5FFFF",  # Light cyan
        "technology": "#C9E7B7",  # Light green
        "physical": "#C9E7B7",  # Light green
        "motivation": "#CCCCFF",  # Light purple
        "implementation": "#FFE0CC",  # Light orange
    }

    # Node shapes by element type
    NODE_SHAPES = {
        "application_component": "rect",
        "application_interface": "circle",
        "application_service": "stadium",
        "application_event": "hexagon",
        "business_process": "subroutine",
        "business_service": "stadium",
        "capability": "trapezoid",
        "requirement": "parallelogram",
        "goal": "parallelogram",
        "driver": "parallelogram",
        "product": "cylinder",
        "node": "cylinder",
        "technology_service": "stadium",
    }

    def generate_cooperation_diagram(self, viewpoint_data: Dict) -> str:
        """
        Generate Mermaid flowchart for Application Cooperation viewpoint.

        Args:
            viewpoint_data: Output from ArchiMateViewpointBuilder.build_cooperation_viewpoint()

        Returns:
            Mermaid.js diagram syntax as string
        """
        if viewpoint_data.get("metadata", {}).get("empty"):
            return self._generate_empty_diagram(
                viewpoint_data["metadata"].get("message", "No data")
            )

        lines = ["graph TD"]  # Top-down flowchart
        lines.append("    %% Application Cooperation Viewpoint")
        lines.append("")

        # Add nodes
        for node in viewpoint_data["nodes"]:
            node_id = f"N{node['id']}"
            label = self._escape_label(node["label"])
            shape = self._get_node_shape(node)

            # Highlight central node
            if node.get("is_central"):
                lines.append(f'    {node_id}[["{label}"]]')
                lines.append(f"    style {node_id} fill:#FFD700,stroke:#333,stroke-width:3px")
            else:
                lines.append(f"    {node_id}{shape}")
                color = self.LAYER_COLORS.get(node.get("layer", ""), "#E0E0E0")
                lines.append(f"    style {node_id} fill:{color},stroke:#333,stroke-width:2px")

        lines.append("")

        # Add edges
        for edge in viewpoint_data["edges"]:
            source_id = f"N{edge['source']}"
            target_id = f"N{edge['target']}"
            label = edge.get("label", "")

            # Different arrow styles for different relationship types
            if edge["type"] == "flow":
                lines.append(f"    {source_id} -->|{label}| {target_id}")
            elif edge["type"] == "serving":
                lines.append(f"    {source_id} -.->|{label}| {target_id}")
            elif edge["type"] == "composition":
                lines.append(f"    {source_id} ==>|{label}| {target_id}")
            else:
                lines.append(f"    {source_id} -->|{label}| {target_id}")

        return "\n".join(lines)

    def generate_usage_diagram(self, viewpoint_data: Dict) -> str:
        """
        Generate Mermaid flowchart for Application Usage viewpoint.

        Args:
            viewpoint_data: Output from ArchiMateViewpointBuilder.build_usage_viewpoint()

        Returns:
            Mermaid.js diagram syntax as string
        """
        if viewpoint_data.get("metadata", {}).get("empty"):
            return self._generate_empty_diagram(
                viewpoint_data["metadata"].get("message", "No data")
            )

        lines = ["graph TB"]  # Top-bottom flowchart
        lines.append("    %% Application Usage Viewpoint")
        lines.append("")

        # Group nodes by layer for better layout
        business_nodes = []
        app_nodes = []

        for node in viewpoint_data["nodes"]:
            if node.get("layer") == "business":
                business_nodes.append(node)
            else:
                app_nodes.append(node)

        # Add business layer nodes first (top)
        if business_nodes:
            lines.append("    %% Business Layer")
            for node in business_nodes:
                node_id = f"N{node['id']}"
                label = self._escape_label(node["label"])
                shape = self._get_node_shape(node)
                lines.append(f"    {node_id}{shape}")
                lines.append(f"    style {node_id} fill:#FFFFB5,stroke:#333,stroke-width:2px")
            lines.append("")

        # Add application layer nodes (bottom)
        if app_nodes:
            lines.append("    %% Application Layer")
            for node in app_nodes:
                node_id = f"N{node['id']}"
                label = self._escape_label(node["label"])
                shape = self._get_node_shape(node)

                if node.get("is_central"):
                    lines.append(f'    {node_id}[["{label}"]]')
                    lines.append(f"    style {node_id} fill:#FFD700,stroke:#333,stroke-width:3px")
                else:
                    lines.append(f"    {node_id}{shape}")
                    lines.append(f"    style {node_id} fill:#B5FFFF,stroke:#333,stroke-width:2px")
            lines.append("")

        # Add edges
        for edge in viewpoint_data["edges"]:
            source_id = f"N{edge['source']}"
            target_id = f"N{edge['target']}"
            label = edge.get("label", "")

            if edge["type"] == "realization":
                lines.append(f"    {source_id} ==>|{label}| {target_id}")
            elif edge["type"] == "serving":
                lines.append(f"    {source_id} -.->|{label}| {target_id}")
            else:
                lines.append(f"    {source_id} -->|{label}| {target_id}")

        return "\n".join(lines)

    def generate_implementation_diagram(self, viewpoint_data: Dict) -> str:
        """
        Generate Mermaid flowchart for Implementation & Migration viewpoint.

        Args:
            viewpoint_data: Output from ArchiMateViewpointBuilder.build_implementation_viewpoint()

        Returns:
            Mermaid.js diagram syntax as string
        """
        if viewpoint_data.get("metadata", {}).get("empty"):
            return self._generate_empty_diagram(
                viewpoint_data["metadata"].get("message", "No data")
            )

        lines = ["graph BT"]  # Bottom-top (implementation realizes application)
        lines.append("    %% Implementation & Migration Viewpoint")
        lines.append("")

        # Add nodes
        for node in viewpoint_data["nodes"]:
            node_id = f"N{node['id']}"
            label = self._escape_label(node["label"])
            shape = self._get_node_shape(node)

            if node.get("is_central"):
                lines.append(f'    {node_id}[["{label}"]]')
                lines.append(f"    style {node_id} fill:#FFD700,stroke:#333,stroke-width:3px")
            elif node.get("type") == "product":
                lines.append(f"    {node_id}[('{label}')]")
                lines.append(f"    style {node_id} fill:#FFE0CC,stroke:#333,stroke-width:2px")
            elif node.get("layer") == "technology":
                lines.append(f"    {node_id}{shape}")
                lines.append(f"    style {node_id} fill:#C9E7B7,stroke:#333,stroke-width:2px")
            else:
                lines.append(f"    {node_id}{shape}")

        lines.append("")

        # Add edges
        for edge in viewpoint_data["edges"]:
            source_id = f"N{edge['source']}"
            target_id = f"N{edge['target']}"
            label = edge.get("label", "")

            if edge["type"] == "realization":
                lines.append(f"    {source_id} ==>|{label}| {target_id}")
            else:
                lines.append(f"    {source_id} -->|{label}| {target_id}")

        return "\n".join(lines)

    def generate_motivation_diagram(self, viewpoint_data: Dict) -> str:
        """
        Generate Mermaid flowchart for Motivation & Compliance viewpoint.

        Args:
            viewpoint_data: Output from ArchiMateViewpointBuilder.build_motivation_viewpoint()

        Returns:
            Mermaid.js diagram syntax as string
        """
        if viewpoint_data.get("metadata", {}).get("empty"):
            return self._generate_empty_diagram(
                viewpoint_data["metadata"].get("message", "No data")
            )

        lines = ["graph TB"]  # Top-bottom (goals drive requirements drive implementation)
        lines.append("    %% Motivation & Compliance Viewpoint")
        lines.append("")

        # Add nodes
        for node in viewpoint_data["nodes"]:
            node_id = f"N{node['id']}"
            label = self._escape_label(node["label"])

            if node.get("is_central"):
                lines.append(f'    {node_id}[["{label}"]]')
                lines.append(f"    style {node_id} fill:#FFD700,stroke:#333,stroke-width:3px")
            elif node.get("type") in ["requirement", "goal", "driver", "constraint"]:
                # Motivation elements use parallelogram shape
                lines.append(f"    {node_id}[/{label}/]")
                lines.append(f"    style {node_id} fill:#CCCCFF,stroke:#333,stroke-width:2px")
            else:
                shape = self._get_node_shape(node)
                lines.append(f"    {node_id}{shape}")

        lines.append("")

        # Add edges
        for edge in viewpoint_data["edges"]:
            source_id = f"N{edge['source']}"
            target_id = f"N{edge['target']}"
            label = edge.get("label", "")

            if edge["type"] == "realization":
                lines.append(f"    {source_id} ==>|{label}| {target_id}")
            elif edge["type"] == "influence":
                lines.append(f"    {source_id} -.->|{label}| {target_id}")
            else:
                lines.append(f"    {source_id} -->|{label}| {target_id}")

        return "\n".join(lines)

    def generate_impact_tree(self, impact_data: Dict) -> str:
        """
        Generate Mermaid diagram for impact analysis tree.

        Args:
            impact_data: Output from ArchiMateViewpointBuilder.calculate_impact_score()

        Returns:
            Mermaid.js diagram syntax as string
        """
        lines = ["graph TD"]
        lines.append("    %% Impact Analysis")
        lines.append("")

        # Central node with impact score
        risk_level = impact_data["risk_level"]
        total_score = impact_data["total_score"]

        risk_colors = {
            "critical": "#FF4444",
            "high": "#FF9944",
            "medium": "#FFDD44",
            "low": "#44FF44",
            "unknown": "#CCCCCC",
        }

        lines.append(f'    ROOT[["Impact Score: {total_score}/100<br/>{risk_level.upper()} RISK"]]')
        lines.append(
            f"    style ROOT fill:{risk_colors[risk_level]},stroke:#333,stroke-width:3px,color:#000"
        )
        lines.append("")

        # Breakdown nodes
        breakdown = impact_data.get("breakdown", {})
        for i, (category, score) in enumerate(breakdown.items()):
            node_id = f"CAT{i}"
            label = f"{category.replace('_', ' ').title()}<br/>{score} pts"
            lines.append(f'    {node_id}["{label}"]')
            lines.append(f"    ROOT --> {node_id}")

        return "\n".join(lines)

    # Private helper methods

    def _get_node_shape(self, node: Dict) -> str:
        """Get Mermaid shape syntax for node."""
        label = self._escape_label(node["label"])
        node_type = node.get("type", "").lower().replace(" ", "_")

        # Map to Mermaid shapes
        if node_type in ["application_interface", "interface"]:
            return f'(("{label}"))'  # Circle
        elif node_type in ["application_service", "business_service", "technology_service"]:
            return f"([{label}])"  # Stadium
        elif "event" in node_type:
            return f"{{{{{label}}}}}"  # Hexagon
        elif "process" in node_type:
            return f"[[{label}]]"  # Subroutine
        elif node_type == "capability":
            return f"[/{label}/]"  # Trapezoid
        elif node_type in ["requirement", "goal", "driver", "constraint"]:
            return f"[/{label}/]"  # Parallelogram
        elif node_type in ["product", "node"]:
            return f'[("{label}")]'  # Cylinder
        else:
            return f'["{label}"]'  # Rectangle (default)

    def _escape_label(self, label: str) -> str:
        """Escape special characters in labels for Mermaid."""
        if not label:
            return "Unnamed"
        # Escape quotes and special chars
        label = label.replace('"', "'")
        label = label.replace("[", "(")
        label = label.replace("]", ")")
        # Truncate long labels
        if len(label) > 40:
            label = label[:37] + "..."
        return label

    def _generate_empty_diagram(self, message: str) -> str:
        """Generate placeholder diagram for empty viewpoints."""
        return f"""graph TD
    EMPTY["{message}"]
    style EMPTY fill:#F0F0F0,stroke:#999,stroke-width:2px,stroke-dasharray: 5 5"""
