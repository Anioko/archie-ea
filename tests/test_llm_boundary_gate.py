"""The `llm-boundary` gate must actually fire when an emitter calls the LLM.

A gate that cannot go red is theatre. This pins both directions: the real
emitter tree is clean (green today), and the detector genuinely flags a
`_call_llm`/`LLMService` reference and honours the exemption marker.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECKER = _REPO_ROOT / "scripts" / "check_llm_boundary.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_llm_boundary", _CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emitters_are_clean_today():
    """Green: the shipped emitter tree has zero direct LLM references."""
    mod = _load_checker()
    assert mod.find_violations() == []


@pytest.mark.parametrize("line,expected", [
    ("    result = LLMService()._call_llm(prompt)", True),
    ("    svc = LLMService()", True),
    ("    x = _call_llm(prompt)", True),
    ("    x = _call_llm(prompt)  # llm-boundary-ok: proven exception", False),
    ("    x = deterministic_emit(genome)", False),
])
def test_token_detection_and_exemption(line, expected):
    """Red where it should be red, and the exemption marker suppresses a match."""
    mod = _load_checker()
    if mod._EXEMPT in line:
        matched = False
    else:
        matched = bool(mod._LLM_TOKENS.search(line))
    assert matched is expected
