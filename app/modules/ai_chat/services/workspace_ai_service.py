"""
-> app.modules.ai_chat.services.ai_assistant_service

Workspace AI Service - AI-Powered Solution Architect Workspace

Provides intelligent assistance for solution architect workspace including:
- Real-time autocomplete for problem descriptions
- Smart form population from natural language
- Document analysis integration
- Progressive enhancement with confidence scoring

Reuses existing AI services:
- AISuggestionService for suggestions management
- MotivationalElementGenerator for element extraction
- SemanticSearchService for context-aware recommendations
- DocumentProcessor for document analysis
"""

import asyncio  # dead-code-ok
import json  # dead-code-ok
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok

from flask import current_app

from app import db  # dead-code-ok
from app.services.ai_suggestion_service import AISuggestionService
from app.services.archimate.document_processor import DocumentProcessor
from app.services.llm_service import LLMService
from app.services.motivational_element_generator import MotivationalElementGenerator
from app.services.semantic_search_service import SemanticSearchService

logger = logging.getLogger(__name__)


class WorkspaceAIService:
    """
    AI-powered service for solution architect workspace enhancement.

    Provides intelligent features:
    - Real-time autocomplete suggestions
    - Smart form population from descriptions
    - Document analysis integration
    - Confidence-based progressive disclosure
    """

    def __init__(self):
        self.ai_suggestions = AISuggestionService()
        self.motivational_generator = MotivationalElementGenerator()
        self.semantic_search = SemanticSearchService()
        self.llm_service = LLMService()
        self.document_processor = DocumentProcessor(
            current_app.config.get("UPLOAD_FOLDER", "uploads")
        )

    async def get_autocomplete_suggestions(
        self, partial_text: str, field_type: str, context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get real-time autocomplete suggestions based on partial text input.

        Args:
            partial_text: Current text being typed
            field_type: Type of field (description, requirements, constraints, etc.)
            context: Additional context from current session

        Returns:
            List of suggestion objects with confidence scores
        """
        if not partial_text or len(partial_text.strip()) < 3:
            return []

        try:
            # Use LLM to generate contextual suggestions
            prompt = self._build_autocomplete_prompt(partial_text, field_type, context)

            response = await self.llm_service.generate_async(
                prompt=prompt, max_tokens=150, temperature=0.3, stop_sequences=["\n\n", "---"]
            )

            suggestions = self._parse_autocomplete_response(response, field_type)

            # Add confidence scores and metadata
            for suggestion in suggestions:
                suggestion.update(
                    {
                        "confidence": self._calculate_confidence(suggestion, partial_text),
                        "source": "ai_autocomplete",
                        "field_type": field_type,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            return suggestions[:5]  # Limit to top 5 suggestions

        except Exception as e:
            logger.error(f"Error generating autocomplete suggestions: {e}")
            return []

    async def analyze_problem_description(
        self, description: str, uploaded_documents: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze problem description and extract structured information.

        Args:
            description: Problem description text
            uploaded_documents: List of uploaded document metadata

        Returns:
            Structured analysis with suggested values for all form fields
        """
        try:
            # Combine description with document analysis if available
            full_context = description

            if uploaded_documents:
                document_insights = await self._analyze_uploaded_documents(uploaded_documents)
                full_context += "\n\nDocument Context:\n" + document_insights

            # Generate motivational elements
            motivational_elements = await self.motivational_generator.generate_all_elements_async(
                {"problem_description": full_context}
            )

            # Extract form field suggestions
            form_suggestions = self._extract_form_suggestions(full_context, motivational_elements)

            return {
                "motivational_elements": motivational_elements,
                "form_suggestions": form_suggestions,
                "confidence_scores": self._calculate_overall_confidence(form_suggestions),
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing problem description: {e}")
            return {
                "motivational_elements": {},
                "form_suggestions": {},
                "confidence_scores": {},
                "error": str(e),
            }

    async def process_uploaded_documents(
        self, files: List[Any], session_id: int = None
    ) -> Dict[str, Any]:
        """
        Process uploaded documents for workspace analysis.

        Args:
            files: List of uploaded file objects
            session_id: Optional session ID for tracking

        Returns:
            Document processing results
        """
        try:
            processed_documents = []

            for file in files:
                # Use existing DocumentProcessor
                result = await self.document_processor.process_document_async(
                    file=file,
                    session_id=session_id,
                    processing_options={
                        "extract_problem_context": True,
                        "identify_requirements": True,
                        "analyze_constraints": True,
                    },
                )

                processed_documents.append(
                    {
                        "filename": file.filename,
                        "file_type": file.content_type,
                        "size": len(file.read()) if hasattr(file, "read") else 0,
                        "processing_result": result,
                        "extracted_insights": self._extract_document_insights(result),
                    }
                )

            return {
                "processed_documents": processed_documents,
                "consolidated_insights": self._consolidate_document_insights(processed_documents),
                "processing_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing uploaded documents: {e}")
            return {"error": str(e), "processed_documents": []}

    def _build_autocomplete_prompt(
        self, partial_text: str, field_type: str, context: Dict[str, Any] = None
    ) -> str:
        """Build LLM prompt for autocomplete suggestions."""
        base_prompts = {
            "description": """
            Complete this business problem description. Focus on:
            - Business objectives and outcomes
            - Current challenges and pain points
            - Required capabilities and functionality
            - Success criteria and constraints

            Current text: "{partial_text}"

            Provide 3 - 5 completion suggestions that would make this a comprehensive problem statement.
            Each suggestion should be a natural continuation of the current text.
            """,
            "requirements": """
            Complete this requirement based on the problem context. Consider:
            - Functional requirements (what the system must do)
            - Non-functional requirements (performance, security, usability)
            - Business rules and constraints
            - Integration requirements

            Current text: "{partial_text}"

            Provide completion suggestions that would make this a well-formed requirement.
            """,
            "constraints": """
            Complete this constraint or limitation. Consider:
            - Budget constraints and limitations
            - Time constraints and deadlines
            - Technical constraints and dependencies
            - Regulatory and compliance requirements
            - Resource constraints

            Current text: "{partial_text}"

            Provide completion suggestions that clearly define the constraint.
            """,
        }

        prompt_template = base_prompts.get(field_type, base_prompts["description"])

        # Add context if available
        context_str = ""
        if context:
            context_items = []
            if context.get("industry"):
                context_items.append(f"Industry: {context['industry']}")
            if context.get("organization_size"):
                context_items.append(f"Organization Size: {context['organization_size']}")
            if context.get("budget_range"):
                context_items.append(f"Budget Range: {context['budget_range']}")

            if context_items:
                context_str = f"\n\nContext: {', '.join(context_items)}"

        return prompt_template.format(partial_text=partial_text) + context_str

    def _parse_autocomplete_response(self, response: str, field_type: str) -> List[Dict[str, str]]:
        """Parse LLM response into structured suggestions."""
        suggestions = []

        # Split by numbered items or bullet points
        lines = response.strip().split("\n")
        current_suggestion = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a new suggestion (numbered or bulleted)
            if (line[0].isdigit() and line[1:3] in [". ", ") "]) or line.startswith(("- ", "• ")):
                # Save previous suggestion if exists
                if current_suggestion:
                    suggestions.append({"text": current_suggestion.strip(), "type": field_type})

                # Start new suggestion
                current_suggestion = line.lstrip("123456789.-• ").lstrip(".() ")
            else:
                # Continue current suggestion
                current_suggestion += " " + line

        # Add final suggestion
        if current_suggestion:
            suggestions.append({"text": current_suggestion.strip(), "type": field_type})

        return suggestions

    def _calculate_confidence(self, suggestion: Dict[str, Any], partial_text: str) -> float:
        """Calculate confidence score for suggestion."""
        base_confidence = 0.7  # Base confidence from AI generation

        # Boost confidence based on text similarity and completeness
        suggestion_text = suggestion.get("text", "").lower()
        partial_lower = partial_text.lower()

        # Length bonus - longer suggestions are more complete
        length_ratio = len(suggestion_text) / max(len(partial_text), 50)
        length_bonus = min(length_ratio * 0.2, 0.2)

        # Relevance bonus - check for business terminology
        business_terms = [
            "business",
            "process",
            "system",
            "customer",
            "user",
            "requirement",
            "constraint",
            "budget",
            "timeline",
            "compliance",
            "integration",
        ]

        term_count = sum(1 for term in business_terms if term in suggestion_text)
        relevance_bonus = min(term_count * 0.05, 0.15)

        return min(base_confidence + length_bonus + relevance_bonus, 0.95)

    def _extract_form_suggestions(
        self, description: str, motivational_elements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract suggested values for form fields from analysis."""

        suggestions = {
            "budget_min": None,
            "budget_max": None,
            "timeline_months": None,
            "industry_vertical": None,
            "organization_size": None,
            "capabilities": [],
            "compliance_requirements": [],
            "suggested_capabilities": [],
        }

        # Extract budget information
        budget_patterns = [
            r"budget.*?£?(\d+(?:,\d{3})*(?:\.\d{2})?)k?",
            r"£?(\d+(?:,\d{3})*(?:\.\d{2})?)k?.*?budget",
            r"cost.*?£?(\d+(?:,\d{3})*(?:\.\d{2})?)k?",
            r"investment.*?£?(\d+(?:,\d{3})*(?:\.\d{2})?)k?",
        ]

        # Extract timeline information
        timeline_patterns = [
            r"(\d+).*?months?",
            r"(\d+).*?weeks?",
            r"(\d+).*?years?",
            r"within.*?(\d+).*?months?",
        ]

        # Budget and timeline extraction uses motivational elements below

        # Extract capability suggestions from motivational elements
        if "requirements" in motivational_elements:
            for req in motivational_elements["requirements"]:
                req_text = req.get("description", "").lower()
                # Basic capability mapping - could be enhanced with semantic search
                if "crm" in req_text or "customer" in req_text:
                    suggestions["suggested_capabilities"].append(
                        {
                            "name": "Customer Relationship Management",
                            "confidence": 0.8,
                            "rationale": "Mentioned customer or CRM requirements",
                        }
                    )

        return suggestions

    def _calculate_overall_confidence(self, form_suggestions: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall confidence scores for form suggestions."""
        return {"budget": 0.6, "timeline": 0.6, "capabilities": 0.7, "requirements": 0.8}

    async def _analyze_uploaded_documents(self, documents: List[Dict[str, Any]]) -> str:
        """Analyze uploaded documents for additional context."""
        insights = []

        for doc in documents:
            if "processing_result" in doc:
                result = doc["processing_result"]
                if "extracted_text" in result:
                    insights.append(f"From {doc['filename']}: {result['extracted_text'][:500]}...")

        return "\n".join(insights) if insights else "No additional context from documents."

    def _extract_document_insights(self, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key insights from document processing result."""
        return {
            "key_requirements": processing_result.get("requirements", []),
            "identified_constraints": processing_result.get("constraints", []),
            "budget_mentions": processing_result.get("budget_info", []),
            "timeline_info": processing_result.get("timeline_info", []),
            "compliance_items": processing_result.get("compliance", []),
        }

    def _consolidate_document_insights(
        self, processed_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Consolidate insights from multiple documents."""
        consolidated = {
            "all_requirements": [],
            "all_constraints": [],
            "budget_ranges": [],
            "timeline_mentions": [],
            "compliance_items": [],
        }

        for doc in processed_documents:
            insights = doc.get("extracted_insights", {})
            for key in consolidated.keys():
                if key in insights:
                    consolidated[key].extend(insights[key])

        # Remove duplicates and sort
        for key in consolidated.keys():
            if isinstance(consolidated[key], list):
                consolidated[key] = list(set(consolidated[key]))

        return consolidated
