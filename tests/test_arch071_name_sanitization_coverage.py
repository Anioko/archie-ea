"""ARCH-071 (extension): HTML-tag stripping on user-supplied name/identifier
fields beyond the application-name field 9cda379 scoped it to.

Covers the two other write paths where the register's XSS-payload style test
("QA-TEST <script>alert(1)</script>") applies to a name/identifier: vendor
creation (app/modules/vendors/routes/unified_vendor_api.py::create_vendor)
and the AI agent's autonomous entity-creation tools (executor.py's single
dispatch choke point in execute(), applied to every tool's name/title args).

Stripping, not entity-escaping, matching validate_application_name's approach
(see app/utils/validators.py) so this does not double-escape on top of
Jinja's own autoescape at render time.
"""
from __future__ import annotations

from app.modules.ai_chat.tools.executor import _strip_tags_from_name_args


def test_agent_tool_dispatch_strips_html_tags_from_name_and_title_args():
    cleaned = _strip_tags_from_name_args({
        "name": "QA-TEST <script>alert(1)</script>",
        "title": "<img src=x onerror=alert(1)>Report",
        "description": "<b>kept verbatim</b> — description is not a name/identifier field",
    })
    assert cleaned["name"] == "QA-TEST alert(1)"
    assert cleaned["title"] == "Report"
    # Only name-like keys are touched — this helper must not become a
    # blanket sanitizer that silently mutates arguments callers didn't ask
    # to have cleaned.
    assert cleaned["description"] == "<b>kept verbatim</b> — description is not a name/identifier field"


def test_agent_tool_dispatch_passes_through_non_string_and_missing_name():
    # Defensive: a malformed tool call (e.g. name omitted, or a non-string
    # value from a confused LLM) must not raise inside the sanitizer.
    assert _strip_tags_from_name_args({}) == {}
    assert _strip_tags_from_name_args({"name": None})["name"] is None
    assert _strip_tags_from_name_args({"name": 123})["name"] == 123
