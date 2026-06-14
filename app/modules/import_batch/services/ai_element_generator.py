"""
AI Element Generator Adapter

Bridges batch import with AIImportService for real ArchiMate element generation.
Replaces mock element generation in batch_processor_service.py.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetrics:
    """Metrics from AI element generation."""

    elements_generated: int
    tokens_used: int
    llm_calls: int
    cost_usd: Decimal
    processing_time_seconds: float
    model_used: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "elements_generated": self.elements_generated,
            "tokens_used": self.tokens_used,
            "llm_calls": self.llm_calls,
            "cost_usd": float(self.cost_usd),
            "processing_time_seconds": self.processing_time_seconds,
            "model_used": self.model_used,
        }


class AIElementGenerator:
    """
    Adapter to use AIImportService for batch processing.

    Provides a bridge between the batch import workflow and the
    existing AI-powered ArchiMate generation in AIImportService.
    """

    # Cost estimation per element type
    COST_PER_1K_TOKENS = Decimal("0.01")  # Approximate cost

    def __init__(self):
        """Initialize the generator."""
        self._ai_service = None
        self._llm_service = None

    @property
    def ai_service(self):
        """Lazy load AIImportService."""
        if self._ai_service is None:
            try:
                from app.modules.import_batch.v2.services.ai_import_service_v2 import AIImportService

                self._ai_service = AIImportService()
                logger.info("AIImportService loaded successfully")
            except ImportError as e:
                logger.warning(f"Could not import AIImportService: {e}")
                self._ai_service = None
        return self._ai_service

    def generate_elements_for_batch_app(
        self,
        app_context: Dict[str, Any],
        mode: str = "standard",
        use_real_ai: bool = True,
    ) -> Tuple[List[Dict[str, Any]], GenerationMetrics]:
        """
        Generate ArchiMate elements for a batch import application.

        Args:
            app_context: Application data from batch import source row
                Expected keys: name, description, type, vendor_name, etc.
            mode: Generation mode (quick/standard/comprehensive)
            use_real_ai: If True, use real AI service; if False, use fallback mock

        Returns:
            Tuple of (elements_list, generation_metrics)
        """
        start_time = time.time()
        app_name = app_context.get("name", app_context.get("application_name", "Application"))

        logger.info(f"Generating ArchiMate elements for '{app_name}' (mode: {mode})")

        elements = []
        metrics = GenerationMetrics(
            elements_generated=0,
            tokens_used=0,
            llm_calls=0,
            cost_usd=Decimal("0"),
            processing_time_seconds=0,
            model_used="mock",
        )

        if use_real_ai and self.ai_service is not None:
            try:
                elements, metrics = self._generate_with_ai_service(app_context, mode)
            except Exception as e:
                logger.error(f"AI generation failed for '{app_name}': {e}")
                raise RuntimeError(
                    f"AI element generation failed for '{app_name}': {e}"
                ) from e
        elif use_real_ai and self.ai_service is None:
            raise RuntimeError(
                f"AI service not available — cannot generate elements for '{app_name}' with use_real_ai=True"
            )
        else:
            # Explicit preview/mock mode — clearly labeled
            elements = self._generate_mock_elements(app_context, mode)
            metrics.model_used = "mock_preview"
            metrics.tokens_used = self._estimate_tokens(elements)
            metrics.llm_calls = 0
            metrics.cost_usd = Decimal("0")

        # Update metrics
        metrics.elements_generated = len(elements)
        metrics.processing_time_seconds = time.time() - start_time

        logger.info(
            f"Generated {len(elements)} elements for '{app_name}' "
            f"in {metrics.processing_time_seconds:.2f}s"
        )

        return elements, metrics

    def _generate_with_ai_service(
        self,
        app_context: Dict[str, Any],
        mode: str,
    ) -> Tuple[List[Dict[str, Any]], GenerationMetrics]:
        """
        Generate elements using the real AIImportService.

        Args:
            app_context: Application data dictionary
            mode: Generation mode

        Returns:
            Tuple of (elements, metrics)
        """
        # Build context string from app data
        context = self._build_context_string(app_context)

        # Use the file-based generation method from AIImportService
        # This handles creating a mock ApplicationComponent internally
        raw_elements = self.ai_service._generate_archimate_with_ai_from_file(app_context, context)

        # Convert to batch import format
        elements = self._convert_to_batch_format(raw_elements, app_context)

        # Estimate metrics from generation
        # In real usage, AIImportService would track actual LLM calls/tokens
        metrics = GenerationMetrics(
            elements_generated=len(elements),
            tokens_used=self._estimate_tokens(elements),
            llm_calls=len(set(e.get("layer", "unknown") for e in elements)),
            cost_usd=self._estimate_cost(elements),
            processing_time_seconds=0,  # Will be set by caller
            model_used="gpt-4",
        )

        return elements, metrics

    def _build_context_string(self, app_context: Dict[str, Any]) -> str:
        """
        Build a context string for AI generation from app data.

        Args:
            app_context: Application data dictionary

        Returns:
            Formatted context string for LLM
        """
        parts = []

        name = app_context.get("name", app_context.get("application_name", ""))
        if name:
            parts.append(f"Application Name: {name}")

        description = app_context.get("description", app_context.get("application_description", ""))
        if description:
            parts.append(f"Description: {description}")

        app_type = app_context.get("type", app_context.get("application_type", ""))
        if app_type:
            parts.append(f"Type: {app_type}")

        vendor = app_context.get("vendor", app_context.get("vendor_name", ""))
        if vendor:
            parts.append(f"Vendor: {vendor}")

        # Add any additional context fields
        for key in ["technology_stack", "business_functions", "capabilities", "domain"]:
            value = app_context.get(key)
            if value:
                parts.append(f"{key.replace('_', ' ').title()}: {value}")

        return "\n".join(parts) if parts else "Application import"

    def _convert_to_batch_format(
        self,
        raw_elements: List[Dict[str, Any]],
        app_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert AIImportService elements to batch import format.

        Args:
            raw_elements: Elements from AIImportService
            app_context: Original app context

        Returns:
            Elements in batch import format
        """
        converted = []
        app_name = app_context.get("name", app_context.get("application_name", "Application"))

        for elem in raw_elements:
            converted_elem = {
                "layer": elem.get("layer", "application"),
                "type": elem.get("type", elem.get("element_type", "element")),
                "name": elem.get("name", f"{app_name} Element"),
                "description": elem.get("description", ""),
                "confidence": elem.get("confidence", elem.get("confidence_score", 0.8)),
                "model": elem.get("model", elem.get("generated_by_model", "gpt-4")),
                "properties": elem.get("properties", {}),
            }

            # Add subtype if present
            if elem.get("subtype") or elem.get("element_subtype"):
                converted_elem["subtype"] = elem.get("subtype") or elem.get("element_subtype")

            converted.append(converted_elem)

        return converted

    def _generate_mock_elements(
        self,
        app_context: Dict[str, Any],
        mode: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate mock elements (fallback when AI is not available).

        Maintains compatibility with original batch_processor_service behavior.
        """
        elements = []
        app_name = app_context.get("name", app_context.get("application_name", "Application"))

        # Define layers and element counts based on mode
        if mode == "quick":
            layers = ["application"]
            elements_per_layer = 3
        elif mode == "comprehensive":
            layers = [
                "motivation",
                "strategy",
                "business",
                "application",
                "technology",
                "implementation",
            ]
            elements_per_layer = 4
        else:  # standard
            layers = ["business", "application", "technology"]
            elements_per_layer = 4

        # Element types by layer
        layer_element_types = {
            "motivation": ["stakeholder", "driver", "goal", "outcome"],
            "strategy": ["capability", "resource", "course_of_action"],
            "business": [
                "business_process",
                "business_service",
                "business_object",
                "business_actor",
            ],
            "application": [
                "application_component",
                "application_service",
                "application_interface",
                "data_object",
            ],
            "technology": ["node", "system_software", "technology_service", "artifact"],
            "implementation": ["work_package", "deliverable", "plateau", "gap"],
        }

        for layer in layers:
            element_types = layer_element_types.get(layer, ["element"])[:elements_per_layer]

            for elem_type in element_types:
                element = {
                    "layer": layer,
                    "type": elem_type,
                    "name": f"{app_name} {elem_type.replace('_', ' ').title()}",
                    "description": f"Auto-generated {elem_type.replace('_', ' ')} for {app_name}",
                    "confidence": 0.75 + (0.15 if layer == "application" else 0.05),
                    "model": "mock",
                    "properties": {},
                }
                elements.append(element)

        return elements

    def _estimate_tokens(self, elements: List[Dict[str, Any]]) -> int:
        """Estimate tokens used based on element count and complexity."""
        # Rough estimate: ~200 tokens per element for generation
        return len(elements) * 200

    def _estimate_cost(self, elements: List[Dict[str, Any]]) -> Decimal:
        """Estimate cost based on estimated tokens."""
        tokens = self._estimate_tokens(elements)
        # GPT-4 pricing: ~$0.03/1K input + $0.06/1K output
        # Simplified estimate
        return Decimal(str(tokens / 1000 * 0.05))
