"""
Permission and Role Models for RBAC
Sprint 1.1: Authentication & Authorization
"""
from datetime import datetime

from app.extensions import db


class Permission(db.Model):
    """Individual permissions that can be granted to roles"""

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(500))
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Permission {self.name}>"


class Role(db.Model):
    """Roles that group permissions"""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    is_system_role = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship("Permission", secondary="role_permissions", backref="roles")

    __table_args__ = (db.UniqueConstraint("tenant_id", "name", name="uq_tenant_role"),)

    def has_permission(self, permission_name):
        """Check if role has specific permission"""
        return any(p.name == permission_name for p in self.permissions)


class RolePermission(db.Model):
    """Many-to-many between roles and permissions"""

    __tablename__ = "role_permissions"

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), primary_key=True)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserRole(db.Model):
    """Many-to-many between users and roles"""

    __tablename__ = "user_roles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), primary_key=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
