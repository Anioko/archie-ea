"""
Rate Limiting Middleware for Architecture Assistant
Sprint 1.3: Security Hardening

Protects AI-heavy endpoints from abuse and DoS attacks.

INSTALLATION:
    pip install flask-limiter redis

USAGE:
    from app.middleware.rate_limiter import limiter

    @bp.route('/api/architecture-assistant/generate-options', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit AI-heavy endpoint
    @login_required
    def generate_options():
        ...
"""

import redis
from flask import current_app, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user


def get_user_identifier():
    """
    Get unique identifier for rate limiting

    Priority:
    1. User ID (if authenticated)
    2. Tenant ID + IP (for tenant-level limits)
    3. IP address only (for anonymous)
    """
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"

    # Fallback to IP address
    return f"ip:{get_remote_address()}"


# Initialize rate limiter
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379/0",
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",  # or "moving-window" for more accuracy
    headers_enabled=True,  # Send X-RateLimit headers
)


def init_limiter(app):
    """Initialize rate limiter with Flask app"""
    limiter.init_app(app)

    # Custom error handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return {
            "error": "Rate limit exceeded",
            "message": f"Too many requests. {e.description}",
            "retry_after": e.description,
        }, 429


# Rate limit configurations for different endpoint types

# Heavy AI operations (expensive LLM calls)
AI_HEAVY_LIMIT = "10 per minute"  # Gap analysis, option generation

# Medium operations (database + some processing)
MEDIUM_LIMIT = "30 per minute"  # Session creation, updates

# Light operations (reads)
LIGHT_LIMIT = "100 per minute"  # List, get operations

# Admin operations
ADMIN_LIMIT = "50 per minute"


# Example usage in routes:

"""
# In app/routes/architecture_assistant_routes.py

from app.middleware.rate_limiter import limiter, AI_HEAVY_LIMIT, MEDIUM_LIMIT, LIGHT_LIMIT

@bp.route('/api/architecture-assistant/gap-analysis', methods=['POST'])
@limiter.limit(AI_HEAVY_LIMIT)  # 10 per minute
@login_required
@requires_permission('gap_analysis.run')
def generate_gap_analysis():
    # Expensive LLM operation
    pass

@bp.route('/api/architecture-assistant/design-solution', methods=['POST'])
@limiter.limit(MEDIUM_LIMIT)  # 30 per minute
@login_required
@requires_permission('architecture.create')
def design_solution():
    # Create session (DB operation)
    pass

@bp.route('/api/architecture-assistant/sessions', methods=['GET'])
@limiter.limit(LIGHT_LIMIT)  # 100 per minute
@login_required
def list_sessions():
    # Read operation
    pass
"""
