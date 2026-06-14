"""
AI Chat Extension Services

Extended capabilities for the Multi-Domain AI Chat system including:
- Visual Generation (diagrams, maps, graphs)
- What-If Scenario Analysis
- Automated Actions
- Advanced Analytics
- Compliance & Standards Checking
- Predictive Insights
"""

from .advanced_analytics_service import AdvancedAnalyticsService
from .automated_actions_service import AutomatedActionsService
from .compliance_standards_service import ComplianceStandardsService
from .predictive_insights_service import PredictiveInsightsService
from .scenario_analysis_service import ScenarioAnalysisService
from .visual_generation_service import VisualGenerationService

__all__ = [
    "VisualGenerationService",
    "ScenarioAnalysisService",
    "AutomatedActionsService",
    "AdvancedAnalyticsService",
    "ComplianceStandardsService",
    "PredictiveInsightsService",
]
