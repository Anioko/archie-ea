"""
Process Optimization Service

Analyzes and optimizes business processes for operational excellence:
- Process efficiency metrics and benchmarking
- Bottleneck identification and resolution
- Process maturity assessment
- Automation opportunities analysis
- Continuous improvement recommendations
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from .decorators import transactional


class ProcessOptimizationService:
    """
    Service for business process optimization and operational excellence.

    Provides comprehensive process analysis:
    - Process efficiency metrics and KPI tracking
    - Benchmarking against industry standards
    - Bottleneck identification and root cause analysis
    - Automation opportunity assessment
    - Process maturity evaluation
    """

    def __init__(self):
        pass

    @transactional
    def analyze_process_portfolio(self, include_benchmarking: bool = True) -> Dict:
        """
        Comprehensive analysis of the entire process portfolio.

        Args:
            include_benchmarking: Include industry benchmarking comparison

        Returns:
            Dict with process optimization analysis results
        """
        # Get all business processes
        # Note: This would be adapted to work with your current process model
        processes = self._get_all_processes()

        # Analyze each process for optimization opportunities
        process_analyses = []
        for process in processes:
            analysis = self._analyze_single_process(process, include_benchmarking)
            process_analyses.append(analysis)

        # Sort by optimization priority (highest first)
        process_analyses.sort(key=lambda x: x["optimization_priority_score"], reverse=True)

        # Categorize by priority levels
        critical_processes = [p for p in process_analyses if p["optimization_level"] == "CRITICAL"]
        high_processes = [p for p in process_analyses if p["optimization_level"] == "HIGH"]
        medium_processes = [p for p in process_analyses if p["optimization_level"] == "MEDIUM"]
        low_processes = [p for p in process_analyses if p["optimization_level"] == "LOW"]

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(process_analyses)

        # Generate optimization recommendations
        recommendations = self._generate_optimization_recommendations(process_analyses)

        return {
            "total_processes": len(processes),
            "process_analyses": process_analyses,
            "critical_processes": critical_processes,
            "high_processes": high_processes,
            "medium_processes": medium_processes,
            "low_processes": low_processes,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _analyze_single_process(self, process, include_benchmarking: bool) -> Dict:
        """Analyze optimization opportunities for a single process."""

        # Calculate different optimization factors
        efficiency_score = self._calculate_efficiency_score(process)
        bottleneck_score = self._calculate_bottleneck_score(process)
        automation_score = self._calculate_automation_score(process)
        maturity_score = self._calculate_maturity_score(process)
        benchmark_score = self._calculate_benchmark_score(process) if include_benchmarking else 0

        # Calculate overall optimization priority score (0 - 100)
        total_score = (
            efficiency_score
            + bottleneck_score
            + automation_score
            + maturity_score
            + benchmark_score
        )

        # Determine optimization level
        if total_score >= 80:
            optimization_level = "CRITICAL"
        elif total_score >= 60:
            optimization_level = "HIGH"
        elif total_score >= 40:
            optimization_level = "MEDIUM"
        else:
            optimization_level = "LOW"

        # Identify specific optimization factors
        optimization_factors = []
        if efficiency_score >= 20:
            optimization_factors.append("EFFICIENCY_IMPROVEMENT")
        if bottleneck_score >= 15:
            optimization_factors.append("BOTTLENECK_RESOLUTION")
        if automation_score >= 15:
            optimization_factors.append("AUTOMATION_OPPORTUNITY")
        if maturity_score >= 15:
            optimization_factors.append("MATURITY_IMPROVEMENT")
        if benchmark_score >= 10 and include_benchmarking:
            optimization_factors.append("BENCHMARK_GAP")

        # Estimate optimization benefits
        optimization_benefits = self._estimate_optimization_benefits(process, total_score)

        return {
            "process_id": process.get("id"),
            "process_name": process.get("name"),
            "process_code": process.get("code"),
            "process_category": process.get("category"),
            "efficiency_score": efficiency_score,
            "bottleneck_score": bottleneck_score,
            "automation_score": automation_score,
            "maturity_score": maturity_score,
            "benchmark_score": benchmark_score,
            "optimization_priority_score": total_score,
            "optimization_level": optimization_level,
            "optimization_factors": optimization_factors,
            "optimization_benefits": optimization_benefits,
            "optimization_assessment": self._generate_optimization_assessment(
                process, optimization_factors, total_score
            ),
        }

    def _calculate_efficiency_score(self, process) -> int:
        """Calculate process efficiency score (0 - 25 points)."""
        # Simplified efficiency calculation
        # In production, this would analyze actual process metrics

        # Check for efficiency indicators
        efficiency_indicators = 0

        # Process cycle time
        if hasattr(process, "cycle_time") and process["cycle_time"]:
            if process["cycle_time"] > 30:  # days
                efficiency_indicators += 10
            elif process["cycle_time"] > 14:
                efficiency_indicators += 5
            elif process["cycle_time"] > 7:
                efficiency_indicators += 2

        # Error rate
        if hasattr(process, "error_rate") and process["error_rate"]:
            if process["error_rate"] > 0.1:  # 10% error rate
                efficiency_indicators += 10
            elif process["error_rate"] > 0.05:
                efficiency_indicators += 5
            elif process["error_rate"] > 0.02:
                efficiency_indicators += 2

        # Resource utilization
        if hasattr(process, "resource_utilization") and process["resource_utilization"]:
            if process["resource_utilization"] < 0.5:  # Less than 50% utilization
                efficiency_indicators += 5
            elif process["resource_utilization"] < 0.7:
                efficiency_indicators += 2

        return min(efficiency_indicators, 25)

    def _calculate_bottleneck_score(self, process) -> int:
        """Calculate bottleneck score (0 - 20 points)."""
        bottleneck_score = 0

        # Check for bottleneck indicators
        if hasattr(process, "bottlenecks") and process["bottlenecks"]:
            bottleneck_score += len(process["bottlenecks"]) * 3

        # Check for manual handoffs
        if hasattr(process, "manual_handoffs") and process["manual_handoffs"] > 5:
            bottleneck_score += 10
        elif process["manual_handoffs"] > 3:
            bottleneck_score += 5
        elif process["manual_handoffs"] > 1:
            bottleneck_score += 2

        # Check for wait times
        if hasattr(process, "average_wait_time") and process["average_wait_time"]:
            if process["average_wait_time"] > 48:  # hours
                bottleneck_score += 10
            elif process["average_wait_time"] > 24:
                bottleneck_score += 5
            elif process["average_wait_time"] > 8:
                bottleneck_score += 2

        return min(bottleneck_score, 20)

    def _calculate_automation_score(self, process) -> int:
        """Calculate automation opportunity score (0 - 20 points)."""
        automation_score = 0

        # Check for manual tasks
        if hasattr(process, "manual_task_percentage") and process["manual_task_percentage"]:
            if process["manual_task_percentage"] > 0.8:  # 80% manual
                automation_score += 15
            elif process["manual_task_percentage"] > 0.6:
                automation_score += 10
            elif process["manual_task_percentage"] > 0.4:
                automation_score += 5
            elif process["manual_task_percentage"] > 0.2:
                automation_score += 2

        # Check for repetitive tasks
        if hasattr(process, "repetitive_tasks") and process["repetitive_tasks"]:
            automation_score += len(process["repetitive_tasks"]) * 2

        # Check for data entry tasks
        if hasattr(process, "data_entry_tasks") and process["data_entry_tasks"]:
            automation_score += len(process["data_entry_tasks"]) * 3

        return min(automation_score, 20)

    def _calculate_maturity_score(self, process) -> int:
        """Calculate process maturity score (0 - 20 points)."""
        maturity_score = 0

        # Check for process documentation
        if hasattr(process, "has_documentation") and process["has_documentation"]:
            maturity_score += 5
        else:
            maturity_score -= 5

        # Check for process metrics
        if hasattr(process, "has_metrics") and process["has_metrics"]:
            maturity_score += 5
        else:
            maturity_score -= 5

        # Check for continuous improvement
        if hasattr(process, "has_continuous_improvement") and process["has_continuous_improvement"]:
            maturity_score += 5
        else:
            maturity_score -= 5

        # Check for standardization
        if hasattr(process, "is_standardized") and process["is_standardized"]:
            maturity_score += 5
        else:
            maturity_score -= 5

        return max(0, min(maturity_score, 20))

    def _calculate_benchmark_score(self, process) -> int:
        """Calculate benchmark gap score (0 - 15 points)."""
        benchmark_score = 0

        # Check if process has benchmark data
        if hasattr(process, "benchmark_available") and process["benchmark_available"]:
            if hasattr(process, "performance_gap") and process["performance_gap"]:
                if process["performance_gap"] > 0.5:  # 50% below benchmark
                    benchmark_score += 15
                elif process["performance_gap"] > 0.3:
                    benchmark_score += 10
                elif process["performance_gap"] > 0.1:
                    benchmark_score += 5
                elif process["performance_gap"] > 0.05:
                    benchmark_score += 2

        return min(benchmark_score, 15)

    def _estimate_optimization_benefits(self, process, score: int) -> Dict:
        """Estimate benefits of process optimization."""

        # Base benefit estimation
        if score >= 80:
            base_benefit = 500000  # $500k for critical optimization
            complexity_multiplier = 1.5
        elif score >= 60:
            base_benefit = 250000  # $250k for high priority
            complexity_multiplier = 1.2
        elif score >= 40:
            base_benefit = 100000  # $100k for medium priority
            complexity_multiplier = 1.0
        else:
            base_benefit = 50000  # $50k for low priority
            complexity_multiplier = 0.8

        # Adjust for process complexity
        if hasattr(process, "complexity") and process["complexity"] == "HIGH":
            complexity_multiplier *= 1.3
        elif hasattr(process, "complexity") and process["complexity"] == "LOW":
            complexity_multiplier *= 0.8

        estimated_benefit = base_benefit * complexity_multiplier

        # Timeframe estimation
        if score >= 80:
            timeframe = "6 - 12 months"
        elif score >= 60:
            timeframe = "3 - 6 months"
        elif score >= 40:
            timeframe = "1 - 3 months"
        else:
            timeframe = "1 - 2 months"

        return {
            "estimated_benefit": estimated_benefit,
            "currency": "USD",
            "timeframe": timeframe,
            "optimization_type": "IMPROVEMENT",
            "complexity": "HIGH"
            if complexity_multiplier > 1.2
            else "MEDIUM"
            if complexity_multiplier > 1.0
            else "LOW",
        }

    def _generate_optimization_assessment(self, process, factors: List, score: int) -> str:
        """Generate optimization assessment for the process."""

        if score >= 80:
            return f"CRITICAL: {process.get('name', 'Unknown')} requires immediate optimization - multiple critical issues identified"
        elif score >= 60:
            return f"HIGH: {process.get('name', 'Unknown')} has significant optimization opportunities requiring attention"
        elif score >= 40:
            return f"MEDIUM: {process.get('name', 'Unknown')} has moderate optimization opportunities that should be considered"
        else:
            return f"LOW: {process.get('name', 'Unknown')} is operating efficiently with minimal optimization needs"

    def _get_all_processes(self) -> List[Dict]:
        """Get all business processes from the database."""
        # This would be adapted to work with your current process model
        # For now, return empty list as placeholder
        return []

    def _calculate_portfolio_metrics(self, process_analyses: List[Dict]) -> Dict:
        """Calculate portfolio-level optimization metrics."""

        total_processes = len(process_analyses)
        critical_count = len([p for p in process_analyses if p["optimization_level"] == "CRITICAL"])
        high_count = len([p for p in process_analyses if p["optimization_level"] == "HIGH"])

        # Optimization factor distribution
        efficiency_count = len(
            [p for p in process_analyses if "EFFICIENCY_IMPROVEMENT" in p["optimization_factors"]]
        )
        bottleneck_count = len(
            [p for p in process_analyses if "BOTTLENECK_RESOLUTION" in p["optimization_factors"]]
        )
        automation_count = len(
            [p for p in process_analyses if "AUTOMATION_OPPORTUNITY" in p["optimization_factors"]]
        )

        # Average scores
        avg_efficiency_score = (
            sum(p["efficiency_score"] for p in process_analyses) / total_processes
            if total_processes > 0
            else 0
        )
        avg_bottleneck_score = (
            sum(p["bottleneck_score"] for p in process_analyses) / total_processes
            if total_processes > 0
            else 0
        )
        avg_automation_score = (
            sum(p["automation_score"] for p in process_analyses) / total_processes
            if total_processes > 0
            else 0
        )
        avg_maturity_score = (
            sum(p["maturity_score"] for p in process_analyses) / total_processes
            if total_processes > 0
            else 0
        )

        return {
            "total_processes": total_processes,
            "critical_optimizations": critical_count,
            "high_optimizations": high_count,
            "efficiency_improvements": efficiency_count,
            "bottleneck_resolutions": bottleneck_count,
            "automation_opportunities": automation_count,
            "average_efficiency_score": round(avg_efficiency_score, 1),
            "average_bottleneck_score": round(avg_bottleneck_score, 1),
            "average_automation_score": round(avg_automation_score, 1),
            "average_maturity_score": round(avg_maturity_score, 1),
            "portfolio_optimization_level": "HIGH"
            if critical_count > 5
            else "MEDIUM"
            if high_count > 10
            else "LOW",
        }

    def _generate_optimization_recommendations(self, process_analyses: List[Dict]) -> List[Dict]:
        """Generate process optimization recommendations."""

        recommendations = []

        # Top 5 critical optimizations
        critical_processes = [p for p in process_analyses if p["optimization_level"] == "CRITICAL"][
            :5
        ]

        for process in critical_processes:
            recommendations.append(
                {
                    "type": "IMMEDIATE_OPTIMIZATION",
                    "priority": "CRITICAL",
                    "process": process["process_name"],
                    "optimization_level": process["optimization_level"],
                    "optimization_factors": process["optimization_factors"],
                    "recommendation": self._get_optimization_recommendation(process),
                    "timeframe": process["optimization_benefits"]["timeframe"],
                    "estimated_benefit": process["optimization_benefits"]["estimated_benefit"],
                    "expected_roi": "HIGH"
                    if process["optimization_priority_score"] >= 85
                    else "MEDIUM",
                }
            )

        # Automation opportunities
        automation_processes = [
            p for p in process_analyses if "AUTOMATION_OPPORTUNITY" in p["optimization_factors"]
        ]
        if automation_processes:
            recommendations.append(
                {
                    "type": "AUTOMATION_IMPLEMENTATION",
                    "priority": "HIGH",
                    "process": f"{len(automation_processes)} processes",
                    "optimization_level": "HIGH",
                    "optimization_factors": ["AUTOMATION_OPPORTUNITY"],
                    "recommendation": "Implement automation for high manual task processes",
                    "timeframe": "3 - 6 months",
                    "estimated_benefit": sum(
                        p["optimization_benefits"]["estimated_benefit"]
                        for p in automation_processes
                    ),
                    "expected_roi": "HIGH",
                }
            )

        # Bottleneck resolution
        bottleneck_processes = [
            p for p in process_analyses if "BOTTLENECK_RESOLUTION" in p["optimization_factors"]
        ]
        if bottleneck_processes:
            recommendations.append(
                {
                    "type": "BOTTLENECK_RESOLUTION",
                    "priority": "MEDIUM",
                    "process": f"{len(bottleneck_processes)} processes",
                    "optimization_level": "MEDIUM",
                    "optimization_factors": ["BOTTLENECK_RESOLUTION"],
                    "recommendation": "Resolve bottlenecks to improve process flow and efficiency",
                    "timeframe": "1 - 3 months",
                    "estimated_benefit": sum(
                        p["optimization_benefits"]["estimated_benefit"]
                        for p in bottleneck_processes
                    ),
                    "expected_roi": "MEDIUM",
                }
            )

        return recommendations

    def _get_optimization_recommendation(self, process: Dict) -> str:
        """Get specific optimization recommendation for a process."""

        factors = process["optimization_factors"]

        if "EFFICIENCY_IMPROVEMENT" in factors:
            return f"Optimize {process['process_name']} for better efficiency - current performance indicates significant improvement opportunities"
        elif "BOTTLENECK_RESOLUTION" in factors:
            return f"Resolve bottlenecks in {process['process_name']} - process flow constraints identified"
        elif "AUTOMATION_OPPORTUNITY" in factors:
            return f"Automate {process['process_name']} - high manual task percentage indicates automation potential"
        elif "MATURITY_IMPROVEMENT" in factors:
            return f"Improve {process['process_name']} maturity - standardization and documentation gaps identified"
        elif "BENCHMARK_GAP" in factors:
            return f"Close benchmark gap for {process['process_name']} - performance below industry standards"
        else:
            return f"Monitor and optimize {process['process_name']} - continuous improvement opportunities identified"
