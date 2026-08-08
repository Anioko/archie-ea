"""Every tool declares whether it writes, and the declaration must be true.

`tier` already existed but conflates reads and writes: 34 of 37 tools are
tier=="auto", covering both find_applications and create_solution. Gating on it
would put every search behind an approval prompt, which is why
`toggle_auto_execute`'s own docstring (chat_core.py) asks for exactly this flag
before the auto-execute preference can be enforced.

The flag also decides which turns render a write receipt and which next-artifact
action is offered, so a wrong value is not cosmetic: it either hides a write from
the user or claims one that did not happen.

The classification was derived by reading each implementation for
db.session.add/commit/delete — including through the five tools that delegate to
a service — not from the tool's name. This file pins that derivation so a new
tool cannot join without a decision, and so a name that reads like a write
(propose_rationalization, run_inference_engine) cannot be silently reclassified.
"""

import re
from pathlib import Path

import pytest

from app.modules.ai_chat.tools.registry import TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parents[1]

# Derived from the implementations, then pinned here.
MUTATING = {
    "create_archimate_element", "create_archimate_relationship", "create_constraint",
    "create_driver", "create_goal", "create_option", "create_requirement",
    "create_risk", "create_solution", "link_application_to_capability",
    "link_application_to_solution", "link_capability_to_solution", "link_vendor_product",
    "mark_option_recommended", "submit_for_arb_review", "update_application_status",
    "update_solution_fields", "update_solution_phase",
}


def test_every_tool_declares_whether_it_mutates():
    """No default. A new tool must make the call explicitly."""
    missing = [t["name"] for t in TOOL_SCHEMAS if "mutates" not in t]
    assert not missing, (
        "these tools do not declare `mutates`, so receipts and approval gating "
        "cannot classify them: %s" % missing
    )


def test_the_declaration_matches_the_implementation():
    """A tool that touches db.session must say so, and vice versa.

    This is the assertion that stops the flag drifting from reality: it re-derives
    the answer from executor.py rather than trusting the registry.
    """
    ex = (ROOT / "app/modules/ai_chat/tools/executor.py").read_text(encoding="utf-8")
    writes_re = re.compile(r"db\.session\.(add|commit|delete)")

    wrong = []
    for tool in TOOL_SCHEMAS:
        name = tool["name"]
        m = re.search(r"def _tool_%s\(self.*?(?=\n    def _tool_|\Z)" % name, ex, re.S)
        if not m:
            continue  # no implementation to compare against
        implementation_writes = bool(writes_re.search(m.group(0)))
        if implementation_writes and not tool["mutates"]:
            wrong.append(f"{name}: writes to the database but declares mutates=False")
        # The reverse is not asserted: a tool may legitimately declare mutates=True
        # while delegating its write to a service, which this regex cannot see.
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("name", sorted(MUTATING))
def test_known_writers_are_flagged(name):
    tool = next(t for t in TOOL_SCHEMAS if t["name"] == name)
    assert tool["mutates"] is True, f"{name} writes to the repository but is not flagged"


def test_a_name_that_sounds_like_a_write_is_not_assumed_to_be_one():
    """propose_rationalization and run_inference_engine read only.

    A startswith("create_")-style heuristic would have missed
    mark_option_recommended and submit_for_arb_review while wrongly flagging
    these — which is why the classification came from the implementations.
    """
    by_name = {t["name"]: t for t in TOOL_SCHEMAS}
    for read_only in ("propose_rationalization", "run_inference_engine",
                      "generate_blueprint_narrative", "simulate_impact",
                      "validate_sap_clean_core"):
        assert by_name[read_only]["mutates"] is False, (
            f"{read_only} does not write; flagging it would put a read behind an "
            f"approval prompt and claim a receipt for a turn that changed nothing"
        )


def test_the_helper_returns_the_same_set():
    from app.modules.ai_chat.tools.registry import mutating_tool_names

    assert mutating_tool_names() == MUTATING
