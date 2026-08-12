"""What ``require_roles`` admits, across the 150 routes that use it.

Until 2026-08-11 the answer was "everybody". ``Role('Architect')`` was the
``default=True`` row, ``User.__init__`` assigned it to every account, and the
decorator granted the token from ``role.name`` — so every user who could log in
satisfied any allow-list containing "architect": 104 decorators, 102 distinct
routes. A procurement user could write to all of them.

That was a deliberate workaround, and ``Role.insert_roles`` said so: the CRUD
guards use ``require_roles("admin", "architect")``, the decorator could not see
a persona, and so the default role "MUST normalize to architect, or every normal
user gets 403 on create/update/delete of their own data".

The workaround is retired by removing its cause. ``require_roles`` now grants
from ``enterprise_role`` through ``PERSONA_GRANTS``, where all three architect
personas satisfy "architect" by being architects; the default role moves to
``User``; and a ``Role`` row grants a token only where it confers permissions
beyond the base, which ``Architect`` and ``User`` do not and ``Administrator``
does.

Measured over every literal allow-list in the codebase, before → after:

    platform_admin          102 → 147     (it never mapped to "admin" before)
    enterprise_architect    107 → 107
    solution_architect      102 → 102
    business_architect      102 → 102
    cto                     102 →   2     (the "executive" routes)
    arb_member              102 →   0
    portfolio_manager       102 →   0
    procurement             102 →   0
    application_manager     102 →   0

No architect persona loses a route, no route becomes unreachable by every
persona, and the four personas that are not architects stop having architect
write access. ``test_no_route_becomes_unreachable`` re-derives that from source
on every run, so a new allow-list token nobody can satisfy fails here rather
than in support.
"""

from __future__ import annotations

import ast
import io
import pathlib
import uuid

import pytest

from app._decorators_base import PERSONA_GRANTS

