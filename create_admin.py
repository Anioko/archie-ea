"""Create the first admin user (and the organization it belongs to).

Run after `flask --app manage init-db`. Reads ADMIN_EMAIL / ADMIN_PASSWORD from the
environment (see .env.example). Safe to re-run: it is a no-op if the admin exists.
"""
from manage import app, db
from app.models import Role, User
from app.models.organization import Organization
from config import Config

with app.app_context():
    Role.insert_roles()
    exists = User.query.filter_by(email=Config.ADMIN_EMAIL).first()
    if exists:
        print("Admin already exists:", Config.ADMIN_EMAIL)
    else:
        # Every user belongs to an organization (users.organization_id is NOT NULL).
        # Create a default organization for the first admin if one does not exist.
        org = Organization.query.filter_by(slug="default").first()
        if org is None:
            org = Organization(name="Default Organization", slug="default")
            db.session.add(org)
            db.session.flush()  # assign org.id before the user references it

        u = User(
            first_name="Admin",
            last_name="User",
            email=Config.ADMIN_EMAIL,
            password=Config.ADMIN_PASSWORD,
            confirmed=True,
        )
        # First admin owns the platform and their organization.
        u.organization_id = org.id
        u.is_org_admin = True
        u.is_platform_admin = True
        db.session.add(u)
        db.session.commit()
        print("Admin created:", Config.ADMIN_EMAIL, "(organization:", org.slug + ")")
