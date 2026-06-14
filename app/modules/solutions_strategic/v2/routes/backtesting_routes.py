"""
Solution AI Backtesting API Routes

Exposes backtesting framework results through REST endpoints.

Endpoints:
    GET  /api/solutions/backtesting/report          - Full accuracy report
    GET  /api/solutions/<id>/backtesting            - Backtesting results for one solution
    POST /api/solutions/<id>/backtesting/validate   - Record a backtesting result
    POST /api/solutions/backtesting/batch-backtest  - Run backtests on multiple solutions
"""

from flask import Blueprint, request, jsonify
from functools import wraps
import logging

from app import db
from app.models.solution_models import Solution
from app.models.solution_governance import SolutionAIBacktesting
from app.modules.solutions_strategic.v2.services.solution_backtesting_service import (
    SolutionBacktestingService,
    get_accuracy_report,
    backtest_single_recommendation
)

logger = logging.getLogger(__name__)

backtesting_bp = Blueprint('solution_backtesting', __name__, url_prefix='/api/solutions')


def require_solution(f):
    """Decorator: verify solution exists before processing."""
    @wraps(f)
    def decorated(*args, **kwargs):
        solution_id = kwargs.get('solution_id')
        solution = Solution.query.get(solution_id)
        
        if not solution:
            return jsonify({'error': f'Solution {solution_id} not found'}), 404
        
        kwargs['solution'] = solution
        return f(*args, **kwargs)
    return decorated


@backtesting_bp.route('/backtesting/report', methods=['GET'])
def get_backtesting_report():
    """
    Get comprehensive accuracy report across all recommendation types.
    
    Query Parameters:
        - format: 'json' (default) or 'csv'
        - include_details: 'true'/'false' - include detailed metrics
    
    Returns:
        {
            'summary': {
                'total_backtests': int,
                'report_generated_at': datetime,
                'overall_accuracy': float,
                'mape_by_type': {...}
            },
            'by_type': {
                'vendor': {...},
                'cost': {...},
                'timeline': {...},
                'risk': {...}
            },
            'success_criteria': {...},
            'recommendations': [...]
        }
    """
    try:
        report = get_accuracy_report()
        
        if 'error' in report:
            return jsonify({
                'success': False,
                'error': report.get('error'),
                'message': 'Failed to generate accuracy report'
            }), 500
        
        return jsonify({
            'success': True,
            'report': report
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating backtesting report: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Internal server error generating report'
        }), 500


