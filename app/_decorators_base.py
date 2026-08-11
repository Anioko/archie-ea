from functools import wraps

from flask import abort, current_app
from flask_login import current_user

from app.models import Permission
import logging

logger = logging.getLogger(__name__)


def permission_required(permission):
    """Restrict a view to users with the given permission."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    return permission_required(Permission.ADMINISTER)(f)


def require_auth(f):
    """Require user authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        return f(*args, **kwargs)

    return decorated_function


def require_feature(feature_key: str, fallback_enabled: bool = True):
    """Require a feature flag to be enabled to access a route.
    
    Args:
        feature_key: The feature flag key to check
        fallback_enabled: If True, allow access when flag doesn't exist (default: True)
                         If False, deny access when flag doesn't exist
    
    Usage:
        @require_feature('user_management')
        @admin.route('/admin/users')
        def users_list():
            ...
    
    When feature is disabled: Returns 404 (not 403) to hide existence
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Import here to avoid circular dependency
            from app.models.feature_flags import FeatureFlag
            
            # Check if feature flag exists and is enabled
            feature = FeatureFlag.query.filter_by(key=feature_key).first()
            
            if feature is None:
                # Feature doesn't exist - use fallback
                if not fallback_enabled:
                    current_app.logger.warning(
                        f"Feature flag '{feature_key}' not found, denying access (fallback_enabled=False)"
                    )
                    abort(404)  # Use 404 not 403 to hide feature existence
            elif not feature.is_active:
                # Feature exists but is disabled
                current_app.logger.info(
                    f"Feature flag '{feature_key}' is disabled, denying access to {f.__name__}"
                )
                abort(404)  # Use 404 not 403 to hide feature existence
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def audit_log(action_name: str):
    """Audit logging decorator for route-level CRUD action tracking (ISS-006).

    Logs the action, user, entity info, and request metadata to AuditLog.
    Gracefully degrades if audit model import fails (e.g., during tests).

    Usage:
        @audit_log("application_create")
        def create_application():
            ...
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)

            # Best-effort audit — never break the request
            try:
                from app.models.audit_log import AuditLog
                from flask import request as _req, g
                from flask_login import current_user as _cu

                user_id = _cu.id if _cu and _cu.is_authenticated else None
                user_email = _cu.email if _cu and _cu.is_authenticated else None

                # Extract entity info from route kwargs or view args
                entity_id = kwargs.get("id") or kwargs.get("item_id") or kwargs.get("review_id")
                entity_type = action_name.rsplit("_", 1)[0] if "_" in action_name else action_name

                AuditLog.log(
                    action=action_name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=_req.remote_addr if _req else None,
                    description=f"{action_name} via {_req.path}" if _req else action_name,
                    status="success",
                    request_id=getattr(g, "request_id", None) if g else None,
                )
            except Exception as exc:
                logger.debug("suppressed error in audit_log.decorator.wrapper (app/_decorators_base.py): %s", exc)  # Never break the request for audit failures

            return result

        return wrapper

    return decorator


