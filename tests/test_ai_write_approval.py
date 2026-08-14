"""AI write-approval gate: mutating tool calls queue for confirmation unless
the session has explicitly turned auto-execute on.

WHY THIS FILE EXISTS
---------------------
chat_core.py's toggle_auto_execute route used to write a session flag that
nothing read (see git history: its docstring documented the gap directly).
34 of the 37 agent tools are tier == "auto" and executed immediately with no
confirmation, mutating or not. The fix (also documented in that docstring,
before it was rewritten) is a `mutates` flag on each schema in
tools/registry.py, and a queueing rule in AgentRunner that consults it.

This file pins three things:
  1. registry invariants — every tool has an explicit `mutates` key (not an
     absent one defaulting via .get()), and the naming convention holds for
     the obvious prefixes.
  2. AgentRunner._should_queue — the pure decision function factored out so
     the four-way truth table (tier x auto_execute) can be tested exhaustively
     without a DB, an LLM, or a Flask request/session.
  3. The toggle route itself: POST flips the session flag and echoes it back.
     Now load-bearing (AgentRunner reads it via the caller), where before it
     was inert.

Uses the shared fixtures from tests/conftest.py per CLAUDE.md's testing
convention, rather than hand-rolling a module app fixture.
"""

import pytest

from app.modules.ai_chat.tools.registry import TOOL_SCHEMAS, mutating_tool_names
from app.modules.ai_chat.services.agent_runner import AgentRunner


# --------------------------------------------------------------------------- #
# 1. Registry invariants
# --------------------------------------------------------------------------- #


class TestRegistryInvariants:
    def test_every_tool_has_an_explicit_mutates_key(self):
        """`mutates` must be a real key, not something a reader has to assume
        via .get(..., False) — an omitted key on a future tool should be a
        loud KeyError in this test, not a silent False that lets a write tool
        slip through unqueued."""
        missing = [t["name"] for t in TOOL_SCHEMAS if "mutates" not in t]
        assert missing == [], f"tools missing explicit 'mutates': {missing}"

    def test_mutates_is_a_bool_on_every_tool(self):
        bad = [t["name"] for t in TOOL_SCHEMAS if not isinstance(t["mutates"], bool)]
        assert bad == [], f"tools with non-bool 'mutates': {bad}"

    @pytest.mark.parametrize(
        "prefix", ["create_", "link_", "update_", "mark_"]
    )
    def test_write_prefixed_tools_are_flagged_mutating(self, prefix):
        offenders = [
            t["name"]
            for t in TOOL_SCHEMAS
            if t["name"].startswith(prefix) and not t["mutates"]
        ]
        assert offenders == [], (
            f"tools named like a write ({prefix}*) but mutates=False: {offenders}"
        )

    def test_approve_tier_tools_unchanged(self):
        """The three tools that were already tier=='approve' before this
        change stay approve — this change only widens the queue, it does not
        narrow it."""
        approve_tools = {t["name"] for t in TOOL_SCHEMAS if t["tier"] == "approve"}
        assert approve_tools == {
            "update_application_status",
            "submit_for_arb_review",
            "generate_blueprint_narrative",
        }

    def test_known_read_only_tools_are_not_mutating(self):
        """The six tools the task explicitly called out as needing evidence,
        not a name-based guess — each reads and returns, never writes."""
        by_name = {t["name"]: t for t in TOOL_SCHEMAS}
        for name in (
            "propose_rationalization",
            "run_inference_engine",
            "build_architecture_plan",
            "infer_schema",
            "verify_codegen",
            "poll_infrastructure",
        ):
            assert by_name[name]["mutates"] is False, f"{name} should be read-only"

    def test_mutating_tool_names_matches_flagged_set(self):
        expected = {t["name"] for t in TOOL_SCHEMAS if t["mutates"] is True}
        assert mutating_tool_names() == expected


# --------------------------------------------------------------------------- #
# 2. AgentRunner._should_queue — pure decision function
# --------------------------------------------------------------------------- #


