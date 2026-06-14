"""
Phase 3: Advanced Recommendation API Endpoints

GET  /api/solutions/<id>/recommendations/processes
GET  /api/solutions/<id>/recommendations/vendors
GET  /api/solutions/<id>/recommendations/vendor-combination
POST /api/solutions/<id>/recommendations/vendors/validate-gaps
"""

from flask import Blueprint, request, jsonify
from app.models.solution_models import Solution
from app.modules.solutions_strategic.v2.services.apqc_process_recommender import APQCProcessRecommender
from app.modules.solutions_strategic.v2.services.vendor_capability_aggregator import VendorCapabilityAggregator
from functools import wraps
import logging
from flask_login import login_required

logger = logging.getLogger(__name__)

recommendations_bp = Blueprint('solution_recommendations_api', __name__, url_prefix='/api/solutions')


def require_solution(f):
    """Decorator: verify solution exists before processing"""
    @wraps(f)
    def decorated(*args, **kwargs):
        solution_id = kwargs.get('solution_id')
        solution = Solution.query.get(solution_id)
        
        if not solution:
            return jsonify({'error': f'Solution {solution_id} not found'}), 404
        
        kwargs['solution'] = solution
        return f(*args, **kwargs)
    return decorated


@recommendations_bp.route('/<int:solution_id>/recommendations/processes', methods=['GET'])
@login_required
@require_solution
def get_process_recommendations(solution_id, solution):
    """Recommend APQC business processes to enhance"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        recommender = APQCProcessRecommender()
        processes = recommender.recommend_processes(solution, limit=limit)
        
        return jsonify({
            'solution_id': solution_id,
            'solution_name': solution.name,
            'domain': solution.business_domain,
            'recommended_processes': processes,
            'count': len(processes),
            'recommendation_type': 'APQC Process Enhancement'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting process recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@recommendations_bp.route('/<int:solution_id>/recommendations/vendors', methods=['GET'])
@login_required
@require_solution
def get_vendor_recommendations(solution_id, solution):
    """Recommend vendors that match solution requirements"""
    try:
        limit = request.args.get('limit', 5, type=int)
        cost_limit = request.args.get('cost_limit', None, type=int)
        
        aggregator = VendorCapabilityAggregator()
        vendors = aggregator.recommend_vendors(
            solution,
            limit=limit,
            cost_constraint=cost_limit
        )
        
        return jsonify({
            'solution_id': solution_id,
            'solution_name': solution.name,
            'recommended_vendors': vendors,
            'count': len(vendors),
            'cost_constraint': cost_limit,
            'recommendation_type': 'Best-of-Breed Vendor Match'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting vendor recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@recommendations_bp.route('/<int:solution_id>/recommendations/vendor-combination', methods=['GET'])
@login_required
@require_solution
def get_vendor_combination(solution_id, solution):
    """Recommend optimal vendor combination for complete coverage"""
    try:
        max_vendors = request.args.get('max_vendors', 3, type=int)
        
        aggregator = VendorCapabilityAggregator()
        combination = aggregator.recommend_vendor_combination(
            solution,
            max_vendors=max_vendors
        )
        
        return jsonify({
            'solution_id': solution_id,
            'solution_name': solution.name,
            'vendor_combination': combination.get('recommended_vendors', []),
            'approach': combination.get('approach', 'single_vendor'),
            'coverage_percentage': round(combination.get('coverage_percentage', 0), 1),
            'uncovered_capabilities': combination.get('uncovered_capabilities', []),
            'estimated_cost': combination.get('estimated_total_cost', 'N/A'),
            'max_vendors_considered': max_vendors
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting vendor combination: {e}")
        return jsonify({'error': str(e)}), 500


@recommendations_bp.route('/<int:solution_id>/recommendations/vendors/validate-gaps', methods=['POST'])
@login_required
@require_solution
def validate_vendor_gaps(solution_id, solution):
    """Identify capability gaps for selected vendors"""
    try:
        data = request.get_json() or {}
        selected_vendors = data.get('vendors', [])
        
        if not selected_vendors:
            return jsonify({'error': 'vendors list required'}), 400
        
        aggregator = VendorCapabilityAggregator()
        gap_analysis = aggregator.identify_capability_gaps(
            solution,
            selected_vendors
        )
        
        return jsonify({
            'solution_id': solution_id,
            'solution_name': solution.name,
            'selected_vendors': selected_vendors,
            'required_capabilities': gap_analysis.get('required_capabilities', []),
            'covered_capabilities_count': gap_analysis.get('covered_count', 0),
            'capability_gaps': gap_analysis.get('gaps', []),
            'gap_count': gap_analysis.get('gap_count', 0),
            'mitigation_options': gap_analysis.get('mitigation_options', [])
        }), 200
    
    except Exception as e:
        logger.error(f"Error validating vendor gaps: {e}")
        return jsonify({'error': str(e)}), 500


@recommendations_bp.route('/<int:solution_id>/recommendations/process-hierarchy', methods=['GET'])
@login_required
@require_solution
def get_process_hierarchy(solution_id, solution):
    """Retrieve APQC process hierarchy reference"""
    try:
        category = request.args.get('category', None)
        
        recommender = APQCProcessRecommender()
        hierarchy = recommender.get_process_hierarchy(category)
        
        return jsonify({
            'solution_id': solution_id,
            'category_filter': category,
            'process_hierarchy': hierarchy,
            'reference': 'APQC Process Classification Framework'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting process hierarchy: {e}")
        return jsonify({'error': str(e)}), 500


@recommendations_bp.route('/<int:solution_id>/recommendations/summary', methods=['GET'])
@login_required
@require_solution
def get_recommendations_summary(solution_id, solution):
    """Get unified recommendations summary across all services"""
    try:
        # Get APQC recommendations
        apqc = APQCProcessRecommender()
        processes = apqc.recommend_processes(solution, limit=3)
        
        # Get vendor recommendations
        vendor_agg = VendorCapabilityAggregator()
        vendors = vendor_agg.recommend_vendors(solution, limit=3)
        
        return jsonify({
            'solution_id': solution_id,
            'solution_name': solution.name,
            'business_domain': solution.business_domain,
            'recommendations': {
                'top_processes': processes,
                'top_vendors': vendors,
                'process_count': len(processes),
                'vendor_count': len(vendors)
            },
            'summary': {
                'total_apqc_processes_available': len(apqc.process_hierarchy),
                'total_vendors_in_database': len(vendor_agg.vendors),
                'recommendation_confidence': 'HIGH' if len(processes) > 0 and len(vendors) > 0 else 'MEDIUM'
            },
            'next_steps': [
                'Review recommended business processes',
                'Evaluate vendor options',
                'Assess capability gaps',
                'Plan implementation roadmap'
            ]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting recommendations summary: {e}")
        return jsonify({'error': str(e)}), 500
