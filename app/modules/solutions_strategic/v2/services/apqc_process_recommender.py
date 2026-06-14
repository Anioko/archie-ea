"""
Phase 3: APQC Process Recommender Service

Maps enterprise solutions to APQC business process framework.
Recommends which business processes should be enhanced/updated based on solution.

Example:
  Solution: "Implement Salesforce CRM"
  → Recommends: Sell product/service, Manage customer relationships, Manage sales leads
"""

from typing import List, Dict, Any, Optional
from app import db
from app.models.solution_models import Solution
import logging

logger = logging.getLogger(__name__)


class APQCProcessRecommender:
    """Recommends APQC processes based on solution characteristics."""
    
    # APQC Process Reference Model (Level 1-2 hierarchy)
    PROCESS_HIERARCHY = {
        'Run Operations': {
            'Supply Chain Management': [
                'Plan supply chain',
                'Source materials/services',
                'Produce/manufacture products',
                'Deliver products/services',
                'Manage logistics'
            ],
            'Customer Service': [
                'Manage customer inquiries',
                'Manage customer complaints',
                'Manage field service',
                'Manage warranty/returns'
            ],
            'Revenue Management': [
                'Manage pricing and promotions',
                'Manage contracts',
                'Process orders',
                'Invoice and collect'
            ]
        },
        'Develop Vision & Strategy': {
            'Define Business Strategy': [
                'Define mission, vision, values',
                'Analyze market trends',
                'Conduct competitive analysis',
                'Set strategic objectives'
            ],
            'Develop Products & Services': [
                'Gather customer requirements',
                'Develop new products',
                'Test products',
                'Launch products'
            ]
        },
        'Enable & Support': {
            'Manage IT': [
                'Define IT strategy',
                'Manage IT infrastructure',
                'Manage data & information',
                'Manage security & compliance'
            ],
            'Manage HR': [
                'Recruit and hire',
                'Develop workforce',
                'Manage employee relations',
                'Manage compensation'
            ],
            'Manage Finance': [
                'Budget and forecast',
                'Manage accounting',
                'Manage tax',
                'Manage financial reporting'
            ]
        },
        'Manage Customers': {
            'Understand Customers': [
                'Analyze customer needs',
                'Conduct market research',
                'Manage customer relationships',
                'Gather customer feedback'
            ],
            'Market & Sell': [
                'Develop marketing strategy',
                'Manage lead generation',
                'Manage sales pipeline',
                'Manage customer relationships'
            ]
        }
    }
    
    # Domain-to-process mappings
    DOMAIN_PROCESS_MAP = {
        'Customer Management': [
            'Manage customer inquiries',
            'Manage customer complaints',
            'Manage customer relationships',
            'Process orders',
            'Manage sales pipeline'
        ],
        'Finance': [
            'Invoice and collect',
            'Manage accounting',
            'Budget and forecast',
            'Manage financial reporting',
            'Manage tax'
        ],
        'Human Resources': [
            'Recruit and hire',
            'Develop workforce',
            'Manage employee relations',
            'Manage compensation'
        ],
        'Supply Chain': [
            'Plan supply chain',
            'Source materials/services',
            'Produce/manufacture products',
            'Deliver products/services',
            'Manage logistics'
        ],
        'IT & Technology': [
            'Define IT strategy',
            'Manage IT infrastructure',
            'Manage data & information',
            'Manage security & compliance'
        ],
        'Marketing & Sales': [
            'Develop marketing strategy',
            'Manage lead generation',
            'Manage sales pipeline',
            'Manage customer relationships'
        ],
        'Operations': [
            'Supply Chain Management',
            'Customer Service',
            'Revenue Management'
        ],
        'Product Development': [
            'Gather customer requirements',
            'Develop new products',
            'Test products',
            'Launch products'
        ],
        'Strategy': [
            'Define mission, vision, values',
            'Analyze market trends',
            'Conduct competitive analysis',
            'Set strategic objectives'
        ]
    }
    
    def __init__(self):
        """Initialize APQC recommender."""
        self.process_hierarchy = self.PROCESS_HIERARCHY
        self.domain_map = self.DOMAIN_PROCESS_MAP
    
    def recommend_processes(
        self, 
        solution: Solution,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recommend APQC processes based on solution.
        
        Args:
            solution: Solution model instance
            limit: Max number of recommendations
            
        Returns:
            List of process recommendations with metadata
        """
        try:
            recommendations = []
            
            # Extract signals from solution
            domain = solution.business_domain or 'General'
            description = (solution.description or '').lower()
            name = (solution.name or '').lower()
            full_text = f"{name} {description}".lower()
            
            # Get processes from domain mapping
            domain_processes = self.domain_map.get(domain, [])
            
            # Enrich each process with relevance score and rationale
            for process in domain_processes:
                # Calculate relevance based on keywords
                relevance_score = self._calculate_relevance(process, full_text)
                
                if relevance_score > 0.3:  # Only include if meaningful match
                    recommendations.append({
                        'process_name': process,
                        'domain': domain,
                        'relevance_score': relevance_score,
                        'impact': self._estimate_impact(process, solution),
                        'implementation_complexity': self._estimate_complexity(process),
                        'expected_benefit': self._estimate_benefit(process, solution),
                        'rationale': self._generate_rationale(process, solution)
                    })
            
            # Sort by relevance score
            recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Return top N
            return recommendations[:limit]
        
        except Exception as e:
            logger.error(f"Error recommending APQC processes: {e}")
            return []
    
    def _calculate_relevance(self, process: str, full_text: str) -> float:
        """Calculate keyword match score (0.0-1.0)."""
        process_lower = process.lower()
        keywords = process_lower.split()
        
        matches = sum(1 for kw in keywords if kw in full_text)
        return min(1.0, matches / len(keywords)) if keywords else 0.0
    
    def _estimate_impact(self, process: str, solution: Solution) -> str:
        """Estimate business impact of this process."""
        high_impact_keywords = ['transform', 'automate', 'optimize', 'scale', 'growth']
        full_text = f"{solution.name} {solution.description}".lower()
        
        if any(kw in full_text for kw in high_impact_keywords):
            return 'HIGH'
        elif solution.estimated_cost and solution.estimated_cost > 1000000:
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def _estimate_complexity(self, process: str) -> str:
        """Estimate implementation complexity."""
        complex_keywords = ['manage', 'integration', 'automation', 'compliance']
        
        if any(kw in process.lower() for kw in complex_keywords):
            return 'High'
        else:
            return 'Medium'
    
    def _estimate_benefit(self, process: str, solution: Solution) -> Dict[str, Any]:
        """Estimate expected benefits from process enhancement."""
        return {
            'efficiency_gain': '15-30%',
            'cost_reduction': '10-20%',
            'cycle_time_reduction': '20-40%',
            'quality_improvement': '25-50%',
            'timeline_months': 6
        }
    
    def _generate_rationale(self, process: str, solution: Solution) -> str:
        """Generate human-readable rationale for recommendation."""
        domain = solution.business_domain or 'General'
        return (
            f"This {domain.lower()} solution aligns with '{process}' "
            f"process in the APQC framework. Enhancement recommended to "
            f"maximize ROI and operational efficiency."
        )
    
    def get_process_hierarchy(
        self, 
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve APQC process hierarchy.
        
        Args:
            category: Optional category filter (e.g., 'Run Operations')
            
        Returns:
            Process hierarchy structure
        """
        if category:
            return self.process_hierarchy.get(category, {})
        return self.process_hierarchy
    
    def validate_process_alignment(
        self,
        solution: Solution,
        target_processes: List[str]
    ) -> Dict[str, Any]:
        """
        Validate that solution aligns with target processes.
        
        Returns alignment assessment with gaps and recommendations.
        """
        try:
            recommendations = self.recommend_processes(solution, limit=20)
            recommended_names = [r['process_name'] for r in recommendations]
            
            # Find alignment and gaps
            aligned = [p for p in target_processes if p in recommended_names]
            gaps = [p for p in target_processes if p not in recommended_names]
            
            return {
                'solution_id': solution.id,
                'total_target_processes': len(target_processes),
                'aligned_count': len(aligned),
                'gap_count': len(gaps),
                'alignment_percentage': (len(aligned) / len(target_processes) * 100) if target_processes else 0,
                'aligned_processes': aligned,
                'gap_processes': gaps,
                'recommendations': recommendations[:5]
            }
        
        except Exception as e:
            logger.error(f"Error validating process alignment: {e}")
            return {
                'error': str(e),
                'alignment_percentage': 0
            }