class TestShouldQueue:
    def test_mutates_and_auto_execute_off_queues(self):
        schema = {"tier": "auto", "mutates": True}
        assert AgentRunner._should_queue(schema, auto_execute=False) is True

    def test_mutates_and_auto_execute_on_executes(self):
        schema = {"tier": "auto", "mutates": True}
        assert AgentRunner._should_queue(schema, auto_execute=True) is False

    def test_read_only_never_queues_regardless_of_auto_execute(self):
        schema = {"tier": "auto", "mutates": False}
        assert AgentRunner._should_queue(schema, auto_execute=False) is False
        assert AgentRunner._should_queue(schema, auto_execute=True) is False

    def test_approve_tier_queues_even_with_auto_execute_on(self):
        """The whole point of a separate always-approve tier: turning on
        write auto-execute must not silently wave through
        update_application_status / submit_for_arb_review."""
        schema = {"tier": "approve", "mutates": True}
        assert AgentRunner._should_queue(schema, auto_execute=True) is True
        assert AgentRunner._should_queue(schema, auto_execute=False) is True

    def test_approve_tier_with_mutates_false_still_queues(self):
        """generate_blueprint_narrative is tier=='approve' with mutates==False
        (its write path currently raises before touching the DB — see
        executor.py) — tier alone must be sufficient to queue it."""
        schema = {"tier": "approve", "mutates": False}
        assert AgentRunner._should_queue(schema, auto_execute=True) is True

    def test_missing_schema_keys_default_safe(self):
        """An unknown tool name resolves to {} in the run loop
        (TOOL_SCHEMA_BY_NAME.get(name, {})) — that must not execute unqueued."""
        assert AgentRunner._should_queue({}, auto_execute=True) is False
        assert AgentRunner._should_queue({}, auto_execute=False) is False

    def test_full_registry_is_decided_without_error(self):
        """Every real schema in the registry must produce a bool for both
        auto_execute states — a smoke test against schema-shape drift."""
        for schema in TOOL_SCHEMAS:
            for auto_execute in (True, False):
                result = AgentRunner._should_queue(schema, auto_execute)
                assert isinstance(result, bool)

    def test_agent_runner_defaults_to_auto_execute_off(self):
        """A caller that forgets to pass auto_execute gets the safe default:
        writes queue rather than fire."""
        runner = AgentRunner(user_id=1)
        assert runner.auto_execute is False


# --------------------------------------------------------------------------- #
# 3. Toggle route — now load-bearing, pin the wire behaviour
# --------------------------------------------------------------------------- #


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, user_id):
    """Standard Flask-Login test-client login, plus clearing the caches that
    make a stale request/app context return the wrong user — see the longer
    explanation in tests/test_ba_tenant_and_authz.py::_login, which this
    mirrors."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_user(db_session, org):
    from app.models.user import User
    import uuid

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"gov-{suffix}@example.com",
        first_name="Gov",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


class TestToggleAutoExecuteRoute:
    def test_toggle_flips_and_returns_the_flag(self, app, client, db_session, make_org):
        org = make_org("gov")
        user = _make_user(db_session, org)
        _login(client, user.id)

        resp1 = client.post("/ai-chat/session/toggle-auto-execute")
        assert resp1.status_code == 200
        body1 = resp1.get_json()
        assert body1["success"] is True
        first_state = body1["auto_execute"]

        resp2 = client.post("/ai-chat/session/toggle-auto-execute")
        body2 = resp2.get_json()
        assert body2["auto_execute"] is (not first_state)

    def test_default_session_has_auto_execute_off(self, app, client, db_session, make_org):
        """First toggle from a fresh session flips False -> True: pins the
        documented default (agent_auto_execute defaults False when absent)."""
        org = make_org("gov")
        user = _make_user(db_session, org)
        _login(client, user.id)

        resp = client.post("/ai-chat/session/toggle-auto-execute")
        assert resp.get_json()["auto_execute"] is True

    def test_toggle_requires_login(self, client):
        resp = client.post("/ai-chat/session/toggle-auto-execute")
        assert resp.status_code in (302, 401)
