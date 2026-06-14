"""
Phase 2: Real-time Suggestion API Endpoints

GET  /api/solutions/<id>/suggestions/vendors
GET  /api/solutions/<id>/suggestions/archimate
GET  /api/solutions/<id>/suggestions/next-actions
GET  /api/solutions/<id>/suggestions/risks
GET  /api/solutions/<id>/suggestions/costs
POST /api/solutions/<id>/suggestions/feedback
"""

from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.ai_suggestion import AISuggestion
from app.models.solution_models import Solution
from app.models.user import Permission, Role
from app.models.solution_reasoning import SolutionAIReasoningState
from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import SolutionAIOrchestrator
from app.modules.solutions_strategic.v2.services.solution_explainability_service import SolutionExplainabilityService
from functools import wraps
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('solution_suggestions_api', __name__, url_prefix='/api/solutions')

# Mutation methods that require ownership verification
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def require_solution(f):
    """Decorator: verify solution exists; for mutations also verify ownership.

    Ownership rule: current_user must either be the solution creator
    (created_by_id) OR have an Administrator/Architect role (permissions >= 64).
    This prevents one architect from mutating another's solution data while
    allowing admins to manage the platform.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        solution_id = kwargs.get('solution_id')
        solution = Solution.query.get(solution_id)

        if not solution:
            return jsonify({'error': f'Solution {solution_id} not found'}), 404

        if request.method in _MUTATION_METHODS:
            # Admins and solution owners may mutate; anyone else gets 403.
            # Use can() first, then fall back to a direct Role query if the
            # backref relationship fails to load (known lazy="dynamic" issue
            # with the Role.users relationship).
            user_is_admin = current_user.can(Permission.ADMINISTER)
            if not user_is_admin and getattr(current_user, 'role_id', None):
                # Fallback: query Role directly to avoid lazy="dynamic" backref issues
                role_obj = db.session.get(Role, current_user.role_id)
                if role_obj and role_obj.permissions is not None:
                    user_is_admin = bool(
                        (role_obj.permissions & Permission.ADMINISTER) == Permission.ADMINISTER
                    )
            user_is_owner = (
                getattr(solution, 'created_by_id', None) is not None
                and solution.created_by_id == current_user.id
            )
            if not (user_is_admin or user_is_owner):
                logger.warning(
                    "Ownership check failed: user %s attempted mutation on solution %s",
                    current_user.id, solution_id,
                )
                return jsonify({'error': 'Forbidden: you do not own this solution'}), 403

        kwargs['solution'] = solution
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/<int:solution_id>/suggestions/vendors', methods=['GET'])
@login_required
@require_solution
def get_vendor_suggestions(solution_id, solution):
    """Fetch vendor recommendations — AI reasoning state + capability-backed pricing."""
    try:
        # --- Existing: AI reasoning state suggestions ---
        state = None
        ai_suggestions = []
        try:
            state = SolutionAIReasoningState.query.filter_by(
                solution_id=solution_id
            ).order_by(SolutionAIReasoningState.created_at.desc()).first()
            if state and state.suggestions:
                ai_suggestions = state.suggestions.get('vendors', [])
        except Exception as e:
            logger.warning("AI reasoning state lookup failed for solution %s: %s", solution_id, e)

        # --- Capability-backed suggestions from VendorProductCapability ---
        capability_suggestions = []
        cap_ids_param = request.args.get('capability_ids', '')
        if cap_ids_param:
            try:
                cap_ids = [int(x.strip()) for x in cap_ids_param.split(',') if x.strip()]
                if cap_ids:
                    from app.modules.solutions_strategic.v2.services.vendor_suggestion_service import VendorSuggestionService
                    svc = VendorSuggestionService()
                    capability_suggestions = svc.get_capability_backed_suggestions(cap_ids)
                else:
                    logger.debug("capability_ids param present but parsed to empty list for solution %s", solution_id)
            except Exception as e:
                logger.warning("Capability suggestion lookup failed for solution %s: %s", solution_id, e)

        return jsonify({
            'solution_id': solution_id,
            'suggestions': ai_suggestions,
            'capability_suggestions': capability_suggestions,
            'confidence': state.confidence_score if state else None,
            'phase': state.adm_phase if state else None,
            'generated_at': state.created_at.isoformat() if state else None,
            'count': len(ai_suggestions),
            'capability_count': len(capability_suggestions),
        }), 200

    except Exception as e:
        logger.error("Unhandled error in vendor suggestions for solution %s: %s", solution_id, e, exc_info=True)
        return jsonify({
            'solution_id': solution_id,
            'suggestions': [],
            'capability_suggestions': [],
            'confidence': None,
            'phase': None,
            'generated_at': None,
            'count': 0,
            'capability_count': 0,
            'error': 'Internal error fetching vendor suggestions',
        }), 200


@api_bp.route('/<int:solution_id>/suggestions/vendors/confirm', methods=['POST'])
@login_required
@require_solution
def confirm_vendor_suggestion(solution_id, solution):
    """Confirm a vendor pricing suggestion — promotes to architect_confirmed."""
    try:
        data = request.get_json()
        if not data or 'pricing_id' not in data:
            return jsonify({'error': 'pricing_id required'}), 400

        from app.modules.solutions_strategic.v2.services.vendor_suggestion_service import VendorSuggestionService
        svc = VendorSuggestionService()
        result = svc.confirm_suggestion(
            pricing_id=data['pricing_id'],
            user_id=current_user.id,
        )
        return jsonify({
            'success': True,
            **result,
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error confirming vendor suggestion: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/vendors/update-pricing', methods=['POST'])
@login_required
@require_solution
def update_vendor_pricing(solution_id, solution):
    """Inline correction — architect updates vendor pricing."""
    try:
        data = request.get_json()
        if not data or 'pricing_id' not in data or 'annual_cost' not in data:
            return jsonify({'error': 'pricing_id and annual_cost required'}), 400

        # Validate pricing_id is an integer
        pricing_id = data['pricing_id']
        if not isinstance(pricing_id, int):
            return jsonify({'error': 'pricing_id must be an integer'}), 400

        # Validate annual_cost is numeric and within bounds
        annual_cost = data['annual_cost']
        if not isinstance(annual_cost, (int, float)):
            return jsonify({'error': 'annual_cost must be a number'}), 400
        if annual_cost < 0:
            return jsonify({'error': 'annual_cost must be >= 0'}), 400
        if annual_cost > 100_000_000:
            return jsonify({'error': 'annual_cost must be <= 100,000,000'}), 400

        from app.modules.solutions_strategic.v2.services.vendor_suggestion_service import VendorSuggestionService
        svc = VendorSuggestionService()
        result = svc.update_pricing(pricing_id, float(annual_cost), current_user.id)
        return jsonify({'success': True, **result}), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error updating vendor pricing: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/vendors/vote-coverage', methods=['POST'])
@login_required
@require_solution
def vote_vendor_coverage(solution_id, solution):
    """Vote on vendor capability coverage percentage."""
    try:
        data = request.get_json()
        if not data or 'mapping_id' not in data:
            return jsonify({'error': 'mapping_id required'}), 400

        # Validate mapping_id is an integer
        mapping_id = data['mapping_id']
        if not isinstance(mapping_id, int):
            return jsonify({'error': 'mapping_id must be an integer'}), 400

        # Validate adjusted_coverage if provided
        adjusted_coverage = data.get('adjusted_coverage')
        if adjusted_coverage is not None:
            if not isinstance(adjusted_coverage, (int, float)):
                return jsonify({'error': 'adjusted_coverage must be a number'}), 400
            if not (0 <= adjusted_coverage <= 100):
                return jsonify({'error': 'adjusted_coverage must be between 0 and 100'}), 400

        from app.modules.solutions_strategic.v2.services.vendor_suggestion_service import VendorSuggestionService
        svc = VendorSuggestionService()
        result = svc.vote_coverage(
            mapping_id, data.get('vote_up', True), adjusted_coverage
        )
        return jsonify({'success': True, **result}), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error recording coverage vote: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/archimate', methods=['GET'])
@login_required
@require_solution
def get_archimate_suggestions(solution_id, solution):
    """Fetch ArchiMate element recommendations with optional decision_point grouping"""
    try:
        state = SolutionAIReasoningState.query.filter_by(
            solution_id=solution_id
        ).order_by(SolutionAIReasoningState.created_at.desc()).first()

        if not state or not state.suggestions:
            return jsonify({
                'solution_id': solution_id,
                'suggestions': [],
                'message': 'No ArchiMate suggestions available yet'
            }), 200

        archimate_suggestions = state.suggestions.get('archimate', [])

        # Optional filters — backward compatible (no params returns all)
        layer_filter = request.args.get('layer', '').strip().lower()
        type_filter = request.args.get('element_type', '').strip().lower()
        if layer_filter:
            archimate_suggestions = [
                e for e in archimate_suggestions
                if e.get('layer', '').lower() == layer_filter
            ]
        if type_filter:
            archimate_suggestions = [
                e for e in archimate_suggestions
                if e.get('element_type', '').lower() == type_filter
            ]

        # Build grouped view by decision_point
        groups = _group_by_decision_point(archimate_suggestions)

        return jsonify({
            'solution_id': solution_id,
            'suggestions': {
                'groups': groups,
                'flat': archimate_suggestions,
            },
            'confidence': state.confidence_score,
            'phase': state.adm_phase,
            'generated_at': state.created_at.isoformat(),
            'count': len(archimate_suggestions),
            'filters_applied': {
                'layer': layer_filter or None,
                'element_type': type_filter or None,
            },
        }), 200

    except Exception as e:
        logger.error(f"Error fetching ArchiMate suggestions: {e}")
        return jsonify({'error': str(e)}), 500


def _group_by_decision_point(elements):
    """Group ArchiMate suggestion elements by their decision_point field.

    Returns a list of dicts, each with ``decision_point`` and ``elements`` keys.
    Elements without a ``decision_point`` are placed in an "Uncategorized" group.
    """
    from collections import OrderedDict

    grouped = OrderedDict()
    for elem in elements:
        dp = elem.get('decision_point') or 'Uncategorized'
        grouped.setdefault(dp, []).append(elem)

    return [
        {'decision_point': dp, 'elements': elems}
        for dp, elems in grouped.items()
    ]


@api_bp.route('/<int:solution_id>/suggestions/next-actions', methods=['GET'])
@login_required
@require_solution
def get_next_actions(solution_id, solution):
    """Fetch recommended next phase actions"""
    try:
        orchestrator = SolutionAIOrchestrator()
        
        # Get next actions from orchestrator - use solution_id not solution
        try:
            next_actions = orchestrator.suggest_next_actions(solution_id=solution_id)
        except (AttributeError, TypeError) as e:
            logger.warning(f"suggest_next_actions failed: {e}. Returning empty.")
            next_actions = []
        
        return jsonify({
            'solution_id': solution_id,
            'next_actions': next_actions if isinstance(next_actions, list) else [],
            'count': len(next_actions) if isinstance(next_actions, list) else 0
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching next actions: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/risks', methods=['GET'])
@login_required
@require_solution
def get_risk_suggestions(solution_id, solution):
    """Fetch identified risks and mitigation strategies with explainability"""
    try:
        state = SolutionAIReasoningState.query.filter_by(
            solution_id=solution_id
        ).order_by(SolutionAIReasoningState.created_at.desc()).first()
        
        if not state or not state.suggestions:
            return jsonify({
                'solution_id': solution_id,
                'suggestions': [],
                'message': 'No risk suggestions available yet'
            }), 200
        
        risk_suggestions = state.suggestions.get('risks', [])
        
        # Add explainability if available
        explainability_service = SolutionExplainabilityService()
        risk_explanation = explainability_service.explain_risk_assessment(
            risks=risk_suggestions,
            solution=solution
        )
        
        return jsonify({
            'solution_id': solution_id,
            'suggestions': risk_suggestions,
            'confidence': state.confidence_score,
            'explainability': risk_explanation,
            'uncertainty_factors': state.uncertainty_factors,
            'phase': state.adm_phase,
            'generated_at': state.created_at.isoformat(),
            'count': len(risk_suggestions)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching risk suggestions: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/costs', methods=['GET'])
@login_required
@require_solution
def get_cost_suggestions(solution_id, solution):
    """Fetch cost estimation and financial recommendations with explainability"""
    try:
        state = SolutionAIReasoningState.query.filter_by(
            solution_id=solution_id
        ).order_by(SolutionAIReasoningState.created_at.desc()).first()
        
        if not state or not state.suggestions:
            return jsonify({
                'solution_id': solution_id,
                'suggestion': None,
                'message': 'No cost estimate available yet'
            }), 200
        
        cost_estimate = state.suggestions.get('cost_estimate', None)
        
        # Add explainability if available
        explainability_service = SolutionExplainabilityService()
        if cost_estimate:
            cost_explanation = explainability_service.explain_cost_estimate(
                estimate=cost_estimate.get('total', 0),
                components=cost_estimate.get('components', {}),
                solution=solution
            )
        else:
            cost_explanation = None
        
        return jsonify({
            'solution_id': solution_id,
            'suggestion': cost_estimate,
            'confidence': state.confidence_score,
            'confidence_intervals': state.confidence_intervals,
            'explainability': cost_explanation,
            'phase': state.adm_phase,
            'generated_at': state.created_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching cost suggestions: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/feedback', methods=['POST'])
@login_required
@require_solution
def submit_suggestion_feedback(solution_id, solution):
    """Record user feedback on suggestion"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate feedback
        feedback = data.get('type') or data.get('feedback')  # Accept either key
        reason = data.get('reason', '')
        reasoning_state_id = data.get('reasoning_state_id')
        
        if not feedback:
            return jsonify({'error': 'Feedback required (accepted/rejected/needs_refinement)'}), 400
        
        # Normalize feedback values
        if feedback == 'accepted':
            feedback = 'accept'
        elif feedback == 'rejected':
            feedback = 'reject'
        elif feedback == 'needs_refinement':
            feedback = 'modify'
        
        if feedback not in ['accept', 'reject', 'modify']:
            return jsonify({'error': 'Invalid feedback value'}), 400
        
        # Get reasoning state
        state = SolutionAIReasoningState.query.get(reasoning_state_id) if reasoning_state_id else \
                SolutionAIReasoningState.query.filter_by(
                    solution_id=solution_id
                ).order_by(SolutionAIReasoningState.created_at.desc()).first()
        
        if not state:
            return jsonify({'error': 'No reasoning state found for this solution'}), 404
        
        # Record feedback
        orchestrator = SolutionAIOrchestrator()
        result = orchestrator.record_feedback(
            reasoning_state_id=state.id,
            feedback=feedback,
            reason=reason
        )
        
        return jsonify({
            'success': True,
            'reasoning_state_id': state.id,
            'feedback_recorded': True,
            'message': 'Feedback recorded successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/regenerate', methods=['POST'])
@login_required
@require_solution
def regenerate_suggestions(solution_id, solution):
    """Trigger fresh AI analysis for a solution."""
    try:
        from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import SolutionAIOrchestrator
        orchestrator = SolutionAIOrchestrator()
        result = orchestrator.enhance_solution_creation(
            solution=solution,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        return jsonify({
            'success': result.get('success', False),
            'message': 'AI analysis complete' if result.get('success') else result.get('error', 'Analysis failed'),
        }), 200
    except Exception as e:
        logger.error(f"Error regenerating suggestions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/status', methods=['GET'])
@login_required
@require_solution
def get_suggestion_status(solution_id, solution):
    """Check status of AI enhancements for solution"""
    try:
        state = SolutionAIReasoningState.query.filter_by(
            solution_id=solution_id
        ).order_by(SolutionAIReasoningState.created_at.desc()).first()
        
        if not state:
            return jsonify({
                'solution_id': solution_id,
                'enhanced': False,
                'message': 'Solution not yet enhanced by AI'
            }), 200
        
        return jsonify({
            'solution_id': solution_id,
            'enhanced': True,
            'reasoning_state_id': state.id,
            'phase': state.adm_phase,
            'confidence': state.confidence_score,
            'has_feedback': state.has_feedback,
            'suggestion_types': list(state.suggestions.keys()) if state.suggestions else [],
            'last_updated': state.created_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error checking suggestion status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/<int:solution_id>/suggestions/<int:suggestion_id>/verdict', methods=['PUT'])
@login_required
@require_solution
def record_suggestion_verdict(solution_id, suggestion_id, solution):
    """Record architect's verdict on an AI suggestion for confidence calibration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        verdict = data.get('verdict')
        if verdict not in ('accepted', 'modified', 'rejected'):
            return jsonify({'error': 'verdict must be accepted, modified, or rejected'}), 400

        suggestion = db.session.get(AISuggestion, suggestion_id)
        if not suggestion:
            return jsonify({'error': 'Suggestion not found'}), 404

        suggestion.architect_verdict = verdict
        suggestion.verdict_note = data.get('note', '')
        suggestion.verdict_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'verdict': verdict,
            'suggestion_id': suggestion_id,
        }), 200

    except Exception as e:
        logger.error(f"Error recording suggestion verdict: {e}")
        return jsonify({'error': str(e)}), 500
