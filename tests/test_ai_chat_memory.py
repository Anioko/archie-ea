"""The chat agent must replay prior turns, and replay them validly.

AgentRunner.run started every turn with
    messages = [{"role": "user", "content": user_message}]
so each message was an independent single-turn call. The model had no idea what
"it" referred to in a follow-up, while the UI presented a persistent thread rail
- the first thing any user tries, and it failed.

The three mechanisms meant to fix this were all disconnected: persist_turn was
imported but defined nowhere (so nothing was ever saved), AIChatMemoryService's
add_message had no callers, and ContextWindowService only fed a token meter over
an always-empty list.

These tests pin the replay contract rather than the plumbing, because the ways
this breaks in production are provider-level: a sequence that does not alternate,
does not start with a user message, or ends with one gets rejected outright.
"""

from __future__ import annotations

import pytest

from app.modules.ai_chat.services.agent_runner import AgentRunner


def turns(*pairs):
    out = []
    for user, assistant in pairs:
        out.append({"role": "user", "content": user})
        out.append({"role": "assistant", "content": assistant})
    return out


def test_no_history_is_a_clean_new_conversation():
    assert AgentRunner._prepare_history(None) == []
    assert AgentRunner._prepare_history([]) == []


def test_prior_turns_are_replayed_in_order():
    prepared = AgentRunner._prepare_history(turns(("what is X", "X is a thing")))
    assert prepared == [
        {"role": "user", "content": "what is X"},
        {"role": "assistant", "content": "X is a thing"},
    ]


def test_result_always_alternates_and_starts_with_user():
    """The provider-level invariant. A stored turn whose assistant reply never
    persisted leaves two user messages adjacent, which is rejected outright."""
    ragged = [
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second, reply never saved"},
        {"role": "assistant", "content": "answer to second"},
        {"role": "assistant", "content": "orphan with no question"},
    ]
    prepared = AgentRunner._prepare_history(ragged)

    assert prepared, "a recoverable turn existed and should have been replayed"
    assert prepared[0]["role"] == "user"
    assert prepared[-1]["role"] == "assistant", (
        "history must not end on a user message - this turn's message goes there"
    )
    roles = [m["role"] for m in prepared]
    assert roles == ["user", "assistant"] * (len(roles) // 2), roles


def test_an_assistant_message_with_no_question_is_dropped():
    prepared = AgentRunner._prepare_history([{"role": "assistant", "content": "orphan"}])
    assert prepared == []


def test_malformed_entries_are_skipped_not_replayed():
    prepared = AgentRunner._prepare_history([
        {"role": "system", "content": "not a conversational turn"},
        {"role": "user", "content": ""},
        {"role": "user"},
        None,
        {"role": "user", "content": "real"},
        {"role": "assistant", "content": "reply"},
    ])
    assert prepared == [
        {"role": "user", "content": "real"},
        {"role": "assistant", "content": "reply"},
    ]


def test_history_is_bounded_by_turn_count():
    prepared = AgentRunner._prepare_history(
        turns(*[(f"q{i}", f"a{i}") for i in range(50)])
    )
    assert len(prepared) == AgentRunner.MAX_HISTORY_TURNS * 2


def test_trimming_drops_the_oldest_and_keeps_the_most_recent():
    """A follow-up refers to the LAST exchange, so that one must survive."""
    prepared = AgentRunner._prepare_history(
        turns(*[(f"q{i}", f"a{i}") for i in range(50)])
    )
    assert prepared[-2:] == [
        {"role": "user", "content": "q49"},
        {"role": "assistant", "content": "a49"},
    ]
    assert not any(m["content"] == "q0" for m in prepared)


def test_a_single_huge_turn_cannot_blow_the_budget():
    huge = "x" * (AgentRunner.MAX_HISTORY_CHARS + 1000)
    prepared = AgentRunner._prepare_history(turns((huge, huge)))
    assert prepared == [], (
        "a turn larger than the whole budget must be dropped, not sent"
    )


def test_run_signature_accepts_history():
    """Guards the wiring: a rename here silently restores the amnesia, because
    both call sites pass history= by keyword."""
    import inspect

    params = inspect.signature(AgentRunner.run).parameters
    assert "history" in params
    assert params["history"].default is None


@pytest.mark.parametrize(
    "call_site",
    ["history=_load_history(incoming_thread_id, current_user.id)", "history=history_for_thread"],
)
def test_both_chat_routes_pass_history(call_site):
    """Non-streaming and streaming must both replay; the UI tries streaming first."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/ai_chat/routes/chat_core.py"
    ).read_text(encoding="utf-8")
    assert call_site in source, "a chat route stopped passing conversation history"