@backtesting_bp.route('/<int:solution_id>/backtesting', methods=['GET'])
@require_solution
def get_solution_backtesting(solution_id, solution):
    """
    Get all backtesting results for a specific solution.
    
    Query Parameters:
        - rec_type: Filter by recommendation type (vendor, cost, timeline, risk)
        - limit: Maximum results (default 50)
    
    Returns:
        {
            'solution_id': int,
            'solution_name': str,
            'backtesting_results': [
                {
                    'id': int,
                    'recommendation_type': str,
                    'predicted_value': {...},
                    'actual_value': {...},
                    'accuracy_pct': float,
                    'mape': float,
                    'calibration_status': str,
                    'created_at': datetime
                },
                ...
            ],
            'summary': {
                'total_results': int,
                'average_accuracy': float,
                'by_type': {...}
            }
        }
    """
    try:
        rec_type = request.args.get('rec_type', None)
        limit = request.args.get('limit', 50, type=int)
        
        # Query backtesting results
        query = SolutionAIBacktesting.query.filter_by(solution_id=solution_id)
        
        if rec_type:
            query = query.filter_by(recommendation_type=rec_type)
        
        backtests = query.order_by(
            SolutionAIBacktesting.created_at.desc()
        ).limit(limit).all()
        
        # Build response
        results = [b.to_dict() for b in backtests]
        
        # Calculate summary
        summary = {
            'total_results': len(backtests),
            'average_accuracy': None,
            'by_type': {}
        }
        
        if backtests:
            accuracies = [b.accuracy_pct for b in backtests if b.accuracy_pct is not None]
            if accuracies:
                summary['average_accuracy'] = sum(accuracies) / len(accuracies)
            
            # Group by type
            for rt in ['vendor', 'cost', 'timeline', 'risk']:
                type_results = [b for b in backtests if b.recommendation_type == rt]
                if type_results:
                    type_accuracies = [b.accuracy_pct for b in type_results if b.accuracy_pct is not None]
                    summary['by_type'][rt] = {
                        'count': len(type_results),
                        'average_accuracy': sum(type_accuracies) / len(type_accuracies) if type_accuracies else None
                    }
        
        return jsonify({
            'success': True,
            'solution_id': solution_id,
            'solution_name': solution.name,
            'backtesting_results': results,
            'summary': summary
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching backtesting results for solution {solution_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch backtesting results'
        }), 500


@backtesting_bp.route('/<int:solution_id>/backtesting/validate', methods=['POST'])
@require_solution
def record_backtesting_result(solution_id, solution):
    """
    Record a backtesting result (prediction vs actual outcome).
    
    Request Body:
        {
            'recommendation_type': 'vendor'|'cost'|'timeline'|'risk',
            'predicted_value': {...},
            'predicted_confidence': 0.0-1.0,
            'actual_value': {...}
        }
    
    Returns:
        {
            'success': bool,
            'backtest_id': int,
            'accuracy_pct': float,
            'error_percentage': float,
            'calibration_status': str,
            'confidence_interval': {...}
        }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['recommendation_type', 'predicted_value', 'predicted_confidence', 'actual_value']
        if not all(field in data for field in required):
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {required}',
                'provided': list(data.keys())
            }), 400
        
        # Validate recommendation type
        valid_types = ['vendor', 'cost', 'timeline', 'risk']
        if data['recommendation_type'] not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid recommendation_type. Must be one of: {valid_types}',
                'provided': data['recommendation_type']
            }), 400
        
        # Record backtesting
        service = SolutionBacktestingService()
        result = service.backtest_recommendation(
            solution_id=solution_id,
            rec_type=data['recommendation_type'],
            predicted_value=data['predicted_value'],
            predicted_confidence=float(data['predicted_confidence']),
            actual_value=data['actual_value']
        )
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 400
        
        return jsonify({
            'success': True,
            'backtest_id': result.get('backtest_id'),
            'accuracy_pct': result.get('accuracy_pct'),
            'error_percentage': result.get('error_percentage'),
            'error_magnitude': result.get('error_magnitude'),
            'calibration_status': result.get('calibration_status'),
            'confidence_interval': result.get('confidence_interval')
        }), 201
    
    except Exception as e:
        logger.error(f"Error recording backtesting result: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to record backtesting result'
        }), 500


@backtesting_bp.route('/backtesting/batch-backtest', methods=['POST'])
def batch_backtest_solutions():
    """
    Run backtests on multiple solutions.
    
    Request Body:
        {
            'solution_ids': [1, 2, 3, ...] (optional - uses recent if not provided),
            'limit': 10 (optional - max solutions to process)
        }
    
    Returns:
        {
            'success': bool,
            'solutions_processed': int,
            'backtests_created': int,
            'errors': [...]
        }
    """
    try:
        data = request.get_json() or {}
        
        solution_ids = data.get('solution_ids', None)
        limit = data.get('limit', 10)
        
        service = SolutionBacktestingService()
        result = service.batch_backtest_solutions(
            solution_ids=solution_ids,
            limit=limit
        )
        
        return jsonify(result), 200 if result.get('success') else 400
    
    except Exception as e:
        logger.error(f"Error in batch backtesting: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to run batch backtesting'
        }), 500


@backtesting_bp.route('/backtesting/summary', methods=['GET'])
def get_backtesting_summary():
    """
    Get high-level backtesting summary (counts by type, overall metrics).
    
    Returns:
        {
            'total_backtests': int,
            'by_recommendation_type': {
                'vendor': int,
                'cost': int,
                'timeline': int,
                'risk': int
            },
            'accuracy_metrics': {
                'overall_accuracy': float,
                'mape_cost': float,
                'mape_timeline': float
            },
            'success_criteria_met': {
                'cost_mape': bool,
                'timeline_mape': bool,
                'vendor_accuracy': bool
            }
        }
    """
    try:
        from sqlalchemy import func
        
        # Count by type
        type_counts = {}
        for rec_type in ['vendor', 'cost', 'timeline', 'risk']:
            count = SolutionAIBacktesting.query.filter_by(
                recommendation_type=rec_type
            ).count()
            type_counts[rec_type] = count
        
        # Get accuracy metrics
        total = SolutionAIBacktesting.query.count()
        if total > 0:
            avg_accuracy = db.session.query(
                func.avg(SolutionAIBacktesting.accuracy_pct)
            ).scalar() or 0.0
            
            cost_mape = db.session.query(
                func.avg(SolutionAIBacktesting.error_percentage)
            ).filter_by(recommendation_type='cost').scalar() or None
            
            timeline_mape = db.session.query(
                func.avg(SolutionAIBacktesting.error_percentage)
            ).filter_by(recommendation_type='timeline').scalar() or None
        else:
            avg_accuracy = 0.0
            cost_mape = None
            timeline_mape = None
        
        # Check success criteria
        success_criteria = {
            'cost_mape': cost_mape is not None and cost_mape < 15.0,
            'timeline_mape': timeline_mape is not None and timeline_mape < 20.0,
            'vendor_accuracy': avg_accuracy > 70.0 if type_counts.get('vendor', 0) > 0 else False
        }
        
        return jsonify({
            'total_backtests': total,
            'by_recommendation_type': type_counts,
            'accuracy_metrics': {
                'overall_accuracy': float(avg_accuracy),
                'mape_cost': float(cost_mape) if cost_mape is not None else None,
                'mape_timeline': float(timeline_mape) if timeline_mape is not None else None
            },
            'success_criteria_met': success_criteria
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting backtesting summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
