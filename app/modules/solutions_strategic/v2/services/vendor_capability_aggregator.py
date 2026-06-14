"""
Phase 3: Vendor Capability Aggregator Service

Unified vendor recommendation engine that:
- Matches solution requirements to vendor capabilities
- Scores vendors based on fit, cost, and references
- Identifies capability gaps
- Recommends vendor combinations
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app import db
from app.models.solution_models import Solution
import logging

logger = logging.getLogger(__name__)


@dataclass
class VendorScore:
    """Vendor scoring breakdown."""
    vendor_id: int
    vendor_name: str
    capability_fit: float  # 0.0-1.0
    cost_value: float      # 0.0-1.0
    market_presence: float # 0.0-1.0
    reliability_score: float # 0.0-1.0
    overall_score: float   # weighted average
    matched_capabilities: List[str]
    gap_capabilities: List[str]
    rationale: str


class VendorCapabilityAggregator:
    """Aggregates vendor data and generates unified recommendations."""
    
    # Core vendor capability categories
    CAPABILITY_CATEGORIES = {
        'CRM': ['Sales Automation', 'Customer Service', 'Marketing Automation', 'Analytics'],
        'ERP': ['Financial Management', 'Supply Chain', 'Inventory', 'HR Management'],
        'HCM': ['Recruitment', 'Learning & Development', 'Compensation', 'Analytics'],
        'BI/Analytics': ['Data Visualization', 'Reporting', 'Predictive Analytics', 'AI/ML'],
        'Cloud Platform': ['Infrastructure', 'Database', 'Security', 'Scalability'],
        'Integration': ['API Integration', 'Data Sync', 'Middleware', 'ETL'],
        'Security': ['Access Control', 'Encryption', 'Compliance', 'Threat Detection'],
        'Collaboration': ['Communication', 'Document Management', 'Project Management', 'Video Conferencing']
    }
    
    # Vendor profiles (stub - in production, loaded from database)
    VENDOR_PROFILES = {
        'Salesforce': {
            'capabilities': ['CRM', 'Cloud Platform', 'Integration', 'Analytics'],
            'cost_tier': 'Premium',
            'market_presence': 0.95,
            'reliability': 0.98,
            'typical_cost_range': '5000-50000/month'
        },
        'Microsoft Dynamics': {
            'capabilities': ['CRM', 'ERP', 'HCM', 'Cloud Platform'],
            'cost_tier': 'Enterprise',
            'market_presence': 0.93,
            'reliability': 0.96,
            'typical_cost_range': '10000-100000/month'
        },
        'SAP': {
            'capabilities': ['ERP', 'BI/Analytics', 'Supply Chain'],
            'cost_tier': 'Enterprise',
            'market_presence': 0.92,
            'reliability': 0.97,
            'typical_cost_range': '50000-500000/month'
        },
        'Workday': {
            'capabilities': ['HCM', 'Cloud Platform', 'Analytics', 'Integration'],
            'cost_tier': 'Enterprise',
            'market_presence': 0.89,
            'reliability': 0.95,
            'typical_cost_range': '20000-200000/month'
        },
        'Tableau': {
            'capabilities': ['BI/Analytics', 'Data Visualization'],
            'cost_tier': 'Mid-Market',
            'market_presence': 0.88,
            'reliability': 0.94,
            'typical_cost_range': '2000-20000/month'
        },
        'Atlassian': {
            'capabilities': ['Collaboration', 'Project Management', 'Integration'],
            'cost_tier': 'SMB',
            'market_presence': 0.85,
            'reliability': 0.93,
            'typical_cost_range': '500-10000/month'
        },
        'Slack': {
            'capabilities': ['Collaboration', 'Communication', 'Integration'],
            'cost_tier': 'SMB',
            'market_presence': 0.87,
            'reliability': 0.92,
            'typical_cost_range': '300-5000/month'
        },
        'AWS': {
            'capabilities': ['Cloud Platform', 'Security', 'Integration'],
            'cost_tier': 'Variable',
            'market_presence': 0.94,
            'reliability': 0.99,
            'typical_cost_range': '1000-1000000+/month'
        }
    }
    
    def __init__(self):
        """Initialize vendor aggregator."""
        self.vendors = self.VENDOR_PROFILES
        self.capabilities = self.CAPABILITY_CATEGORIES
    
    def recommend_vendors(
        self,
        solution: Solution,
        limit: int = 5,
        cost_constraint: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend vendors for solution.
        
        Args:
            solution: Solution model instance
            limit: Max number of recommendations
            cost_constraint: Optional max monthly cost
            
        Returns:
            Ranked list of vendor recommendations with scores
        """
        try:
            # Extract required capabilities from solution
            required_capabilities = self._extract_capabilities(solution)
            
            # Score each vendor
            scores = []
            for vendor_name, vendor_profile in self.vendors.items():
                score = self._score_vendor(
                    vendor_name,
                    vendor_profile,
                    required_capabilities,
                    cost_constraint
                )
                
                if score:
                    scores.append(score)
            
            # Sort by overall score
            scores.sort(key=lambda x: x.overall_score, reverse=True)
            
            # Convert to dict and return top N
            return [
                {
                    'vendor_name': s.vendor_name,
                    'vendor_id': s.vendor_id,
                    'overall_score': round(s.overall_score, 3),
                    'capability_fit': round(s.capability_fit, 3),
                    'cost_value': round(s.cost_value, 3),
                    'market_presence': round(s.market_presence, 3),
                    'reliability_score': round(s.reliability_score, 3),
                    'matched_capabilities': s.matched_capabilities,
                    'gap_capabilities': s.gap_capabilities,
                    'rationale': s.rationale
                }
                for s in scores[:limit]
            ]
        
        except Exception as e:
            logger.error(f"Error recommending vendors: {e}")
            return []
    
    def _extract_capabilities(self, solution: Solution) -> List[str]:
        """Extract required capabilities from solution description."""
        domain = solution.business_domain or 'General'
        description = (solution.description or '').lower()
        name = (solution.name or '').lower()
        full_text = f"{domain} {name} {description}".lower()
        
        matched_capabilities = []
        
        # Search for capability keywords
        capability_keywords = {
            'CRM': ['salesforce', 'crm', 'customer relationship', 'customer management'],
            'ERP': ['erp', 'enterprise resource', 'sap', 'dynamics', 'financials'],
            'HCM': ['hcm', 'hr', 'human capital', 'workforce', 'recruitment', 'workday'],
            'BI/Analytics': ['analytics', 'bi', 'business intelligence', 'dashboard', 'tableau', 'reporting'],
            'Cloud Platform': ['cloud', 'aws', 'azure', 'gcp', 'infrastructure', 'iaas'],
            'Integration': ['integration', 'api', 'middleware', 'etl', 'sync'],
            'Security': ['security', 'compliance', 'encryption', 'access control'],
            'Collaboration': ['collaboration', 'communication', 'slack', 'teams', 'project management']
        }
        
        for category, keywords in capability_keywords.items():
            if any(kw in full_text for kw in keywords):
                matched_capabilities.append(category)
        
        return matched_capabilities if matched_capabilities else ['Cloud Platform', 'Integration']
    
    def _score_vendor(
        self,
        vendor_name: str,
        vendor_profile: Dict[str, Any],
        required_capabilities: List[str],
        cost_constraint: Optional[int] = None
    ) -> Optional[VendorScore]:
        """Score a single vendor against requirements."""
        try:
            # Check cost constraint
            if cost_constraint:
                # Simple heuristic: higher tier = higher cost
                tier_cost_map = {
                    'SMB': 5000,
                    'Mid-Market': 15000,
                    'Premium': 25000,
                    'Enterprise': 75000,
                    'Variable': 50000
                }
                estimated_cost = tier_cost_map.get(vendor_profile['cost_tier'], 25000)
                if estimated_cost > cost_constraint:
                    return None  # Filtered out by cost
            
            # Calculate capability fit
            vendor_capabilities = vendor_profile.get('capabilities', [])
            matched = [c for c in required_capabilities if c in vendor_capabilities]
            gaps = [c for c in required_capabilities if c not in vendor_capabilities]
            
            capability_fit = (
                len(matched) / len(required_capabilities)
                if required_capabilities
                else 0.5
            )
            
            # Cost value (inverse - cheaper = higher value)
            cost_value = 1.0 if vendor_profile['cost_tier'] == 'SMB' else \
                        0.8 if vendor_profile['cost_tier'] == 'Mid-Market' else \
                        0.6 if vendor_profile['cost_tier'] in ['Premium', 'Enterprise'] else 0.5
            
            # Market presence (already in profile)
            market_presence = vendor_profile.get('market_presence', 0.7)
            
            # Reliability (already in profile)
            reliability_score = vendor_profile.get('reliability', 0.9)
            
            # Weighted overall score
            overall_score = (
                capability_fit * 0.40 +
                market_presence * 0.25 +
                reliability_score * 0.20 +
                cost_value * 0.15
            )
            
            return VendorScore(
                vendor_id=hash(vendor_name) % 10000,
                vendor_name=vendor_name,
                capability_fit=capability_fit,
                cost_value=cost_value,
                market_presence=market_presence,
                reliability_score=reliability_score,
                overall_score=overall_score,
                matched_capabilities=matched,
                gap_capabilities=gaps,
                rationale=self._generate_vendor_rationale(
                    vendor_name,
                    matched,
                    gaps,
                    vendor_profile
                )
            )
        
        except Exception as e:
            logger.error(f"Error scoring vendor {vendor_name}: {e}")
            return None
    
    def _generate_vendor_rationale(
        self,
        vendor_name: str,
        matched_capabilities: List[str],
        gap_capabilities: List[str],
        vendor_profile: Dict[str, Any]
    ) -> str:
        """Generate human-readable recommendation rationale."""
        parts = [
            f"{vendor_name} provides {', '.join(matched_capabilities[:2])} capabilities"
        ]
        
        if gap_capabilities:
            parts.append(f"with optional {', '.join(gap_capabilities[:1])} through integrations")
        
        parts.append(f"({vendor_profile['cost_tier']} tier).")
        
        return ' '.join(parts)
    
    def recommend_vendor_combination(
        self,
        solution: Solution,
        max_vendors: int = 3
    ) -> Dict[str, Any]:
        """
        Recommend a combination of vendors to cover all capabilities.
        
        Useful for best-of-breed approach.
        """
        try:
            required_capabilities = self._extract_capabilities(solution)
            recommendations = self.recommend_vendors(solution, limit=10)
            
            # Greedy algorithm: select vendors covering most uncovered capabilities
            selected = []
            covered_capabilities = set()
            
            for vendor in recommendations:
                if len(selected) >= max_vendors:
                    break
                
                new_capabilities = set(vendor['matched_capabilities']) - covered_capabilities
                
                if new_capabilities or len(selected) == 0:
                    selected.append(vendor)
                    covered_capabilities.update(vendor['matched_capabilities'])
            
            remaining_gaps = set(required_capabilities) - covered_capabilities
            
            return {
                'solution_id': solution.id,
                'approach': 'best_of_breed' if len(selected) > 1 else 'single_vendor',
                'recommended_vendors': selected,
                'coverage_percentage': (
                    len(covered_capabilities) / len(required_capabilities) * 100
                    if required_capabilities else 0
                ),
                'uncovered_capabilities': list(remaining_gaps),
                'estimated_total_cost': self._estimate_total_cost(selected)
            }
        
        except Exception as e:
            logger.error(f"Error recommending vendor combination: {e}")
            return {'error': str(e)}
    
    def _estimate_total_cost(self, vendors: List[Dict[str, Any]]) -> str:
        """Estimate combined monthly cost."""
        tier_costs = {
            'SMB': 3000,
            'Mid-Market': 15000,
            'Premium': 25000,
            'Enterprise': 75000
        }
        
        # This is simplified - in production would use actual vendor pricing
        total = sum(
            tier_costs.get(vendor.get('cost_tier', 'Mid-Market'), 15000)
            for vendor in vendors
        )
        
        return f"${total:,}/month estimated"
    
    def identify_capability_gaps(
        self,
        solution: Solution,
        recommended_vendors: List[str]
    ) -> Dict[str, Any]:
        """Identify capability gaps after vendor selection."""
        try:
            required_capabilities = self._extract_capabilities(solution)
            
            # Aggregate covered capabilities from selected vendors
            covered = set()
            for vendor_name in recommended_vendors:
                if vendor_name in self.vendors:
                    vendor_caps = self.vendors[vendor_name].get('capabilities', [])
                    covered.update(vendor_caps)
            
            gaps = [c for c in required_capabilities if c not in covered]
            
            return {
                'required_capabilities': required_capabilities,
                'covered_count': len(covered),
                'gap_count': len(gaps),
                'gaps': gaps,
                'mitigation_options': self._suggest_gap_mitigation(gaps)
            }
        
        except Exception as e:
            logger.error(f"Error identifying capability gaps: {e}")
            return {'error': str(e)}
    
    def _suggest_gap_mitigation(self, gaps: List[str]) -> List[Dict[str, str]]:
        """Suggest ways to mitigate capability gaps."""
        return [
            {
                'gap': gap,
                'option1': f'Use specialized {gap} vendor',
                'option2': 'Build custom integration',
                'option3': 'Implement open-source solution'
            }
            for gap in gaps[:3]
        ]
