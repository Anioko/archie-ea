"""Internal API bridge — the single in-process path for calling this app's
own Flask routes without a real network hop.

Two callers, two modes, one function:

- **MCP tools** (``app/modules/mcp/tools/*``) call with ``bearer=``. The
  inner request is dispatched with a fresh, empty cookie jar carrying only
  the caller's OAuth bearer token — it authenticates through
  ``app.modules.oauth_provider.identity`` exactly as an external bearer
  request would, and never sees the outer request's session or ``g``.
- ``app.modules.ai_chat.services.nl_query_router`` calls with
  ``pass_session=True``, its existing behaviour from before this module
  existed, unchanged.

Every call sets the ``archie.internal_bridge`` WSGI environ key. This is not
an HTTP header — a real client cannot set it, because WSGI servers only
populate ``HTTP_*`` environ keys from actual request headers — so
``app.modules.oauth_provider.identity`` can trust it to recognise a
same-process dispatch.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from flask import current_app


class InternalAPIResult:
    """The result of one in-process call, mirroring a real HTTP response."""

    __slots__ = ("status_code", "json", "raw_body", "latency_ms")

    def __init__(self, status_code: int, json_body: Any, raw_body: bytes, latency_ms: float):
        self.status_code = status_code
        self.json = json_body
        self.raw_body = raw_body
        self.latency_ms = latency_ms

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def bytes_returned(self) -> int:
        return len(self.raw_body or b"")


def call_internal_api(
    method: str,
    path: str,
    *,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    bearer: Optional[str] = None,
    pass_session: bool = False,
) -> InternalAPIResult:
    """Dispatch an internal Flask route in-process and return its response.

    Exactly one of *bearer* / *pass_session* is meaningful per caller: MCP
    tools always pass ``bearer`` and never ``pass_session``; the NL query
    router always passes ``pass_session=True`` and never ``bearer``.
    """
    method = method.upper()
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    environ_overrides = {"archie.internal_bridge": True}

    start = time.monotonic()
    if pass_session:
        # Unchanged from the NL query router's pre-existing implementation:
        # a context-managed test client whose session/cookies are visible
        # to code inspecting flask.session immediately after the call.
        with current_app.test_client() as client:
            resp = client.open(
                path,
                method=method,
                query_string=params,
                json=json_body,
                headers=headers,
                environ_overrides=environ_overrides,
            )
            status_code = resp.status_code
            raw_body = resp.data
            json_data = resp.get_json(silent=True)
    else:
        # Bearer mode: a throwaway client with its own empty cookie jar —
        # the inner request carries no session, only the bearer token.
        client = current_app.test_client()
        resp = client.open(
            path,
            method=method,
            query_string=params,
            json=json_body,
            headers=headers,
            environ_overrides=environ_overrides,
        )
        status_code = resp.status_code
        raw_body = resp.data
        json_data = resp.get_json(silent=True)
    latency_ms = (time.monotonic() - start) * 1000

    return InternalAPIResult(status_code, json_data, raw_body, latency_ms)
