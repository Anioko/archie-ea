"""A chat turn with no LLM provider must reach the user as an ADMIN state.

Archie is a system of record. With no provider configured the only honest
outcomes are "here is what an administrator must do" or a real error — never a
fabricated answer, and never a bare machine code the user cannot act on.

What the server already does right, and what these tests pin
------------------------------------------------------------
`FeatureFlagService.require_ai_for_route` (app/services/feature_flag_service.py)
short-circuits the chat endpoints with

    503 {"error": "service_unavailable",
         "feature": "chat",
         "message": "AI feature 'chat' is not available. LLM provider must be
                     configured."}

That is correct and actionable, and it fires *before* the model allow-list
check in `send_message`, so the no-provider condition is never misreported as
`invalid_model`. An earlier draft of this module asserted the opposite — that
the turn returned 200 with the AgentRunner fallback text. That expectation was
simply wrong about this codebase: the gate runs first. The test was corrected
to the real contract rather than the product being changed to match it.

The defect was one layer up, in the client
------------------------------------------
`app/static/js/ai_chat/app.js` read `data.error` (the machine code
`"service_unavailable"`) and never `data.message`, so the user was shown
"Request Error (HTTP 503): service_unavailable" with a Retry button that could
never succeed and no route to the remedy. The streaming path was worse: it
threw `Error('stream ' + status)`, discarding the body entirely.

The `message` field is therefore load-bearing UI contract, not decoration —
these tests exist so it cannot be dropped or renamed without a failure here.

The session conftest deliberately blanks every `*_API_KEY` env var, so these
tests run in the genuine no-provider condition without patching anything.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def chat_user(db_session, make_org):
    """A logged-in-able user in a fresh org, with no enabled provider row."""
    from app.models.models import APISettings
    from app.models.user import User

    org = make_org("aichat")

    # Assert the precondition rather than assume it: the point of these tests
    # is the no-provider condition, and a stray enabled row would silently
    # turn them green for the wrong reason.
    assert APISettings.query.filter_by(enabled=True).count() == 0, (
        "these tests require the no-provider condition; an enabled "
        "APISettings row is present"
    )

    user = User(
        first_name="Chat",
        last_name="Tester",
        email=f"chat-{uuid.uuid4().hex[:8]}@example.test",
        organization_id=org.id,
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"message": "What applications do we own?", "domain": "general"},
            id="no-model-named",
        ),
        pytest.param(
            {
                "message": "What applications do we own?",
                "domain": "general",
                "model": "gpt-4o",
            },
            id="model-named",
        ),
    ],
)
def test_no_provider_turn_is_an_actionable_administrative_state(
    client, login_as, chat_user, payload
):
    """503 naming the remedy — and never a misdiagnosis of the model."""
    login_as(client, chat_user)
    resp = client.post("/ai-chat/message", json=payload)

    body = resp.get_json()
    assert resp.status_code == 503, resp.get_data(as_text=True)
    assert body["error"] == "service_unavailable"

    # The human-readable remedy. This is what the chat client renders; if it
    # is dropped or renamed, the user is left with a bare machine code.
    assert "message" in body, (
        "the client renders body['message']; without it the user sees only "
        f"the machine code. got: {body!r}"
    )
    assert "provider must be configured" in body["message"].lower(), (
        f"the 503 must name the remedy, got: {body['message']!r}"
    )

    # A missing provider is an administrative condition, not bad user input.
    # Blaming the model would send an administrator to the model picker
    # instead of to Admin > API Settings.
    assert body["error"] != "invalid_model"

    # And nothing may claim the system of record changed.
    assert not body.get("actions_taken")
    assert not body.get("response")


def test_no_provider_streaming_turn_is_also_an_administrative_state(
    client, login_as, chat_user
):
    """The streaming endpoint is the primary path — it must gate identically.

    If only the non-streaming endpoint gated, the UI's preferred path would
    open a stream that produced no tokens, and the user would watch an empty
    bubble instead of being told a provider is missing.
    """
    login_as(client, chat_user)
    resp = client.post(
        "/ai-chat/message/stream",
        json={"message": "What applications do we own?", "domain": "general"},
    )

    assert resp.status_code == 503, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["error"] == "service_unavailable"
    assert "provider must be configured" in body["message"].lower()
