"""COM-013: PostHog product analytics service.

Design:
- Reads POSTHOG_API_KEY and POSTHOG_HOST from environment at init time.
- If POSTHOG_API_KEY is not set, all methods are graceful no-ops.
- All HTTP calls run in background daemon threads (fire-and-forget) with a
  2-second timeout so they never slow down the main request.
- distinct_id format: "{org_id}:{user_id}"
"""

import logging
import os
import threading
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_CAPTURE_PATH = "/capture/"


class AnalyticsService:
    def __init__(self) -> None:
        self.api_key: str = os.environ.get("POSTHOG_API_KEY", "")
        self.host: str = os.environ.get(
            "POSTHOG_HOST", "https://app.posthog.com"
        ).rstrip("/")
        self._enabled: bool = bool(self.api_key)
        if not self._enabled:
            logger.debug("PostHog: POSTHOG_API_KEY not set — analytics disabled.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, payload: Dict[str, Any]) -> None:
        """Fire-and-forget: POST *payload* to PostHog in a background thread."""
        if not self._enabled:
            return

        def _send() -> None:
            try:
                requests.post(
                    f"{self.host}{_CAPTURE_PATH}",
                    json=payload,
                    timeout=2,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("PostHog send failed (non-blocking): %s", exc)

        t = threading.Thread(target=_send, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Capture a custom analytics event.

        No-op when POSTHOG_API_KEY is not set.
        """
        if not self._enabled:
            logger.debug("PostHog no-op: capture(%s, %s)", distinct_id, event)
            return

        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "distinct_id": distinct_id,
            "event": event,
            "properties": properties or {},
        }
        self._post(payload)

    def identify(
        self,
        distinct_id: str,
        user_properties: Dict[str, Any],
    ) -> None:
        """Send an $identify call to set persistent user properties.

        Typically called after login with org_id, role, plan, etc.
        No-op when POSTHOG_API_KEY is not set.
        """
        if not self._enabled:
            logger.debug("PostHog no-op: identify(%s)", distinct_id)
            return

        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "distinct_id": distinct_id,
            "event": "$identify",
            "properties": {
                "$set": user_properties,
            },
        }
        self._post(payload)

    def page(
        self,
        distinct_id: str,
        page_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a $pageview event.

        No-op when POSTHOG_API_KEY is not set.
        """
        if not self._enabled:
            logger.debug("PostHog no-op: page(%s, %s)", distinct_id, page_name)
            return

        props: Dict[str, Any] = dict(properties or {})
        props["$current_url"] = page_name
        self.capture(distinct_id, "$pageview", props)
