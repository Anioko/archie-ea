"""Blueprint visibility and Code Workbench authorization must agree."""

from types import SimpleNamespace

from app.modules.codegen.routes._helpers import _check_access
from app.modules.solutions_strategic.v2.routes.solution_design_routes import (
    _check_solution_access,
)


def _user(user_id, email, *, admin=False, platform_admin=False):
    return SimpleNamespace(
        id=user_id,
        email=email,
        is_authenticated=True,
        is_admin=lambda: admin,
        is_platform_admin=platform_admin,
    )


def _solution(**overrides):
    values = {
        "created_by_id": 10,
        "solution_owner": "owner@example.com",
        "business_sponsor": None,
        "technical_lead": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_non_stakeholder_is_not_admitted_by_bound_is_admin_method():
    outsider = _user(20, "outsider@example.com")

    assert _check_solution_access(_solution(), outsider) is False
    assert _check_access(_solution(), outsider) is False


def test_blueprint_and_codegen_admit_creator_stakeholder_and_platform_admin():
    solution = _solution()
    users = [
        _user(10, "creator@example.com"),
        _user(20, "OWNER@example.com"),
        _user(30, "platform@example.com", platform_admin=True),
    ]

    for user in users:
        assert _check_solution_access(solution, user) is True
        assert _check_access(solution, user) is True
