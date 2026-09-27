"""A-06: blind-generation prompts must receive repo-context + no-duplicate instruction.

Unit tests on prompt-building only -- no live LLM call. Exercises
SolutionAIOrchestrator._gather_duplicate_avoidance_context and confirms it is
wired into DRAFT_ARCHITECTURE_PROMPT, ARCHITECTURE_VARIANTS_PROMPT and
STRATEGY_SPECIALIST_PROMPT.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def orchestrator():
    from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import (
        SolutionAIOrchestrator,
    )

    return SolutionAIOrchestrator()


def test_draft_architecture_prompt_has_repo_context_placeholder(orchestrator):
    """The template itself must declare the repo-context slot and the rule."""
    prompt = orchestrator.DRAFT_ARCHITECTURE_PROMPT
    assert "{existing_repository_context}" in prompt
    assert "DO NOT DUPLICATE" in prompt


def test_architecture_variants_prompt_has_repo_context_placeholder(orchestrator):
    prompt = orchestrator.ARCHITECTURE_VARIANTS_PROMPT
    assert "{existing_repository_context}" in prompt
    assert "duplicate" in prompt.lower()


def test_strategy_specialist_prompt_has_repo_context_placeholder(orchestrator):
    prompt = orchestrator.STRATEGY_SPECIALIST_PROMPT
    assert "{existing_repository_context}" in prompt
    assert "DO NOT DUPLICATE" in prompt


def test_gather_duplicate_avoidance_context_lists_existing_names(db_session, make_org, tenant_ctx):
    """Given existing ArchiMateElement/Solution rows, the context block names them."""
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_models import Solution

    org = make_org("dup-ctx")

    with tenant_ctx(org.id):
        solution = Solution(name="Target Solution", business_domain="Finance", organization_id=org.id)
        other_solution = Solution(
            name="Existing Payments Platform", business_domain="Finance", organization_id=org.id
        )
        elem = ArchiMateElement(
            name="Existing Payment Gateway",
            type="ApplicationComponent",
            organization_id=org.id,
        )
        db_session.add_all([solution, other_solution, elem])
        db_session.flush()

        from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import (
            SolutionAIOrchestrator,
        )

        orch = SolutionAIOrchestrator()
        ctx = orch._gather_duplicate_avoidance_context(solution)

    assert "Existing Payment Gateway" in ctx
    assert "Existing Payments Platform" in ctx
    assert "DO NOT DUPLICATE" in ctx


def test_gather_duplicate_avoidance_context_empty_repo_is_safe(db_session, make_org, tenant_ctx):
    """No existing entities -> returns '' rather than raising, prompt .format() still works."""
    from app.models.solution_models import Solution

    org = make_org("dup-ctx-empty")

    with tenant_ctx(org.id):
        solution = Solution(name="Lonely Solution", business_domain="HR", organization_id=org.id)
        db_session.add(solution)
        db_session.flush()

        from app.modules.solutions_strategic.v2.services.solution_ai_orchestrator import (
            SolutionAIOrchestrator,
        )

        orch = SolutionAIOrchestrator()
        ctx = orch._gather_duplicate_avoidance_context(solution)
    assert isinstance(ctx, str)
