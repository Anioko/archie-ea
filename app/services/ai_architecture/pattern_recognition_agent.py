"""
Pattern Recognition Agent

Identifies architectural patterns from solution descriptions and maps them
to established frameworks (TOGAF, Zachman).
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternRecognitionAgent:
    """
    Agent for identifying architectural patterns in solution descriptions.

    Maps solution characteristics to established architectural patterns
    and frameworks with confidence scoring.
    """

    # Architectural patterns database
    ARCHITECTURAL_PATTERNS = {
        "microservices": {
            "keywords": ["microservice", "service", "distributed", "independent", "deployment"],
            "characteristics": [
                "service decomposition",
                "independent deployment",
                "data isolation",
                "api gateway",
            ],
            "confidence_threshold": 0.4,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "monolithic": {
            "keywords": ["monolith", "single", "unified", "centralized"],
            "characteristics": ["single codebase", "centralized deployment", "shared database"],
            "confidence_threshold": 0.3,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "layered": {
            "keywords": ["layer", "tier", "separation", "architecture"],
            "characteristics": [
                "separation of concerns",
                "layered architecture",
                "dependency flow",
            ],
            "confidence_threshold": 0.3,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "event_driven": {
            "keywords": ["event", "message", "queue", "async", "publisher", "subscriber"],
            "characteristics": [
                "event-driven architecture",
                "loose coupling",
                "asynchronous communication",
            ],
            "confidence_threshold": 0.4,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "cqrs": {
            "keywords": ["cqrs", "command", "query", "read", "write", "separation"],
            "characteristics": [
                "command query separation",
                "read/write separation",
                "different models",
            ],
            "confidence_threshold": 0.5,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "event_sourcing": {
            "keywords": ["event sourcing", "event store", "immutable", "audit", "replay"],
            "characteristics": ["immutable event log", "state reconstruction", "audit trail"],
            "frameworks": ["TOGAF"],
            "confidence_threshold": 0.5,
        },
        "api_gateway": {
            "keywords": ["gateway", "api", "routing", "proxy", "aggregation"],
            "characteristics": ["API gateway pattern", "request routing", "service aggregation"],
            "confidence_threshold": 0.3,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "hexagonal": {
            "keywords": ["hexagonal", "ports", "adapters", "dependency", "inversion"],
            "characteristics": [
                "hexagonal architecture",
                "port-adapter pattern",
                "dependency inversion",
            ],
            "confidence_threshold": 0.5,
            "frameworks": ["TOGAF", "Zachman"],
        },
        "serverless": {
            "keywords": ["serverless", "function", "lambda", "faas", "event"],
            "characteristics": ["serverless architecture", "function as a service", "event-driven"],
            "confidence_threshold": 0.4,
            "frameworks": ["TOGAF"],
        },
        "event_sourcing": {
            "keywords": ["event sourcing", "event store", "immutable", "audit", "replay"],
            "characteristics": ["immutable event log", "state reconstruction", "audit trail"],
            "frameworks": ["TOGAF"],
            "confidence_threshold": 0.5,
        },
        "api_gateway": {
            "keywords": ["gateway", "api", "routing", "aggregation", "security"],
            "characteristics": ["single entry point", "request routing", "composition", "security"],
            "confidence_threshold": 0.6,
            "frameworks": ["TOGAF"],
        },
    }

    # Trade-off scenarios for analysis
    TRADEOFF_SCENARIOS = {
        "monolith_vs_microservices": {
            "description": "Monolithic vs Microservices Architecture",
            "options": ["monolithic", "microservices"],
            "criteria": ["scalability", "complexity", "development_speed", "operational_overhead"],
        },
        "sql_vs_nosql": {
            "description": "SQL vs NoSQL Database Selection",
            "options": ["sql", "nosql"],
            "criteria": ["consistency", "scalability", "query_flexibility", "maturity"],
        },
        "cloud_vs_onpremise": {
            "description": "Cloud vs On-Premise Deployment",
            "options": ["cloud", "onpremise"],
            "criteria": ["cost", "control", "scalability", "compliance"],
        },
        "sync_vs_async": {
            "description": "Synchronous vs Asynchronous Communication",
            "options": ["synchronous", "asynchronous"],
            "criteria": ["responsiveness", "complexity", "reliability", "debugging"],
        },
        "rest_vs_graphql": {
            "description": "REST vs GraphQL API Design",
            "options": ["rest", "graphql"],
            "criteria": ["flexibility", "performance", "simplicity", "tooling"],
        },
    }

    # TOGAF ADM phases mapping
    TOGAF_PHASES = {
        "preliminary": "Vision and business principles",
        "architecture_vision": "High-level architecture vision",
        "business_architecture": "Business processes and functions",
        "information_systems_architecture": "Data and application architecture",
        "technology_architecture": "Technology infrastructure",
        "opportunities_and_solutions": "Implementation options",
        "migration_planning": "Transition strategy",
        "implementation_governance": "Architecture governance",
    }

    # Zachman framework mapping
    ZACHMAN_FRAMEWORK = {
        "scope": "Ballpark view - executive level",
        "business_model": "Business view - owner level",
        "system_model": "System view - designer level",
        "technology_model": "Technology view - builder level",
        "detailed_representations": "Detailed view - subcontractor level",
        "functioning_enterprise": "Actual system - user level",
    }

    async def recognize_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recognize architectural patterns from solution context.

        Args:
            context: Solution context including description and characteristics

        Returns:
            Dictionary with recognized patterns and confidence scores
        """
        try:
            description = context.get("solution_description", "").lower()
            solution_type = context.get("solution_type", "")
            business_domain = context.get("business_domain", "")
            capabilities = context.get("capabilities", [])
            constraints = context.get("constraints", [])

            # Combine all text for analysis
            full_text = " ".join(
                [
                    description,
                    solution_type,
                    business_domain,
                    " ".join([cap.get("name", "") for cap in capabilities]),
                    " ".join(constraints),
                ]
            ).lower()

            # Pattern recognition
            recognized_patterns = []
            for pattern_name, pattern_info in self.ARCHITECTURAL_PATTERNS.items():
                confidence = self._calculate_pattern_confidence(full_text, pattern_info)
                if confidence >= pattern_info["confidence_threshold"]:
                    recognized_patterns.append(
                        {
                            "name": pattern_name,
                            "confidence": confidence,
                            "description": self._get_pattern_description(pattern_name),
                            "rationale": self._generate_pattern_rationale(full_text, pattern_info),
                            "frameworks": pattern_info["frameworks"],
                            "characteristics": pattern_info["characteristics"],
                        }
                    )

            # Sort by confidence
            recognized_patterns.sort(key=lambda x: x["confidence"], reverse=True)

            # Framework mapping
            framework_mapping = self._map_to_frameworks(recognized_patterns, context)

            result = {
                "success": True,
                "patterns": recognized_patterns[:5],  # Top 5 patterns
                "primary_pattern": recognized_patterns[0] if recognized_patterns else None,
                "framework_mapping": framework_mapping,
                "confidence": recognized_patterns[0]["confidence"] if recognized_patterns else 0.0,
                "analysis_details": {
                    "text_analyzed": full_text[:200] + "..." if len(full_text) > 200 else full_text,
                    "patterns_considered": len(self.ARCHITECTURAL_PATTERNS),
                    "threshold_met": len(
                        [p for p in recognized_patterns if p["confidence"] >= 0.7]
                    ),
                },
            }

            logger.info(f"Pattern recognition completed: {len(recognized_patterns)} patterns found")
            return result

        except Exception as e:
            logger.error(f"Error in pattern recognition: {e}")
            return {
                "success": False,
                "error": str(e),
                "patterns": [],
                "confidence": 0.0,
            }

    def _calculate_pattern_confidence(self, text: str, pattern_info: Dict) -> float:
        """Calculate confidence score for a pattern based on text analysis."""
        keywords = pattern_info["keywords"]
        characteristics = pattern_info["characteristics"]

        # Keyword matching (40% weight)
        keyword_matches = sum(1 for keyword in keywords if keyword in text)
        keyword_score = (keyword_matches / len(keywords)) * 0.4

        # Characteristics matching (60% weight)
        char_matches = sum(
            1 for char in characteristics if any(word in text for word in char.lower().split())
        )
        char_score = (char_matches / len(characteristics)) * 0.6

        confidence = min(keyword_score + char_score, 1.0)
        return round(confidence, 3)

    def _get_pattern_description(self, pattern_name: str) -> str:
        """Get human-readable description for a pattern."""
        descriptions = {
            "microservices": "Decompose application into small, independent services",
            "event_driven": "Use events to communicate between loosely coupled components",
            "layered": "Organize code into distinct layers with specific responsibilities",
            "hexagonal": "Isulate application core from external concerns using ports and adapters",
            "cqrs": "Separate read and write operations for better scalability",
            "serverless": "Build applications without managing server infrastructure",
            "api_gateway": "Use a single entry point to manage and route API requests",
            "event_sourcing": "Store all changes to application state as a sequence of events",
        }
        return descriptions.get(pattern_name, "Architectural pattern for system design")

    def _generate_pattern_rationale(self, text: str, pattern_info: Dict) -> str:
        """Generate rationale for why a pattern was identified."""
        matched_keywords = [kw for kw in pattern_info["keywords"] if kw in text]
        if matched_keywords:
            return f"Identified by keywords: {', '.join(matched_keywords[:3])}"
        return "Pattern matches solution characteristics"

    def _map_to_frameworks(self, patterns: List[Dict], context: Dict) -> Dict[str, Any]:
        """Map recognized patterns to TOGAF and Zachman frameworks."""
        mapping = {
            "togaf": {
                "recommended_phases": [],
                "alignment_score": 0.0,
                "recommendations": [],
            },
            "zachman": {
                "recommended_rows": [],
                "alignment_score": 0.0,
                "recommendations": [],
            },
        }

        # TOGAF mapping based on patterns
        if any(p["name"] in ["microservices", "layered"] for p in patterns):
            mapping["togaf"]["recommended_phases"].extend(
                [
                    "architecture_vision",
                    "business_architecture",
                    "information_systems_architecture",
                    "technology_architecture",
                ]
            )

        if any(p["name"] in ["event_driven", "cqrs", "event_sourcing"] for p in patterns):
            mapping["togaf"]["recommended_phases"].extend(
                [
                    "information_systems_architecture",
                    "technology_architecture",
                ]
            )

        # Zachman mapping based on solution complexity
        solution_type = context.get("solution_type", "")
        if solution_type in ["Platform", "Integration"]:
            mapping["zachman"]["recommended_rows"].extend(
                [
                    "business_model",
                    "system_model",
                    "technology_model",
                ]
            )
        else:
            mapping["zachman"]["recommended_rows"].extend(
                [
                    "scope",
                    "business_model",
                    "system_model",
                ]
            )

        # Calculate alignment scores
        mapping["togaf"]["alignment_score"] = min(
            len(mapping["togaf"]["recommended_phases"]) / 4, 1.0
        )
        mapping["zachman"]["alignment_score"] = min(
            len(mapping["zachman"]["recommended_rows"]) / 3, 1.0
        )

        # Generate recommendations
        if mapping["togaf"]["alignment_score"] > 0.7:
            mapping["togaf"]["recommendations"].append(
                "Strong alignment with TOGAF ADM methodology"
            )
        elif mapping["togaf"]["alignment_score"] > 0.4:
            mapping["togaf"]["recommendations"].append(
                "Moderate alignment with TOGAF - consider additional phases"
            )

        if mapping["zachman"]["alignment_score"] > 0.7:
            mapping["zachman"]["recommendations"].append(
                "Good fit with Zachman framework structure"
            )
        elif mapping["zachman"]["alignment_score"] > 0.4:
            mapping["zachman"]["recommendations"].append(
                "Partial fit with Zachman - expand analysis"
            )

        return mapping

    def _identify_relevant_scenarios(self, context: Dict) -> Dict[str, Dict]:
        """Identify which trade-off scenarios are relevant for this context."""
        relevant = {}
        description = context.get("solution_description", "").lower()
        solution_type = context.get("solution_type", "")
        business_domain = context.get("business_domain", "")
        constraints = [c.lower() for c in context.get("constraints", [])]

        # Check each scenario for relevance
        for scenario_name, scenario_info in self.TRADEOFF_SCENARIOS.items():
            relevance_score = 0

            # Check description keywords
            if scenario_name == "monolith_vs_microservices":
                if any(kw in description for kw in ["service", "api", "distributed", "scale"]):
                    relevance_score += 2
                if solution_type in ["platform", "integration"]:
                    relevance_score += 1

            elif scenario_name == "sql_vs_nosql":
                if any(kw in description for kw in ["database", "data", "storage", "query"]):
                    relevance_score += 2
                if any(kw in description for kw in ["unstructured", "big data", "document"]):
                    relevance_score += 1

            elif scenario_name == "cloud_vs_onpremise":
                if any(kw in description for kw in ["cloud", "hosting", "infrastructure"]):
                    relevance_score += 2
                if "cloud" in constraints or "on-premise" in constraints:
                    relevance_score += 1

            elif scenario_name == "sync_vs_async":
                if any(kw in description for kw in ["real-time", "immediate", "instant"]):
                    relevance_score += 2
                if any(kw in description for kw in ["queue", "message", "event"]):
                    relevance_score += 1

            elif scenario_name == "rest_vs_graphql":
                if any(kw in description for kw in ["api", "interface", "integration"]):
                    relevance_score += 2
                if any(kw in description for kw in ["flexible", "query", "data"]):
                    relevance_score += 1

            # Include if relevant enough
            if relevance_score >= 2:
                relevant[scenario_name] = scenario_info

        return relevant
