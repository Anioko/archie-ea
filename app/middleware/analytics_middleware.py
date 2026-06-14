"""COM-013: Auto-pageview analytics middleware.

Registers an after_request hook that captures a $pageview event for every
HTML response when POSTHOG_API_KEY is set.  No-op otherwise.
"""

import logging

from flask import g, request
from flask_login import current_user

logger = logging.getLogger(__name__)


def install_analytics(app) -> None:
    """Register the PostHog pageview after_request hook on *app*.

    Safe to call even when POSTHOG_API_KEY is absent — the AnalyticsService
    will be _enabled=False and every call becomes a no-op.
    """
    from app.services.analytics_service import AnalyticsService

    _svc = AnalyticsService()

    @app.after_request
    def _track_pageview(response):
        try:
            content_type = response.content_type or ""
            if "text/html" not in content_type:
                return response

            if not getattr(current_user, "is_authenticated", False):
                return response

            org_id = getattr(g, "current_org_id", None)
            user_id = getattr(current_user, "id", None)
            if user_id is None:
                return response

            distinct_id = f"{org_id}:{user_id}"
            _svc.page(
                distinct_id=distinct_id,
                page_name=request.path,
                properties={
                    "page": request.endpoint,
                    "path": request.path,
                    "org_id": org_id,
                    "user_id": user_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("PostHog pageview tracking failed (non-blocking): %s", exc)

        return response
