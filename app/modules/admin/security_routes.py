from flask import Blueprint, render_template, jsonify, request, current_app
import secrets
from app.services.security_hardening import SecurityMiddleware

security_bp = Blueprint('security_bp', __name__)

@security_bp.route('/admin/security', methods=['GET'])
def security_dashboard():
    # Simulate header status and rate limit stats
    headers = {
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none';",
        'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
    }
    # For demo, show current rate limit store
    rate_limit_stats = list(SecurityMiddleware._rate_limit_store.items())
    return render_template('admin/security.html', headers=headers, rate_limit_stats=rate_limit_stats)

@security_bp.route('/api/admin/security/rotate-secret', methods=['POST'])
def rotate_secret():
    # Generate a new secret key stub
    new_secret = secrets.token_urlsafe(48)
    # Log the action (stub)
    current_app.logger.info(f"SECRET_KEY rotated by user {request.remote_addr}")
    instructions = (
        "A new SECRET_KEY has been generated. To apply, update your config file and restart the server. "
        "Never share this key."
    )
    return jsonify({
        'new_secret_stub': new_secret,
        'instructions': instructions
    })
