"""Regression tests for actionable cross-browser console diagnostics."""

from tests.smoke.test_accessibility_audit import _violation_evidence
from tests.smoke.test_archetype_journeys import _format_console_error


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
