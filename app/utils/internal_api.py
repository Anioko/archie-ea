"""Shared utility for calling internal Flask routes in-process.

Used by MCP tools and the AI chat NL query router to call REST endpoints
through Flask's test client, avoiding external HTTP calls while still going
through the full middleware stack.
"""

from __future__ import annotations

from typing import Any


def call_internal_api(
    method: str,
    path: str,
    *,
    query_string: dict | None = None,
    json_body: dict | None = None,
    pass_session: bool = False,
) -> tuple[int, Any]:
    """Call an internal Flask route in-process and return (status_code, data).

    Uses Flask's test client so the request goes through the full middleware
    stack (tenant context, tenant isolation, login_required) without a real
    network call.

    Args:
        method: HTTP method (GET or POST).
        path: The route path (e.g. "/api/v1/intelligence/impact/42").
        query_string: Optional query parameters dict.
        json_body: Optional JSON body for POST requests.
        pass_session: If True, copy the current Flask session cookie into the
            test client so the route sees the authenticated user.

    Returns:
        A tuple of (status_code, data) where data is the parsed JSON response
        or an empty dict if parsing fails.
    """
    from flask import current_app, g, session

    # A nested call made through the test client here runs inside the SAME
    # app context as the outer request (Flask only pushes a new one when the
    # top of the stack belongs to a different app), so it shares this `g` —
    # including flask-login's cached g._login_user. The session-policy
    # before_request hook would otherwise see that identity, look for a
    # matching server-side session record for the inner request's own (here,
    # blank-or-copied) session, find none, and revoke/clear — which mutates
    # the shared g and leaves the OUTER request looking logged out. The
    # outer request already established its own identity through its own
    # authentication path before making this call; the nested call is an
    # implementation detail of serving it, not a second session to police.
    previous_internal_call = getattr(g, "_internal_api_call", False)
    g._internal_api_call = True
    try:
        with current_app.test_client() as client:
            if pass_session:
                with client.session_transaction() as sess:
                    sess.update(session)

            if method.upper() == "GET":
                resp = client.get(path, query_string=query_string or {})
            else:
                resp = client.post(path, json=json_body or {})

            try:
                data = resp.get_json()
            except Exception:
                data = {}
            return resp.status_code, data if data is not None else {}
    finally:
        g._internal_api_call = previous_internal_call