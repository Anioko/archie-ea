"""Diagnose tenant isolation empirically. DB counts only — no ML model load."""
from app import create_app, db
from flask import g
from app.models.organization import Organization
from app.models.application_portfolio import ApplicationComponent, VendorContract
from app.models.business_capabilities import BusinessCapability
from app.models.solution_models import Solution
from app.models.unified_capability import UnifiedCapability
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

app = create_app()

def counts():
    def c(m):
        try:
            return m.query.count()
        except Exception as e:
            db.session.rollback()
            return f"ERR:{type(e).__name__}"
    return {
        "apps": c(ApplicationComponent),
        "caps": c(BusinessCapability),
        "solutions": c(Solution),
        "vendors": c(VendorOrganization),
        "unified_caps": c(UnifiedCapability),
        "vendor_products": c(VendorProduct),
        "vendor_contracts": c(VendorContract),
    }

with app.app_context():
    if hasattr(g, "current_org_id"):
        del g.current_org_id
    orgs = Organization.query.all()
    print("ORGS:", [(o.id, o.name) for o in orgs])
    print("GLOBAL (no tenant ctx):", counts())
    for o in orgs:
        g.current_org_id = o.id
        print(f"org {o.id} [{o.name}]:", counts())
    # which models are TenantMixin?
    from app.models.mixins.core import TenantMixin
    for m in [ApplicationComponent, BusinessCapability, Solution, VendorOrganization,
              UnifiedCapability, VendorProduct, VendorContract]:
        print(f"  {m.__name__:22} TenantMixin={issubclass(m, TenantMixin)}  org_col={'organization_id' in m.__table__.columns}")
