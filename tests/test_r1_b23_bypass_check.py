"""R1-B23: Gateway bypass enumeration.

Every LLMInteraction creation must go through ``LLMService._call_llm``
(the gateway). Files that create LLMInteraction outside this method are
bypass sites and are listed here.

The `llm-boundary` gate (scripts/check_llm_boundary.py) enforces that the
deterministic emitter tree has zero LLM references. This test extends that
principle: it enumerates all files that bypass the gateway so the list is
visible and reviewable.

Per the brief: call sites in files owned by R1-B11 or R1-B22 get a failing
test for TB-0112.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that create LLMInteraction directly and are NOT inside the gateway
# (_call_llm / _call_llm_with_failover). Each entry is (relative_path, reason).
# This is a living list: adding a bypass is a defect unless the new file is
# itself part of the gateway service.
EXPECTED_BYPASSES: list[tuple[str, str]] = [
    (
        "app/modules/ai_chat/services/llm_service_impl.py",
        "log_decision creates LLMInteraction directly (line ~2940) — owned by gateway service",
    ),
    (
        "app/modules/ai_chat/services/llm_cost_tracker.py",
        "track_interaction creates LLMInteraction directly — gateway-adjacent cost tracking",
    ),
    (
        "app/modules/architecture/services/document_processor.py",
        "creates LLMInteraction outside gateway — bypass",
    ),
    (
        "app/modules/architecture/services/document_analysis_service.py",
        "creates LLMInteraction outside gateway — bypass",
    ),
    (
        "app/modules/architecture/services/multi_modal_llm_service.py",
        "creates LLMInteraction outside gateway — bypass",
    ),
]


def _scan_llm_interaction_creations() -> list[tuple[str, int]]:
    """Find every file that contains 'LLMInteraction(' constructor calls.

    Returns (relative_path, line_number) for each match.
    """
    results: list[tuple[str, int]] = []
    pattern = re.compile(r"LLMInteraction\s*\(")

    py_files = sorted(REPO_ROOT.rglob("*.py"))
    for path in py_files:
        # Skip venv, cache, node_modules, migrations
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part.startswith(".") or part in ("__pycache__", "node_modules", "venv")
               for part in path.parts):
            continue
        if "migrations" in rel:
            continue
        # Skip test files — they reference LLMInteraction to set up test data
        if rel.startswith("tests/"):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line) and "LLMInteraction(" in line:
                results.append((rel, lineno))

    return results


def test_bypasses_listed():
    """Every LLMInteraction creation outside the gateway is accounted for.

    This test discovers all LLMInteraction( constructor calls across the
    codebase and asserts that each one is either inside the gateway service
    or listed in EXPECTED_BYPASSES.

    Adding a new LLMInteraction( call without adding it here is a defect.
    """
    # Files that are part of the gateway and exempt from bypass labelling
    GATEWAY_FILES = {
        "app/modules/ai_chat/services/llm_service_impl.py",
        "app/models/models.py",  # model definition itself
    }

    discovered = _scan_llm_interaction_creations()
    expected_rel_set = {e[0] for e in EXPECTED_BYPASSES}

    unaccounted = []
    for rel, lineno in discovered:
        if rel in GATEWAY_FILES:
            continue
        if rel in expected_rel_set:
            continue
        unaccounted.append((rel, lineno))

    assert unaccounted == [], (
        f"Unaccounted LLMInteraction( call(s) not in EXPECTED_BYPASSES or GATEWAY_FILES:\n"
        + "\n".join(f"  {f}:{ln}" for f, ln in unaccounted)
    )


def test_known_bypasses_are_still_present():
    """The bypasses we expect still exist (catches refactoring drift)."""
    discovered = _scan_llm_interaction_creations()
    discovered_files = {f for f, _ in discovered}

    for rel, reason in EXPECTED_BYPASSES:
        assert rel in discovered_files, (
            f"Expected bypass {rel} no longer creates LLMInteraction. "
            f"Update EXPECTED_BYPASSES if refactored. Reason: {reason}"
        )


def test_llm_boundary_gate_is_clean():
    """The llm-boundary gate still passes on the emitter tree.

    Reuses the same checker as test_llm_boundary_gate.py to confirm no
    regression.
    """
    import importlib.util

    checker_path = REPO_ROOT / "scripts" / "check_llm_boundary.py"
    spec = importlib.util.spec_from_file_location("check_llm_boundary", checker_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    violations = mod.find_violations()
    assert violations == [], (
        f"llm-boundary violations in emitter tree:\n"
        + "\n".join(f"  {f}:{ln}: {txt}" for f, ln, txt in violations)
    )