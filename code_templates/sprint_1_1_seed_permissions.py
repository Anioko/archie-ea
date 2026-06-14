"""
Seed Initial Permissions and Roles
Sprint 1.1: Authentication & Authorization
"""
from app import create_app, db
from app.models.permission import Permission, Role, RolePermission


def seed_permissions():
    """Create initial permissions"""

    permissions = [
        # Architecture permissions
        ("architecture.view", "View architecture sessions", "architecture"),
        ("architecture.create", "Create architecture sessions", "architecture"),
        ("architecture.edit", "Edit architecture sessions", "architecture"),
        ("architecture.delete", "Delete architecture sessions", "architecture"),
        # Gap analysis permissions
        ("gap_analysis.run", "Run gap analysis", "architecture"),
        ("gap_analysis.view", "View gap analysis results", "architecture"),
        # Solution options permissions
        ("options.generate", "Generate solution options", "architecture"),
        ("options.view", "View solution options", "architecture"),
        ("options.compare", "Compare solution options", "architecture"),
        # ADR permissions
        ("adr.create", "Create ADRs", "adr"),
        ("adr.view", "View ADRs", "adr"),
        ("adr.edit", "Edit ADRs", "adr"),
        ("adr.export", "Export ADRs", "adr"),
        ("adr.approve", "Approve ADRs", "adr"),
        # ARB permissions
        ("arb.submit", "Submit ARB packages", "arb"),
        ("arb.review", "Review ARB submissions", "arb"),
        ("arb.approve", "Approve ARB submissions", "arb"),
        # Admin permissions
        ("admin.users", "Manage users", "admin"),
        ("admin.roles", "Manage roles", "admin"),
        ("admin.settings", "Manage settings", "admin"),
    ]

    created_perms = {}
    for name, desc, cat in permissions:
        perm = Permission.query.filter_by(name=name).first()
        if not perm:
            perm = Permission(name=name, description=desc, category=cat)
            db.session.add(perm)
            print(f"Created permission: {name}")
        created_perms[name] = perm

    db.session.commit()
    return created_perms


def seed_roles(tenant_id=1):
    """Create initial roles"""

    perms = seed_permissions()

    roles_config = {
        "Viewer": [
            "architecture.view",
            "gap_analysis.view",
            "options.view",
            "adr.view",
        ],
        "Solution Architect": [
            "architecture.view",
            "architecture.create",
            "architecture.edit",
            "gap_analysis.run",
            "gap_analysis.view",
            "options.generate",
            "options.view",
            "options.compare",
            "adr.create",
            "adr.view",
            "adr.export",
        ],
        "Enterprise Architect": [
            "architecture.view",
            "architecture.create",
            "architecture.edit",
            "gap_analysis.run",
            "gap_analysis.view",
            "options.generate",
            "options.view",
            "options.compare",
            "adr.create",
            "adr.view",
            "adr.edit",
            "adr.export",
            "adr.approve",
            "arb.submit",
            "arb.review",
        ],
        "ARB Member": [
            "architecture.view",
            "gap_analysis.view",
            "options.view",
            "adr.view",
            "arb.review",
            "arb.approve",
        ],
        "Administrator": list(perms.keys()),  # All permissions
    }

    for role_name, perm_names in roles_config.items():
        role = Role.query.filter_by(tenant_id=tenant_id, name=role_name).first()
        if not role:
            role = Role(
                tenant_id=tenant_id,
                name=role_name,
                description=f"System role: {role_name}",
                is_system_role=True,
            )
            db.session.add(role)

            # Add permissions to role
            for perm_name in perm_names:
                if perm_name in perms:
                    role.permissions.append(perms[perm_name])

            print(f"Created role: {role_name} with {len(perm_names)} permissions")

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Seeding permissions and roles...")
        seed_roles()
        print("Done!")
