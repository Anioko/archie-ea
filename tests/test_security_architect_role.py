"""G6 (capability-gap register): security_architect is a first-class role.

These pin the pieces that make the role first-class rather than a phantom that
falls back to the solution_architect sidebar and the enterprise_architect
persona -- and that the built-but-orphaned regulatory-compliance model now has a
navigable door. Pure-function assertions run without a database; the one route
check uses only the app fixture (registration lookup, no request/DB).
"""

import pytest


def test_security_architect_is_a_valid_role():
    from app.models.user import VALID_ROLES, ROLE_SECURITY_ARCHITECT

    assert ROLE_SECURITY_ARCHITECT == "security_architect"
    assert "security_architect" in VALID_ROLES


def test_security_architect_resolves_to_its_own_persona_not_the_ea_fallback():
    from app.modules.ai_chat.services.architect_persona_charters import (
        get_default_chat_persona,
        build_architect_prompt,
    )

    persona = get_default_chat_persona("security_architect")
    assert persona == "security_architect"
    assert persona != "enterprise_architect"

    prompt = build_architect_prompt(persona)
    assert prompt, "security_architect has no charter"
    # Mirrors the governance/evidence tone the other charters carry.
    assert "NO FABRICATION" in prompt


class _Stub:
    """Minimal stand-in for a User -- get_user_role() only reads the attr."""

    def __init__(self, role):
        self.enterprise_role = role
        self.is_platform_admin = False


def test_get_user_role_returns_the_security_value():
    from app.utils.role_access import get_user_role

    assert get_user_role(_Stub("security_architect")) == "security_architect"


def test_sidebar_sections_include_governance_and_compliance_but_not_admin():
    from app.utils.role_access import (
        ROLE_SECTION_ACCESS,
        can_access_section,
        ROLE_SECURITY_ARCHITECT,
    )

    sections = ROLE_SECTION_ACCESS[ROLE_SECURITY_ARCHITECT]
    assert "governance" in sections
    assert "compliance" in sections
    # Security-sensitive: the role must NOT gain the admin/platform surface.
    assert "administration" not in sections

    user = _Stub("security_architect")
    assert can_access_section(user, "governance") is True
    assert can_access_section(user, "compliance") is True
    assert can_access_section(user, "administration") is False


def test_security_architect_does_not_get_admin_zone_in_the_sidebar():
    from app.utils.role_access import SIDEBAR_ZONES, ROLE_SECURITY_ARCHITECT

    zone_names = {z["zone"] for z in SIDEBAR_ZONES[ROLE_SECURITY_ARCHITECT]}
    assert "admin" not in zone_names


def test_compliance_link_points_at_the_regulatory_dashboard(app):
    """The role's Compliance link must reach the orphaned-model dashboard, and
    that endpoint must actually be registered -- not the procurement license
    dashboard it used to point at, which @requires_procurement 403s for it."""
    from app.utils.role_access import SIDEBAR_ZONES, ROLE_SECURITY_ARCHITECT

    links = [
        link
        for zone in SIDEBAR_ZONES[ROLE_SECURITY_ARCHITECT]
        for link in zone["links"]
    ]
    compliance = [link for link in links if link["label"] == "Compliance"]
    assert compliance, "security_architect has no Compliance link"
    endpoint = compliance[0]["endpoint"]
    assert endpoint == "application_mgmt.compliance_frameworks_dashboard"
    assert endpoint != "procurement.compliance_dashboard"
    # The endpoint must be registered, or the sidebar silently drops the link.
    assert endpoint in app.view_functions


def test_data_architect_is_first_class_with_its_own_persona():
    from app.models.user import VALID_ROLES
    from app.modules.ai_chat.services.architect_persona_charters import (
        get_default_chat_persona,
    )
    from app.utils.role_access import ROLE_SECTION_ACCESS, ROLE_DATA_ARCHITECT

    assert "data_architect" in VALID_ROLES
    assert get_default_chat_persona("data_architect") == "data_architect"
    assert "administration" not in ROLE_SECTION_ACCESS[ROLE_DATA_ARCHITECT]
