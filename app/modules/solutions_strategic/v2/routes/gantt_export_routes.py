"""
ent-05 Gantt Chart Export API Routes
- GET  /api/solutions/<id>/gantt-export/csv
- GET  /api/solutions/<id>/gantt-export/svg
- POST /api/solutions/<id>/gantt-export/png (async)
"""

from flask import Blueprint, jsonify, request, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
import logging
import io
from datetime import datetime

from app import db
from app.models.solution_models import Solution
from app.models.roadmap_models import RoadmapWorkPackage
from app.modules.solutions_strategic.v2.services.gantt_enhancement_service import (
    GanttExportService,
    CriticalPathAnalyzer,
    RiskScoringService
)

logger = logging.getLogger(__name__)

gantt_export_bp = Blueprint('gantt_export', __name__, url_prefix='/api')


@gantt_export_bp.route('/solutions/<int:solution_id>/gantt-export/csv', methods=['GET'])
@login_required
def export_gantt_csv(solution_id: int):
    """Export Gantt chart to CSV format."""
    try:
        solution = Solution.query.get_or_404(solution_id)
        
        # Get work packages
        work_packages = RoadmapWorkPackage.query.filter_by(
            source_id=solution_id, source_type="solution"
        ).all()
        
        # Transform to Gantt format
        tasks = [
            {
                'id': str(wp.id),
                'name': wp.name,
                'group': wp.business_capability or 'General',
                'start_date': wp.start_date.isoformat() if wp.start_date else None,
                'end_date': wp.end_date.isoformat() if wp.end_date else None,
                'status': wp.status or 'planned',
                'progress': wp.progress_percentage or 0,
                'dependencies': [],
                'meta': {
                    'priority': wp.priority or 'medium',
                    'assigned_to': wp.assigned_to or 'Unassigned',
                    'estimated_cost': f'£{wp.estimated_cost:,.0f}' if wp.estimated_cost else '—',
                    'risk_level': wp.risk_level or 'medium',
                }
            }
            for wp in work_packages
        ]
        
        # Generate CSV
        csv_data = GanttExportService.export_to_csv(tasks, {})
        
        # Return as file download
        return send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'gantt-{solution.id}-{datetime.now().strftime("%Y%m%d")}.csv'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Gantt CSV: {e}", exc_info=True)
        return jsonify({'error': 'Failed to export Gantt chart'}), 500


