from manage import app, db
from app.models import Role, User
from config import Config

with app.app_context():
    Role.insert_roles()
    exists = User.query.filter_by(email=Config.ADMIN_EMAIL).first()
    if exists:
        print("Admin already exists:", Config.ADMIN_EMAIL)
    else:
        u = User(
            first_name='Admin',
            last_name='User',
            email=Config.ADMIN_EMAIL,
            password=Config.ADMIN_PASSWORD,
            confirmed=True
        )
        db.session.add(u)
        db.session.commit()
        print("Admin created:", Config.ADMIN_EMAIL)
