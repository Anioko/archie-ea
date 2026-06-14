"""
Phase 4 Workflow Orchestration API Endpoints
GET  /api/solutions/<id>/workflow/tasks
GET  /api/solutions/<id>/workflow/gantt
GET  /api/solutions/<id>/workflow/critical-path
POST /api/solutions/<id>/workflow/estimate
"""

from flask import Blueprint, jsonify, request
from functools import wraps
from sqlalchemy.orm import joinedload  # dead-code-ok
import logging

from app import db
from app.models.solution_models import Solution
from app.models.solution_workflow import SolutionWorkflow, SolutionWorkflowTask  # dead-code-ok
from app.modules.solutions_strategic.v2.services.workflow_orchestrator_service import WorkflowOrchestratorService
from app.modules.solutions_strategic.v2.services.critical_path_analyzer import CriticalPathAnalyzer
from app.modules.solutions_strategic.v2.services.gantt_chart_generator import GanttChartGenerator
from flask_login import login_required

logger = logging.getLogger(__name__)

workflow_api_bp = Blueprint('workflow_api', __name__, url_prefix='/api')


def require_workflow(f):
    """Decorator to ensure workflow exists for solution."""
    @wraps(f)
    def decorated_function(solution_id, *args, **kwargs):
        workflow = SolutionWorkflow.query.filter_by(solution_id=solution_id).first()
        if not workflow:
            return jsonify({
                'error': f'No workflow found for solution {solution_id}',
                'workflow_status': 'not_generated'
            }), 404
        return f(solution_id, workflow, *args, **kwargs)
    return decorated_function


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/tasks', methods=['GET'])
@login_required
@require_workflow
def get_workflow_tasks(solution_id, workflow):
    """
    Get all tasks in the workflow.
    
    Query params:
    - phase: Filter by phase name
    - critical_only: Only return critical path tasks
    """
    try:
        phase_filter = request.args.get('phase')
        critical_only = request.args.get('critical_only', 'false').lower() == 'true'
        
        tasks = workflow.tasks
        
        if phase_filter:
            tasks = [t for t in tasks if t.phase_name == phase_filter]
        
        if critical_only:
            tasks = [t for t in tasks if t.is_critical]
        
        return jsonify({
            'solution_id': solution_id,
            'task_count': len(tasks),
            'tasks': [t.to_dict() for t in tasks],
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching workflow tasks: {str(e)}")
        return jsonify({'error': 'Failed to fetch tasks'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/gantt', methods=['GET'])
@login_required
@require_workflow
def get_workflow_gantt(solution_id, workflow):
    """
    Get Gantt chart data for visualization.
    
    Returns complete Gantt chart structure with:
    - Timeline (weeks)
    - Phases (rows)
    - Bars (tasks)
    - Milestones
    - Dependencies
    - Statistics
    """
    try:
        # Reconstruct Gantt data from workflow
        tasks_data = [t.to_dict() for t in workflow.tasks]
        
        generator = GanttChartGenerator(
            project_start_date=workflow.project_start_date or None,
            tasks=tasks_data
        )
        
        gantt_data = generator.generate_full_gantt_data()
        
        return jsonify({
            'solution_id': solution_id,
            'gantt': gantt_data,
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating Gantt data: {str(e)}")
        return jsonify({'error': 'Failed to generate Gantt chart'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/critical-path', methods=['GET'])
@login_required
@require_workflow
def get_critical_path(solution_id, workflow):
    """
    Get critical path analysis.
    
    Returns:
    - Critical path tasks
    - Project duration
    - Bottlenecks
    - Acceleration opportunities
    - Risk assessment
    """
    try:
        tasks_data = [t.to_dict() for t in workflow.tasks]
        
        analyzer = CriticalPathAnalyzer(tasks_data)
        analyzer.calculate_critical_path()
        summary = analyzer.get_summary()
        
        # Get critical path tasks with details
        critical_tasks = [
            t.to_dict() for t in workflow.tasks 
            if t.is_critical
        ]
        
        return jsonify({
            'solution_id': solution_id,
            'critical_path': summary.get('critical_path', []),
            'critical_tasks': critical_tasks,
            'project_duration_days': summary['project_duration_days'],
            'buffers': summary['buffers'],
            'total_calendar_duration': summary['total_calendar_duration'],
            'risk_assessment': summary['risk_assessment'],
            'bottlenecks': summary['bottlenecks'],
            'acceleration_opportunities': summary['acceleration_opportunities'],
            'recommendation': summary['recommendation'],
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error analyzing critical path: {str(e)}")
        return jsonify({'error': 'Failed to analyze critical path'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/summary', methods=['GET'])
@login_required
@require_workflow
def get_workflow_summary(solution_id, workflow):
    """
    Get high-level workflow summary.
    
    Returns:
    - Timeline overview
    - Phase breakdown
    - Key metrics
    - Status
    """
    try:
        phases_summary = {}
        for phase_name in set(t.phase_name for t in workflow.tasks):
            phase_tasks = [t for t in workflow.tasks if t.phase_name == phase_name]
            phase_start = min((t.earliest_start for t in phase_tasks), default=0)
            phase_end = max((t.earliest_finish for t in phase_tasks), default=0)
            
            phases_summary[phase_name] = {
                'task_count': len(phase_tasks),
                'duration_days': phase_end - phase_start,
                'start_day': phase_start,
                'end_day': phase_end,
                'critical_tasks': sum(1 for t in phase_tasks if t.is_critical)
            }
        
        return jsonify({
            'solution_id': solution_id,
            'workflow_status': 'generated',
            'total_tasks': workflow.num_tasks,
            'total_duration_days': workflow.total_duration_days,
            'buffered_duration_days': workflow.total_duration_days + workflow.total_buffer_days,
            'critical_path_length': workflow.critical_path_length,
            'num_phases': workflow.num_phases,
            'phases': phases_summary,
            'min_team_size': workflow.min_team_size,
            'max_team_size': workflow.max_team_size,
            'risk_confidence': workflow.risk_confidence,
            'project_start': workflow.project_start_date.isoformat() if workflow.project_start_date else None,
            'project_end': workflow.project_end_date.isoformat() if workflow.project_end_date else None,
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching workflow summary: {str(e)}")
        return jsonify({'error': 'Failed to fetch summary'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/phases', methods=['GET'])
@login_required
@require_workflow
def get_workflow_phases(solution_id, workflow):
    """
    Get phase breakdown with task listings.
    
    Returns phases ordered by sequence with all contained tasks.
    """
    try:
        phases_data = []
        
        for phase_name in set(t.phase_name for t in workflow.tasks):
            phase_tasks = sorted(
                [t for t in workflow.tasks if t.phase_name == phase_name],
                key=lambda x: x.phase_sequence
            )
            
            if not phase_tasks:
                continue
            
            phase_info = {
                'phase_name': phase_name,
                'sequence': phase_tasks[0].phase_sequence,
                'task_count': len(phase_tasks),
                'duration_days': sum(t.duration_days for t in phase_tasks),
                'critical_tasks': [t.task_id for t in phase_tasks if t.is_critical],
                'tasks': [t.to_dict() for t in phase_tasks]
            }
            phases_data.append(phase_info)
        
        # Sort by sequence
        phases_data.sort(key=lambda p: p['sequence'])
        
        return jsonify({
            'solution_id': solution_id,
            'num_phases': len(phases_data),
            'phases': phases_data,
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching phases: {str(e)}")
        return jsonify({'error': 'Failed to fetch phases'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/estimate', methods=['POST'])
@login_required
def post_workflow_estimate(solution_id):
    """
    Generate or regenerate workflow estimate.
    
    Request body:
    {
        'force_regenerate': bool (optional, default False)
    }
    
    Returns: Created/updated workflow
    """
    try:
        # Check if solution exists
        solution = Solution.query.get(solution_id)
        if not solution:
            return jsonify({'error': f'Solution {solution_id} not found'}), 404
        
        # Check if workflow already exists
        existing_workflow = SolutionWorkflow.query.filter_by(solution_id=solution_id).first()
        force_regenerate = request.json.get('force_regenerate', False) if request.json else False
        
        if existing_workflow and not force_regenerate:
            return jsonify({
                'message': 'Workflow already exists',
                'workflow': existing_workflow.to_dict(include_tasks=False)
            }), 200
        
        if existing_workflow and force_regenerate:
            # Delete old workflow
            db.session.delete(existing_workflow)
            db.session.commit()
        
        # Generate new workflow
        orchestrator = WorkflowOrchestratorService()
        workflow = orchestrator.generate_workflow(
            solution_id=solution_id,
            solution_description=solution.description
        )
        
        if not workflow:
            return jsonify({
                'error': 'Failed to generate workflow',
                'reason': 'Orchestrator service error'
            }), 500
        
        return jsonify({
            'message': 'Workflow generated successfully',
            'workflow': workflow.to_dict(include_tasks=False)
        }), 201
    
    except Exception as e:
        logger.error(f"Error generating workflow estimate: {str(e)}")
        return jsonify({'error': 'Failed to generate estimate'}), 500


@workflow_api_bp.route('/solutions/<int:solution_id>/workflow/dependencies', methods=['GET'])
@login_required
@require_workflow
def get_task_dependencies(solution_id, workflow):
    """
    Get task dependency graph.
    
    Returns:
    - All tasks with dependency information
    - Dependency edges
    - Blocking relationships
    """
    try:
        # Build dependency map
        dependency_graph = {
            'nodes': [],
            'edges': []
        }
        
        for task in workflow.tasks:
            dependency_graph['nodes'].append({
                'id': task.task_id,
                'title': task.title,
                'phase': task.phase_name,
                'duration': task.duration_days,
                'is_critical': task.is_critical,
                'earliest_start': task.earliest_start
            })
            
            for dep_id in (task.dependencies or []):
                dependency_graph['edges'].append({
                    'from': dep_id,
                    'to': task.task_id,
                    'type': 'blocks'
                })
        
        return jsonify({
            'solution_id': solution_id,
            'dependency_graph': dependency_graph,
            'timestamp': workflow.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching dependencies: {str(e)}")
        return jsonify({'error': 'Failed to fetch dependencies'}), 500
