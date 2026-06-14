"""Permission and Role models for RBAC.

The canonical Role model is defined in app.models.user (with permissions bitfield,
description, and created_at columns). This module provides the Permission model and
the UserRole / RolePermission junction tables for the granular RBAC layer.

ROLE-ASSOCIATION MECHANISMS
============================
Two mechanisms exist side-by-side — do NOT mix them:

1. User.role_id FK (app.models.user)
   - Bitfield-based: Role.permissions & Permission.ADMINISTER
   - Used by user.can() / user.is_admin() for all auth guards
   - Authoritative for the current application

2. UserRole junction table (this file)
   - Many-to-many: user ↔ role, role ↔ permission
   - Intended for future fine-grained RBAC expansion
   - Not yet wired into any auth guard — do not use for access control until
     user.can() is updated to consult this table
"""

from datetime import datetime

from app import db


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserRole(db.Model):
    """Junction table linking users to roles (granular RBAC layer).

    Not used by user.can() — see module docstring for guidance.
    """

    __tablename__ = "user_roles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RolePermission(db.Model):
    """Junction table linking roles to fine-grained permissions."""

    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
