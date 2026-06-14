"""Capability-driven ArchiMate template generation service."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.datetime_helpers import utcnow
from app.services.application_capability_catalog import CATALOG_ROOT, CapabilitySpec, FunctionSpec
from app.services.archimate.archimate_validator import ArchiMateValidator

logger = logging.getLogger(__name__)

ElementDict = Dict[str, object]
RelationshipDict = Dict[str, object]


def _normalize_selection(capability_names: Optional[Iterable[str]]) -> Optional[Set[str]]:
    if not capability_names:
        return None

    normalized = {name.strip().lower() for name in capability_names if name and name.strip()}
    return normalized or None


class CapabilityTemplateService:
    """Generate ArchiMate models from the curated capability catalog."""

    _TEMPLATE_CATALOG: List[Dict[str, str]] = [
        {
            "name": "capability_model.json.j2",
            "description": "ArchiMate JSON exchange document derived from capabilities.",
            "content_type": "application/json",
        },
        {
            "name": "capability_model.xml.j2",
            "description": "XML representation suitable for ArchiMate exchange tooling.",
            "content_type": "application/xml",
        },
    ]

    def __init__(
        self,
        catalog_root: CapabilitySpec = CATALOG_ROOT,
        validator: Optional[ArchiMateValidator] = None,
    ) -> None:
        self._catalog_root = catalog_root
        self._validator = validator or ArchiMateValidator()

        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(enabled_extensions=("json", "xml")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_model(
        self,
        capability_names: Optional[Iterable[str]] = None,
        model_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, object]:
        """Create an ArchiMate model seeded from the capability hierarchy."""
        selection = _normalize_selection(capability_names)
        builder = _CapabilityModelBuilder(
            catalog_root=self._catalog_root,
            validator=self._validator,
            selected_names=selection,
        )
        build_result = builder.build()

        model = {
            "name": model_name or "Application Capability Reference Architecture",
            "type": "archimate",
            "description": description
            or "Template-driven architecture derived from the application capability catalog.",
            "elements": build_result.elements,
            "relationships": build_result.relationships,
            "metadata": {
                "generation_method": "capability_template",
                "generated_at": utcnow().isoformat(),
                "selected_capabilities": sorted(builder.top_level_names),
                "statistics": build_result.statistics,
            },
        }

        logger.info(
            "Generated capability-based ArchiMate model: %s elements, %s relationships",
            len(build_result.elements),
            len(build_result.relationships),
        )

        return model

    def render_model(
        self,
        model: Dict[str, object],
        *,
        template_name: str = "capability_model.json.j2",
    ) -> str:
        """Render the generated model using the requested template."""
        available_names = {entry["name"] for entry in self._TEMPLATE_CATALOG}
        if template_name not in available_names:
            raise ValueError(
                f"Unknown capability template '{template_name}'. Available: {sorted(available_names)}"
            )

        template = self._env.get_template(template_name)
        return template.render(model=model)

    def render_model_to_json(self, model: Dict[str, object]) -> str:
        """Render the generated model through the JSON exchange template."""
        return self.render_model(model, template_name="capability_model.json.j2")

    def available_templates(self) -> List[Dict[str, str]]:
        """List render templates exposed by this service."""
        return list(self._TEMPLATE_CATALOG)


class _BuildResult:
    def __init__(
        self,
        elements: List[ElementDict],
        relationships: List[RelationshipDict],
        statistics: Dict[str, object],
    ) -> None:
        self.elements = elements
        self.relationships = relationships
        self.statistics = statistics


class _CapabilityModelBuilder:
    """Internal helper to compile capability definitions into ArchiMate structures."""

    def __init__(
        self,
        catalog_root: CapabilitySpec,
        validator: ArchiMateValidator,
        selected_names: Optional[Set[str]],
    ) -> None:
        self._catalog_root = catalog_root
        self._validator = validator
        self._selected_names = selected_names

        self._elements: List[ElementDict] = []
        self._relationships: List[RelationshipDict] = []
        self._element_index: Dict[Tuple[str, str], ElementDict] = {}
        self._type_counter: Counter[str] = Counter()
        self._capability_level_counter: Counter[int] = Counter()
        self.top_level_names: Set[str] = set()

    def build(self) -> _BuildResult:
        for capability in self._catalog_root.children:
            self._walk_capability(capability, parent_capability=None, ancestor_included=False)

        statistics: Dict[str, object] = {
            "element_types": dict(sorted(self._type_counter.items())),
            "total_elements": len(self._elements),
            "total_relationships": len(self._relationships),
            "capability_levels": dict(sorted(self._capability_level_counter.items())),
        }

        return _BuildResult(self._elements, self._relationships, statistics)

    # ----- traversal helpers -----

    def _walk_capability(
        self,
        spec: CapabilitySpec,
        parent_capability: Optional[ElementDict],
        ancestor_included: bool,
    ) -> None:
        include_self = ancestor_included or self._should_include(spec)
        if not include_self:
            return

        capability_element = self._ensure_capability_element(spec)

        if spec.level == 1:
            self.top_level_names.add(spec.name)

        if parent_capability is not None:
            self._add_relationship(
                relationship_type="Aggregation",
                source=parent_capability,
                target=capability_element,
                description=f"{parent_capability['name']} groups {capability_element['name']}",
            )

        component_element = None
        if spec.level >= 2:
            component_element = self._ensure_application_component(spec, capability_element)

        for function_spec in spec.functions:
            self._create_function_suite(
                capability_spec=spec,
                function_spec=function_spec,
                capability_element=capability_element,
                component_element=component_element,
            )

        for child in spec.children:
            self._walk_capability(child, capability_element, ancestor_included=include_self)

    def _should_include(self, spec: CapabilitySpec) -> bool:
        if self._selected_names is None:
            return True

        if spec.name.lower() in self._selected_names:
            return True

        return any(self._should_include(child) for child in spec.children)

    # ----- element creation -----

    def _ensure_capability_element(self, spec: CapabilitySpec) -> ElementDict:
        key = ("Capability", spec.name)
        existing = self._element_index.get(key)
        if existing:
            return existing

        element = self._add_element(
            name=spec.name,
            element_type="Capability",
            layer="strategy",
            description=spec.description,
            metadata={
                "level": spec.level,
                "domain": spec.domain,
                "category": spec.category,
                "capability_type": spec.capability_type,
            },
        )
        self._capability_level_counter[spec.level] += 1
        return element

    def _ensure_application_component(
        self,
        spec: CapabilitySpec,
        capability_element: ElementDict,
    ) -> ElementDict:
        component_name = f"{spec.name} Application Component"
        key = ("ApplicationComponent", component_name)
        existing = self._element_index.get(key)
        if existing:
            return existing

        component = self._add_element(
            name=component_name,
            element_type="ApplicationComponent",
            layer="application",
            description=f"Application component realizing the {spec.name} capability.",
            metadata={
                "capability": spec.name,
                "level": spec.level,
            },
        )

        self._add_relationship(
            relationship_type="Realization",
            source=capability_element,
            target=component,
            description=f"{capability_element['name']} is fulfilled by {component['name']}",
        )
        return component

    def _create_function_suite(
        self,
        capability_spec: CapabilitySpec,
        function_spec: FunctionSpec,
        capability_element: ElementDict,
        component_element: Optional[ElementDict],
    ) -> None:
        base_name = function_spec.name
        function_name = f"{base_name} Application Function ({capability_spec.name})"
        function_element = self._add_element(
            name=function_name,
            element_type="ApplicationFunction",
            layer="application",
            description=function_spec.description,
            metadata={
                "capability": capability_spec.name,
                "function_name": base_name,
                "function_type": function_spec.function_type,
                "is_automated": function_spec.is_automated,
                "automation_level": function_spec.automation_level,
            },
        )

        if component_element is not None:
            self._add_relationship(
                relationship_type="Composition",
                source=component_element,
                target=function_element,
                description=f"{component_element['name']} is composed of {function_element['name']}",
            )

        service_name = f"{base_name} Application Service ({capability_spec.name})"
        service_element = self._add_element(
            name=service_name,
            element_type="ApplicationService",
            layer="application",
            description=f"Service exposure for {base_name.lower()}.",
            metadata={
                "capability": capability_spec.name,
                "realizes_function": base_name,
            },
        )

        self._add_relationship(
            relationship_type="Realization",
            source=function_element,
            target=service_element,
            description=f"{function_element['name']} realizes {service_element['name']}",
        )

        technology_name = f"{base_name} Technology Service ({capability_spec.name})"
        technology_element = self._add_element(
            name=technology_name,
            element_type="TechnologyService",
            layer="technology",
            description=f"Platform capabilities enabling {base_name.lower()}.",
            metadata={
                "capability": capability_spec.name,
                "supports_function": base_name,
            },
        )

        if component_element is not None:
            self._add_relationship(
                relationship_type="Serving",
                source=technology_element,
                target=component_element,
                description=f"{technology_element['name']} serves {component_element['name']}",
            )

        requirement_name = f"{base_name} Requirement ({capability_spec.name})"
        requirement_element = self._add_element(
            name=requirement_name,
            element_type="Requirement",
            layer="motivation",
            description=f"Requirement derived from {base_name.lower()} capability function.",
            metadata={
                "capability": capability_spec.name,
                "origin_function": base_name,
            },
        )

        self._add_relationship(
            relationship_type="Realization",
            source=requirement_element,
            target=service_element,
            description=f"{requirement_element['name']} is realized by {service_element['name']}",
        )

        self._add_relationship(
            relationship_type="Realization",
            source=requirement_element,
            target=technology_element,
            description=f"{requirement_element['name']} is realized by {technology_element['name']}",
        )

    # ----- primitive builders -----

    def _add_element(
        self,
        name: str,
        element_type: str,
        layer: str,
        description: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ElementDict:
        key = (element_type, name)
        existing = self._element_index.get(key)
        if existing:
            return existing

        element_id = f"elem_{len(self._elements) + 1}"
        element: ElementDict = {
            "id": element_id,
            "name": name,
            "type": element_type,
            "layer": layer,
            "description": description,
        }
        if metadata:
            element["metadata"] = metadata

        self._elements.append(element)
        self._element_index[key] = element
        self._type_counter[element_type] += 1
        return element

    def _add_relationship(
        self,
        relationship_type: str,
        source: ElementDict,
        target: ElementDict,
        description: str,
    ) -> None:
        allowed = self._validator.get_allowed_relationship_types(source["type"], target["type"])
        if relationship_type not in allowed:
            raise ValueError(
                f"Relationship '{relationship_type}' not permitted between {source['type']} and {target['type']}"
            )

        relationship: RelationshipDict = {
            "id": f"rel_{len(self._relationships) + 1}",
            "type": relationship_type,
            "source": source["name"],
            "target": target["name"],
            "source_id": source["id"],
            "target_id": target["id"],
            "description": description,
        }
        self._relationships.append(relationship)
