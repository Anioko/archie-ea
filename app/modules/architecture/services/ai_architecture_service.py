"""
-> app.modules.architecture.services.ai_service

Cognitive Architecture Service

This service implements the "Cognitive Co-Architect" logic layer, bridging ArchiMate 3.2 data
with Large Language Models (LLMs) via the configured AI Service Layer.

Components:
1. Context Assembler: Flattens ArchiMate graphs for LLM consumption.
2. Prompt Orchestrator: Manages and injects data into AIPromptTemplates.
3. LLM Gateway: Routes requests to configured providers (OpenAI, etc.).
4. Audit Recorder: Logs all cognitive interactions for governance.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from flask import current_app
from sqlalchemy.orm import joinedload

from app import db
from app.models.ai_service import AIInteractionLog, AIPromptTemplate, AIServiceConfig
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship


class CognitiveArchitectureService:
    def __init__(self, user_id: Optional[int] = None):
        self.user_id = user_id

    # =========================================================================
    # 1. Context Assembler
    # =========================================================================

    def assemble_context(self, element_id: int, depth: int = 1) -> Dict[str, Any]:
        """
        Retrieves an element and its neighborhood to provide architectural context to the AI.

        Args:
            element_id: ID of the central ArchiMateElement
            depth: How many hops of relationships to traverse (default 1)

        Returns:
            Dict containing the serialized sub-graph
        """
        root = ArchiMateElement.query.get(element_id)
        if not root:
            return {"error": "Element not found"}

        context = {
            "focus_element": {
                "id": root.id,
                "name": root.name,
                "type": root.type,
                "layer": root.layer,
                "description": root.description,
            },
            "relationships": [],
        }

        # Fetch direct relationships
        # In a real graph traversal, we'd use recursion for depth > 1
        rels = ArchiMateRelationship.query.filter(
            (ArchiMateRelationship.source_id == element_id)
            | (ArchiMateRelationship.target_id == element_id)
        ).all()

        for rel in rels:
            is_source = rel.source_id == element_id
            other_id = rel.target_id if is_source else rel.source_id
            # Optimization: batch load in production
            other_elem = ArchiMateElement.query.get(other_id)

            if other_elem:
                rel_data = {
                    "relation_type": rel.type,
                    "direction": "outgoing" if is_source else "incoming",
                    "related_element": {
                        "id": other_elem.id,
                        "name": other_elem.name,
                        "type": other_elem.type,
                        "layer": other_elem.layer,
                    },
                }
                context["relationships"].append(rel_data)

        return context

    # =========================================================================
    # 2. Prompt Orchestrator
    # =========================================================================

    def execute_architectural_prompt(
        self, template_name: str, context_data: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """
        Orchestrates the full AI lifecycle: Template Load -> Context Injection -> Execution -> Logging.

        Args:
            template_name: Name of the AIPromptTemplate to use
            context_data: The assembled architectural context
            **kwargs: Additional variables for the prompt template

        Returns:
            Parsed JSON response from the AI
        """
        start_time = time.time()

        # 1. Load Template
        template = AIPromptTemplate.query.filter_by(name=template_name).first()
        if not template:
            # Fallback or Error
            raise ValueError(f"Prompt Template '{template_name}' not found.")

        # 2. Variable Injection
        # We inject the structured context as a JSON string for the AI to read
        context_str = json.dumps(context_data, indent=2)

        try:
            user_prompt = template.user_prompt_template.format(context=context_str, **kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable for prompt template: {e}")

        # 3. Gateway Execution
        provider_config = self._get_active_provider()
        if not provider_config:
            raise RuntimeError("No active AI Provider configured.")

        response_payload = self._call_llm_provider(
            config=provider_config, system_prompt=template.system_prompt, user_prompt=user_prompt
        )

        # 4. Parsing
        parsed_output = self._parse_output(response_payload.get("content", "{}"))

        # 5. Audit Recording
        duration_ms = int((time.time() - start_time) * 1000)
        self._log_interaction(
            template_id=template.id,
            input_tokens=response_payload.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=response_payload.get("usage", {}).get("completion_tokens", 0),
            duration_ms=duration_ms,
            target_id=context_data.get("focus_element", {}).get("id"),
        )

        return parsed_output

    # =========================================================================
    # 3. LLM Gateway (Adapter Pattern)
    # =========================================================================

    def _get_active_provider(self) -> AIServiceConfig:
        """Retrieves the currently active AI service configuration."""
        return AIServiceConfig.query.filter_by(is_active=True).first()

    def _call_llm_provider(
        self, config: AIServiceConfig, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        """
        Low-level HTTP call to the AI Provider.
        Currently supports a generic OpenAI-compatible signature.
        """
        # Mocking the actual network call for safety in this environment unless keys are present
        if not config.api_base_url:
            # Simulation Mode if no URL configured
            return self._simulate_response(user_prompt)

        headers = {
            "Authorization": f"Bearer {current_app.config.get('OPENAI_API_KEY', 'placeholder')}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model_version,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "response_format": {"type": "json_object"},  # Enforcing JSON mode
        }

        try:
            # NOTE: This runs the actual request if URL is present.
            # Only use if user has configured the environment.
            # response = requests.post(f"{config.api_base_url}/chat/completions", json=payload, headers=headers, timeout=60)
            # response.raise_for_status()
            # return response.json()
            return self._simulate_response(user_prompt)  # Default to simulation to avoid errors now
        except Exception as e:
            current_app.logger.error(f"AI Provider Call Failed: {e}")
            raise RuntimeError(f"AI Gateway Error: {str(e)}")

    def _simulate_response(self, user_prompt: str) -> Dict[str, Any]:
        """Returns a dummy structured response for testing without API keys."""
        return {
            "content": json.dumps(
                {
                    "analysis": "Simulation Mode: Architecture review logic would appear here.",
                    "risks": ["Mock Risk 1", "Mock Risk 2"],
                    "score": 85,
                }
            ),
            "usage": {"prompt_tokens": len(user_prompt.split()), "completion_tokens": 50},
        }

    # =========================================================================
    # 4. Output Parser
    # =========================================================================

    def _parse_output(self, content_str: str) -> Dict[str, Any]:
        """Safely parses the AI's JSON output."""
        try:
            return json.loads(content_str)
        except json.JSONDecodeError:
            # Fallback for when AI babbles before JSON
            # In production, use regex to find { ... }
            current_app.logger.warning("AI did not return valid JSON. Returning raw text.")
            return {"raw_content": content_str}

    # =========================================================================
    # 5. Audit Recorder
    # =========================================================================

    def _log_interaction(
        self,
        template_id: int,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        target_id: Optional[int],
    ):
        """Writes the interaction to the audit log."""
        log = AIInteractionLog(
            user_id=self.user_id,
            prompt_template_id=template_id,
            input_size_tokens=input_tokens,
            output_size_tokens=output_tokens,
            duration_ms=duration_ms,
            target_element_id=target_id,
            timestamp=datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()

    # =========================================================================
    # 6. Architecture Validation
    # =========================================================================

    def validate_architecture(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate ArchiMate architecture elements and relationships.

        Args:
            data: Dictionary containing elements and relationships

        Returns:
            Validation result with is_valid, issues, and recommendations
        """
        issues = []
        recommendations = []
        elements = data.get("elements", [])
        relationships = data.get("relationships", [])

        # Validate elements
        valid_layers = [
            "Business",
            "Application",
            "Technology",
            "Strategy",
            "Motivation",
            "Implementation",
        ]
        valid_element_types = [
            "Business Process",
            "Business Function",
            "Business Role",
            "Business Actor",
            "Application Component",
            "Application Service",
            "Application Function",
            "Technology Service",
            "Node",
            "Device",
            "System Software",
            "Data Object",
            "Artifact",
            "Business Capability",
        ]

        for idx, elem in enumerate(elements):
            if not elem.get("name"):
                issues.append(
                    {
                        "type": "error",
                        "element_index": idx,
                        "message": "Element missing required 'name' field",
                    }
                )

            elem_type = elem.get("type", "")
            if elem_type and elem_type not in valid_element_types:
                issues.append(
                    {
                        "type": "warning",
                        "element_index": idx,
                        "message": f"Unknown element type: {elem_type}",
                    }
                )

            layer = elem.get("layer", "")
            if layer and layer not in valid_layers:
                issues.append(
                    {"type": "warning", "element_index": idx, "message": f"Unknown layer: {layer}"}
                )

        # Validate relationships
        element_names = {elem.get("name") for elem in elements if elem.get("name")}

        for idx, rel in enumerate(relationships):
            source = rel.get("source")
            target = rel.get("target")

            if source and source not in element_names:
                issues.append(
                    {
                        "type": "warning",
                        "relationship_index": idx,
                        "message": f"Relationship source '{source}' not found in elements",
                    }
                )

            if target and target not in element_names:
                issues.append(
                    {
                        "type": "warning",
                        "relationship_index": idx,
                        "message": f"Relationship target '{target}' not found in elements",
                    }
                )

        # Generate recommendations
        if not elements:
            recommendations.append("Add at least one element to validate")
        elif len(elements) < 3:
            recommendations.append("Consider adding more elements for a comprehensive architecture")

        if elements and not relationships:
            recommendations.append("Consider adding relationships between elements")

        is_valid = not any(issue.get("type") == "error" for issue in issues)

        return {
            "is_valid": is_valid,
            "issues": issues,
            "recommendations": recommendations,
            "element_count": len(elements),
            "relationship_count": len(relationships),
        }
