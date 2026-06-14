from flask import Blueprint, render_template, jsonify
from app.services.platform_health_service import platform_health_service
from app.services.rbac_service import rbac_service

health_bp = Blueprint('health_bp', __name__)

@health_bp.route('/admin/health')
@rbac_service.require_role('org_admin')
def health_dashboard():
    summary = platform_health_service.get_health_summary()
    components = platform_health_service.get_component_status()
    error_trend = platform_health_service.get_error_trend()
    return render_template('admin/health.html', summary=summary, components=components, error_trend=error_trend)

@health_bp.route('/api/admin/health/status')
@rbac_service.require_role('org_admin')
def api_health_status():
    return jsonify(platform_health_service.get_health_summary())

@health_bp.route('/api/admin/health/components')
@rbac_service.require_role('org_admin')
def api_health_components():
    return jsonify(platform_health_service.get_component_status())
