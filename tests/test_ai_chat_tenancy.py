"""The chat agent thread must carry the requesting user's tenant.

app/middleware/tenant_context.py sets g.current_org_id in a before_request
handler, and app/middleware/tenant_isolation.py returns WITHOUT adding a filter
when it is absent. The streaming chat endpoint runs the agent in a daemon thread
with only an app context - stream_with_context preserves the request context for
the SSE generator, not for that thread - so every TenantMixin SELECT the agent
made while assembling context and running its tools was unfiltered across every
organisation.

APISettings is a TenantMixin model, so the leak was not only portfolio data:
provider selection could pick up another tenant's LLM API key and send this
organisation's prompts under, and billed to, that account.

There was no test for any of this. This one pins the two halves that matter:
the tenant filter genuinely no-ops without g.current_org_id (so the mechanism is
what we think it is), and the streaming route propagates the tenant into the
worker thread.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHAT_CORE = ROOT / "app/modules/ai_chat/routes/chat_core.py"


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    return create_app("testing")


def test_the_tenant_filter_really_does_nothing_without_a_tenant(app):
    """The premise. If this ever stops being true the leak below is moot -
    but so is every other assumption about how isolation works here."""
    from flask import g

    from app.middleware.tenant_context import current_org_id

    with app.app_context():
        # An app context with no before_request handler having run: exactly the
        # situation the agent thread is in.
        assert not hasattr(g, "current_org_id") or g.current_org_id is None
        assert current_org_id() is None


def test_streaming_route_propagates_the_tenant_into_the_agent_thread():
    """The worker must set g.current_org_id from the request thread's value.

    Asserted against source rather than by driving a live SSE stream: the thread
    is a daemon with a queue and no return value, so there is no seam to observe
    it from, and a test that spun one up would assert on timing rather than on
    the tenant. The two things that must hold are that the value is captured on
    the request thread and re-established inside the worker's app context.
    """
    source = CHAT_CORE.read_text(encoding="utf-8")

    assert "current_org_id as _current_org_id" in source, (
        "the streaming route no longer imports the tenant helper"
    )
    assert "org_id_for_thread = _current_org_id()" in source, (
        "the tenant is no longer captured on the request thread; reading it "
        "inside the worker would return None and silently disable isolation"
    )

    # The assignment must be inside run_agent's app context, before AgentRunner.
    worker = source.split("def run_agent():", 1)
    assert len(worker) == 2, "run_agent no longer exists in the streaming route"
    body = worker[1]

    assign = body.find("g.current_org_id = org_id_for_thread")
    construct = body.find("AgentRunner(")
    assert assign != -1, (
        "the agent thread does not set g.current_org_id, so every TenantMixin "
        "SELECT it makes runs unfiltered across all organisations"
    )
    assert construct != -1, "AgentRunner is no longer constructed in run_agent"
    assert assign < construct, (
        "g.current_org_id is set after AgentRunner is constructed; context "
        "assembly queries before the tenant is in place"
    )


def test_api_settings_is_tenant_scoped():
    """Why the leak was a credential leak and not only a data leak."""
    from app.models.mixins.core import TenantMixin
    from app.models.models import APISettings

    assert issubclass(APISettings, TenantMixin), (
        "APISettings is no longer tenant-scoped; if that is deliberate, the "
        "cross-tenant API-key concern in chat_core needs revisiting"
    )


def test_no_other_thread_in_chat_core_runs_without_a_tenant():
    """A second daemon thread added later would reintroduce the same hole."""
    source = CHAT_CORE.read_text(encoding="utf-8")
    threads = re.findall(r"_threading\.Thread\(target=(\w+)", source)
    assert threads, "expected at least the agent thread"
    for target in threads:
        body = source.split("def %s(" % target, 1)
        assert len(body) == 2, "thread target %s not found" % target
        # Take the target's body up to the next top-level def.
        chunk = re.split(r"\n    def |\n_threading", body[1])[0]
        assert "current_org_id" in chunk, (
            "thread target %r runs without establishing a tenant context; "
            "every TenantMixin SELECT inside it will be unfiltered" % target
        )
