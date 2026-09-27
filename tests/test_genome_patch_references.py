"""Retrieval of known-good reference architectures for a proposal, and their
inclusion in the synthesis prompt. Deterministic; no LLM, no DB."""
from app.modules.genome.patch.references import (
    retrieve_reference_patterns,
    references_prompt_block,
)
from app.modules.genome.patch.synth import _build_prompt


def test_web_request_retrieves_the_3_tier_pattern():
    refs = retrieve_reference_patterns("we need a browser-based web application portal")
    ids = {r["id"] for r in refs}
    assert "3_tier_web" in ids
    top = refs[0]
    assert top["exemplar_elements"]  # carries type@layer exemplars
    assert all("type" in e and "layer" in e for e in top["exemplar_elements"])


def test_microservices_and_events_retrieve_those_patterns():
    refs = retrieve_reference_patterns("event-driven microservices with a message bus")
    ids = {r["id"] for r in refs}
    assert ids & {"microservices", "event_driven"}


def test_no_match_returns_empty_never_a_fabricated_reference():
    assert retrieve_reference_patterns("qwerty zxcvb nonsense token") == []
    assert references_prompt_block("qwerty zxcvb nonsense token") == ""


def test_limit_is_respected():
    refs = retrieve_reference_patterns("web application api data warehouse mobile serverless", limit=2)
    assert len(refs) <= 2


def test_prompt_block_names_the_reference():
    block = references_prompt_block("web application portal")
    assert "reference architectures" in block.lower()
    assert "Tier" in block or "tier" in block


def test_build_prompt_folds_in_references_for_a_web_request():
    p = _build_prompt("build a web application portal", organization_id=1, proposed_by="1")
    assert "reference architectures" in p.lower()


def test_build_prompt_omits_references_when_none_match():
    p = _build_prompt("qwerty zxcvb nonsense", organization_id=1, proposed_by="1")
    # no reference block, but the prompt still forms and carries the request
    assert "reference architectures" not in p.lower()
    assert "qwerty zxcvb nonsense" in p
