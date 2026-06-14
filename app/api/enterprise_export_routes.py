"""Enterprise export API routes - PDF, PowerPoint, Excel, ArchiMate XML

Provides download endpoints for Fortune 500 export formats.
All exports require authentication and audit logging.
"""

from flask import Blueprint, send_file, request, abort, current_app
from flask_login import login_required, current_user
from io import BytesIO
from datetime import datetime
import logging

from app.services.enterprise_export import EnterpriseExportService
from app.models import Solution, Application
from app.extensions import db

logger = logging.getLogger(__name__)

export_bp = Blueprint('enterprise_export', __name__, url_prefix='/api/export')


@export_bp.route('/solutions/<int:solution_id>/pdf', methods=['GET'])
@login_required
def export_solution_pdf(solution_id):
    """Export Solution Architecture Document as PDF."""
    solution = Solution.query.get_or_404(solution_id)
    
    # Audit log
    logger.info(f"PDF export: Solution {solution_id} by user {current_user.id}")
    
    try:
        pdf_bytes = EnterpriseExportService.export_solution_pdf(solution_id)
        
        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"SAD_{solution.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        logger.error(f"PDF export failed for solution {solution_id}: {e}")
        abort(500, description="PDF export failed. Contact administrator.")


@export_bp.route('/solutions/<int:solution_id>/pptx', methods=['GET'])
@login_required
def export_solution_pptx(solution_id):
    """Export Solution as PowerPoint presentation."""
    solution = Solution.query.get_or_404(solution_id)
    
    logger.info(f"PowerPoint export: Solution {solution_id} by user {current_user.id}")
    
    try:
        pptx_bytes = EnterpriseExportService.export_solution_pptx(solution_id)
        
        return send_file(
            BytesIO(pptx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            download_name=f"{solution.name.replace(' ', '_')}_Presentation_{datetime.now().strftime('%Y%m%d')}.pptx"
        )
    except Exception as e:
        logger.error(f"PowerPoint export failed: {e}")
        abort(500, description="PowerPoint export failed.")


@export_bp.route('/portfolio/excel', methods=['GET'])
@login_required
def export_portfolio_excel():
    """Export application portfolio to Excel."""
    logger.info(f"Excel portfolio export by user {current_user.id}")
    
    try:
        excel_bytes = EnterpriseExportService.export_portfolio_excel()
        
        return send_file(
            BytesIO(excel_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"Portfolio_Export_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        abort(500, description="Excel export failed.")


@export_bp.route('/archimate/xml', methods=['POST'])
@login_required
def export_archimate_xml():
    """Export ArchiMate elements as Open Exchange Format XML.
    
    Request body:
        {
            "element_ids": [1, 2, 3] or null for all,
            "include_relationships": true
        }
    """
    data = request.get_json() or {}
    element_ids = data.get('element_ids')
    
    logger.info(f"ArchiMate XML export by user {current_user.id}, elements: {len(element_ids) if element_ids else 'all'}")
    
    try:
        xml_content = EnterpriseExportService.export_archimate_xml(element_ids)
        
        return send_file(
            BytesIO(xml_content.encode('utf-8')),
            mimetype='application/xml',
            as_attachment=True,
            download_name=f"ArchiMate_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        )
    except Exception as e:
        logger.error(f"ArchiMate XML export failed: {e}")
        abort(500, description="ArchiMate export failed.")
