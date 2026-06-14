from flask import Blueprint, render_template, request, jsonify, current_app
from app.services.analytics_service import AnalyticsService

analytics_bp = Blueprint('analytics_bp', __name__)
service = AnalyticsService()

@analytics_bp.route('/admin/analytics', methods=['GET'])
def analytics_dashboard():
    return render_template('admin/analytics.html')

@analytics_bp.route('/api/analytics/event', methods=['POST'])
def track_event():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    event_name = data.get('event_name')
    properties = data.get('properties', {})
    if not user_id or not event_name:
        return jsonify({'error': 'user_id and event_name required'}), 400
    service.track_event(user_id, event_name, properties)
    return jsonify({'status': 'ok'})
