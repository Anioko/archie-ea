"""
AI Architecture Reasoning Engine

Core orchestrator for all AI reasoning agents in solution architecture.
Provides parallel execution and unified interface for architectural intelligence.

Includes:
- Circuit breaker for resilience
- Caching for performance
- Rate limiting for abuse prevention
- Cost tracking for budget management
- Audit trail for compliance
- Metrics collection for monitoring
- Output validation for quality
- Explainability for transparency
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .ai_reasoning_infrastructure import (
    AIAnalysisCache,
    AuditTrail,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CostTracker,
    ExplainabilityEnhancer,
    FeedbackCollector,
    MetricsCollector,
    OutputValidator,
    RateLimiter,
)
from .pattern_recognition_agent import PatternRecognitionAgent
from .quality_optimization_agent import QualityOptimizationAgent
from .risk_assessment_agent import RiskAssessmentAgent
from .technology_selection_agent import TechnologySelectionAgent
from .tradeoff_analysis_agent import TradeoffAnalysisAgent

logger = logging.getLogger(__name__)


class AIReasoningEngine:
    """
    Core AI reasoning engine for architectural intelligence.

    Orchestrates 5 specialized agents to provide comprehensive
    architectural analysis and recommendations.

    Features:
    - Parallel agent execution with circuit breakers
    - Result caching for identical requests
    - Rate limiting to prevent abuse
    - Cost tracking for budget management
    - Comprehensive audit trail
    - Output validation and consistency checking
    - Explainable recommendations
    """

    def __init__(self):
        """Initialize the AI reasoning engine with all agents and infrastructure."""
        # Initialize agents
        self.pattern_recognizer = PatternRecognitionAgent()
        self.tradeoff_analyzer = TradeoffAnalysisAgent()
        self.risk_assessor = RiskAssessmentAgent()
        self.tech_selector = TechnologySelectionAgent()
        self.quality_optimizer = QualityOptimizationAgent()

        # Initialize infrastructure
        self.circuit_registry = CircuitBreakerRegistry()
        self.cache = AIAnalysisCache()
        self.rate_limiter = RateLimiter(
            requests_per_minute=30, requests_per_hour=200, burst_limit=5
        )
        self.cost_tracker = CostTracker()
        self.audit_trail = AuditTrail()
        self.metrics = MetricsCollector()
        self.feedback_collector = FeedbackCollector()

        # Create circuit breakers for each agent
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60)
        self.agent_breakers = {
            "pattern_recognition": self.circuit_registry.get_or_create(
                "pattern_recognition", config
            ),
            "tradeoff_analysis": self.circuit_registry.get_or_create("tradeoff_analysis", config),
            "risk_assessment": self.circuit_registry.get_or_create("risk_assessment", config),
            "technology_selection": self.circuit_registry.get_or_create(
                "technology_selection", config
            ),
            "quality_optimization": self.circuit_registry.get_or_create(
                "quality_optimization", config
            ),
        }

    async def analyze_solution_context(
        self,
        solution_description: str,
        solution_type: Optional[str] = None,
        business_domain: Optional[str] = None,
        capabilities: Optional[List[Dict]] = None,
        constraints: Optional[List[str]] = None,
        compliance_requirements: Optional[List[str]] = None,
        organization_size: Optional[str] = None,
        industry_vertical: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        timeline_months: Optional[int] = None,
        user_count: Optional[int] = None,
        is_critical: Optional[bool] = False,
        user_id: Optional[str] = "system",
        skip_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Run comprehensive AI analysis on solution context.

        Features integrated:
        - Rate limiting to prevent abuse
        - Caching for identical requests
        - Circuit breakers for resilience
        - Cost tracking for budget management
        - Audit trail for compliance
        - Output validation for quality
        - Explainability for recommendations

        Args:
            solution_description: Description of the solution
            solution_type: Type of solution (Platform, Product, Service, Integration)
            business_domain: Business domain of the solution
            capabilities: List of selected capabilities
            constraints: List of technical/business constraints
            compliance_requirements: List of compliance needs
            organization_size: smb, midmarket, enterprise
            industry_vertical: Industry sector
            budget_min: Minimum budget
            budget_max: Maximum budget
            timeline_months: Timeline constraint in months
            user_count: Expected number of users
            is_critical: Whether this is business-critical
            user_id: User making the request (for audit/rate limiting)
            skip_cache: Skip cache and force fresh analysis

        Returns:
            Comprehensive analysis results from all agents
        """
        analysis_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        context = {}

        # =====================================================================
        # INPUT VALIDATION
        # =====================================================================
        if not solution_description or len(solution_description.strip()) < 10:
            logger.warning(
                "AI reasoning analysis failed: solution_description is required (min 10 chars)"
            )
            self.metrics.increment("analysis_rejected", labels={"reason": "invalid_input"})
            return {
                "success": False,
                "error": "Solution description is required and must be at least 10 characters",
                "context": context,
                "analysis_id": analysis_id,
            }

        # =====================================================================
        # RATE LIMITING
        # =====================================================================
        rate_ok, rate_msg = self.rate_limiter.check_limit(user_id)
        if not rate_ok:
            logger.warning(f"Rate limit exceeded for user {user_id}: {rate_msg}")
            self.metrics.increment("analysis_rejected", labels={"reason": "rate_limit"})
            return {
                "success": False,
                "error": rate_msg,
                "context": context,
                "analysis_id": analysis_id,
                "rate_limited": True,
            }

        # =====================================================================
        # BUDGET CHECK
        # =====================================================================
        budget_ok, budget_msg = self.cost_tracker.check_budget()
        if not budget_ok:
            logger.warning(f"Budget exceeded: {budget_msg}")
            self.metrics.increment("analysis_rejected", labels={"reason": "budget"})
            return {
                "success": False,
                "error": budget_msg,
                "context": context,
                "analysis_id": analysis_id,
                "budget_exceeded": True,
            }

        # Build context for agents
        context = {
            "solution_description": solution_description or "",
            "solution_type": solution_type or "",
            "business_domain": business_domain or "",
            "capabilities": capabilities or [],
            "constraints": constraints or [],
            "compliance_requirements": compliance_requirements or [],
            "organization_size": organization_size or "midmarket",
            "industry_vertical": industry_vertical or "general",
            "budget_range": {
                "min": budget_min or 0,
                "max": budget_max or 999999,
            },
            "timeline_months": timeline_months or 12,
            "user_count": user_count or 100,
            "is_critical": is_critical or False,
        }

        # =====================================================================
        # CACHE CHECK
        # =====================================================================
        if not skip_cache:
            cached = self.cache.get(context)
            if cached:
                logger.info(f"Cache hit for analysis {analysis_id}")
                self.metrics.increment("cache_hits")
                cached["from_cache"] = True
                cached["analysis_id"] = analysis_id
                return cached

        self.metrics.increment("cache_misses")

        try:
            logger.info(
                f"Starting AI reasoning analysis {analysis_id} for: {solution_description[:100]}"
            )
            self.rate_limiter.record_request(user_id)

            # =================================================================
            # RUN AGENTS WITH CIRCUIT BREAKERS
            # =================================================================
            agent_results = await self._run_agents_with_resilience(context)

            # =================================================================
            # VALIDATE OUTPUTS
            # =================================================================
            validation_warnings = self._validate_outputs(agent_results)

            # =================================================================
            # ENHANCE WITH EXPLAINABILITY
            # =================================================================
            enhanced_results = self._enhance_explainability(agent_results, context)

            # =================================================================
            # BUILD ANALYSIS RESULT
            # =================================================================
            duration_ms = (time.time() - start_time) * 1000

            analysis = {
                "success": True,
                "analysis_id": analysis_id,
                "context": context,
                "analysis_timestamp": time.time(),
                "duration_ms": round(duration_ms, 2),
                "agents": enhanced_results,
                "summary": self._generate_summary(list(agent_results.values())),
                "recommendations": self._generate_recommendations(
                    list(agent_results.values()), context
                ),
                "validation_warnings": validation_warnings,
                "infrastructure": {
                    "cache_status": self.cache.get_stats(),
                    "circuit_breakers": self.circuit_registry.get_all_status(),
                    "rate_limit_usage": self.rate_limiter.get_usage(user_id),
                },
            }

            # =================================================================
            # RECORD METRICS AND AUDIT
            # =================================================================
            self.metrics.increment("analysis_completed", labels={"status": "success"})
            self.metrics.histogram("analysis_duration_ms", duration_ms)

            self.audit_trail.log(
                event_type="ai_analysis",
                user_id=user_id,
                operation="analyze_solution_context",
                context_summary=solution_description[:100],
                result_summary=f"{len(analysis['recommendations'])} recommendations",
                duration_ms=duration_ms,
                success=True,
                metadata={"analysis_id": analysis_id},
            )

            # Estimate and record cost (approximate tokens)
            estimated_tokens = len(solution_description) // 4 + 500  # Rough estimate
            self.cost_tracker.record_usage(
                operation="analyze_solution_context",
                agent="ai_reasoning_engine",
                tokens_input=estimated_tokens,
                tokens_output=estimated_tokens * 2,
                user_id=user_id,
            )

            # =================================================================
            # CACHE RESULT
            # =================================================================
            self.cache.set(context, analysis, ttl=3600)

            logger.info(f"AI reasoning analysis {analysis_id} completed in {duration_ms:.1f}ms")
            return analysis

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Error in AI reasoning analysis {analysis_id}: {e}")

            self.metrics.increment("analysis_completed", labels={"status": "error"})
            self.audit_trail.log(
                event_type="ai_analysis",
                user_id=user_id,
                operation="analyze_solution_context",
                context_summary=solution_description[:100] if solution_description else "",
                result_summary="",
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
                metadata={"analysis_id": analysis_id},
            )

            return {
                "success": False,
                "error": str(e),
                "context": context,
                "analysis_id": analysis_id,
            }

    async def _run_agents_with_resilience(self, context: Dict) -> Dict[str, Dict]:
        """Run all agents with circuit breaker protection."""
        agent_configs = [
            ("pattern_recognition", self.pattern_recognizer.recognize_patterns),
            ("tradeoff_analysis", self.tradeoff_analyzer.analyze_tradeoffs),
            ("risk_assessment", self.risk_assessor.assess_risks),
            ("technology_selection", self.tech_selector.recommend_technologies),
            ("quality_optimization", self.quality_optimizer.optimize_quality),
        ]

        async def run_with_breaker(name: str, func, ctx: Dict) -> tuple:
            breaker = self.agent_breakers[name]
            can_execute, reason = breaker.can_execute()

            if not can_execute:
                logger.warning(f"Circuit breaker {name} is open: {reason}")
                return name, {"error": reason, "circuit_breaker_open": True, "success": False}

            try:
                result = await func(ctx)
                breaker.record_success()
                return name, result
            except Exception as e:
                breaker.record_failure()
                logger.error(f"Agent {name} failed: {e}")
                return name, {"error": str(e), "success": False}

        # Run all agents in parallel
        tasks = [run_with_breaker(name, func, context) for name, func in agent_configs]
        results = await asyncio.gather(*tasks)

        return {name: result for name, result in results}

    def _validate_outputs(self, agent_results: Dict[str, Dict]) -> List[str]:
        """Validate agent outputs for consistency and quality."""
        warnings = []

        # Validate individual outputs
        if "pattern_recognition" in agent_results:
            valid, errors = OutputValidator.validate_pattern_recognition(
                agent_results["pattern_recognition"]
            )
            if not valid:
                warnings.extend([f"Pattern Recognition: {e}" for e in errors])

        if "risk_assessment" in agent_results:
            valid, errors = OutputValidator.validate_risk_assessment(
                agent_results["risk_assessment"]
            )
            if not valid:
                warnings.extend([f"Risk Assessment: {e}" for e in errors])

        if "technology_selection" in agent_results:
            valid, errors = OutputValidator.validate_technology_selection(
                agent_results["technology_selection"]
            )
            if not valid:
                warnings.extend([f"Technology Selection: {e}" for e in errors])

        # Cross-agent consistency check
        consistent, consistency_warnings = OutputValidator.check_cross_agent_consistency(
            agent_results
        )
        if not consistent:
            warnings.extend(consistency_warnings)

        return warnings

    def _enhance_explainability(
        self, agent_results: Dict[str, Dict], context: Dict
    ) -> Dict[str, Dict]:
        """Enhance agent results with explanations."""
        enhanced = {}

        for agent_name, result in agent_results.items():
            if not result.get("success", True) or "error" in result:
                enhanced[agent_name] = result
                continue

            enhanced_result = dict(result)

            # Enhance patterns with explanations
            if agent_name == "pattern_recognition" and "patterns" in result:
                enhanced_result["patterns"] = [
                    ExplainabilityEnhancer.explain_pattern_selection(p, context)
                    for p in result["patterns"]
                ]

            # Enhance risks with explanations
            elif agent_name == "risk_assessment" and "risks" in result:
                enhanced_result["risks"] = [
                    ExplainabilityEnhancer.explain_risk_score(r, context) for r in result["risks"]
                ]

            # Enhance technology choices with explanations
            elif agent_name == "technology_selection" and "recommendations" in result:
                enhanced_result["recommendations"] = [
                    ExplainabilityEnhancer.explain_technology_choice(t, context)
                    for t in result["recommendations"]
                ]

            enhanced[agent_name] = enhanced_result

        return enhanced

    def _generate_summary(self, results: List) -> Dict[str, Any]:
        """Generate executive summary from all agent results."""
        summary = {
            "overall_confidence": 0.0,
            "key_patterns": [],
            "primary_risks": [],
            "recommended_technologies": [],
            "quality_focus_areas": [],
        }

        # Extract key insights from each agent
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue

            agent_names = [
                "pattern_recognition",
                "tradeoff_analysis",
                "risk_assessment",
                "technology_selection",
                "quality_optimization",
            ]
            agent_name = agent_names[i]

            if agent_name == "pattern_recognition" and result.get("patterns"):
                summary["key_patterns"] = [p["name"] for p in result["patterns"][:3]]
                summary["overall_confidence"] = max(
                    summary["overall_confidence"], result.get("confidence", 0)
                )

            elif agent_name == "risk_assessment" and result.get("risks"):
                summary["primary_risks"] = [r["description"] for r in result["risks"][:3]]

            elif agent_name == "technology_selection" and result.get("recommendations"):
                summary["recommended_technologies"] = [
                    t["technology"] for t in result["recommendations"][:5]
                ]

            elif agent_name == "quality_optimization" and result.get("optimization_areas"):
                summary["quality_focus_areas"] = [
                    a["attribute"] for a in result["optimization_areas"][:3]
                ]

        return summary

    def _generate_recommendations(self, results: List, context: Dict) -> List[Dict]:
        """Generate actionable recommendations from all agent results."""
        recommendations = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue

            agent_names = [
                "pattern_recognition",
                "tradeoff_analysis",
                "risk_assessment",
                "technology_selection",
                "quality_optimization",
            ]
            agent_name = agent_names[i]

            if agent_name == "pattern_recognition" and result.get("patterns"):
                for pattern in result["patterns"][:2]:
                    recommendations.append(
                        {
                            "type": "architectural_pattern",
                            "priority": "high" if pattern.get("confidence", 0) > 0.8 else "medium",
                            "title": f"Adopt {pattern['name']} pattern",
                            "description": pattern.get("description", ""),
                            "rationale": pattern.get("rationale", ""),
                        }
                    )

            elif agent_name == "risk_assessment" and result.get("risks"):
                for risk in result["risks"][:2]:
                    recommendations.append(
                        {
                            "type": "risk_mitigation",
                            "priority": "high" if risk.get("impact", 0) > 0.7 else "medium",
                            "title": f"Mitigate: {risk['description']}",
                            "description": risk.get("mitigation", ""),
                            "rationale": f"Risk impact: {risk.get('impact', 0):.1f}",
                        }
                    )

            elif agent_name == "technology_selection" and result.get("recommendations"):
                for tech in result["recommendations"][:2]:
                    recommendations.append(
                        {
                            "type": "technology_choice",
                            "priority": "medium",
                            "title": f"Consider {tech['technology']}",
                            "description": tech.get("rationale", ""),
                            "rationale": f"Fit score: {tech.get('fit_score', 0):.1f}",
                        }
                    )

            elif agent_name == "quality_optimization" and result.get("optimization_areas"):
                for area in result["optimization_areas"][:2]:
                    recommendations.append(
                        {
                            "type": "quality_improvement",
                            "priority": "medium",
                            "title": f"Optimize {area['attribute']}",
                            "description": area.get("recommendation", ""),
                            "rationale": f"Current score: {area.get('current_score', 0):.1f}",
                        }
                    )

        return recommendations[:10]  # Limit to top 10 recommendations

    # =========================================================================
    # MONITORING & OBSERVABILITY METHODS
    # =========================================================================

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the AI reasoning engine."""
        circuit_status = self.circuit_registry.get_all_status()
        open_circuits = sum(1 for s in circuit_status.values() if s["state"] == "open")

        return {
            "status": "healthy"
            if open_circuits == 0
            else "degraded"
            if open_circuits < 3
            else "unhealthy",
            "agents": {
                name: {
                    "status": "available" if s["state"] == "closed" else "unavailable",
                    "failures": s["failure_count"],
                }
                for name, s in circuit_status.items()
            },
            "cache": self.cache.get_stats(),
            "cost": self.cost_tracker.get_summary(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics for monitoring dashboards."""
        return {
            "metrics": self.metrics.get_metrics(),
            "audit_stats": self.audit_trail.get_statistics(),
            "circuit_breakers": self.circuit_registry.get_all_status(),
            "cache_stats": self.cache.get_stats(),
            "cost_summary": self.cost_tracker.get_summary(),
        }

    def get_audit_log(
        self, user_id: str = None, operation: str = None, success: bool = None, limit: int = 100
    ) -> List[Dict]:
        """Get audit log entries."""
        return self.audit_trail.query(
            user_id=user_id,
            operation=operation,
            success=success,
            limit=limit,
        )

    def record_feedback(
        self,
        analysis_id: str,
        user_id: str,
        recommendation_type: str,
        recommendation_id: str,
        feedback_type: str,
        rating: int = None,
        comment: str = None,
    ):
        """Record user feedback on recommendations."""
        self.feedback_collector.record_feedback(
            analysis_id=analysis_id,
            user_id=user_id,
            recommendation_type=recommendation_type,
            recommendation_id=recommendation_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
        )

    def record_outcome(self, analysis_id: str, recommendation_id: str, outcome: str):
        """Record outcome of implemented recommendation."""
        return self.feedback_collector.record_outcome(analysis_id, recommendation_id, outcome)

    def get_feedback_stats(self, recommendation_type: str = None) -> Dict:
        """Get feedback statistics."""
        return self.feedback_collector.get_recommendation_stats(recommendation_type)

    def invalidate_cache(self, context: Dict = None):
        """Invalidate cache entries."""
        self.cache.invalidate(context)

    def reset_circuit_breakers(self):
        """Reset all circuit breakers (admin operation)."""
        for breaker in self.agent_breakers.values():
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
        logger.info("All circuit breakers reset")


# Import CircuitState for reset operation
from .ai_reasoning_infrastructure import CircuitState
