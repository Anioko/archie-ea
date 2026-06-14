"""
-> app.modules.architecture.services.governance_service

rchitecture validation and integrity checking."""

import logging
from typing import Dict, List, Tuple

from app.extensions import db
from app.models.archimate_core import ArchiMateElement as ArchitectureElement, ArchiMateRelationship as Relationship

logger = logging.getLogger(__name__)

# Valid ArchiMate 3.2 element types — all 63 types across 8 layers
# Aligned with composer_renderer.js and archimate_viewpoint_service.py
VALID_ELEMENT_TYPES = {
    # Strategy (4)
    "Capability", "Resource", "ValueStream", "CourseOfAction",
    # Motivation (10)
    "Stakeholder", "Driver", "Assessment", "Goal", "Outcome",
    "Principle", "Requirement", "Constraint", "Meaning", "Value",
    # Business (13)
    "BusinessActor", "BusinessRole", "BusinessProcess", "BusinessFunction",
    "BusinessService", "BusinessEvent", "BusinessObject", "BusinessInteraction",
    "BusinessCollaboration", "BusinessInterface", "Product", "Contract", "Representation",
    # Application (9)
    "ApplicationComponent", "ApplicationCollaboration", "ApplicationInterface",
    "ApplicationFunction", "ApplicationInteraction", "ApplicationService",
    "ApplicationProcess", "ApplicationEvent", "DataObject",
    # Technology (13)
    "Node", "Device", "SystemSoftware", "TechnologyCollaboration",
    "TechnologyInterface", "Path", "CommunicationNetwork", "TechnologyFunction",
    "TechnologyProcess", "TechnologyInteraction", "TechnologyService",
    "TechnologyEvent", "Artifact",
    # Physical (4)
    "Equipment", "Facility", "DistributionNetwork", "Material",
    # Implementation & Migration (5)
    "WorkPackage", "Deliverable", "ImplementationEvent", "Plateau", "Gap",
    # Composite (4)
    "Grouping", "Location", "AndJunction", "OrJunction",
    # Legacy snake_case aliases (backward compat with existing data)
    "business_actor", "business_role", "business_process", "business_function",
    "business_object", "business_service", "business_event",
    "application_component", "application_service", "application_interface",
    "application_process", "application_function", "application_event",
    "technology_node", "technology_service", "technology_interface",
    "technology_event", "artifact", "device", "communication_network",
}

# Valid ArchiMate layers — all 8
VALID_LAYERS = {
    "motivation", "strategy", "business", "application",
    "technology", "physical", "implementation", "composite",
}

# Valid relationship types — ArchiMate 3.2 standard (11) + legacy aliases
VALID_RELATIONSHIP_TYPES = {
    # ArchiMate 3.2 standard
    "Composition", "Aggregation", "Assignment", "Realization",
    "Serving", "Access", "Influence", "Triggering", "Flow",
    "Specialization", "Association",
    # Legacy aliases
    "is_used_by", "serves", "realizes", "aggregates", "composes", "flows_to",
    "specializes", "triggers", "associated_with", "assigned_to", "accesses",
}


