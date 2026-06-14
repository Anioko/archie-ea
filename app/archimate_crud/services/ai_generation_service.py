"""
AI Generation Service for ArchiMate Elements
Finds information from documents, internet, and generates ArchiMate elements
"""

import logging
from typing import Any, Dict, List, Optional

from app import db
from app.services.archimate.archimate_llm_service import ArchiMateLLMService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class AIGenerationService:
    """Service for AI-powered element generation"""

    def __init__(self):
        self.llm_service = LLMService()
        self.archimate_service = ArchiMateLLMService()

    def generate_element(
        self, layer: str, element_type: str, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate an ArchiMate element using AI

        Args:
            layer: ArchiMate layer (motivation, strategy, business)
            element_type: Element type (e.g., Goal, Driver, BusinessProcess)
            prompt: User prompt describing what to generate
            context: Additional context (documents, existing elements, etc.)

        Returns:
            Dictionary with generated element data
        """
        try:
            # Build context-aware prompt
            system_prompt = self._build_system_prompt(layer, element_type)
            user_prompt = self._build_user_prompt(prompt, context)

            # Call LLM service
            response = self.llm_service.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=2000,
            )

            # Parse response
            element_data = self._parse_llm_response(response, element_type)

            return {"success": True, "element": element_data, "raw_response": response}

        except Exception as e:
            logger.error(f"Error generating {element_type}: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _build_system_prompt(self, layer: str, element_type: str) -> str:
        """Build system prompt for element generation with element-specific strategies"""
        layer_descriptions = {
            "motivation": 'Motivation Layer elements represent the "why" - stakeholders, drivers, goals, requirements',
            "strategy": "Strategy Layer elements represent strategic resources, capabilities, and courses of action",
            "business": "Business Layer elements represent business actors, processes, services, and objects",
        }

        # Element-specific generation strategies
        element_strategies = self._get_element_strategy(element_type, layer)

        return f"""You are an expert enterprise architect specializing in ArchiMate 3.2 notation.

Your task is to generate a {element_type} element for the {layer.capitalize()} Layer.

{layer_descriptions.get(layer, '')}

{element_strategies}

Generate a complete, well-structured {element_type} element with:
- Clear, descriptive name (noun phrase following ArchiMate naming conventions)
- Detailed description explaining purpose, characteristics, and business value
- Relevant attributes specific to {element_type} (see strategy above)
- Proper ArchiMate 3.2 compliance and metamodel alignment

Return your response as JSON with the following structure:
{{
    "name": "Element name",
    "description": "Detailed description",
    "attributes": {{
        "key1": "value1",
        "key2": "value2"
    }}
}}"""

    def _get_element_strategy(self, element_type: str, layer: str) -> str:
        """Get element-specific generation strategy and rules"""
        strategies = {
            # Motivation Layer
            "Stakeholder": """STRATEGY FOR STAKEHOLDER:
- Name should identify a person, group, or organization with interest in the architecture
- Include: stakeholder_type (internal/external/executive/operational/regulatory), role, organization, power_level, interest_level
- Description should explain their influence, concerns, and relationship to the architecture
- Example: "Customer Service Department" (internal, operational) or "Regulatory Compliance Board" (external, regulatory)""",
            "Driver": """STRATEGY FOR DRIVER:
- Name should describe a change or force that creates motivation for change
- Include: driver_type (regulatory/competitive/customer/technology/financial/operational), source (internal/external), urgency
- Description should explain the driver's impact and why it matters
- Drivers typically influence Goals and Requirements
- Example: "GDPR Compliance Requirement" (regulatory, external) or "Customer Demand for Mobile Access" (customer, external)""",
            "Goal": """STRATEGY FOR GOAL:
- Name should state a desired end state or outcome (use action-oriented language)
- Include: goal_type (strategic/operational/tactical), category (growth/efficiency/innovation/compliance/quality), achievement_status, progress_percentage
- Description should explain what success looks like and how it will be measured
- Goals are influenced by Drivers and influence Requirements
- Example: "Increase Customer Satisfaction to 90%" (strategic, quality) or "Reduce Operational Costs by 15%" (operational, efficiency)""",
            "Requirement": """STRATEGY FOR REQUIREMENT:
- Name should state a specific need or constraint that must be satisfied
- Include: requirement_type (functional/non-functional), priority (high/medium/low), status
- Description should be specific, measurable, and testable
- Requirements are influenced by Goals and constrain BusinessProcesses/BusinessServices
- Example: "System must process 1000 transactions per minute" (non-functional, high priority)""",
            "Outcome": """STRATEGY FOR OUTCOME:
- Name should describe a measurable result or effect
- Include: outcome_type (benefit/risk), measurement_criteria, target_value
- Description should explain how the outcome will be measured and its business impact
- Outcomes result from CoursesOfAction or ValueStreams
- Example: "20% Reduction in Customer Churn" (benefit) or "Improved Data Security Posture" (benefit)""",
            "Principle": """STRATEGY FOR PRINCIPLE:
- Name should state a fundamental rule or guideline
- Include: principle_type (architectural/business/technical), category, enforcement_level
- Description should explain the rationale and implications
- Principles guide decision-making and constrain design
- Example: "Cloud-First Strategy" (architectural) or "Data Privacy by Design" (business)""",
            # Strategy Layer
            "Resource": """STRATEGY FOR RESOURCE:
- Name should identify a strategic asset or capability
- Include: resource_type (tangible/intangible), strategic_value, ownership
- Description should explain the resource's strategic importance and how it creates value
- Resources are used by Capabilities
- Example: "Customer Database" (intangible) or "Brand Reputation" (intangible)""",
            "Capability": """STRATEGY FOR CAPABILITY:
- Name should describe an ability to achieve a specific outcome (use verb + noun format)
- Include: capability_level (level0 - level5), maturity, strategic_importance
- Description should explain what the capability enables and its business value
- Capabilities are realized by BusinessProcesses and BusinessServices
- Example: "Customer Onboarding Capability" or "Digital Payment Processing Capability" """,
            "ValueStream": """STRATEGY FOR VALUESTREAM:
- Name should describe a series of steps that create value for stakeholders
- Include: value_stream_type, stages, customer_journey_phase
- Description should explain the value created at each stage
- ValueStreams are composed of ValueStreamStages
- Example: "Customer Acquisition Value Stream" or "Product Delivery Value Stream" """,
            "CourseOfAction": """STRATEGY FOR COURSEOFACTION:
- Name should describe a plan or approach to achieve a goal
- Include: action_type (strategic/operational), timeline, expected_outcome
- Description should explain the approach, steps, and expected results
- CoursesOfAction realize Goals and create Outcomes
- Example: "Digital Transformation Initiative" or "Cloud Migration Program" """,
            # Business Layer
            "BusinessActor": """STRATEGY FOR BUSINESSACTOR:
- Name should identify an organizational entity (person, department, organization)
- Include: actor_type (Department/Team/Business Unit/External Partner/Individual), location, headcount
- Description should explain the actor's role and responsibilities
- BusinessActors perform BusinessRoles and are assigned to BusinessProcesses
- Example: "Sales Department" (Department) or "Customer Support Team" (Team)""",
            "BusinessProcess": """STRATEGY FOR BUSINESSPROCESS:
- Name should describe a sequence of business activities (use verb + noun format)
- Include: process_type (operational/management/supporting), frequency, average_duration_minutes
- Description should explain the process steps, inputs, outputs, and business value
- BusinessProcesses are performed by BusinessActors and realize BusinessServices
- Example: "Process Customer Order" or "Manage Employee Onboarding" """,
            "BusinessService": """STRATEGY FOR BUSINESSSERVICE:
- Name should describe a service provided to customers (use noun phrase)
- Include: service_type, business_criticality, sla_availability_target
- Description should explain what the service does, who uses it, and its value proposition
- BusinessServices are realized by BusinessProcesses
- Example: "Customer Support Service" or "Order Fulfillment Service" """,
            "BusinessObject": """STRATEGY FOR BUSINESSOBJECT:
- Name should identify a conceptual business entity or data object
- Include: object_type, data_classification, retention_policy
- Description should explain what information the object represents and its business purpose
- BusinessObjects are accessed by BusinessProcesses
- Example: "Customer Record" or "Product Catalog" """,
            "Product": """STRATEGY FOR PRODUCT:
- Name should identify a product or service offering
- Include: product_type, product_category, target_market, value_proposition, pricing_model
- Description should explain the product's features, benefits, and market positioning
- Products bundle BusinessServices and Contracts
- Example: "Enterprise Cloud Platform" or "Mobile Banking App" """,
        }

        return strategies.get(
            element_type,
            f"""STRATEGY FOR {element_type}:
- Follow ArchiMate 3.2 naming conventions for {layer} layer elements
- Include relevant attributes based on the element's purpose
- Ensure the element aligns with ArchiMate metamodel relationships
- Description should clearly explain business value and purpose""",
        )

    def _build_user_prompt(self, prompt: str, context: Optional[Dict[str, Any]]) -> str:
        """Build user prompt with context"""
        user_prompt = f"Generate an ArchiMate element based on: {prompt}\n\n"

        if context:
            if context.get("documents"):
                user_prompt += f"Relevant documents: {context['documents']}\n\n"
            if context.get("related_elements"):
                user_prompt += f"Related elements: {context['related_elements']}\n\n"
            if context.get("requirements"):
                user_prompt += f"Requirements: {context['requirements']}\n\n"

        return user_prompt

    def _parse_llm_response(self, response: str, element_type: str) -> Dict[str, Any]:
        """Parse LLM response into element data"""
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data
            except json.JSONDecodeError:
                pass

        # Fallback: parse as text
        return {
            "name": f"Generated {element_type}",
            "description": response[:500] if len(response) > 500 else response,
            "attributes": {},
        }

    def search_documents(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents for relevant information.

        Searches through uploaded documents in the system including:
        - AI Chat document uploads
        - Document analysis records

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing document excerpts and metadata
        """
        results = []
        query_lower = query.lower()

        try:
            # Search AI Chat Document Uploads
            from app.models.ai_chat_document import AIChatDocumentUpload

            # Search by filename and analysis results
            documents = (
                AIChatDocumentUpload.query.filter(
                    db.or_(
                        AIChatDocumentUpload.file_name.ilike(f"%{query}%"),
                        AIChatDocumentUpload.original_filename.ilike(f"%{query}%"),
                        AIChatDocumentUpload.chat_context_summary.ilike(f"%{query}%"),
                        AIChatDocumentUpload.analysis_results.ilike(f"%{query}%"),
                    )
                )
                .filter(AIChatDocumentUpload.status == "completed")
                .order_by(AIChatDocumentUpload.created_at.desc())
                .limit(limit)
                .all()
            )

            for doc in documents:
                # Extract relevant excerpt from analysis results or summary
                excerpt = self._extract_relevant_excerpt(
                    doc.chat_context_summary or doc.analysis_results or "", query_lower
                )

                results.append(
                    {
                        "source": "ai_chat_upload",
                        "document_id": doc.id,
                        "file_name": doc.original_filename or doc.file_name,
                        "file_type": doc.file_type,
                        "excerpt": excerpt,
                        "confidence": doc.confidence,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "relevance": self._calculate_relevance(
                            query_lower, f"{doc.file_name} {doc.chat_context_summary or ''}"
                        ),
                    }
                )

        except ImportError:
            logger.warning("AIChatDocumentUpload model not available")
        except Exception as e:
            logger.error(f"Error searching AI chat documents: {e}")

        try:
            # Search Document Analysis records
            from app.models.document_analysis import DocumentAnalysis

            analyses = (
                DocumentAnalysis.query.filter(
                    db.or_(
                        DocumentAnalysis.file_name.ilike(f"%{query}%"),
                        DocumentAnalysis.analysis_results.ilike(f"%{query}%"),
                        DocumentAnalysis.archimate_elements.ilike(f"%{query}%"),
                    )
                )
                .filter(DocumentAnalysis.status == "completed")
                .order_by(DocumentAnalysis.created_at.desc())
                .limit(limit)
                .all()
            )

            for analysis in analyses:
                # Extract relevant excerpt
                content = analysis.analysis_results or analysis.archimate_elements or ""
                excerpt = self._extract_relevant_excerpt(content, query_lower)

                results.append(
                    {
                        "source": "document_analysis",
                        "document_id": analysis.id,
                        "file_name": analysis.file_name,
                        "entity_type": analysis.entity_type,
                        "entity_id": analysis.entity_id,
                        "excerpt": excerpt,
                        "confidence": analysis.confidence,
                        "elements_count": analysis.elements_count,
                        "created_at": analysis.created_at.isoformat()
                        if analysis.created_at
                        else None,
                        "relevance": self._calculate_relevance(
                            query_lower, f"{analysis.file_name} {content[:500]}"
                        ),
                    }
                )

        except ImportError:
            logger.warning("DocumentAnalysis model not available")
        except Exception as e:
            logger.error(f"Error searching document analyses: {e}")

        # Sort results by relevance score
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        return results[:limit]

    def _extract_relevant_excerpt(self, content: str, query: str, max_length: int = 500) -> str:
        """
        Extract the most relevant excerpt from content based on query.

        Args:
            content: Full content to search
            query: Search query (lowercase)
            max_length: Maximum length of excerpt

        Returns:
            Relevant excerpt from the content
        """
        if not content:
            return ""

        content_lower = content.lower()
        query_pos = content_lower.find(query)

        if query_pos >= 0:
            # Found query, extract surrounding context
            start = max(0, query_pos - 100)
            end = min(len(content), query_pos + len(query) + 400)
            excerpt = content[start:end]

            # Add ellipsis if truncated
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(content):
                excerpt = excerpt + "..."

            return excerpt
        else:
            # Query not found directly, return beginning of content
            return content[:max_length] + ("..." if len(content) > max_length else "")

    def _calculate_relevance(self, query: str, content: str) -> float:
        """
        Calculate relevance score for a document based on query match.

        Args:
            query: Search query (lowercase)
            content: Content to score

        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not content:
            return 0.0

        content_lower = content.lower()
        query_words = query.split()

        # Count exact query matches
        exact_matches = content_lower.count(query)

        # Count individual word matches
        word_matches = sum(1 for word in query_words if word in content_lower)

        # Calculate score based on matches
        if exact_matches > 0:
            score = min(1.0, 0.5 + (exact_matches * 0.1))
        elif word_matches > 0:
            score = (word_matches / len(query_words)) * 0.5
        else:
            score = 0.0

        return round(score, 2)

    def search_internet(self, query: str) -> List[Dict[str, Any]]:
        """
        Search internet for relevant information.

        Note: External internet search is not currently available in this system.
        This method returns a message indicating the limitation and suggests
        using document search or manual research instead.

        Args:
            query: Search query string

        Returns:
            List with a single entry explaining the service limitation
        """
        logger.info(f"Internet search requested for query: {query}")

        return [
            {
                "source": "system_message",
                "status": "unavailable",
                "message": (
                    "External internet search is not currently available. "
                    "Please use the document search feature to find information "
                    "from uploaded documents, or conduct manual research using "
                    "external search engines and import the findings as documents."
                ),
                "query": query,
                "suggestions": [
                    "Upload relevant documents for analysis",
                    "Use document search to find existing information",
                    "Manually research and add findings to the system",
                ],
            }
        ]