def role_required(*roles):
    """Restrict access to users whose ``enterprise_role`` is in *roles* (ENT-068).

    Falls back to ``is_admin()`` so existing admin users are never locked out.
    Must be placed **after** ``@login_required`` in the decorator stack.

    Usage::

        from app.decorators import role_required
        from app.models.user import ROLE_SOLUTION_ARCHITECT, ROLE_PLATFORM_ADMIN

        @app.route("/solutions/<int:id>/edit", methods=["POST"])
        @login_required
        @role_required(ROLE_SOLUTION_ARCHITECT, ROLE_PLATFORM_ADMIN)
        def edit_solution(id):
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            # Backward compat: legacy admin flag overrides role check
            if hasattr(current_user, "is_admin") and current_user.is_admin():
                return f(*args, **kwargs)
            if not hasattr(current_user, "enterprise_role"):
                abort(403)
            if current_user.enterprise_role not in roles:
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Which allow-list tokens each persona satisfies.
#
# The allow-lists across the codebase use seven tokens: admin, architect,
# compliance_officer, business_architect, enterprise_architect, executive and
# analyst. `enterprise_role` uses a different, finer vocabulary. This is the
# join between them, and it is deliberately explicit rather than derived: an
# architect persona satisfying the generic "architect" token is a decision, not
# a string coincidence, and adding a persona should require making that decision
# again.
#
# compliance_officer and analyst are intentionally granted by no persona. No
# persona claims either, and inventing one would hand 16 routes to a population
# nobody chose. They remain reachable through an explicitly assigned Role or
# role_archetype, and every route naming them also names admin or architect.
PERSONA_GRANTS = {
    # "architect" as well as "admin": six routes are guarded by architect-only
    # allow-lists such as ("architect", "compliance_officer"), and the platform
    # administrator reached all of them before this change. Tightening is meant
    # to remove architect write access from personas that are not architects,
    # not to lock the superuser out of six pages.
    "platform_admin": {"admin", "platform_admin", "architect"},
    "enterprise_architect": {"architect", "enterprise_architect"},
    "solution_architect": {"architect", "solution_architect"},
    "business_architect": {"architect", "business_architect"},
    "arb_member": {"arb_member"},
    "portfolio_manager": {"portfolio_manager"},
    "cto": {"cto", "executive"},
    "procurement": {"procurement"},
    "application_manager": {"application_manager"},
}


def _confers_permissions(role_obj) -> bool:
    """Does this Role row grant anything beyond the base permission?

    A role that confers no permission must not confer access either. The
    Architect and User rows both carry Permission.GENERAL — the same value an
    account has by existing — so neither says anything about what its holder may
    do. Administrator carries ADMINISTER and does.

    Fails closed: a Role whose permissions cannot be read grants nothing.
    """
    try:
        from app.models import Permission

        base = Permission.GENERAL
    except Exception:  # noqa: BLE001 - authorisation must not depend on an import
        base = 1
    permissions = getattr(role_obj, "permissions", None)
    if not isinstance(permissions, int):
        return False
    return permissions > base


def require_roles(*allowed_roles):
    """Require the user to satisfy one of the given allow-list tokens.

    Args:
        *allowed_roles: tokens the user must satisfy at least one of

    Usage:
        @require_roles('admin', 'architect')
        def admin_endpoint():
            ...

    Grants come from, in order of how much they mean:

    * ``enterprise_role`` — the persona, expanded through ``PERSONA_GRANTS``
    * ``is_platform_admin`` / ``is_org_admin`` — "admin"
    * ``role_archetype``, and any explicitly assigned ``roles`` collection
    * the single ``role`` relationship, **only** where that row confers
      permissions beyond the base — see ``_confers_permissions``

    Returns:
        403 Forbidden if the user satisfies none of them
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            def _normalize_role_name(raw_role):
                if raw_role is None:
                    return None
                role_name = str(raw_role).strip().lower()
                if role_name.startswith("<role '") and role_name.endswith("'>"):
                    role_name = role_name[7:-2]
                role_name = role_name.replace(" ", "_")
                if role_name == "administrator":
                    return "admin"
                return role_name
            
            # Get user roles (handle different user model formats)
            user_roles = set()
            
            # Try getting roles as list of role objects
            if hasattr(current_user, 'roles'):
                for role in current_user.roles:
                    if hasattr(role, 'name'):
                        normalized = _normalize_role_name(role.name)
                        if normalized:
                            user_roles.add(normalized)
                        if hasattr(role, "index"):
                            normalized_index = _normalize_role_name(role.index)
                            if normalized_index:
                                user_roles.add(normalized_index)
                    elif isinstance(role, str):
                        normalized = _normalize_role_name(role)
                        if normalized:
                            user_roles.add(normalized)
            
            # Try getting roles as list of strings
            if hasattr(current_user, 'role_names'):
                user_roles.update(
                    normalized
                    for normalized in (
                        _normalize_role_name(r) for r in current_user.role_names
                    )
                    if normalized
                )
            
            # The single `role` relationship, but only when the row confers
            # something.
            #
            # Role('Architect') used to be the default=True row, so
            # User.__init__ handed it to every account and this branch granted
            # "architect" — and with it the 104 routes whose allow-list contains
            # it — to everyone who could log in. It was a deliberate workaround:
            # insert_roles said the default "MUST normalize to architect, or
            # every normal user gets 403 on create/update/delete of their own
            # data". That was true while this decorator could not see a persona.
            # It can now (below), so the workaround is retired and the grant is
            # limited to roles that carry real permissions — Administrator, not
            # the base-permission User and Architect rows.
            role_obj = getattr(current_user, "role", None)
            if role_obj is not None:
                if hasattr(role_obj, "name"):
                    if _confers_permissions(role_obj):
                        for value in (role_obj.name, getattr(role_obj, "index", None)):
                            normalized = _normalize_role_name(value)
                            if normalized:
                                user_roles.add(normalized)
                else:
                    normalized = _normalize_role_name(role_obj)
                    if normalized:
                        user_roles.add(normalized)

            if hasattr(current_user, "role_archetype") and current_user.role_archetype:
                normalized_archetype = _normalize_role_name(current_user.role_archetype)
                if normalized_archetype:
                    user_roles.add(normalized_archetype)

            # The admin flags are an authorisation fact in their own right and
            # do not depend on which Role row a user happens to carry.
            if getattr(current_user, "is_platform_admin", False) or getattr(
                current_user, "is_org_admin", False
            ):
                user_roles.add("admin")

            # enterprise_role is the persona the product is organised around: it
            # drives the sidebar, the dashboard cards and the AI charters, and
            # it is now what this decorator actually gates on. PERSONA_GRANTS
            # maps each persona onto the vocabulary the allow-lists use, so an
            # architect persona satisfies the generic "architect" token as well
            # as its own name.
            enterprise_role = getattr(current_user, "enterprise_role", None)
            if enterprise_role:
                normalized_enterprise = _normalize_role_name(enterprise_role)
                if normalized_enterprise:
                    user_roles.add(normalized_enterprise)
                    user_roles.update(PERSONA_GRANTS.get(normalized_enterprise, ()))

            # Check if user has any of the required roles (case-insensitive)
            required = set(
                normalized
                for normalized in (_normalize_role_name(r) for r in allowed_roles)
                if normalized
            )
            
            if not user_roles & required:  # No intersection = no common roles
                current_app.logger.warning(
                    f"Access denied to {f.__name__}: user {getattr(current_user, 'email', None) or current_user.id} "
                    f"has roles {user_roles}, required {required}"
                )
                abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator
