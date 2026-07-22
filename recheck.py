import sys
from manage import app
app.config["WTF_CSRF_ENABLED"] = False
app.config["PROPAGATE_EXCEPTIONS"] = True
from app import db
with app.app_context():
    try:
        from app.models.user import User
    except Exception:
        from app.models import User
    uid = User.query.filter_by(email="demo@archiedemo.com").first().id
c = app.test_client()
with c.session_transaction() as s:
    s["_user_id"] = str(uid); s["_fresh"] = True
routes = sys.argv[1:] or ["/arb/decisions", "/governance/principles", "/governance/standards", "/governance/roadmap"]
for u in routes:
    try:
        r = c.get(u); print(f"  {r.status_code}  {u}")
    except Exception as e:
        print(f"  EXC:{type(e).__name__}: {str(e)[:120]}  {u}")
