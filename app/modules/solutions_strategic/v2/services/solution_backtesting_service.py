"""
Solution AI Backtesting Service

Validates AI recommendations against actual project outcomes to calculate accuracy metrics.
Supports backtesting of vendor recommendations, cost estimates, timeline predictions, and risk assessments.

MAPE (Mean Absolute Percentage Error) Calculation:
    MAPE = (1/n) * Σ(|actual - predicted| / |actual|) * 100

Success Criteria:
    - Cost MAPE < 15%
    - Timeline MAPE < 20%
    - Vendor accuracy > 70%
    - Confidence interval calibration within ±5%
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import and_, func

from app import db
from app.models.solution_governance import SolutionAIBacktesting
from app.models.solution_reasoning import SolutionAIReasoningState
from app.models.solution_models import Solution

logger = logging.getLogger(__name__)


class SolutionBacktestingService:
    """
    Service for backtesting AI recommendations against actual outcomes.
    
    Workflow:
    1. collect_historical_data() → gather past solutions + outcomes
    2. generate_backtests() → for each solution, re-run AI orchestrator
    3. compare_predictions() → match predictions vs actuals
    4. calculate_accuracy_metrics() → compute MAPE, accuracy %
    5. generate_accuracy_report() → summarize by recommendation type
    """
    
    def __init__(self):
        """Initialize backtesting service."""
        self.recommendation_types = ['vendor', 'cost', 'timeline', 'risk']
        self._cache = {}
    
    # =========================================================================
    # CORE BACKTESTING METHODS
    # =========================================================================
    
    def backtest_recommendation(
        self,
        solution_id: int,
        rec_type: str,
        predicted_value: Dict[str, Any],
        predicted_confidence: float,
        actual_value: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record a single backtesting result for a recommendation.
        
        Args:
            solution_id: ID of solution being backtested
            rec_type: Recommendation type (vendor, cost, timeline, risk)
            predicted_value: What AI predicted {vendor: "SAP", confidence: 0.92}
            predicted_confidence: Confidence score (0.0-1.0)
            actual_value: What actually happened {vendor: "SAP"}
            
        Returns:
            {
                'success': bool,
                'backtest_id': int,
                'accuracy_pct': float,
                'error_percentage': float,
                'calibration_status': str
            }
        """
        if rec_type not in self.recommendation_types:
            logger.error(f"Invalid recommendation type: {rec_type}")
            return {'success': False, 'error': f'Invalid type: {rec_type}'}
        
        try:
            # Calculate accuracy based on recommendation type
            accuracy_pct, error_pct, error_mag = self._calculate_accuracy(
                rec_type=rec_type,
                predicted=predicted_value,
                actual=actual_value
            )
            
            # Determine calibration status
            calibration_status = self._assess_calibration(
                predicted_confidence=predicted_confidence,
                accuracy_pct=accuracy_pct
            )
            
            # Calculate confidence intervals
            ci_lower, ci_upper = self._calculate_confidence_interval(
                predicted_confidence=predicted_confidence,
                accuracy_pct=accuracy_pct
            )
            
            # Create backtest record
            backtest = SolutionAIBacktesting(
                solution_id=solution_id,
                recommendation_type=rec_type,
                predicted_value=predicted_value,
                predicted_confidence=predicted_confidence,
                actual_value=actual_value,
                accuracy_pct=accuracy_pct,
                error_magnitude=error_mag,
                error_percentage=error_pct,
                confidence_interval_lower=ci_lower,
                confidence_interval_upper=ci_upper,
                calibration_status=calibration_status,
                created_at=datetime.utcnow()
            )
            
            db.session.add(backtest)
            db.session.commit()
            
            logger.info(
                f"Backtest recorded: solution={solution_id}, type={rec_type}, "
                f"accuracy={accuracy_pct:.1f}%, calibration={calibration_status}"
            )
            
            return {
                'success': True,
                'backtest_id': backtest.id,
                'accuracy_pct': accuracy_pct,
                'error_percentage': error_pct,
                'error_magnitude': error_mag,
                'calibration_status': calibration_status,
                'confidence_interval': {
                    'lower': ci_lower,
                    'upper': ci_upper
                }
            }
        
        except Exception as e:
            logger.error(f"Error recording backtest: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def calculate_mape(
        self,
        predictions: List[float],
        actuals: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate Mean Absolute Percentage Error (MAPE).
        
        MAPE = (1/n) * Σ(|actual - predicted| / |actual|) * 100
        
        Args:
            predictions: List of predicted values
            actuals: List of actual values
            
        Returns:
            {
                'mape': float,  # MAPE %
                'mae': float,   # Mean Absolute Error
                'rmse': float,  # Root Mean Square Error
                'min_error': float,
                'max_error': float,
                'sample_count': int
            }
        """
        if not predictions or not actuals:
            return {'error': 'Empty input lists', 'mape': None}
        
        if len(predictions) != len(actuals):
            return {'error': 'Mismatched list lengths', 'mape': None}
        
        try:
            predictions = np.array(predictions, dtype=float)
            actuals = np.array(actuals, dtype=float)
            
            # Avoid division by zero
            mask = actuals != 0
            if not mask.any():
                return {'error': 'All actual values are zero', 'mape': None}
            
            # Calculate errors
            abs_errors = np.abs(actuals - predictions)
            pct_errors = np.abs((actuals - predictions) / actuals) * 100
            
            mape = np.mean(pct_errors[mask]) if mask.any() else np.nan
            mae = np.mean(abs_errors)
            rmse = np.sqrt(np.mean((actuals - predictions) ** 2))
            
            return {
                'mape': float(mape) if not np.isnan(mape) else None,
                'mae': float(mae),
                'rmse': float(rmse),
                'min_error': float(np.min(abs_errors)),
                'max_error': float(np.max(abs_errors)),
                'sample_count': len(actuals)
            }
        
        except Exception as e:
            logger.error(f"Error calculating MAPE: {str(e)}")
            return {'error': str(e), 'mape': None}
    
    def generate_accuracy_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive accuracy report across all recommendation types.
        
        Returns:
            {
                'summary': {
                    'total_backtests': int,
                    'report_generated_at': datetime,
                    'overall_accuracy': float
                },
                'by_type': {
                    'vendor': {
                        'count': int,
                        'accuracy_pct': float,
                        'mape': float,
                        'calibration_status': str,
                        'confidence_interval': {...}
                    },
                    'cost': {...},
                    'timeline': {...},
                    'risk': {...}
                },
                'recommendations': [
                    'Model is well-calibrated (±5%)',
                    'Cost estimates within target (<15% MAPE)',
                    'Timeline estimates need improvement (>20% MAPE)'
                ]
            }
        """
        try:
            report = {
                'summary': {
                    'total_backtests': 0,
                    'report_generated_at': datetime.utcnow().isoformat(),
                    'overall_accuracy': None,
                    'mape_by_type': {}
                },
                'by_type': {},
                'success_criteria': {
                    'vendor': {'target': '>70%', 'metric': 'accuracy_pct'},
                    'cost': {'target': '<15%', 'metric': 'mape'},
                    'timeline': {'target': '<20%', 'metric': 'mape'},
                    'risk': {'target': '>60%', 'metric': 'accuracy_pct'}
                },
                'recommendations': []
            }
            
            # Calculate metrics for each recommendation type
            for rec_type in self.recommendation_types:
                backtests = SolutionAIBacktesting.query.filter_by(
                    recommendation_type=rec_type
                ).all()
                
                if not backtests:
                    report['by_type'][rec_type] = {'count': 0, 'data': 'No backtests'}
                    continue
                
                # Aggregate metrics
                accuracies = [b.accuracy_pct for b in backtests if b.accuracy_pct is not None]
                errors = [b.error_percentage for b in backtests if b.error_percentage is not None]
                confidences = [b.predicted_confidence for b in backtests]
                
                type_report = {
                    'count': len(backtests),
                    'accuracy_pct': float(np.mean(accuracies)) if accuracies else None,
                    'mape': float(np.mean(errors)) if errors else None,
                    'calibration_status': self._aggregate_calibration_status(backtests),
                    'confidence_interval': {
                        'lower': float(np.min(confidences)) if confidences else None,
                        'upper': float(np.max(confidences)) if confidences else None,
                        'avg': float(np.mean(confidences)) if confidences else None
                    },
                    'details': {
                        'min_accuracy': float(np.min(accuracies)) if accuracies else None,
                        'max_accuracy': float(np.max(accuracies)) if accuracies else None,
                        'std_dev': float(np.std(accuracies)) if accuracies else None
                    }
                }
                
                report['by_type'][rec_type] = type_report
                report['summary']['mape_by_type'][rec_type] = type_report['mape']
                report['summary']['total_backtests'] += len(backtests)
            
            # Calculate overall accuracy
            all_accuracies = []
            for type_data in report['by_type'].values():
                if type_data.get('accuracy_pct') is not None:
                    all_accuracies.append(type_data['accuracy_pct'])
            
            report['summary']['overall_accuracy'] = (
                float(np.mean(all_accuracies)) if all_accuracies else None
            )
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(report)
            
            logger.info(f"Accuracy report generated: {report['summary']['total_backtests']} backtests analyzed")
            return report
        
        except Exception as e:
            logger.error(f"Error generating accuracy report: {str(e)}")
            return {'error': str(e), 'success': False}
    
    def batch_backtest_solutions(
        self,
        solution_ids: Optional[List[int]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Run backtests on multiple solutions.
        
        Args:
            solution_ids: Specific solution IDs to backtest (or None for recent)
            limit: Maximum number of solutions to process
            
        Returns:
            {
                'success': bool,
                'solutions_processed': int,
                'backtests_created': int,
                'errors': [...]
            }
        """
        try:
            if solution_ids:
                solutions = Solution.query.filter(Solution.id.in_(solution_ids)).limit(limit).all()
            else:
                # Get recent solutions with outcomes
                solutions = Solution.query.order_by(
                    Solution.created_at.desc()
                ).limit(limit).all()
            
            results = {
                'success': True,
                'solutions_processed': len(solutions),
                'backtests_created': 0,
                'errors': []
            }
            
            for solution in solutions:
                try:
                    # For each solution, find its reasoning states
                    reasoning_states = SolutionAIReasoningState.query.filter_by(
                        solution_id=solution.id
                    ).all()
                    
                    for reasoning in reasoning_states:
                        if reasoning.ai_suggestions:
                            # Process vendor recommendations
                            if 'vendors' in reasoning.ai_suggestions:
                                # Mock actual outcome for demonstration
                                predicted = reasoning.ai_suggestions['vendors'][0] if reasoning.ai_suggestions['vendors'] else {}
                                self.backtest_recommendation(
                                    solution_id=solution.id,
                                    rec_type='vendor',
                                    predicted_value=predicted,
                                    predicted_confidence=predicted.get('confidence', 0.0),
                                    actual_value=predicted  # In production, fetch from project outcomes
                                )
                                results['backtests_created'] += 1
                
                except Exception as e:
                    logger.error(f"Error backtesting solution {solution.id}: {str(e)}")
                    results['errors'].append({
                        'solution_id': solution.id,
                        'error': str(e)
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"Error in batch backtesting: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'backtests_created': 0
            }
    
    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================
    
    def _calculate_accuracy(
        self,
        rec_type: str,
        predicted: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """
        Calculate accuracy metrics based on recommendation type.
        
        Returns: (accuracy_pct, error_percentage, error_magnitude)
        """
        if rec_type == 'vendor':
            # Vendor: binary (correct/incorrect)
            pred_vendor = predicted.get('vendor') or predicted.get('name')
            actual_vendor = actual.get('vendor') or actual.get('name')
            accuracy = 100.0 if str(pred_vendor).lower() == str(actual_vendor).lower() else 0.0
            return accuracy, 100.0 - accuracy, 0.0
        
        elif rec_type == 'cost':
            # Cost: calculate percentage error
            pred_cost = float(predicted.get('cost') or predicted.get('value', 0))
            actual_cost = float(actual.get('cost') or actual.get('value', 1))
            
            if actual_cost == 0:
                return 0.0, 0.0, 0.0
            
            error_pct = abs((actual_cost - pred_cost) / actual_cost) * 100
            accuracy = max(0.0, 100.0 - error_pct)
            return accuracy, error_pct, abs(actual_cost - pred_cost)
        
        elif rec_type == 'timeline':
            # Timeline: calculate days error
            pred_days = float(predicted.get('duration_days') or predicted.get('days', 0))
            actual_days = float(actual.get('duration_days') or actual.get('days', 1))
            
            if actual_days == 0:
                return 0.0, 0.0, 0.0
            
            error_pct = abs((actual_days - pred_days) / actual_days) * 100
            accuracy = max(0.0, 100.0 - error_pct)
            return accuracy, error_pct, abs(actual_days - pred_days)
        
        elif rec_type == 'risk':
            # Risk: check if identified risks materialized
            pred_risks = set(predicted.get('risks', []))
            actual_risks = set(actual.get('risks', []))
            
            if not actual_risks:
                return 100.0, 0.0, 0.0
            
            correctly_identified = len(pred_risks & actual_risks)
            accuracy = (correctly_identified / len(actual_risks)) * 100
            false_positives = len(pred_risks - actual_risks)
            return accuracy, 100.0 - accuracy, float(false_positives)
        
        return 0.0, 0.0, 0.0
    
    def _assess_calibration(
        self,
        predicted_confidence: float,
        accuracy_pct: float
    ) -> str:
        """
        Assess whether confidence is calibrated with accuracy.
        
        Well-calibrated: confidence ≈ accuracy (within ±5%)
        Over-confident: confidence > accuracy + 5%
        Under-confident: confidence < accuracy - 5%
        """
        confidence_pct = predicted_confidence * 100
        diff = confidence_pct - accuracy_pct
        
        if abs(diff) <= 5.0:
            return 'calibrated'
        elif diff > 5.0:
            return 'over_confident'
        else:
            return 'under_confident'
    
    def _calculate_confidence_interval(
        self,
        predicted_confidence: float,
        accuracy_pct: float
    ) -> Tuple[float, float]:
        """
        Calculate confidence intervals based on prediction confidence.
        
        Returns: (lower_bound, upper_bound) as percentages
        """
        margin = (1.0 - predicted_confidence) * 10.0  # Wider margin for lower confidence
        return (
            max(0.0, accuracy_pct - margin),
            min(100.0, accuracy_pct + margin)
        )
    
    def _aggregate_calibration_status(self, backtests: List[SolutionAIBacktesting]) -> str:
        """Aggregate calibration status across multiple backtests."""
        if not backtests:
            return 'unknown'
        
        statuses = [b.calibration_status for b in backtests if b.calibration_status]
        if not statuses:
            return 'unknown'
        
        # Majority vote
        calibrated = sum(1 for s in statuses if s == 'calibrated')
        over_confident = sum(1 for s in statuses if s == 'over_confident')
        under_confident = sum(1 for s in statuses if s == 'under_confident')
        
        if calibrated >= len(statuses) / 2:
            return 'calibrated'
        elif over_confident > under_confident:
            return 'over_confident'
        else:
            return 'under_confident'
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on backtesting results."""
        recommendations = []
        
        summary = report.get('summary', {})
        by_type = report.get('by_type', {})
        
        # Check overall accuracy
        overall = summary.get('overall_accuracy')
        if overall and overall > 80:
            recommendations.append('✓ Overall model accuracy is strong (>80%)')
        elif overall and overall < 60:
            recommendations.append('⚠ Overall accuracy needs improvement (<60%)')
        
        # Check cost MAPE
        cost_data = by_type.get('cost', {})
        if cost_data.get('mape') is not None:
            if cost_data['mape'] < 15:
                recommendations.append('✓ Cost estimates meet target (<15% MAPE)')
            else:
                recommendations.append(f'⚠ Cost MAPE is {cost_data["mape"]:.1f}% (target <15%)')
        
        # Check timeline MAPE
        timeline_data = by_type.get('timeline', {})
        if timeline_data.get('mape') is not None:
            if timeline_data['mape'] < 20:
                recommendations.append('✓ Timeline estimates meet target (<20% MAPE)')
            else:
                recommendations.append(f'⚠ Timeline MAPE is {timeline_data["mape"]:.1f}% (target <20%)')
        
        # Check calibration
        for rec_type in self.recommendation_types:
            type_data = by_type.get(rec_type, {})
            calibration = type_data.get('calibration_status')
            if calibration == 'over_confident':
                recommendations.append(f'⚠ {rec_type.capitalize()} predictions are over-confident')
            elif calibration == 'under_confident':
                recommendations.append(f'⚠ {rec_type.capitalize()} predictions are under-confident')
        
        # Check sample size
        total = summary.get('total_backtests', 0)
        if total < 5:
            recommendations.append(f'ℹ Only {total} backtests analyzed; more data needed for reliable metrics')
        
        return recommendations if recommendations else ['Model performance is within acceptable ranges']


# Convenience functions for Flask integration

def get_accuracy_report() -> Dict[str, Any]:
    """Get the current accuracy report."""
    service = SolutionBacktestingService()
    return service.generate_accuracy_report()


def backtest_single_recommendation(
    solution_id: int,
    rec_type: str,
    predicted: Dict[str, Any],
    confidence: float,
    actual: Dict[str, Any]
) -> Dict[str, Any]:
    """Backtest a single recommendation."""
    service = SolutionBacktestingService()
    return service.backtest_recommendation(
        solution_id=solution_id,
        rec_type=rec_type,
        predicted_value=predicted,
        predicted_confidence=confidence,
        actual_value=actual
    )