class ArchitectureValidator:
    """Validates architecture elements and relationships."""
    
    @staticmethod
    def validate_element(data: Dict) -> Tuple[bool, List[str]]:
        """Validate element data.
        
        Returns: (is_valid, error_list)
        """
        errors = []
        
        # Required fields
        if not data.get("name"):
            errors.append("Element name is required")
        elif len(data["name"]) > 200:
            errors.append("Element name must be < 200 characters")
        
        if not data.get("element_type"):
            errors.append("Element type is required")
        elif data["element_type"] not in VALID_ELEMENT_TYPES:
            errors.append(f"Invalid element type. Valid options: {', '.join(VALID_ELEMENT_TYPES)}")
        
        # Optional but validated
        if "layer" in data and data["layer"] and data["layer"] not in VALID_LAYERS:
            errors.append(f"Invalid layer. Valid options: {', '.join(VALID_LAYERS)}")
        
        if "description" in data and len(data.get("description", "")) > 1000:
            errors.append("Description must be < 1000 characters")
        
        # Check for duplicates
        if "id" not in data:  # Creating new
            existing = ArchitectureElement.query.filter_by(name=data["name"]).first()
            if existing:
                errors.append(f"Element with name '{data['name']}' already exists")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_relationship(data: Dict) -> Tuple[bool, List[str]]:
        """Validate relationship data.
        
        Returns: (is_valid, error_list)
        """
        errors = []
        
        # Required fields
        if not data.get("source_id"):
            errors.append("Source element ID required")
        elif not ArchitectureElement.query.get(data["source_id"]):
            errors.append(f"Source element {data['source_id']} not found")
        
        if not data.get("target_id"):
            errors.append("Target element ID required")
        elif not ArchitectureElement.query.get(data["target_id"]):
            errors.append(f"Target element {data['target_id']} not found")
        
        if not data.get("relationship_type"):
            errors.append("Relationship type is required")
        elif data["relationship_type"] not in VALID_RELATIONSHIP_TYPES:
            errors.append(f"Invalid relationship type. Valid options: {', '.join(VALID_RELATIONSHIP_TYPES)}")
        
        # Self-relationships not allowed
        if data.get("source_id") == data.get("target_id"):
            errors.append("Cannot create self-referential relationship")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_relationships_integrity() -> List[str]:
        """Check all relationships in system for integrity violations.
        
        Returns: List of error messages
        """
        errors = []
        relationships = Relationship.query.all()
        
        for rel in relationships:
            # Check elements exist
            if not ArchitectureElement.query.get(rel.source_id):
                errors.append(f"Relationship {rel.id}: Source element {rel.source_id} missing")
            
            if not ArchitectureElement.query.get(rel.target_id):
                errors.append(f"Relationship {rel.id}: Target element {rel.target_id} missing")
            
            # Check for self-refs
            if rel.source_id == rel.target_id:
                errors.append(f"Relationship {rel.id}: Self-referential relationship")
        
        return errors
    
    @staticmethod
    def detect_circular_dependencies() -> List[Tuple[int, int]]:
        """Find circular dependencies in architecture.
        
        Returns: List of (element_id, element_id) tuples forming cycles
        """
        # Build adjacency map
        graph = {}
        relationships = Relationship.query.all()
        
        for rel in relationships:
            if rel.source_id not in graph:
                graph[rel.source_id] = []
            graph[rel.source_id].append(rel.target_id)
        
        cycles = []
        visited = set()
        rec_stack = set()
        
        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycles.append((node, neighbor))
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                has_cycle(node, [node])
        
        return cycles
    
    @staticmethod
    def would_create_cycle(source_id: int, target_id: int) -> bool:
        """Check if adding this relationship would create a cycle."""
        # Simple check: is there a path from target back to source?
        visited = set()
        
        def can_reach(start, end):
            if start == end:
                return True
            if start in visited:
                return False
            
            visited.add(start)
            
            for rel in Relationship.query.filter_by(source_id=start).all():
                if can_reach(rel.target_id, end):
                    return True
            
            return False
        
        return can_reach(target_id, source_id)
    
    @staticmethod
    def check_naming_convention(name: str) -> Tuple[bool, str]:
        """Check if name follows naming convention.
        
        Returns: (is_valid, message)
        """
        if not name or len(name) == 0:
            return False, "Name cannot be empty"
        
        if len(name) > 200:
            return False, "Name must be < 200 characters"
        
        # Must start with letter or number
        if not name[0].isalnum():
            return False, "Name must start with letter or number"
        
        # Allow letters, numbers, hyphens, underscores, spaces
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ")
        if not all(c in allowed_chars for c in name):
            return False, "Name contains invalid characters"
        
        return True, "Name is valid"
