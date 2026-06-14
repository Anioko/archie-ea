"""
Analytics, natural language query, and recommendation routes.

Routes: analytics/usage, analytics/domains, analytics/quality,
        extensions/analytics/portfolio-health, nl-query, nl-query/examples,
        recommendations, recommendations/quick-stats, recommendations/alerts.
"""

import logging

from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from . import unified_ai_chat_bp
from .chat_views import get_chat_service

logger = logging.getLogger(__name__)


def _default_usage_analytics() -> dict:
    return {
        "total_conversations": 0,
        "total_messages": 0,
        "active_days": 0,
        "avg_messages_per_session": 0,
    }


def _default_domain_analytics() -> dict:
    return {
        "domains": [],
        "total_domains": 0,
        "total_messages": 0,
    }


def _default_quality_metrics() -> dict:
    return {
        "response_quality_score": None,
        "avg_response_time_ms": None,
        "success_rate": 0,
        "feedback_count": 0,
    }

@unified_ai_chat_bp.route("/analytics/usage", methods=["GET"])
@login_required
def get_usage_analytics():
    """Get AI chat usage analytics for the current user."""
    try:
        chat_service = get_chat_service()
        if hasattr(chat_service, "get_usage_analytics"):
            analytics = chat_service.get_usage_analytics(current_user.id)
        else:
            logger.warning("MultiDomainChatService missing get_usage_analytics; returning defaults")
            analytics = _default_usage_analytics()

        return jsonify({"success": True, "analytics": analytics})

    except Exception as e:
        logger.error(f"Usage analytics failed: {e}", exc_info=True)
        return jsonify(
            {
                "success": True,
                "analytics": _default_usage_analytics(),
            }
        )


@unified_ai_chat_bp.route("/analytics/domains", methods=["GET"])
@login_required
def get_domain_analytics():
    """Get usage analytics by domain."""
    try:
        chat_service = get_chat_service()
        if hasattr(chat_service, "get_domain_analytics"):
            analytics = chat_service.get_domain_analytics()
        else:
            logger.warning("MultiDomainChatService missing get_domain_analytics; returning defaults")
            analytics = _default_domain_analytics()

        return jsonify({"success": True, "analytics": analytics})

    except Exception as e:
        logger.error(f"Domain analytics failed: {e}", exc_info=True)
        return jsonify(
            {
                "success": True,
                "analytics": _default_domain_analytics(),
            }
        )


@unified_ai_chat_bp.route("/analytics/quality", methods=["GET"])
@login_required
def get_quality_metrics():
    """Get AI response quality metrics."""
    try:
        chat_service = get_chat_service()
        if hasattr(chat_service, "get_quality_metrics"):
            metrics = chat_service.get_quality_metrics()
        else:
            logger.warning("MultiDomainChatService missing get_quality_metrics; returning defaults")
            metrics = _default_quality_metrics()

        return jsonify({"success": True, "metrics": metrics})

    except Exception as e:
        logger.error(f"Quality metrics failed: {e}", exc_info=True)
        return jsonify(
            {
                "success": True,
                "metrics": _default_quality_metrics(),
            }
        )


@unified_ai_chat_bp.route("/extensions/analytics/portfolio-health", methods=["GET"])
@login_required
def get_portfolio_health():
    """Get portfolio health score and metrics."""
    try:
        scope = request.args.get("scope", "all")
        ALLOWED_SCOPES = {"all", "active", "retiring", "planning", "critical"}
        if scope not in ALLOWED_SCOPES:
            scope = "all"

        chat_service = get_chat_service()
        result = chat_service.get_advanced_analytics(
            "portfolio_health", {"scope": scope}
        )

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting portfolio health: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ============================================================================
# NATURAL LANGUAGE QUERY ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/nl-query", methods=["POST"])
@login_required
@audit_log("natural_language_query")
def natural_language_query():
    """
    Process a natural language query against the database.

    Expected JSON body:
    {
        "query": "Show me all applications without business owner",
        "persona": "enterprise_architect" (optional)
    }
    """
    try:
        from app.services.natural_language_query_service import (
            NaturalLanguageQueryService,
        )

        data = request.get_json()
        if not data or not data.get("query"):
            return jsonify({"success": False, "error": "Query is required"}), 400

        query = data.get("query")
        persona = data.get("persona")

        nl_service = NaturalLanguageQueryService()
        result = nl_service.process_query(query, persona)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Error processing NL query: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An internal error occurred",
                    "suggestions": [
                        "Try: 'Show all applications without business owner'",
                        "Try: 'List capabilities with maturity below 3'",
                        "Try: 'Which vendors expire in 90 days?'",
                    ],
                }
            ),
            500,
        )


@unified_ai_chat_bp.route("/nl-query/examples")
@login_required
def get_query_examples():
    """Get example queries for the NL Query interface."""
    try:
        from app.services.natural_language_query_service import (
            NaturalLanguageQueryService,
        )

        nl_service = NaturalLanguageQueryService()
        examples = nl_service.get_supported_queries()
        return jsonify(examples)

    except Exception as e:
        current_app.logger.error(f"Error getting query examples: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ============================================================================
# RECOMMENDATIONS ENGINE ROUTES
# ============================================================================


@unified_ai_chat_bp.route("/recommendations")
@login_required
def get_recommendations():
    """
    Get actionable recommendations and alerts.

    Query params:
    - persona: Filter by persona (optional)
    - refresh: Force refresh cache (optional)
    """
    try:
        from app.services.recommendations_engine_service import (
            RecommendationsEngineService,
        )

        persona = request.args.get("persona")
        refresh = request.args.get("refresh", "false").lower() == "true"

        rec_service = RecommendationsEngineService()
        recommendations = rec_service.get_all_recommendations(
            persona=persona, refresh=refresh
        )

        return jsonify(recommendations)
    except Exception as e:
        current_app.logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "error": "An internal error occurred",
                    "alerts": [],
                    "recommendations": [],
                    "summary": {"total": 0},
                }
            ),
            500,
        )


@unified_ai_chat_bp.route("/recommendations/quick-stats")
@login_required
def get_quick_stats():
    """Get quick statistics for dashboard display."""
    try:
        from app.services.recommendations_engine_service import (
            RecommendationsEngineService,
        )

        rec_service = RecommendationsEngineService()
        stats = rec_service.get_quick_stats()

        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"Error getting quick stats: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@unified_ai_chat_bp.route("/recommendations/alerts")
@login_required
def get_alerts_only():
    """Get only alerts (for notification badges, etc.)."""
    try:
        from app.services.recommendations_engine_service import (
            RecommendationsEngineService,
        )

        persona = request.args.get("persona")
        rec_service = RecommendationsEngineService()
        data = rec_service.get_all_recommendations(persona=persona)

        # Return only alerts with summary
        return jsonify(
            {
                "alerts": data.get("alerts", []),
                "summary": data.get("summary", {}),
                "health_score": data.get("health_score", 0),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error getting alerts: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred", "alerts": []}), 500


