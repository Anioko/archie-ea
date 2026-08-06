"""An answer about the portfolio must be checkable against the rows it came from.

Chat responses carried no provenance: the model could say "Salesforce is your CRM
system of record and is end-of-life in 2027" and the reader had no id, no link
and no way to tell a real row from a fluent invention. AIChatLinkService existed
with zero callers and would not have helped - it regex-matched the USER'S
QUESTION against a static map of dashboard URLs, producing generic page links
rather than record citations. AIHallucinationDetector likewise had zero callers.

Citations are derived from the tool results server-side rather than asked of the
model, because a citation the model writes is another claim, and the claim is
what is being verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.ai_chat.services.agent_runner import AgentRunner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    import os

    os.environ.setdefault("FLASK_CONFIG", "testing")
    os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
    from app import create_app

    return create_app("testing")


def runner():
    return AgentRunner(user_id=1)


def test_read_tool_rows_become_sources(app):
    sources = []
    with app.test_request_context("/"):
        runner()._collect_sources(
            "find_applications",
            {"success": True, "result": [{"id": 7, "name": "Salesforce"}]},
            sources,
        )
    assert len(sources) == 1
    assert sources[0]["type"] == "application"
    assert sources[0]["id"] == 7
    assert sources[0]["name"] == "Salesforce"


def test_the_same_record_is_not_cited_twice(app):
    """The same row commonly comes back from several tools in one turn."""
    sources = []
    row = {"success": True, "result": [{"id": 7, "name": "Salesforce"}]}
    with app.test_request_context("/"):
        runner()._collect_sources("find_applications", row, sources)
        runner()._collect_sources("find_applications_by_capability", row, sources)
    assert len(sources) == 1


def test_failed_and_write_tools_produce_no_citations(app):
    sources = []
    with app.test_request_context("/"):
        runner()._collect_sources(
            "find_applications", {"success": False, "error": "boom"}, sources
        )
        runner()._collect_sources(
            "create_solution", {"success": True, "result": [{"id": 1, "name": "X"}]}, sources
        )
    assert sources == [], "only successful READ tools describe existing records"


def test_rows_without_an_identity_are_skipped(app):
    sources = []
    with app.test_request_context("/"):
        runner()._collect_sources(
            "find_applications",
            {"success": True, "result": [
                {"id": None, "name": "no id"},
                {"id": 3},
                "not a dict",
                {"id": 4, "name": "keeps"},
            ]},
            sources,
        )
    assert [s["name"] for s in sources] == ["keeps"]


def test_citations_are_capped(app):
    sources = []
    with app.test_request_context("/"):
        runner()._collect_sources(
            "find_applications",
            {"success": True, "result": [{"id": i, "name": f"app{i}"} for i in range(200)]},
            sources,
        )
    assert len(sources) == AgentRunner.MAX_SOURCES, (
        "a broad query must not bury the answer under its own footnotes"
    )


def test_a_url_is_built_for_a_registered_record_type(app):
    with app.test_request_context("/"):
        url = AgentRunner._source_url("application", {"id": 7, "name": "Salesforce"})
    assert url and str(7) in url, url


def test_a_missing_url_degrades_to_no_link_not_an_error(app):
    """Blueprints register non-fatally, so an unresolvable endpoint must cost the
    link, not the citation."""
    with app.test_request_context("/"):
        assert AgentRunner._source_url("not_a_real_type", {"id": 1}) is None
        # archimate needs layer+type; without them there is nothing to build.
        assert AgentRunner._source_url("archimate_element", {"id": 1}) is None


def test_sources_reach_both_chat_responses():
    source = (ROOT / "app/modules/ai_chat/routes/chat_core.py").read_text(encoding="utf-8")
    assert '"sources": agent_result.get("sources", [])' in source, (
        "the non-streaming response dropped its citations"
    )


def test_context_used_is_no_longer_hardcoded_true():
    """It asserted grounding on every response regardless of whether any context
    was built - _build_system_prompt swallows failures into an empty string."""
    source = (ROOT / "app/modules/ai_chat/routes/chat_core.py").read_text(encoding="utf-8")
    assert '"context_used": True' not in source
    assert '"context_used": bool(agent_result.get("sources"))' in source


def test_the_ui_renders_citations_escaped():
    """Record names are database content rendered into innerHTML."""
    ui = (ROOT / "app/templates/ai_chat/index.html").read_text(encoding="utf-8")
    assert "function renderSources(" in ui
    assert "${renderSources(metadata.sources)}" in ui
    assert "escapeForHtml(s.name)" in ui
    assert "escapeForHtml(s.url)" in ui


def test_the_model_is_told_the_grounding_contract():
    runner_src = (
        ROOT / "app/modules/ai_chat/services/agent_runner.py"
    ).read_text(encoding="utf-8")
    prefix = runner_src.split('_AGENT_PREFIX = """', 1)[1].split('"""', 1)[0]

    assert "system of record" in prefix
    assert "_omitted" in prefix, "the model must know withheld context is not empty"
    assert "showing" in prefix.lower() and "total" in prefix.lower(), (
        "the model must be told to report the true total, not the row count"
    )