# A route guarded by exactly ("admin", "architect", "business_architect").
GUARDED_URL = "/capability-map/import/preview"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Personas that are not architects and must not hold architect write access.
NON_ARCHITECT_PERSONAS = [
    "arb_member",
    "portfolio_manager",
    "procurement",
    "application_manager",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(db_session, org_id, *, enterprise_role=None, role_name=None):
    from app.models.user import Role, User

    user = User(
        email=f"roles-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Role",
        last_name="Probe",
        organization_id=org_id,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    if role_name is not None:
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name)
            db_session.add(role)
            db_session.flush()
        user.role = role
    # is_platform_admin defaults True on this model; an "admin" flag would grant
    # the admin token and mask what the persona itself is worth.
    user.is_platform_admin = False
    user.is_org_admin = False
    db_session.add(user)
    db_session.commit()
    return user.id


def _as(app, user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    # Flask-Login caches the resolved user on `g`, and pytest-flask reuses one
    # context across the test; without clearing it a second login silently runs
    # as the first user — which in a permission test reports a pass for the
    # wrong reason.
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)
    return client


def _post_a_file(client):
    return client.post(
        GUARDED_URL,
        data={"file": (io.BytesIO(b"name\nProbe Capability\n"), "probe.csv")},
        content_type="multipart/form-data",
    )


def _literal_allow_lists():
    """Every ``@require_roles(...)`` in the app whose arguments are literals."""
    found = []
    for path in (REPO_ROOT / "app").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                name = (
                    decorator.func.id
                    if isinstance(decorator.func, ast.Name)
                    else getattr(decorator.func, "attr", "")
                )
                if name != "require_roles":
                    continue
                tokens, literal = set(), True
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        tokens.add(arg.value.lower())
                    else:
                        literal = False
                if literal and tokens:
                    found.append(
                        (str(path.relative_to(REPO_ROOT)), node.name, frozenset(tokens))
                    )
    return found


def _grants(persona):
    return {persona} | set(PERSONA_GRANTS.get(persona, ()))


@pytest.fixture(autouse=True)
def _no_csrf(app):
    previous = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        yield
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous


# ---------------------------------------------------------------------------
# The matrix, re-derived from source
# ---------------------------------------------------------------------------


def test_there_are_allow_lists_to_check():
    """Guard against the AST walk silently finding nothing and passing."""
    assert len(_literal_allow_lists()) > 100


def test_no_route_becomes_unreachable(app):
    """Every guarded route must be reachable by at least one persona.

    An allow-list token no persona satisfies is a page that exists and nobody
    can open — the failure mode this tightening could plausibly introduce.
    """
    orphans = [
        f"{path}:{func} {sorted(tokens)}"
        for path, func, tokens in _literal_allow_lists()
        if not any(tokens & _grants(persona) for persona in PERSONA_GRANTS)
    ]
    assert not orphans, "no persona can reach:\n  " + "\n  ".join(orphans)


@pytest.mark.parametrize("persona", ["enterprise_architect", "solution_architect",
                                     "business_architect", "platform_admin"])
def test_an_architect_persona_keeps_the_architect_routes(app, persona):
    """The personas the platform is for must not lose write access."""
    grants = _grants(persona)
    architect_routes = [
        (path, func)
        for path, func, tokens in _literal_allow_lists()
        if "architect" in tokens
    ]
    assert architect_routes
    unreachable = [
        f"{path}:{func}"
        for path, func, tokens in _literal_allow_lists()
        if "architect" in tokens and not (tokens & grants)
    ]
    assert not unreachable, f"{persona} lost:\n  " + "\n  ".join(unreachable)


def test_an_arb_member_can_still_review():
    """Reviewing is what the persona is for.

    begin_arb_review, approve_solution and reject_solution were reachable by an
    arb_member only through the default Role('Architect') every account carried
    — the accidental grant this change removed. Without arb_member in
    _REVIEW_ROLES the tightening would have left the Architecture Review Board
    workflow operable by architects and admins and not by its own members.
    """
    from app.modules.architecture.routes.arb_workflow_routes import _REVIEW_ROLES

    assert set(_REVIEW_ROLES) & _grants("arb_member"), (
        "an arb_member satisfies no token in the ARB review allow-list"
    )


@pytest.mark.parametrize("persona", NON_ARCHITECT_PERSONAS)
def test_a_non_architect_persona_holds_no_architect_write_access(persona):
    """The tightening itself: 102 routes each of these used to reach."""
    grants = _grants(persona)
    assert "architect" not in grants, (
        f"{persona} satisfies the generic architect token, which is the hole "
        "this change closes"
    )
    reachable = [
        f"{path}:{func}"
        for path, func, tokens in _literal_allow_lists()
        if tokens & grants
    ]
    assert not reachable, (
        f"{persona} still reaches architecture routes:\n  " + "\n  ".join(reachable[:10])
    )


# ---------------------------------------------------------------------------
# The live decorator, through a real route
# ---------------------------------------------------------------------------


def test_a_business_architect_can_reach_a_route_named_for_them(
    app, db_session, make_org, tenant_ctx
):
    org = make_org(f"roles-ba-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="business_architect")

    assert _post_a_file(_as(app, user_id)).status_code == 200


def test_a_solution_architect_can_still_edit_their_own_data(
    app, db_session, make_org, tenant_ctx
):
    """The "CRUD is broken" symptom the default Architect role existed to avoid.

    solution_architect is what an invited user gets when no persona is chosen,
    so this is the common account.
    """
    org = make_org(f"roles-sa-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="solution_architect")

    assert _post_a_file(_as(app, user_id)).status_code == 200


def test_a_procurement_persona_is_now_refused(app, db_session, make_org, tenant_ctx):
    """Was 200 through the default role every account carried."""
    org = make_org(f"roles-deny-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="procurement")

    assert _post_a_file(_as(app, user_id)).status_code == 403


def test_the_architect_role_row_alone_grants_nothing(
    app, db_session, make_org, tenant_ctx
):
    """A role conferring no permission must not confer access.

    Architect and User both hold Permission.GENERAL — the permission an account
    has by existing — so neither says anything about what its holder may do.
    """
    org = make_org(f"roles-rolerow-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(
            db_session, org.id, enterprise_role="procurement", role_name="Architect"
        )

    assert _post_a_file(_as(app, user_id)).status_code == 403


def test_the_administrator_role_row_still_grants_admin(
    app, db_session, make_org, tenant_ctx
):
    """Administrator carries ADMINISTER, so it is a real authorisation fact."""
    org = make_org(f"roles-adminrow-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(
            db_session, org.id, enterprise_role="procurement", role_name="Administrator"
        )

    assert _post_a_file(_as(app, user_id)).status_code == 200


def test_the_admin_flag_grants_admin_on_its_own(app, db_session, make_org, tenant_ctx):
    org = make_org(f"roles-flag-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        user_id = _user(db_session, org.id, enterprise_role="procurement")
        from app.models.user import User

        db_session.get(User, user_id).is_platform_admin = True
        db_session.commit()

    assert _post_a_file(_as(app, user_id)).status_code == 200


def test_an_anonymous_request_is_refused(app):
    resp = _post_a_file(app.test_client())
    # @login_required runs first and redirects to the login page; that or a 401
    # is correct, a 200 never is.
    assert resp.status_code in (302, 401), resp.status_code


# ---------------------------------------------------------------------------
# The default role
# ---------------------------------------------------------------------------


def test_the_default_role_confers_no_authorisation(app, db_session):
    """Whatever the default is, every account gets it — so it must grant nothing."""
    from app._decorators_base import _confers_permissions
    from app.models.user import Role

    default_role = Role.query.filter_by(default=True).first()
    assert default_role is not None, "new users would receive no role at all"
    assert not _confers_permissions(default_role), (
        f"the default role {default_role.name!r} confers permissions, so every "
        "account on the platform holds them"
    )


def test_insert_roles_makes_user_the_default(app, db_session):
    from app.models.user import Role

    Role.insert_roles()
    default_role = Role.query.filter_by(default=True).first()
    assert default_role.name == "User"
    assert Role.query.filter_by(name="Architect").one().default is False
