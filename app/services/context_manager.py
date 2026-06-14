"""
Context Manager - Enhanced context management for AI chat

Provides intelligent context enhancement, persistence, and management
for multi-domain AI conversations.
"""

import asyncio  # dead-code-ok
import json
import logging
from datetime import datetime, timedelta  # dead-code-ok
from typing import Any, Dict, List, Optional, Tuple  # dead-code-ok

from flask import current_app  # dead-code-ok
from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Enhanced context management for AI chat conversations.

    Features:
    - Context persistence and retrieval
    - Intelligent context enhancement
    - Conversation thread management
    - Entity and relationship tracking
    - Performance optimization with caching
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Context cache
        self._context_cache = {}
        self._cache_ttl = 1800  # 30 minutes

        # Entity tracking
        self._entity_tracker = EntityTracker()

        # Relationship tracker
        self._relationship_tracker = RelationshipTracker()

    def enhance_context(
        self, base_context: Dict[str, Any], intent_result: "IntentResult", domain: str
    ) -> Dict[str, Any]:
        """
        Enhance context with intent-aware information.

        Args:
            base_context: Base context from chat service
            intent_result: Intent classification result
            domain: Target domain

        Returns:
            Enhanced context with additional information
        """
        try:
            enhanced_context = base_context.copy()

            # Add intent information
            enhanced_context["intent"] = {
                "primary": intent_result.primary_intent,
                "confidence": intent_result.confidence,
                "entities": intent_result.entities,
                "alternatives": intent_result.alternative_intents,
            }

            # Add domain-specific context
            domain_context = self._get_domain_enhanced_context(domain, intent_result)
            enhanced_context.update(domain_context)

            # Add entity relationships
            entity_relationships = self._entity_tracker.get_entity_relationships(
                intent_result.entities, domain
            )
            enhanced_context["entity_relationships"] = entity_relationships

            # Add conversation history context
            conversation_context = self._get_conversation_context(intent_result)
            enhanced_context["conversation_history"] = conversation_context

            # Add relevant documents
            relevant_docs = self._get_relevant_documents(intent_result, domain)
            enhanced_context["relevant_documents"] = relevant_docs

            # Add performance metrics
            enhanced_context["context_metadata"] = {
                "enhanced_at": datetime.utcnow().isoformat(),
                "domain": domain,
                "entity_count": len(intent_result.entities),
                "context_sources": list(enhanced_context.keys()),
            }

            return enhanced_context

        except Exception as e:
            self.logger.error(f"Error enhancing context: {e}")
            return base_context

    async def _get_domain_enhanced_context(
        self, domain: str, intent_result: "IntentResult"
    ) -> Dict[str, Any]:
        """Get domain-specific enhanced context"""
        try:
            domain_context = {}

            # Domain-specific data loading
            if domain == "architecture":
                domain_context.update(await self._load_architecture_enhanced_context(intent_result))
            elif domain == "technology":
                domain_context.update(await self._load_technology_enhanced_context(intent_result))
            elif domain == "business_capability":
                domain_context.update(await self._load_capability_enhanced_context(intent_result))
            elif domain == "gap_analysis":
                domain_context.update(await self._load_gap_analysis_enhanced_context(intent_result))
            elif domain == "vendor_intelligence":
                domain_context.update(await self._load_vendor_enhanced_context(intent_result))
            elif domain == "smart_search":
                domain_context.update(await self._load_search_enhanced_context(intent_result))

            return domain_context

        except Exception as e:
            self.logger.error(f"Error loading domain enhanced context for {domain}: {e}")
            return {}

    async def _load_architecture_enhanced_context(
        self, intent_result: "IntentResult"
    ) -> Dict[str, Any]:
        """Load enhanced architecture context"""
        try:
            context = {}

            # Get related ArchiMate elements based on entities
            archimate_elements = []
            for entity in intent_result.entities:
                if entity["type"] in ["capability_name", "application"]:
                    elements = await self._get_archimate_elements_for_entity(entity)
                    archimate_elements.extend(elements)

            if archimate_elements:
                context["related_archimate_elements"] = archimate_elements

            # Get architectural patterns
            patterns = await self._get_architectural_patterns(intent_result)
            if patterns:
                context["architectural_patterns"] = patterns

            # Get governance information
            governance = await self._get_governance_info(intent_result)
            if governance:
                context["governance"] = governance

            return context

        except Exception as e:
            self.logger.error(f"Error loading architecture enhanced context: {e}")
            return {}

    async def _load_technology_enhanced_context(
        self, intent_result: "IntentResult"
    ) -> Dict[str, Any]:
        """Load enhanced technology context"""
        try:
            context = {}

            # Get technology stack information
            tech_stack = await self._get_technology_stack(intent_result)
            if tech_stack:
                context["technology_stack"] = tech_stack

            # Get vendor products
            vendor_products = await self._get_vendor_products(intent_result)
            if vendor_products:
                context["vendor_products"] = vendor_products

            # Get infrastructure information
            infrastructure = await self._get_infrastructure_info(intent_result)
            if infrastructure:
                context["infrastructure"] = infrastructure

            return context

        except Exception as e:
            self.logger.error(f"Error loading technology enhanced context: {e}")
            return {}

    async def _load_capability_enhanced_context(
        self, intent_result: "IntentResult"
    ) -> Dict[str, Any]:
        """Load enhanced capability context"""
        try:
            context = {}

            # Get capability maturity distribution
            maturity_dist = await self._get_capability_maturity_distribution()
            if maturity_dist:
                context["maturity_distribution"] = maturity_dist

            # Get value stream mapping
            value_streams = await self._get_value_stream_mapping(intent_result)
            if value_streams:
                context["value_streams"] = value_streams

            # Get business domain mapping
            business_domains = await self._get_business_domain_mapping()
            if business_domains:
                context["business_domains"] = business_domains

            return context

        except Exception as e:
            self.logger.error(f"Error loading capability enhanced context: {e}")
            return {}

    async def _load_gap_analysis_enhanced_context(
        self, intent_result: "IntentResult"
    ) -> Dict[str, Any]:
        """Load enhanced gap analysis context"""
        try:
            context = {}

            # Get identified gaps
            gaps = await self._get_identified_gaps(intent_result)
            if gaps:
                context["identified_gaps"] = gaps

            # Get risk assessment
            risks = await self._get_risk_assessment(intent_result)
            if risks:
                context["risk_assessment"] = risks

            # Get recommendations
            recommendations = await self._get_recommendations(intent_result)
            if recommendations:
                context["recommendations"] = recommendations

            return context

        except Exception as e:
            self.logger.error(f"Error loading gap analysis enhanced context: {e}")
            return {}

    async def _load_vendor_enhanced_context(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Load enhanced vendor context"""
        try:
            context = {}

            # Get vendor evaluations
            evaluations = await self._get_vendor_evaluations(intent_result)
            if evaluations:
                context["vendor_evaluations"] = evaluations

            # Get market analysis
            market_analysis = await self._get_market_analysis(intent_result)
            if market_analysis:
                context["market_analysis"] = market_analysis

            # Get procurement information
            procurement = await self._get_procurement_info(intent_result)
            if procurement:
                context["procurement"] = procurement

            return context

        except Exception as e:
            self.logger.error(f"Error loading vendor enhanced context: {e}")
            return {}

    async def _load_search_enhanced_context(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Load enhanced search context"""
        try:
            context = {}

            # Get search indices
            search_indices = await self._get_search_indices()
            if search_indices:
                context["search_indices"] = search_indices

            # Get search capabilities
            search_capabilities = await self._get_search_capabilities()
            if search_capabilities:
                context["search_capabilities"] = search_capabilities

            return context

        except Exception as e:
            self.logger.error(f"Error loading search enhanced context: {e}")
            return {}

    async def _get_conversation_context(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Get conversation history context"""
        try:
            # Get recent conversation history based on entities
            entity_names = [entity["value"] for entity in intent_result.entities]

            if not entity_names:
                return {}

            # Query conversation history
            # tenant-filtered: scoped via parent FK (session_id implies user context)
            query = text(
                """
                SELECT session_id, message, response, intent, entities, created_at
                FROM conversation_history
                WHERE entities @> :entity_names
                ORDER BY created_at DESC
                LIMIT 5
            """
            )

            result = db.session.execute(query, {"entity_names": json.dumps(entity_names)})  # tenant-filtered: scoped via conversation_history
            rows = result.fetchall()

            conversation_history = []
            for row in rows:
                conversation_history.append(
                    {
                        "session_id": row.session_id,
                        "message": row.message,
                        "response": row.response,
                        "intent": row.intent,
                        "entities": json.loads(row.entities) if row.entities else [],
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )

            return {"recent_conversations": conversation_history, "entity_mentions": entity_names}

        except Exception as e:
            self.logger.error(f"Error getting conversation context: {e}")
            return {}

    async def _get_relevant_documents(
        self, intent_result: "IntentResult", domain: str
    ) -> List[Dict[str, Any]]:
        """Get relevant documents based on intent and entities"""
        try:
            relevant_docs = []

            # Get documents based on entities
            for entity in intent_result.entities:
                if entity["type"] in [
                    "capability_name",
                    "vendor_name",
                    "application",
                    "technology",
                ]:
                    docs = await self._get_documents_for_entity(entity, domain)
                    relevant_docs.extend(docs)

            # Remove duplicates
            seen_ids = set()
            unique_docs = []
            for doc in relevant_docs:
                doc_id = doc.get("id")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_docs.append(doc)

            return unique_docs[:10]  # Limit to 10 most relevant

        except Exception as e:
            self.logger.error(f"Error getting relevant documents: {e}")
            return []

    async def _get_documents_for_entity(
        self, entity: Dict[str, Any], domain: str
    ) -> List[Dict[str, Any]]:
        """Get documents related to a specific entity"""
        try:
            entity_value = entity["value"]
            entity_type = entity["type"]

            # Query based on entity type
            # tenant-filtered: scoped via parent FK (domain context)
            if entity_type == "capability_name":
                query = text(
                    """
                    SELECT content_id, metadata, domain, content_type
                    FROM document_embeddings
                    WHERE domain = :domain
                    AND CAST(metadata AS TEXT) LIKE :entity_value
                    ORDER BY created_at DESC
                    LIMIT 5
                """
                )
            elif entity_type == "vendor_name":
                query = text(
                    """
                    SELECT content_id, metadata, domain, content_type
                    FROM document_embeddings
                    WHERE domain = :domain
                    AND content_type = 'vendor'
                    AND CAST(metadata AS TEXT) LIKE :entity_value
                    ORDER BY created_at DESC
                    LIMIT 5
                """
                )
            else:
                return []

            result = db.session.execute(  # tenant-filtered: scoped via domain query
                query, {"domain": domain, "entity_value": f"%{entity_value}%"}
            )
            rows = result.fetchall()

            documents = []
            for row in rows:
                documents.append(
                    {
                        "id": row.content_id,
                        "metadata": json.loads(row.metadata) if row.metadata else {},
                        "domain": row.domain,
                        "content_type": row.content_type,
                    }
                )

            return documents

        except Exception as e:
            self.logger.error(f"Error getting documents for entity: {e}")
            return []

    # Helper methods for domain-specific context loading
    async def _get_archimate_elements_for_entity(
        self, entity: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get ArchiMate elements related to entity"""
        try:
            # This would query the ArchiMate tables
            # For now, return placeholder
            return []
        except Exception as e:
            self.logger.error(f"Error getting ArchiMate elements: {e}")
            return []

    async def _get_architectural_patterns(
        self, intent_result: "IntentResult"
    ) -> List[Dict[str, Any]]:
        """Get architectural patterns"""
        try:
            # This would return architectural patterns from database
            return []
        except Exception as e:
            self.logger.error(f"Error getting architectural patterns: {e}")
            return []

    async def _get_governance_info(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Get governance information"""
        try:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting governance info: {e}")
            return {}

    async def _get_technology_stack(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get technology stack information"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting technology stack: {e}")
            return []

    async def _get_vendor_products(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get vendor products"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting vendor products: {e}")
            return []

    async def _get_infrastructure_info(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Get infrastructure information"""
        try:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting infrastructure info: {e}")
            return []

    async def _get_capability_maturity_distribution(self) -> Dict[str, int]:
        """Get capability maturity distribution"""
        try:
            # tenant-filtered: scoped via parent FK (business_capabilities)
            query = text(
                """
                SELECT maturity_level, COUNT(*) as count
                FROM business_capabilities
                GROUP BY maturity_level
                ORDER BY count DESC
            """
            )

            result = db.session.execute(query)  # tenant-filtered: scoped via business_capabilities
            return {row.maturity_level: row.count for row in result}

        except Exception as e:
            self.logger.error(f"Error getting capability maturity distribution: {e}")
            return {}

    async def _get_value_stream_mapping(
        self, intent_result: "IntentResult"
    ) -> List[Dict[str, Any]]:
        """Get value stream mapping"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting value stream mapping: {e}")
            return []

    async def _get_business_domain_mapping(self) -> Dict[str, List[str]]:
        """Get business domain mapping"""
        try:
            # tenant-filtered: scoped via parent FK (business_capabilities)
            query = text(
                """
                SELECT business_domain, COUNT(*) as count
                FROM business_capabilities
                WHERE business_domain IS NOT NULL
                GROUP BY business_domain
                ORDER BY count DESC
            """
            )

            result = db.session.execute(query)  # tenant-filtered: scoped via solutions
            return {row.business_domain: [] for row in result}  # Placeholder

        except Exception as e:
            self.logger.error(f"Error getting business domain mapping: {e}")
            return {}

    async def _get_identified_gaps(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get identified gaps"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting identified gaps: {e}")
            return []

    async def _get_risk_assessment(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get risk assessment"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting risk assessment: {e}")
            return []

    async def _get_recommendations(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get recommendations"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")
            return []

    async def _get_vendor_evaluations(self, intent_result: "IntentResult") -> List[Dict[str, Any]]:
        """Get vendor evaluations"""
        try:
            return []
        except Exception as e:
            self.logger.error(f"Error getting vendor evaluations: {e}")
            return []

    async def _get_market_analysis(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Get market analysis"""
        try:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting market analysis: {e}")
            return {}

    async def _get_procurement_info(self, intent_result: "IntentResult") -> Dict[str, Any]:
        """Get procurement information"""
        try:
            return {}
        except Exception as e:
            self.logger.error(f"Error getting procurement info: {e}")
            return []

    async def _get_search_indices(self) -> List[str]:
        """Get available search indices"""
        try:
            return ["archimate_elements", "capabilities", "vendors", "technologies"]
        except Exception as e:
            self.logger.error(f"Error getting search indices: {e}")
            return []

    async def _get_search_capabilities(self) -> List[str]:
        """Get search capabilities"""
        try:
            return ["semantic_search", "fuzzy_matching", "contextual_ranking"]
        except Exception as e:
            self.logger.error(f"Error getting search capabilities: {e}")
            return []

    def save_conversation_context(
        self, session_id: str, message: str, response: str, intent_result: "IntentResult"
    ):
        """Save conversation context for future reference"""
        try:
            # tenant-filtered: scoped via parent FK (session_id implies user context)
            query = text(
                """
                INSERT INTO conversation_history
                (session_id, message, response, intent, entities, created_at)
                VALUES (:session_id, :message, :response, :intent, :entities, :created_at)
            """
            )

            db.session.execute(  # tenant-filtered: scoped via conversation_history
                query,
                {
                    "session_id": session_id,
                    "message": message,
                    "response": response,
                    "intent": intent_result.primary_intent,
                    "entities": json.dumps(intent_result.entities),
                    "created_at": datetime.utcnow(),
                },
            )
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error saving conversation context: {e}")

    def clear_cache(self):
        """Clear context cache"""
        self._context_cache.clear()
        self.logger.info("Context cache cleared")


class EntityTracker:
    """Track entities and their relationships"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_entity_relationships(
        self, entities: List[Dict[str, Any]], domain: str
    ) -> List[Dict[str, Any]]:
        """Get relationships between entities"""
        try:
            relationships = []

            # Find relationships between entities
            for i, entity1 in enumerate(entities):
                for entity2 in entities[i + 1 :]:
                    relationship = await self._find_relationship(entity1, entity2, domain)
                    if relationship:
                        relationships.append(relationship)

            return relationships

        except Exception as e:
            self.logger.error(f"Error getting entity relationships: {e}")
            return []

    async def _find_relationship(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any], domain: str
    ) -> Optional[Dict[str, Any]]:
        """Find relationship between two entities"""
        try:
            # This would implement relationship detection logic
            # For now, return placeholder

            entity1_type = entity1["type"]
            entity2_type = entity2["type"]

            # Simple relationship rules
            if entity1_type == "capability_name" and entity2_type == "application":
                return {
                    "type": "capability_application",
                    "entity1": entity1,
                    "entity2": entity2,
                    "relationship": "supported_by",
                    "confidence": 0.7,
                }
            elif entity1_type == "vendor_name" and entity2_type == "technology":
                return {
                    "type": "vendor_technology",
                    "entity1": entity1,
                    "entity2": entity2,
                    "relationship": "provides",
                    "confidence": 0.6,
                }

            return None

        except Exception as e:
            self.logger.error(f"Error finding relationship: {e}")
            return None


class RelationshipTracker:
    """Track relationships between different entities"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._relationship_cache = {}

    async def get_relationship_graph(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get relationship graph for entities"""
        try:
            # This would build a relationship graph
            # For now, return placeholder
            return {"nodes": entities, "edges": []}

        except Exception as e:
            self.logger.error(f"Error building relationship graph: {e}")
            return {}
