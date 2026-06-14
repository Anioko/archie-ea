"""
Role-Based Navigation Access Control (NS-006)

Defines which navigation sections each enterprise_role can access.
Used by admin_sidebar.html to filter navigation items.

Part of North Star Persona MVP implementation.
ADR Reference: docs/adr/0009-persona-based-navigation.md
"""

from typing import Dict, List, Set

from app.models.user import (
    ROLE_APPLICATION_MANAGER,
    ROLE_ARB_MEMBER,
    ROLE_CTO,
    ROLE_ENTERPRISE_ARCHITECT,
    ROLE_PLATFORM_ADMIN,
    ROLE_PORTFOLIO_MANAGER,
    ROLE_PROCUREMENT,
    ROLE_SOLUTION_ARCHITECT,
    VALID_ROLES,
)


# Navigation sections defined in the sidebar
NAVIGATION_SECTIONS = [
    "home",
    "solutions",
    "portfolio",
    "architecture",
    "capabilities",
    "roadmaps",
    "governance",
    "procurement",
    "my_applications",
    "data_integration",
    "administration",
]

# Role to sections mapping
# Each role has a set of sections they can access
ROLE_SECTION_ACCESS: Dict[str, Set[str]] = {
    ROLE_SOLUTION_ARCHITECT: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "roadmaps",
        "governance",
        "data_integration",
    },
    ROLE_ENTERPRISE_ARCHITECT: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "roadmaps",
        "governance",
        "data_integration",
    },
    ROLE_ARB_MEMBER: {
        "home",
        "solutions",
        "portfolio",
        "governance",
    },
    ROLE_PORTFOLIO_MANAGER: {
        "home",
        "solutions",
        "portfolio",
        "capabilities",
        "roadmaps",
        "governance",
        "procurement",  # Read-only access to procurement for cost visibility
    },
    ROLE_CTO: {
        "home",
        "solutions",
        "portfolio",
        "capabilities",
        "roadmaps",
        "governance",
    },
    ROLE_PROCUREMENT: {
        "home",
        "portfolio",  # Read-only for app-vendor context
        "procurement",
    },
    ROLE_APPLICATION_MANAGER: {
        "home",
        "solutions",  # Read-only for impact awareness
        "portfolio",  # Read-only for integration context
        "my_applications",
        "roadmaps",  # Read-only
    },
    ROLE_PLATFORM_ADMIN: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "roadmaps",
        "governance",
        "procurement",
        "my_applications",
        "data_integration",
        "administration",
    },
}

# Sections that require specific roles (exclusive access)
EXCLUSIVE_SECTIONS: Dict[str, List[str]] = {
    "administration": [ROLE_PLATFORM_ADMIN],
    "procurement": [ROLE_PROCUREMENT, ROLE_PORTFOLIO_MANAGER, ROLE_PLATFORM_ADMIN],
    "my_applications": [ROLE_APPLICATION_MANAGER, ROLE_PLATFORM_ADMIN],
}

# Default role if user has no enterprise_role set
DEFAULT_ROLE = ROLE_SOLUTION_ARCHITECT


def get_user_role(user) -> str:
    """Get user's enterprise role with fallback to default."""
    if not user or not hasattr(user, "enterprise_role"):
        return DEFAULT_ROLE
    return user.enterprise_role or DEFAULT_ROLE


def can_access_section(user, section: str) -> bool:
    """
    Check if user can access a navigation section.

    Args:
        user: User object with enterprise_role attribute
        section: Navigation section identifier

    Returns:
        True if user can access the section
    """
    role = get_user_role(user)
    allowed_sections = ROLE_SECTION_ACCESS.get(role, set())
    return section in allowed_sections


def get_visible_sections(user) -> List[str]:
    """
    Get list of navigation sections visible to user.

    Args:
        user: User object with enterprise_role attribute

    Returns:
        List of section identifiers user can see
    """
    role = get_user_role(user)
    allowed_sections = ROLE_SECTION_ACCESS.get(role, set())
    # Return in defined order
    return [s for s in NAVIGATION_SECTIONS if s in allowed_sections]


def is_admin(user) -> bool:
    """Check if user has admin role."""
    return get_user_role(user) == ROLE_PLATFORM_ADMIN


def is_procurement(user) -> bool:
    """Check if user has procurement role."""
    return get_user_role(user) == ROLE_PROCUREMENT


def is_application_manager(user) -> bool:
    """Check if user has application manager role."""
    return get_user_role(user) == ROLE_APPLICATION_MANAGER


def get_role_display_name(role: str) -> str:
    """Get human-readable name for role."""
    from app.models.user import ROLE_DISPLAY_NAMES
    return ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())


def get_all_roles_with_access(section: str) -> List[str]:
    """Get all roles that can access a section."""
    return [
        role for role, sections in ROLE_SECTION_ACCESS.items()
        if section in sections
    ]


# Context processor for templates
def role_access_context_processor():
    """
    Provide role access functions to Jinja2 templates.

    Usage in template:
        {% if can_access_section(current_user, 'administration') %}
    """
    return {
        "can_access_section": can_access_section,
        "get_visible_sections": get_visible_sections,
        "is_admin": is_admin,
        "is_procurement": is_procurement,
        "is_application_manager": is_application_manager,
        "get_role_display_name": get_role_display_name,
    }
