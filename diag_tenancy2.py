"""Definitive isolation test: set a NON-EXISTENT org and see what still leaks.
DB counts only — no ML model load."""
from app import create_app, db
from flask import g
from sqlalchemy import text, func
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.solution_models import Solution

app = create_app()
with app.app_context():
    FAKE = 999999  # no org has this id
    g.current_org_id = FAKE
    print(f"Tenant context = org {FAKE} (does not exist). A correct filter -> 0 rows.\n")

    for label, m in [("ApplicationComponent", ApplicationComponent),
                     ("BusinessCapability", BusinessCapability),
                     ("Solution", Solution)]:
        via_query = m.query.count()                                   # ORM .query pattern
        via_func = db.session.query(func.count(m.id)).scalar()        # dashboard's exact pattern
        print(f"{label:22} .query.count()={via_query:>4}   func.count()={via_func:>4}   "
              f"{'ISOLATED' if (via_query==0 and via_func==0) else 'LEAKS'}")

    # dashboard data_coverage uses RAW SQL — bypasses ORM filter entirely
    raw = db.session.execute(text("SELECT COUNT(*) FROM application_components")).scalar()
    print(f"\nRAW SQL COUNT(application_components) = {raw}   "
          f"{'(bypasses filter — LEAKS across orgs)' if raw > 0 else ''}")
