"""Wave AI-1 follow-up: five new persona charters + alias joins.

Covers arb_member, portfolio_manager, cto, procurement, application_manager
charters (mission / SCOPE OF DUTY / HOW YOU ANSWER / hard rules), the
solution_architect -> solutions_architect and cio -> cto alias joins, and the
platform_admin "intentionally charter-less" contract.

Only needs the session-scoped ``app`` fixture from tests/conftest.py — the
context builders are ``_safe()``-wrapped, so they degrade to "unavailable"
without any seeded data.
"""

from app.models.user import VALID_ROLES
from app.modules.ai_chat.services.architect_persona_charters import (
    build_architect_prompt,
)

NEW_PERSONAS = (
    "arb_member",
    "portfolio_manager",
    "cto",
    "procurement",
    "application_manager",
)


def test_new_personas_have_charters_with_hard_rules_and_live_data(app):
    with app.app_context():
        for persona in NEW_PERSONAS:
            prompt = build_architect_prompt(persona)
            assert prompt is not None, f"{persona} should resolve to a charter"
            assert "HARD RULES" in prompt
            assert "Live Platform Data" in prompt


def test_solution_architect_alias_resolves(app):
    with app.app_context():
        prompt = build_architect_prompt("solution_architect")
        assert prompt is not None
        assert "HARD RULES" in prompt


def test_cio_alias_resolves_to_cto(app):
    with app.app_context():
        prompt = build_architect_prompt("cio")
        assert prompt is not None
        assert "HARD RULES" in prompt


def test_every_enterprise_role_except_platform_admin_has_a_charter(app):
    with app.app_context():
        for role in VALID_ROLES:
            prompt = build_architect_prompt(role)
            if role == "platform_admin":
                assert prompt is None, "platform_admin is intentionally charter-less"
            else:
                assert prompt is not None, f"{role} should resolve to a charter"
