"""What the model is told about the customer's estate must be true.

Two defects, same theme as the tool-count one: the model was misled about what
it had been given, so it answered confidently from a fragment.

1. The context block was `json.dumps(ctx)[:6000]` - a raw slice of a JSON
   string. It cut mid-token, so the model received malformed JSON ending
   part-way through a value, and nothing said anything had been removed. A
   context truncated from 40 elements to 22 looked exactly like a portfolio
   containing 22.

2. The DEFAULT domain injected six integers and a static domain list - not one
   application, capability or vendor NAME. The assistant knew the shape of the
   portfolio and none of its contents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.ai_chat.services.agent_runner import AgentRunner

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Context serialisation
# --------------------------------------------------------------------------

def test_empty_context_produces_no_block():
    assert AgentRunner._serialise_context({}) == ""
    assert AgentRunner._serialise_context(None) == ""


def test_context_within_budget_is_untouched_and_parseable():
    ctx = {"portfolio_summary": {"total_applications": 5000}, "domains": ["a", "b"]}
    assert json.loads(AgentRunner._serialise_context(ctx)) == ctx


def test_oversized_context_stays_valid_json():
    """The whole point. A mid-token slice is unparseable, and the model then
    guesses where the data stopped."""
    ctx = {
        "portfolio_summary": {"total_applications": 5000},
        "elements": [{"id": i, "name": "e" * 200} for i in range(200)],
    }
    out = AgentRunner._serialise_context(ctx)

    parsed = json.loads(out)  # would raise on a mid-token cut
    assert isinstance(parsed, dict)
    assert len(out) <= AgentRunner.MAX_CONTEXT_CHARS


def test_oversized_context_names_what_it_dropped():
    ctx = {
        "portfolio_summary": {"total_applications": 5000},
        "elements": [{"id": i, "name": "e" * 200} for i in range(200)],
    }
    parsed = json.loads(AgentRunner._serialise_context(ctx))

    assert "elements" in parsed["_omitted"]["keys"], (
        "the model must be told a key was withheld, or absent reads as empty"
    )
    assert "NOT empty" in parsed["_omitted"]["reason"]


def test_the_smallest_keys_survive_so_totals_are_not_lost():
    """Totals are the authority on portfolio size; a big list is replaceable by
    a tool call. Drop the list, keep the numbers."""
    ctx = {
        "portfolio_summary": {"total_applications": 5000},
        "elements": [{"id": i, "name": "e" * 200} for i in range(200)],
    }
    parsed = json.loads(AgentRunner._serialise_context(ctx))

    assert parsed["portfolio_summary"]["total_applications"] == 5000
    assert "elements" not in parsed


def test_a_single_oversized_key_is_flagged_rather_than_silently_cut():
    huge = {"only": [{"name": "x" * 500} for _ in range(100)]}
    out = AgentRunner._serialise_context(huge)

    assert "CONTEXT TRUNCATED MID-VALUE" in out, (
        "when a lone key cannot be dropped the cut must be announced"
    )


def test_serialiser_is_used_and_the_raw_slice_is_gone():
    source = (ROOT / "app/modules/ai_chat/services/agent_runner.py").read_text(encoding="utf-8")
    assert "self._serialise_context(raw_ctx)" in source
    # Match the ASSIGNMENT, not the mention: _serialise_context's docstring
    # quotes the old expression to explain what it replaced.
    assert "ctx_block = json.dumps(" not in source, "the raw mid-token slice is back"


# --------------------------------------------------------------------------
# Default-domain grounding
# --------------------------------------------------------------------------

@pytest.mark.parametrize("entity", ["applications", "capabilities", "vendors"])
def test_default_context_names_entities_not_only_counts(entity):
    """The default domain is what an ordinary chat turn gets. Counts alone let
    the model describe the portfolio's shape and nothing in it."""
    source = (
        ROOT / "app/modules/ai_chat/services/multi_domain_chat_service.py"
    ).read_text(encoding="utf-8")

    general = source.split("def _load_general_context", 1)[1].split("\n    def ", 1)[0]
    assert '"portfolio_sample"' in general, "the default domain injects no entity names"
    assert '"%s"' % entity in general, "no %s are named in the default context" % entity


def test_the_sample_is_labelled_as_a_sample():
    """An unlabelled list of 20 of 5,000 applications reads as the portfolio -
    which would swap one grounding failure for a worse one."""
    source = (
        ROOT / "app/modules/ai_chat/services/multi_domain_chat_service.py"
    ).read_text(encoding="utf-8")
    general = source.split("def _load_general_context", 1)[1].split("\n    def ", 1)[0]

    assert "NOT the" in general and "full portfolio" in general
    assert '"of_applications"' in general, (
        "the sample must carry the true total beside it"
    )
