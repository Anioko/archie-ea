"""Regression tests for actionable cross-browser console diagnostics."""

from tests.smoke.test_accessibility_audit import _violation_evidence
from tests.smoke.test_archetype_journeys import (
    STRUCTURED_ERROR_PROBE,
    _format_console_error,
    _format_page_error,
)


class _Handle:
    def __init__(self, value):
        self._value = value

    def json_value(self):
        return self._value


class _Message:
    type = "error"
    text = "Object"
    args = [_Handle({"status": 503, "url": "/architecture/api/layer/counts"})]
    location = {
        "url": "http://127.0.0.1/static/js/core/03-fetch.js",
        "lineNumber": 152,
        "columnNumber": 20,
    }


def test_console_object_is_serialized_with_source_location():
    diagnostic = _format_console_error(_Message())

    assert '"status": 503' in diagnostic
    assert '"url": "/architecture/api/layer/counts"' in diagnostic
    assert "03-fetch.js:152:20" in diagnostic
    assert diagnostic != "Object"


def test_accessibility_violation_preserves_affected_selectors():
    evidence = _violation_evidence({
        "impact": "serious",
        "nodes": [
            {"target": ["#model-select"], "failureSummary": "Fix contrast"},
            {"target": [".chat-status", "span"], "failureSummary": "Fix contrast"},
        ],
    })

    assert evidence == {
        "impact": "serious",
        "count": 2,
        "targets": ["#model-select", ".chat-status > span"],
    }


class _PageError:
    name = "Error"
    message = "Object"
    stack = "Object@http://127.0.0.1/static/js/dashboard.js:123:9"


def test_page_error_preserves_stack_when_message_is_opaque():
    diagnostic = _format_page_error(_PageError())

    assert "Object" in diagnostic
    assert "dashboard.js:123:9" in diagnostic


def test_plain_uncaught_objects_are_mirrored_to_structured_console_capture():
    assert "unhandledrejection" in STRUCTURED_ERROR_PROBE
    assert "event.error" in STRUCTURED_ERROR_PROBE
    assert "event.reason" in STRUCTURED_ERROR_PROBE
    assert "console.error" in STRUCTURED_ERROR_PROBE
