"""
Natural Language Query Service

Translates natural language questions into database queries and returns
structured results. Supports querying applications, capabilities, vendors,
ArchiMate elements, and cross-domain analysis.

Features:
- Intent detection from natural language
- Safe ORM query generation
- Result formatting for different output types
- Query explanation and transparency
- Persona-aware query prioritization
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Query

from app import db
from app.models.application_layer import ApplicationInterface
from app.models.application_portfolio import ApplicationComponent
from app.models.archimate_core import ArchiMateElement
from app.models.business_capabilities import BusinessCapability
from app.models.unified_capability import UnifiedCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.services.multi_domain_chat_service import PERSONA_CONFIGS

logger = logging.getLogger(__name__)


# Persona-specific query focus and suggestions
PERSONA_QUERY_CONTEXT = {
    "enterprise_architect": {
        "priority_entities": ["application", "capability", "element"],
        "priority_fields": ["criticality", "strategic_alignment", "health", "risk"],
        "suggested_queries": [
            "Show portfolio health across applications",
            "Which applications violate architecture principles?",
            "List capabilities without supporting applications",
            "Show applications with single points of failure",
        ],
    },
    "solutions_architect": {
        "priority_entities": ["application", "element", "vendor"],
        "priority_fields": ["technology", "integration", "dependencies"],
        "suggested_queries": [
            "Show applications by integration complexity",
            "List vendor products by capability",
            "Which systems have the most dependencies?",
            "Find applications using deprecated technology",
        ],
    },
    "application_architect": {
        "priority_entities": ["application", "element"],
        "priority_fields": ["health", "technology", "technical_debt", "modernization"],
        "suggested_queries": [
            "Show applications with high technical debt",
            "List applications candidates for modernization",
            "Which applications have lowest health scores?",
            "Find applications without API documentation",
        ],
    },
    "integration_architect": {
        "priority_entities": ["application", "element"],
        "priority_fields": ["interfaces", "dependencies", "data_flows"],
        "suggested_queries": [
            "Show all application interfaces",
            "List point-to-point integrations",
            "Which applications have most interfaces?",
            "Find applications without integration documentation",
        ],
    },
    "systems_architect": {
        "priority_entities": ["application", "element"],
        "priority_fields": ["dr", "security", "infrastructure", "availability"],
        "suggested_queries": [
            "Show applications without DR plan",
            "List applications with security concerns",
            "Which systems lack high availability?",
            "Find infrastructure single points of failure",
        ],
    },
    "business_architect": {
        "priority_entities": ["capability", "application"],
        "priority_fields": ["maturity", "automation", "value_stream"],
        "suggested_queries": [
            "Show capability maturity distribution",
            "List capabilities with low automation",
            "Which capabilities lack application support?",
            "Find gaps in value stream coverage",
        ],
    },
    "business_analyst": {
        "priority_entities": ["capability", "application"],
        "priority_fields": ["requirements", "processes", "stakeholders"],
        "suggested_queries": [
            "List capabilities supporting key processes",
            "Show applications by stakeholder group",
            "Which requirements lack traceability?",
            "Find capabilities needing process improvement",
        ],
    },
    "product_analyst": {
        "priority_entities": ["capability", "application", "vendor"],
        "priority_fields": ["features", "customer", "roadmap"],
        "suggested_queries": [
            "Show capabilities by customer impact",
            "List applications supporting customer journeys",
            "Which features close capability gaps?",
            "Find capabilities differentiating from competitors",
        ],
    },
    "cio": {
        "priority_entities": ["application", "vendor", "capability"],
        "priority_fields": ["cost", "risk", "strategic_alignment", "compliance"],
        "suggested_queries": [
            "Show top 10 applications by annual cost",
            "List high-risk vendors",
            "What is portfolio health score?",
            "Show compliance gaps requiring attention",
        ],
    },
}


class NaturalLanguageQueryService:
    """
    Service for translating natural language to database queries.
    """

    # Query intent patterns
    INTENT_PATTERNS = {
        "list": r"\b(list|show|display|get|find|retrieve|what are|which)\b",
        "count": r"\b(count|how many|number of|total)\b",
        "filter_missing": r"\b(without|missing|no|lacking|empty|null|undefined)\b",
        "filter_has": r"\b(with|having|has|contains|includes)\b",
        "compare": r"\b(compare|versus|vs|difference|between)\b",
        "aggregate": r"\b(sum|average|avg|total|maximum|minimum|max|min)\b",
        "time_based": r"\b(expiring|expired|due|upcoming|last|recent|old|new)\b",
        "threshold": r"\b(below|above|under|over|less than|more than|greater|fewer)\b",
        "top_bottom": r"\b(top|bottom|highest|lowest|best|worst|most|least)\b",
    }

    # Entity type patterns. Each noun allows an optional plural 's' (and
    # capability's -ies) so that "vendors", "products", "elements", etc. are
    # detected — without it the singular-only patterns failed to match plural
    # queries and silently fell through to the default ("application"), e.g.
    # "show vendors expiring in 90 days" was classified as applications.
    ENTITY_PATTERNS = {
        "application": r"\b(applications?|apps?|systems?|software|platforms?)\b",
        "capability": r"\b(capabilit(?:y|ies)|business capabilit(?:y|ies))\b",
        "vendor": r"\b(vendors?|suppliers?|providers?|partners?)\b",
        "product": r"\b(products?|solutions?|tools?|services?)\b",
        "element": r"\b(elements?|archimate|components?|artifacts?)\b",
    }

    # Field mapping for each entity type
    # Each value lists aliases ordered so the first REAL column on the model is
    # preferred. Aliases also include human terms (e.g. "maturity") so the query
    # text matches; resolution against the model picks the actual column name.
    FIELD_MAPPINGS = {
        "application": {
            "owner": ["business_owner", "application_owner", "technical_owner", "owner"],
            "status": ["lifecycle_status", "status"],
            "technology": ["technology_stack", "technology", "tech"],
            "domain": ["business_domain", "domain"],
            "description": ["description", "desc"],
            "name": ["name", "title"],
            "cost": ["total_cost_of_ownership", "license_cost_annual", "annual_cost", "cost", "tco"],
            "risk": ["business_risk", "technical_risk", "risk_level", "risk_score", "risk"],
            "criticality": ["criticality", "business_criticality"],
        },
        "capability": {
            "maturity": ["current_maturity_level", "maturity_level", "maturity", "maturity_score"],
            "level": ["level", "hierarchy_level"],
            "domain": ["business_domain", "domain"],
            "parent": ["parent_id", "parent"],
        },
        "vendor": {
            "type": ["vendor_type", "type", "category"],
            "tier": ["strategic_tier", "tier"],
            "contract": ["contract_end_date", "contract_expiry"],
            "risk": ["vendor_lock_in_risk", "acquisition_risk", "risk_level", "risk_score", "risk"],
        },
    }

    # Time period mappings
    TIME_PERIODS = {
        "days": {"30 days": 30, "60 days": 60, "90 days": 90, "week": 7, "month": 30},
        "patterns": r"(\d+)\s*(days?|weeks?|months?|years?)",
    }

    def __init__(self):
        """Initialize the NL Query Service."""
        self.query_history = []

    def process_query(self, query: str, persona: str = None) -> Dict[str, Any]:
        """
        Process a natural language query and return results.

        Args:
            query: Natural language query string
            persona: Optional persona for context-aware results

        Returns:
            Dict with results, query explanation, and metadata
        """
        try:
            # Normalize query
            query_lower = query.lower().strip()

            # Detect intent
            intent = self._detect_intent(query_lower)

            # Detect entity type
            entity_type = self._detect_entity_type(query_lower)

            # Extract filters and conditions
            filters = self._extract_filters(query_lower, entity_type)

            # Build and execute query
            results, orm_query = self._execute_query(entity_type, intent, filters)

            # Format results
            formatted_results = self._format_results(results, entity_type, intent)

            # Generate explanation
            explanation = self._generate_explanation(
                query, entity_type, intent, filters, len(results)
            )

            # Store in history
            self.query_history.append(
                {
                    "query": query,
                    "entity_type": entity_type,
                    "intent": intent,
                    "result_count": len(results),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # Get persona-specific suggestions
            suggestions = self._generate_follow_up_suggestions(
                entity_type, intent, results, persona
            )

            # Get persona config for additional context
            persona_info = None
            if persona and persona in PERSONA_CONFIGS:
                persona_info = {
                    "name": PERSONA_CONFIGS[persona]["name"],
                    "focus_areas": PERSONA_CONFIGS[persona]["focus_areas"],
                }

            return {
                "success": True,
                "query": query,
                "intent": intent,
                "entity_type": entity_type,
                "result_count": len(results),
                "results": formatted_results,
                "explanation": explanation,
                "filters_applied": filters,
                "persona_context": persona,
                "persona_info": persona_info,
                "suggestions": suggestions,
            }

        except Exception as e:
            logger.error(f"Error processing NL query: {e}", exc_info=True)
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "suggestions": self._get_query_suggestions(query),
            }

    def _detect_intent(self, query: str) -> str:
        """Detect the primary intent of the query."""
        intents_found = []

        for intent, pattern in self.INTENT_PATTERNS.items():
            if re.search(pattern, query, re.IGNORECASE):
                intents_found.append(intent)

        # Prioritize intents
        if "count" in intents_found:
            return "count"
        elif "compare" in intents_found:
            return "compare"
        elif "aggregate" in intents_found:
            return "aggregate"
        elif "top_bottom" in intents_found:
            return "top_bottom"
        else:
            return "list"

    def _detect_entity_type(self, query: str) -> str:
        """Detect the primary entity type being queried."""
        for entity, pattern in self.ENTITY_PATTERNS.items():
            if re.search(pattern, query, re.IGNORECASE):
                return entity

        # Default to application if no entity detected
        return "application"

    def _model_for_entity(self, entity_type: str):
        """Map an entity type to its ORM model (to resolve field aliases to real columns)."""
        return {
            "application": ApplicationComponent,
            "capability": BusinessCapability,
            "vendor": VendorOrganization,
            "product": VendorProduct,
            "element": ArchiMateElement,
        }.get(entity_type, ApplicationComponent)

    def _extract_filters(self, query: str, entity_type: str) -> Dict[str, Any]:
        """Extract filter conditions from the query."""
        filters = {
            "missing_fields": [],
            "has_fields": [],
            "threshold_conditions": [],
            "time_conditions": [],
            "text_search": None,
            "limit": None,
            "order_by": None,
            "order_direction": "desc",
        }

        field_mapping = self.FIELD_MAPPINGS.get(entity_type, {})
        model = self._model_for_entity(entity_type)

        def _resolve_column(field_aliases):
            """First alias that is a real column on the model, else None.

            The mapping's first alias is not always the actual column name
            (e.g. capability maturity is ``current_maturity_level``), and some
            requested fields have no backing column at all (applications carry
            no numeric risk/cost). Returning None lets the caller skip the
            filter rather than silently build one that never applies — which
            previously returned the full unfiltered list while the explanation
            still claimed the filter was applied.
            """
            return next((a for a in field_aliases if hasattr(model, a)), None)

        def _resolve_numeric_column(field_aliases):
            """First alias that is a real numeric column (for < / > thresholds).

            Skips string columns (e.g. business_risk VARCHAR) so we never emit a
            numeric comparison against text — which would error or mislead.
            """
            numeric = ("INTEGER", "BIGINT", "SMALLINT", "FLOAT", "REAL", "NUMERIC", "DECIMAL", "DOUBLE")
            for a in field_aliases:
                col = getattr(model, a, None)
                if col is None:
                    continue
                try:
                    if any(t in str(col.type).upper() for t in numeric):
                        return a
                except Exception:
                    continue
            return None

        def _query_mentions(field_aliases):
            return any(alias.lower() in query for alias in field_aliases)

        # Detect missing field filters
        if re.search(self.INTENT_PATTERNS["filter_missing"], query):
            for field_name, field_aliases in field_mapping.items():
                if not _query_mentions(field_aliases):
                    continue
                col = _resolve_column(field_aliases)
                if col:
                    filters["missing_fields"].append(col)

        # Detect "has" field filters
        if re.search(self.INTENT_PATTERNS["filter_has"], query):
            for field_name, field_aliases in field_mapping.items():
                if not _query_mentions(field_aliases):
                    continue
                col = _resolve_column(field_aliases)
                if col:
                    filters["has_fields"].append(col)

        # Detect threshold conditions
        threshold_match = re.search(
            r"(below|above|under|over|less than|more than|greater than|fewer than)\s*(\d+)", query
        )
        if threshold_match:
            operator = threshold_match.group(1)
            value = int(threshold_match.group(2))
            # Apply to the first mentioned field that maps to a real column.
            for field_name, field_aliases in field_mapping.items():
                if not _query_mentions(field_aliases):
                    continue
                col = _resolve_numeric_column(field_aliases)
                if not col:
                    continue
                filters["threshold_conditions"].append(
                    {
                        "field": col,
                        "operator": "lt"
                        if operator in ["below", "under", "less than", "fewer than"]
                        else "gt",
                        "value": value,
                    }
                )
                break

        # Detect time-based conditions
        time_match = re.search(self.TIME_PERIODS["patterns"], query)
        if time_match:
            amount = int(time_match.group(1))
            unit = time_match.group(2)
            if "week" in unit:
                days = amount * 7
            elif "month" in unit:
                days = amount * 30
            elif "year" in unit:
                days = amount * 365
            else:
                days = amount

            if "expir" in query:
                filters["time_conditions"].append({"type": "expiring", "days": days})

        # Detect top/bottom limits
        top_match = re.search(r"(top|bottom|first|last)\s*(\d+)", query)
        if top_match:
            filters["limit"] = int(top_match.group(2))
            filters["order_direction"] = "desc" if top_match.group(1) in ["top", "first"] else "asc"

        # Detect specific text search
        quoted_match = re.search(r'"([^"]+)"', query)
        if quoted_match:
            filters["text_search"] = quoted_match.group(1)

        return filters

    def _execute_query(self, entity_type: str, intent: str, filters: Dict) -> Tuple[List, Query]:
        """Execute the database query based on detected parameters."""

        # Select the appropriate model
        if entity_type == "application":
            model = ApplicationComponent
            query = model.query
        elif entity_type == "capability":
            model = BusinessCapability
            query = model.query
        elif entity_type == "vendor":
            model = VendorOrganization
            query = model.query
        elif entity_type == "product":
            model = VendorProduct
            query = model.query
        elif entity_type == "element":
            model = ArchiMateElement
            query = model.query
        else:
            model = ApplicationComponent
            query = model.query

        def _is_string_col(col):
            """Only string columns can be compared to '' — comparing an INTEGER
            column to '' makes Postgres raise 'invalid input syntax for integer'."""
            try:
                return "CHAR" in str(col.type).upper() or "TEXT" in str(col.type).upper()
            except Exception:
                return False

        # Apply missing field filters (NULL, plus '' only for string columns)
        for field in filters.get("missing_fields", []):
            if hasattr(model, field):
                col = getattr(model, field)
                query = query.filter(
                    or_(col == None, col == "") if _is_string_col(col) else col == None
                )

        # Apply has field filters
        for field in filters.get("has_fields", []):
            if hasattr(model, field):
                col = getattr(model, field)
                query = query.filter(
                    and_(col != None, col != "") if _is_string_col(col) else col != None
                )

        # Apply threshold conditions
        for condition in filters.get("threshold_conditions", []):
            field = condition["field"]
            if hasattr(model, field):
                if condition["operator"] == "lt":
                    query = query.filter(getattr(model, field) < condition["value"])
                else:
                    query = query.filter(getattr(model, field) > condition["value"])

        # Apply time conditions
        for time_cond in filters.get("time_conditions", []):
            if time_cond["type"] == "expiring":
                future_date = datetime.utcnow() + timedelta(days=time_cond["days"])
                # Check for contract_end_date or similar fields
                if hasattr(model, "contract_end_date"):
                    query = query.filter(
                        and_(
                            model.contract_end_date != None,
                            model.contract_end_date <= future_date,
                            model.contract_end_date >= datetime.utcnow(),
                        )
                    )

        # Apply text search
        if filters.get("text_search"):
            search_term = f"%{filters['text_search']}%"
            if hasattr(model, "name"):
                query = query.filter(model.name.ilike(search_term))

        # Apply ordering
        if hasattr(model, "name"):
            if filters.get("order_direction") == "asc":
                query = query.order_by(asc(model.name))
            else:
                query = query.order_by(desc(model.name))

        # Apply limit
        if filters.get("limit"):
            query = query.limit(filters["limit"])
        else:
            query = query.limit(100)  # Default limit

        # Execute query
        if intent == "count":
            count = query.count()
            return [{"count": count}], query
        else:
            results = query.all()
            return results, query

    def _format_results(self, results: List, entity_type: str, intent: str) -> List[Dict]:
        """Format query results for display."""
        if intent == "count":
            return results  # Already formatted

        formatted = []
        for item in results:
            if entity_type == "application":
                formatted.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": getattr(item, "description", "")[:100]
                        if getattr(item, "description", None)
                        else "",
                        "status": getattr(item, "status", "Unknown"),
                        "business_owner": getattr(item, "business_owner", "Not assigned"),
                        "technology_stack": getattr(item, "technology_stack", "Not specified"),
                        "business_domain": getattr(item, "business_domain", "Not specified"),
                        "criticality": getattr(item, "criticality", "Not rated"),
                        "entity_type": "Application",
                    }
                )
            elif entity_type == "capability":
                formatted.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": getattr(item, "description", "")[:100]
                        if getattr(item, "description", None)
                        else "",
                        "level": getattr(item, "level", "Unknown"),
                        "maturity_level": getattr(item, "maturity_level", "Not assessed"),
                        "business_domain": getattr(item, "business_domain", "Not specified"),
                        "automation_level": getattr(item, "automation_level", "Not assessed"),
                        "entity_type": "Capability",
                    }
                )
            elif entity_type == "vendor":
                formatted.append(
                    {
                        "id": item.id,
                        "name": getattr(
                            item, "name", "Unknown"
                        ),  # Fixed: VendorOrganization uses 'name' directly
                        "vendor_type": getattr(item, "vendor_type", "Unknown"),
                        "strategic_tier": getattr(item, "strategic_tier", "Not classified"),
                        "status": getattr(item, "status", "Unknown"),
                        "country": getattr(item, "country", "Not specified"),
                        "contract_end_date": str(getattr(item, "contract_end_date", ""))
                        if getattr(item, "contract_end_date", None)
                        else "Not specified",
                        "entity_type": "Vendor",
                    }
                )
            elif entity_type == "element":
                formatted.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "element_type": getattr(
                            item, "type", "Unknown"
                        ),  # Fixed: ArchiMateElement uses 'type' not 'element_type'
                        "layer": getattr(item, "layer", "Unknown"),
                        "description": getattr(item, "description", "")[:100]
                        if getattr(item, "description", None)
                        else "",
                        "entity_type": "ArchiMate Element",
                    }
                )
            else:
                formatted.append(
                    {
                        "id": getattr(item, "id", None),
                        "name": getattr(item, "name", "Unknown"),
                        "entity_type": entity_type.title(),
                    }
                )

        return formatted

    def _generate_explanation(
        self, query: str, entity_type: str, intent: str, filters: Dict, result_count: int
    ) -> str:
        """Generate a human-readable explanation of the query."""
        explanation_parts = []

        plural = {
            "application": "applications",
            "capability": "capabilities",
            "vendor": "vendors",
            "product": "products",
            "element": "elements",
        }.get(entity_type, f"{entity_type}s")

        def _humanize(field):
            # current_maturity_level -> "maturity level"; business_owner -> "business owner"
            return field.replace("current_", "").replace("_", " ").strip()

        # Intent explanation
        if intent == "count":
            explanation_parts.append(f"Counting {plural}")
        elif intent == "compare":
            explanation_parts.append(f"Comparing {plural}")
        else:
            explanation_parts.append(f"Listing {plural}")

        # Filter explanations
        if filters.get("missing_fields"):
            fields = ", ".join(_humanize(f) for f in filters["missing_fields"])
            explanation_parts.append(f"where {fields} is missing")

        if filters.get("threshold_conditions"):
            for cond in filters["threshold_conditions"]:
                op = "less than" if cond["operator"] == "lt" else "greater than"
                explanation_parts.append(f"where {_humanize(cond['field'])} is {op} {cond['value']}")

        if filters.get("time_conditions"):
            for time_cond in filters["time_conditions"]:
                explanation_parts.append(f"expiring within {time_cond['days']} days")

        if filters.get("limit"):
            explanation_parts.append(f"limited to {filters['limit']} results")

        # Result count
        explanation_parts.append(f"- Found {result_count} result(s)")

        return " ".join(explanation_parts)

    def _generate_follow_up_suggestions(
        self, entity_type: str, intent: str, results: List, persona: str = None
    ) -> List[str]:
        """Generate follow-up query suggestions based on results and persona."""
        suggestions = []

        # Use persona-specific suggestions if available
        if persona and persona in PERSONA_QUERY_CONTEXT:
            suggestions = PERSONA_QUERY_CONTEXT[persona]["suggested_queries"]
        elif entity_type == "application":
            suggestions = [
                "Show applications with high criticality",
                "List applications without disaster recovery",
                "Which applications have technical debt?",
                "Show applications by business domain",
            ]
        elif entity_type == "capability":
            suggestions = [
                "Show capabilities with maturity below 3",
                "List capabilities without automation",
                "Which capabilities lack application support?",
                "Show L1 capabilities",
            ]
        elif entity_type == "vendor":
            suggestions = [
                "List vendors expiring in 90 days",
                "Show strategic tier 1 vendors",
                "Which vendors have high risk?",
                "List vendors by spend",
            ]

        return suggestions[:4]

    def _get_query_suggestions(self, failed_query: str) -> List[str]:
        """Provide suggestions when a query fails."""
        return [
            "Try: 'Show all applications without business owner'",
            "Try: 'List capabilities with maturity below 3'",
            "Try: 'Which vendors expire in 90 days?'",
            "Try: 'Count applications by status'",
        ]

    def get_supported_queries(self, persona: str = None) -> Dict[str, List[str]]:
        """Return examples of supported query types, optionally persona-specific."""
        # If persona is specified, return persona-specific queries first
        if persona and persona in PERSONA_QUERY_CONTEXT:
            persona_config = PERSONA_QUERY_CONTEXT[persona]
            return {
                "recommended_for_role": persona_config["suggested_queries"],
                "applications": [
                    "Show all applications without business owner",
                    "List applications with no DR plan",
                    "Which applications have high criticality?",
                    "Show top 10 applications by cost",
                ],
                "capabilities": [
                    "List capabilities with maturity below 3",
                    "Show capabilities without automation",
                    "Which capabilities have no supporting applications?",
                ],
                "vendors": [
                    "List vendors expiring in 90 days",
                    "Show strategic tier 1 vendors",
                    "Which vendors have high risk rating?",
                ],
            }

        return {
            "applications": [
                "Show all applications without business owner",
                "List applications with no DR plan",
                "Which applications have high criticality?",
                "Show top 10 applications by cost",
                "Find applications in Finance domain",
            ],
            "capabilities": [
                "List capabilities with maturity below 3",
                "Show capabilities without automation",
                "Which capabilities have no supporting applications?",
                "Find L2 capabilities in Sales domain",
            ],
            "vendors": [
                "List vendors expiring in 90 days",
                "Show strategic tier 1 vendors",
                "Which vendors have contracts ending soon?",
                "Find vendors with high risk rating",
            ],
            "general": [
                "How many applications do we have?",
                "Count capabilities by level",
                "Show recent changes",
                "List items needing review",
            ],
        }

    def get_persona_query_context(self, persona: str) -> Dict[str, Any]:
        """Get query context for a specific persona."""
        if persona not in PERSONA_QUERY_CONTEXT:
            return {
                "success": False,
                "error": f"Unknown persona: {persona}",
                "available_personas": list(PERSONA_QUERY_CONTEXT.keys()),
            }

        context = PERSONA_QUERY_CONTEXT[persona]
        persona_info = PERSONA_CONFIGS.get(persona, {})

        return {
            "success": True,
            "persona": persona,
            "name": persona_info.get("name", persona),
            "priority_entities": context["priority_entities"],
            "priority_fields": context["priority_fields"],
            "suggested_queries": context["suggested_queries"],
            "focus_areas": persona_info.get("focus_areas", []),
        }
