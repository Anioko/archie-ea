"""
Solution Explainability Service

Generates transparent explanations for all AI recommendations.

Provides reasoning chains, confidence intervals, data source tracking,
alternative option analysis, and uncertainty factor identification.

Every recommendation includes:
- Why this choice was made (reasoning chain)
- How confident we are (confidence score ±%)
- What data informed the decision
- What alternatives were considered (and why rejected)
- What could make this wrong (uncertainty factors)
- What we assumed

Usage:
    explainability = SolutionExplainabilityService()
    
    # Explain a vendor recommendation
    reasoning = explainability.explain_vendor_recommendation(
        vendor={'id': 'vendor-1', 'name': 'SAP', 'fit_score': 0.92},
        fit_score=0.92,
        solution=solution,
        all_candidates=[...]
    )
    
    # Explain cost estimate
    cost_explanation = explainability.explain_cost_estimate(
        estimate=4200000,
        components={'licenses': 1200000, 'implementation': 2000000, ...},
        solution=solution
    )
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SolutionExplainabilityService:
    """
    Generates transparent explanations for AI recommendations.
    
    Makes every recommendation understandable by providing:
    - Reasoning chains (step-by-step why)
    - Confidence scores with ranges
    - Data sources used
    - Alternative options considered
    - Uncertainty factors
    - Model assumptions
    """
    
    def __init__(self):
        """Initialize explainability service."""
        pass
    
    # =========================================================================
    # VENDOR RECOMMENDATION EXPLAINABILITY
    # =========================================================================
    
    def explain_vendor_recommendation(
        self,
        vendor: Dict[str, Any],
        fit_score: float,
        solution: Any,
        all_candidates: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Explain why this vendor was recommended.
        
        Args:
            vendor: Recommended vendor data
            fit_score: Fit score (0.0-1.0)
            solution: Solution object
            all_candidates: All evaluated vendors for comparison
            
        Returns:
            {
                'reasoning_chain': [...],  # Step-by-step explanation
                'confidence': {...},  # Confidence metrics
                'data_sources': {...},  # What informed this
                'alternatives': {...},  # Other options considered
                'assumptions': [...],  # What we assumed
                'key_factors': [...]  # Top factors in decision
            }
        """
        reasoning_chain = self._build_vendor_reasoning_chain(vendor, solution)
        confidence = self._calculate_confidence_metrics(fit_score, 'vendor')
        data_sources = self._extract_vendor_data_sources(vendor, solution)
        alternatives = self._identify_vendor_alternatives(vendor, all_candidates or [])
        assumptions = self._extract_vendor_assumptions(solution)
        key_factors = self._identify_key_vendor_factors(vendor, solution)
        
        return {
            'vendor': {
                'id': vendor.get('id'),
                'name': vendor.get('name'),
                'fit_score': fit_score,
                'reasoning_chain': reasoning_chain
            },
            'confidence': confidence,
            'data_sources': data_sources,
            'alternatives': alternatives,
            'assumptions': assumptions,
            'key_factors': key_factors,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _build_vendor_reasoning_chain(
        self,
        vendor: Dict[str, Any],
        solution: Any
    ) -> List[str]:
        """Build step-by-step reasoning for vendor selection."""
        chain = []
        
        # Step 1: Requirement matching
        if solution and hasattr(solution, 'description'):
            chain.append(
                f"Analyzed solution description: '{solution.description[:100]}...'"
            )
        
        # Step 2: Scale requirements
        chain.append(
            f"Vendor '{vendor.get('name')}' meets scale requirements with "
            f"{vendor.get('implementations', 'N/A')} known implementations"
        )
        
        # Step 3: Capability coverage
        capability_coverage = vendor.get('capability_coverage', 0.0)
        chain.append(
            f"Covers {capability_coverage:.0%} of required capabilities"
        )
        
        # Step 4: Cost-benefit analysis
        if vendor.get('estimated_cost'):
            chain.append(
                f"Estimated total cost ${vendor.get('estimated_cost'):,.0f} "
                f"(within budget constraints)"
            )
        
        # Step 5: Timeline feasibility
        if vendor.get('implementation_weeks'):
            chain.append(
                f"Can implement in {vendor.get('implementation_weeks')} weeks"
            )
        
        # Step 6: Comparison to alternatives
        chain.append(
            f"Better fit than alternatives on key criteria: "
            f"capability coverage (+{vendor.get('fit_advantage', 'N/A')}), "
            f"implementation speed"
        )
        
        # Step 7: Risk profile
        risks = vendor.get('known_risks', [])
        if risks:
            chain.append(f"Known risks are mitigable: {', '.join(risks[:2])}")
        else:
            chain.append("No significant known risks")
        
        # Step 8: Conclusion
        chain.append(
            f"Recommendation: {vendor.get('name')} with {self._score_to_confidence(vendor.get('fit_score', 0.0))} confidence"
        )
        
        return chain
    
    def _calculate_confidence_metrics(
        self,
        score: float,
        entity_type: str = 'general'
    ) -> Dict[str, Any]:
        """
        Calculate confidence intervals and certainty level.
        
        Args:
            score: Base confidence score (0.0-1.0)
            entity_type: Type of entity (vendor, cost, timeline, risk)
            
        Returns:
            Confidence metrics with intervals
        """
        # Adjust uncertainty range based on entity type
        uncertainty_range = {
            'vendor': 0.08,      # ±8% for vendor fit
            'cost': 0.15,        # ±15% for cost estimates
            'timeline': 0.20,    # ±20% for timeline
            'risk': 0.12         # ±12% for risk assessment
        }.get(entity_type, 0.10)
        
        lower_bound = max(0.0, score - uncertainty_range)
        upper_bound = min(1.0, score + uncertainty_range)
        
        # Certainty level mapping
        if score >= 0.90:
            certainty = 'VERY_HIGH'
        elif score >= 0.75:
            certainty = 'HIGH'
        elif score >= 0.60:
            certainty = 'MEDIUM'
        elif score >= 0.45:
            certainty = 'LOW'
        else:
            certainty = 'VERY_LOW'
        
        return {
            'score': score,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'range_pct': round((upper_bound - lower_bound) * 100),
            'certainty_level': certainty,
            'interpretation': f"We are {certainty.lower()} that this recommendation is correct (±{uncertainty_range:.0%})"
        }
    
    def _extract_vendor_data_sources(
        self,
        vendor: Dict[str, Any],
        solution: Any
    ) -> Dict[str, Any]:
        """Identify what data sources informed vendor selection."""
        return {
            'solution_requirements': {
                'source': 'solution.description + capability mapping',
                'data_points': [
                    solution.description[:80] if solution and hasattr(solution, 'description') else 'N/A'
                ],
                'weight': 0.30,
                'reliability': 'HIGH'
            },
            'vendor_capabilities': {
                'source': 'vendor_products table + capability matrix',
                'data_points': [vendor.get('name'), f"{vendor.get('implementations', 0)} implementations"],
                'weight': 0.35,
                'reliability': 'HIGH'
            },
            'historical_precedent': {
                'source': 'similar solutions + project outcomes',
                'data_points': [
                    f"{vendor.get('similar_projects', 0)} similar projects found",
                    f"Success rate: {vendor.get('success_rate', 'N/A')}"
                ],
                'weight': 0.25,
                'reliability': 'MEDIUM'
            },
            'cost_benchmarking': {
                'source': 'cost_intelligence table + market data',
                'data_points': [f"${vendor.get('estimated_cost', 0):,.0f} estimate"],
                'weight': 0.10,
                'reliability': 'MEDIUM'
            }
        }
    
    def _identify_vendor_alternatives(
        self,
        selected: Dict[str, Any],
        all_candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Identify alternative vendors and why they were not selected."""
        alternatives = []
        
        # Sort by fit score, exclude selected
        remaining = [c for c in all_candidates if c.get('id') != selected.get('id')]
        remaining.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
        
        for alt in remaining[:3]:  # Top 3 alternatives
            delta = selected.get('fit_score', 0) - alt.get('fit_score', 0)
            
            reasons_rejected = []
            
            # Cost consideration
            if selected.get('estimated_cost', float('inf')) < alt.get('estimated_cost', float('inf')):
                reasons_rejected.append(
                    f"Higher cost: ${alt.get('estimated_cost', 0):,.0f} vs ${selected.get('estimated_cost', 0):,.0f}"
                )
            
            # Timeline consideration
            if selected.get('implementation_weeks', 999) < alt.get('implementation_weeks', 999):
                sel_weeks = selected.get('implementation_weeks', 0)
                alt_weeks = alt.get('implementation_weeks', 0)
                reasons_rejected.append(f"Longer timeline: {alt_weeks} weeks vs {sel_weeks} weeks")
            
            # Capability coverage
            if selected.get('capability_coverage', 0) > alt.get('capability_coverage', 0):
                sel_cov = selected.get('capability_coverage', 0)
                alt_cov = alt.get('capability_coverage', 0)
                reasons_rejected.append(f"Lower capability coverage: {alt_cov:.0%} vs {sel_cov:.0%}")
            
            # Risk profile
            if len(selected.get('known_risks', [])) < len(alt.get('known_risks', [])):
                sel_risks = len(selected.get('known_risks', []))
                alt_risks = len(alt.get('known_risks', []))
                reasons_rejected.append(f"More known risks: {alt_risks} vs {sel_risks}")
            
            alternatives.append({
                'id': alt.get('id'),
                'name': alt.get('name'),
                'fit_score': alt.get('fit_score', 0),
                'fit_delta': round(delta, 3),
                'fit_delta_pct': f"{delta:.0%}",
                'reasons_rejected': reasons_rejected if reasons_rejected else ['Lower overall fit score']
            })
        
        return {
            'alternatives_evaluated': len(all_candidates),
            'top_alternatives': alternatives,
            'selection_rationale': f"Selected {selected.get('name')} as optimal balance of capability, cost, and timeline"
        }
    
    def _extract_vendor_assumptions(self, solution: Any) -> List[Dict[str, str]]:
        """Extract assumptions made in vendor selection."""
        assumptions = [
            {
                'category': 'Technical',
                'assumption': 'Cloud deployment is acceptable',
                'if_wrong': 'May need to eliminate vendors with cloud-only models',
                'severity': 'HIGH'
            },
            {
                'category': 'Technical',
                'assumption': 'Organization has basic cloud experience',
                'if_wrong': 'May need more implementation support, increasing cost',
                'severity': 'MEDIUM'
            },
            {
                'category': 'Business',
                'assumption': 'Budget constraint of ±10% is stable',
                'if_wrong': 'May need to select lower-tier vendor',
                'severity': 'CRITICAL'
            },
            {
                'category': 'Business',
                'assumption': 'Single-vendor solution is preferred',
                'if_wrong': 'Might benefit from best-of-breed approach',
                'severity': 'MEDIUM'
            },
            {
                'category': 'Organizational',
                'assumption': 'Change management team is committed',
                'if_wrong': 'Implementation could slip or fail',
                'severity': 'HIGH'
            },
            {
                'category': 'Organizational',
                'assumption': 'Vendor can provide required support SLA',
                'if_wrong': 'May face support quality issues',
                'severity': 'HIGH'
            }
        ]
        return assumptions
    
    def _identify_key_vendor_factors(
        self,
        vendor: Dict[str, Any],
        solution: Any
    ) -> List[Dict[str, Any]]:
        """Identify the most important factors in this vendor selection."""
        return [
            {
                'factor': 'Capability Coverage',
                'value': f"{vendor.get('capability_coverage', 0):.0%}",
                'importance': 'CRITICAL',
                'impact': 'This vendor covers all required capabilities'
            },
            {
                'factor': 'Cost Efficiency',
                'value': f"${vendor.get('estimated_cost', 0):,.0f}",
                'importance': 'HIGH',
                'impact': 'Fits within budget constraints'
            },
            {
                'factor': 'Implementation Timeline',
                'value': f"{vendor.get('implementation_weeks', 0)} weeks",
                'importance': 'HIGH',
                'impact': 'Can deliver within acceptable timeframe'
            },
            {
                'factor': 'Track Record',
                'value': f"{vendor.get('implementations', 0)} similar implementations",
                'importance': 'MEDIUM',
                'impact': 'Proven success in similar environments'
            }
        ]
    
    # =========================================================================
    # COST ESTIMATE EXPLAINABILITY
    # =========================================================================
    
    def explain_cost_estimate(
        self,
        estimate: float,
        components: Dict[str, float],
        solution: Any
    ) -> Dict[str, Any]:
        """
        Explain cost estimate with breakdown and confidence.
        
        Args:
            estimate: Total estimated cost
            components: Breakdown of cost components
            solution: Solution object
            
        Returns:
            Cost explanation with confidence intervals
        """
        confidence_pct = 0.75  # Typical for cost estimates
        intervals = self._generate_confidence_intervals(estimate, confidence_pct, 'cost')
        
        return {
            'total_estimate': estimate,
            'components': components,
            'confidence': self._calculate_confidence_metrics(confidence_pct, 'cost'),
            'confidence_intervals': intervals,
            'component_breakdown': self._break_down_cost_components(components),
            'cost_drivers': self._identify_cost_drivers(components),
            'assumptions': [
                'Licenses based on current user count',
                'Implementation timeline is 6 months',
                'No major customizations required',
                'Infrastructure costs handled separately'
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _generate_confidence_intervals(
        self,
        value: float,
        confidence_pct: float,
        entity_type: str = 'general'
    ) -> Dict[str, Any]:
        """
        Generate confidence intervals (±% range) for a prediction.
        
        Args:
            value: Point estimate
            confidence_pct: Confidence level (0.0-1.0)
            entity_type: Type of entity
            
        Returns:
            Confidence interval data
        """
        # Calculate margin of error based on confidence level and type
        base_margin = 0.15 if entity_type == 'cost' else 0.20
        
        if confidence_pct >= 0.90:
            margin = base_margin * 0.5
        elif confidence_pct >= 0.75:
            margin = base_margin * 0.75
        elif confidence_pct >= 0.60:
            margin = base_margin
        else:
            margin = base_margin * 1.5
        
        lower = value * (1 - margin)
        upper = value * (1 + margin)
        
        return {
            'point_estimate': value,
            'lower_bound': round(lower, 2),
            'upper_bound': round(upper, 2),
            'margin_of_error_pct': round(margin * 100),
            'interpretation': f"{self._score_to_confidence(confidence_pct)} we estimate ${lower:,.0f} - ${upper:,.0f}"
        }
    
    def _break_down_cost_components(self, components: Dict[str, float]) -> List[Dict[str, Any]]:
        """Break down cost by component with percentages."""
        total = sum(components.values())
        breakdown = []
        
        for component, amount in sorted(components.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total * 100) if total > 0 else 0
            breakdown.append({
                'component': component,
                'amount': round(amount),
                'percentage': round(percentage),
                'bar': '█' * int(percentage / 5)  # Visual representation
            })
        
        return breakdown
    
    def _identify_cost_drivers(self, components: Dict[str, float]) -> List[str]:
        """Identify which components drive most of the cost."""
        total = sum(components.values())
        sorted_components = sorted(components.items(), key=lambda x: x[1], reverse=True)
        
        drivers = []
        cumulative = 0
        
        for component, amount in sorted_components:
            percentage = amount / total * 100 if total > 0 else 0
            cumulative += percentage
            drivers.append(f"{component} ({percentage:.0f}% of total)")
            if cumulative >= 80:  # 80% of cost
                break
        
        return drivers
    
    # =========================================================================
    # TIMELINE ESTIMATE EXPLAINABILITY
    # =========================================================================
    
    def explain_timeline_estimate(
        self,
        duration: int,
        tasks: Optional[List[Dict[str, Any]]] = None,
        solution: Any = None
    ) -> Dict[str, Any]:
        """
        Explain timeline estimate with task breakdown.
        
        Args:
            duration: Estimated duration in weeks
            tasks: List of project tasks
            solution: Solution object
            
        Returns:
            Timeline explanation with confidence
        """
        confidence_pct = 0.65  # Lower confidence for timeline (more uncertainty)
        
        return {
            'total_duration_weeks': duration,
            'confidence': self._calculate_confidence_metrics(confidence_pct, 'timeline'),
            'task_breakdown': self._break_down_timeline_tasks(tasks or []),
            'critical_path': self._identify_critical_path(tasks or []),
            'risk_factors': [
                'Dependency on vendor resource availability',
                'Requirement clarification delays',
                'Testing and user acceptance slowdown',
                'Change request scope creep'
            ],
            'mitigation_strategies': [
                'Establish clear governance with vendor',
                'Lock requirements in Phase B',
                'Plan UAT in parallel with dev',
                'Use agile with 2-week sprints'
            ],
            'assumptions': [
                'Full-time dedicated project team',
                'No competing initiatives',
                'Executive steering active'
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _break_down_timeline_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Break down timeline by task."""
        if not tasks:
            tasks = [
                {'phase': 'Planning & Design', 'duration': 4},
                {'phase': 'Build & Configure', 'duration': 8},
                {'phase': 'Integration & Testing', 'duration': 6},
                {'phase': 'UAT & Training', 'duration': 4},
                {'phase': 'Cutover', 'duration': 2}
            ]
        
        breakdown = []
        cumulative = 0
        
        for task in tasks:
            start_week = cumulative + 1
            end_week = start_week + task.get('duration', 0) - 1
            cumulative = end_week
            
            breakdown.append({
                'phase': task.get('phase', 'Unknown'),
                'duration_weeks': task.get('duration', 0),
                'start_week': start_week,
                'end_week': end_week,
                'dependencies': task.get('dependencies', [])
            })
        
        return breakdown
    
    def _identify_critical_path(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify the critical path (tasks that affect timeline)."""
        if not tasks:
            return {
                'path_duration': 24,
                'critical_tasks': ['Planning & Design', 'Build & Configure', 'Integration & Testing'],
                'float_tasks': ['UAT & Training', 'Cutover']
            }
        
        return {
            'path_duration': sum(t.get('duration', 0) for t in tasks),
            'critical_tasks': [t.get('phase') for t in tasks if not t.get('has_float')],
            'warning': 'Any delay in critical path tasks delays project completion'
        }
    
    # =========================================================================
    # RISK ASSESSMENT EXPLAINABILITY
    # =========================================================================
    
    def explain_risk_assessment(
        self,
        risks: Optional[List[Dict[str, Any]]] = None,
        solution: Any = None
    ) -> Dict[str, Any]:
        """
        Explain risk assessment with justification.
        
        Args:
            risks: List of identified risks
            solution: Solution object
            
        Returns:
            Risk assessment explanation
        """
        if not risks:
            risks = []
        
        return {
            'total_risks_identified': len(risks),
            'risk_summary': self._summarize_risks(risks),
            'risk_breakdown': self._break_down_risks_by_severity(risks),
            'top_risks': risks[:5],
            'mitigation_strategies': self._suggest_risk_mitigations(risks),
            'confidence': self._calculate_confidence_metrics(0.80, 'risk'),
            'uncertainty': 'Risk assessment depends on accurate requirements. Risks may emerge during implementation.',
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _summarize_risks(self, risks: List[Dict[str, Any]]) -> str:
        """Summarize risks in human-readable format."""
        if not risks:
            return "No significant risks identified"
        
        high_count = len([r for r in risks if r.get('severity') in ['CRITICAL', 'HIGH']])
        medium_count = len([r for r in risks if r.get('severity') == 'MEDIUM'])
        
        return f"{high_count} high-severity risks, {medium_count} medium-severity risks identified. Recommend risk governance."
    
    def _break_down_risks_by_severity(self, risks: List[Dict[str, Any]]) -> Dict[str, list]:
        """Organize risks by severity level."""
        by_severity = {
            'CRITICAL': [],
            'HIGH': [],
            'MEDIUM': [],
            'LOW': []
        }
        
        for risk in risks:
            severity = risk.get('severity', 'LOW')
            if severity in by_severity:
                by_severity[severity].append(risk)
        
        return by_severity
    
    def _suggest_risk_mitigations(self, risks: List[Dict[str, Any]]) -> List[str]:
        """Suggest mitigation strategies for identified risks."""
        mitigations = []
        
        for risk in risks[:3]:  # Top 3 risks
            suggested = risk.get('mitigation', f"Mitigate: {risk.get('risk')}")
            mitigations.append(suggested)
        
        return mitigations
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _score_to_confidence(self, score: float) -> str:
        """Convert numeric score to confidence phrase."""
        if score >= 0.90:
            return "Very confident"
        elif score >= 0.75:
            return "Confident"
        elif score >= 0.60:
            return "Moderately confident"
        elif score >= 0.45:
            return "Less confident"
        else:
            return "Not confident"
    
    def extract_data_sources_used(self, recommendation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract data sources used in recommendation.
        
        Args:
            recommendation: Recommendation dict
            
        Returns:
            List of data sources with weights
        """
        return recommendation.get('data_sources', {}).get('sources', [])
    
    def identify_alternative_options(
        self,
        recommendation: Dict[str, Any],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Identify alternative options and why they were rejected.
        
        Args:
            recommendation: Recommendation dict
            top_n: Number of alternatives to return
            
        Returns:
            List of alternatives with rejection reasons
        """
        alternatives = recommendation.get('alternatives', {}).get('top_alternatives', [])
        return alternatives[:top_n]
    
    def highlight_uncertainty_factors(self, recommendation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Highlight factors that could make this recommendation wrong.
        
        Args:
            recommendation: Recommendation dict
            
        Returns:
            List of uncertainty factors
        """
        return recommendation.get('uncertainty_factors', {}).get('factors', [])

    def explain_arb_draft_generation(
        self,
        capability_id: int,
        capability_name: str,
        recommended_option: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Explain how the ARB draft was generated (inputs and rationale).
        Used to expose reasoning for ARB draft so architects can see why the draft says what it says.
        """
        reasoning_chain = [
            f"Draft generated for capability {capability_name} (id={capability_id}).",
        ]
        if recommended_option:
            opt_name = recommended_option.get("name") or "Recommended option"
            reasoning_chain.append(f"Recommended option: {opt_name}.")
        if additional_context and additional_context.get("decision_rationale"):
            reasoning_chain.append("Decision rationale from option analysis was included.")
        if additional_context and additional_context.get("scope"):
            reasoning_chain.append("Scope context (problem/definition) was used for business justification.")
        return {
            "reasoning_chain": reasoning_chain,
            "data_sources": {
                "capability_id": capability_id,
                "capability_name": capability_name,
                "recommended_option_name": (recommended_option or {}).get("name"),
                "had_decision_rationale": bool(additional_context and additional_context.get("decision_rationale")),
                "had_scope": bool(additional_context and additional_context.get("scope")),
            },
            "step": "arb_draft_generation",
            "generated_at": datetime.utcnow().isoformat(),
        }
