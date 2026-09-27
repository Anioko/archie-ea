"""Read tools must not present a truncated page as the whole set.

Every read tool returned `"count": len(rows)` with a message of the form
"Found N application(s)" - where N was the LIMIT, not the number of matches.
Asked "how many applications are in production?" against a 5,000-application
estate, the model was handed

    {"count": 15, "message": "Found 15 application(s)."}

and answered "15". It reported exactly what the tool told it and thereby
invented a fact about the customer's portfolio.

This is the failure CLAUDE.md's "never invent data" rule exists to prevent, and
the fabricated-data gate cannot see it: that gate inspects templates and view
code, not tool-result strings assembled server-side. Hence this test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.ai_chat.tools.executor import ToolExecutor

EXECUTOR = Path(__file__).resolve().parents[1] / "app/modules/ai_chat/tools/executor.py"


def test_truncation_is_stated_with_both_numbers():
    result = ToolExecutor._coverage([{"id": 1}] * 15, 4812, "application(s)")

    assert result["returned"] == 15
    assert result["total"] == 4812
    assert result["truncated"] is True
    assert "15" in result["message"] and "4812" in result["message"], (
        "the model must see both numbers or it will report the page size"
    )


def test_a_complete_set_says_so():
    result = ToolExecutor._coverage([{"id": 1}] * 3, 3, "application(s)")

    assert result["truncated"] is False
    assert "3" in result["message"]
    assert "4812" not in result["message"]


def test_an_empty_result_is_not_reported_as_truncated():
    result = ToolExecutor._coverage([], 0, "application(s)")
    assert result["returned"] == 0
    assert result["total"] == 0
    assert result["truncated"] is False


def test_an_unknown_total_is_declared_unknown_not_implied_complete():
    """Some tools return top-N by relevance, where no total is meaningful.
    Silence there would read as completeness."""
    result = ToolExecutor._coverage([{"id": 1}] * 10, None, "relevant capabilities")

    assert result["total"] is None
    assert result["truncated"] is None
    assert "not determined" in result["message"], result["message"]
    assert "do not report this as a total" in result["message"]


def test_count_is_retained_for_existing_consumers():
    """`count` predates this change and is read elsewhere; it stays as the
    number of rows returned, with `total` carrying the new information."""
    result = ToolExecutor._coverage([{"id": 1}] * 15, 4812, "x")
    assert result["count"] == result["returned"] == 15


def test_no_read_tool_still_reports_a_bare_row_count_as_the_finding():
    """The regression guard. A new read tool that hand-rolls
    `"count": len(rows)` reintroduces exactly the defect above."""
    source = EXECUTOR.read_text(encoding="utf-8")

    # Ignore the explanatory docstring on _coverage itself.
    body = source.split("def _get_organization_id", 1)[1]
    offenders = [
        line.strip()
        for line in body.splitlines()
        if re.search(r'"count":\s*len\(', line)
    ]
    assert not offenders, (
        "%d read tool(s) still report a truncated row count as the result; "
        "use self._coverage(rows, total, noun) instead:\n  %s"
        % (len(offenders), "\n  ".join(offenders))
    )


@pytest.mark.parametrize(
    "marker",
    [
        "total = q.count()",              # find_applications, elements, gaps, technical
        "total_mapped = _map_q.count()",  # find_applications_by_capability
        "total_capabilities = _cap_q.count()",  # search_capabilities_by_problem
    ],
)
def test_totals_are_counted_before_the_limit_is_applied(marker):
    """Counting after .limit() would just return the page size again."""
    assert marker in EXECUTOR.read_text(encoding="utf-8"), (
        "a tool stopped counting its matching set before truncating"
    )


def test_semantic_search_admits_the_size_of_the_pool_it_searched():
    """The candidate pool is capped at 600 with no ORDER BY, so on a larger
    capability model it ranks an arbitrary subset. Saying nothing implies it
    searched everything."""
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "capabilities_searched" in source
    assert "capabilities_total" in source
    assert "the remainder was not examined" in source