@gantt_export_bp.route('/solutions/<int:solution_id>/gantt-export/svg', methods=['GET'])
@login_required
def export_gantt_svg(solution_id: int):
    """Export Gantt chart to SVG format."""
    try:
        solution = Solution.query.get_or_404(solution_id)
        
        # Get work packages
        work_packages = RoadmapWorkPackage.query.filter_by(
            source_id=solution_id, source_type="solution"
        ).all()
        
        # Transform to Gantt format
        tasks = [
            {
                'id': str(wp.id),
                'name': wp.name,
                'group': wp.business_capability or 'General',
                'start_date': wp.start_date.isoformat() if wp.start_date else None,
                'end_date': wp.end_date.isoformat() if wp.end_date else None,
                'status': wp.status or 'planned',
                'progress': wp.progress_percentage or 0,
                'dependencies': [],
                'meta': {
                    'priority': wp.priority or 'medium',
                    'assigned_to': wp.assigned_to or 'Unassigned',
                    'estimated_cost': f'£{wp.estimated_cost:,.0f}' if wp.estimated_cost else '—',
                    'risk_level': wp.risk_level or 'medium',
                }
            }
            for wp in work_packages
        ]
        
        # Generate SVG
        svg_data = GanttExportService.export_to_svg(tasks, {})
        
        # Return as file download
        return send_file(
            io.BytesIO(svg_data.encode('utf-8')),
            mimetype='image/svg+xml',
            as_attachment=True,
            download_name=f'gantt-{solution.id}-{datetime.now().strftime("%Y%m%d")}.svg'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Gantt SVG: {e}", exc_info=True)
        return jsonify({'error': 'Failed to export Gantt chart'}), 500


@gantt_export_bp.route('/solutions/<int:solution_id>/gantt-export/png', methods=['POST'])
@login_required
def export_gantt_png(solution_id: int):
    """Export Gantt chart to PNG format (async)."""
    try:
        solution = Solution.query.get_or_404(solution_id)
        
        # This would normally trigger an async job
        # For now, return a message that this feature is in progress
        return jsonify({
            'status': 'pending',
            'message': 'PNG export is being processed. Feature coming soon.',
            'job_id': None
        }), 202
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Gantt PNG export: {e}", exc_info=True)
        return jsonify({'error': 'Failed to start export'}), 500


@gantt_export_bp.route('/solutions/<int:solution_id>/gantt-risk-analysis', methods=['GET'])
@login_required
def get_gantt_risk_analysis(solution_id: int):
    """Get risk analysis for Gantt chart tasks."""
    try:
        solution = Solution.query.get_or_404(solution_id)
        
        # Get work packages
        work_packages = RoadmapWorkPackage.query.filter_by(
            source_id=solution_id, source_type="solution"
        ).all()
        
        # Transform to Gantt format
        tasks = [
            {
                'id': str(wp.id),
                'name': wp.name,
                'group': wp.business_capability or 'General',
                'start_date': wp.start_date.isoformat() if wp.start_date else None,
                'end_date': wp.end_date.isoformat() if wp.end_date else None,
                'status': wp.status or 'planned',
                'progress': wp.progress_percentage or 0,
                'is_critical': wp.is_critical or False,
                'meta': {
                    'priority': wp.priority or 'medium',
                    'risk_level': wp.risk_level or 'medium',
                }
            }
            for wp in work_packages
        ]
        
        # Calculate portfolio risk
        portfolio_risk = RiskScoringService.calculate_portfolio_risk(tasks)
        
        # Assess individual task risks
        task_risks = [
            {
                'task_id': t['id'],
                'task_name': t['name'],
                'assessed_risk': RiskScoringService.assess_task_risk(t),
                'risk_color': RiskScoringService.get_risk_color(
                    RiskScoringService.assess_task_risk(t)
                )
            }
            for t in tasks
        ]
        
        return jsonify({
            'portfolio_risk': portfolio_risk,
            'task_risks': task_risks
        }), 200
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Gantt risk analysis: {e}", exc_info=True)
        return jsonify({'error': 'Failed to analyze risks'}), 500


@gantt_export_bp.route('/solutions/<int:solution_id>/gantt-critical-path', methods=['GET'])
@login_required
def get_gantt_critical_path(solution_id: int):
    """Get critical path analysis for Gantt chart."""
    try:
        solution = Solution.query.get_or_404(solution_id)
        
        # Get work packages
        work_packages = RoadmapWorkPackage.query.filter_by(
            source_id=solution_id, source_type="solution"
        ).all()
        
        # Transform to Gantt format
        tasks = [
            {
                'id': str(wp.id),
                'name': wp.name,
                'start_date': wp.start_date.isoformat() if wp.start_date else None,
                'end_date': wp.end_date.isoformat() if wp.end_date else None,
                'dependencies': []
            }
            for wp in work_packages
        ]
        
        # Calculate critical path
        critical_tasks, critical_length = CriticalPathAnalyzer.calculate_critical_path(tasks)
        
        return jsonify({
            'critical_tasks': critical_tasks,
            'critical_path_length_days': critical_length,
            'critical_path_length_weeks': round(critical_length / 7, 1),
            'total_tasks': len(tasks),
            'critical_task_count': len(critical_tasks),
            'parallelization_potential': round((len(tasks) - len(critical_tasks)) / max(len(tasks), 1), 2)
        }), 200
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating critical path: {e}", exc_info=True)
        return jsonify({'error': 'Failed to calculate critical path'}), 500
