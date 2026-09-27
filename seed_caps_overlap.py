# -*- coding: utf-8 -*-
"""Create the SAP+SFDC business capabilities and map them to applications with
deliberate overlaps so the Heat Map / Gap Analysis demonstrates the
'who owns this capability - SAP or Salesforce?' decision."""
from manage import app
from app import db
from sqlalchemy import func
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.application_capability import ApplicationCapabilityMapping

CAPS = ["Customer Master", "Lead-to-Opportunity", "Quote-to-Cash", "Order Management",
        "Service & Case Management", "Billing & Invoicing", "Master Data Management"]

# (capability, application, support_level, coverage%, strength)  -- OVERLAP = same cap, 2 apps
MAPS = [
    ("Customer Master", "SAP S/4HANA", "full", 90, "critical"),
    ("Customer Master", "Salesforce Sales Cloud", "full", 85, "critical"),      # OVERLAP
    ("Lead-to-Opportunity", "Salesforce Sales Cloud", "full", 95, "critical"),
    ("Quote-to-Cash", "Salesforce CPQ", "full", 80, "strong"),
    ("Quote-to-Cash", "SAP S/4HANA", "partial", 60, "strong"),                  # OVERLAP
    ("Order Management", "SAP S/4HANA", "full", 90, "critical"),
    ("Order Management", "Legacy Order Portal", "partial", 40, "weak"),          # OVERLAP
    ("Service & Case Management", "Salesforce Service Cloud", "full", 95, "critical"),
    ("Billing & Invoicing", "SAP S/4HANA", "full", 85, "strong"),
    ("Billing & Invoicing", "Legacy Billing Engine", "partial", 50, "moderate"), # OVERLAP
    ("Master Data Management", "SAP BTP", "full", 80, "strong"),
]

with app.app_context():
    from app.models.organization import Organization
    org_id = Organization.query.order_by(Organization.id.asc()).first().id
    capid = {}
    for i, name in enumerate(CAPS):
        c = BusinessCapability.query.filter_by(name=name).first()
        if not c:
            c = BusinessCapability(name=name, level=2, code="SFCAP-%02d" % i)
            db.session.add(c); db.session.flush()
        capid[name] = c.id
    appid = {a.name: a.id for a in ApplicationComponent.query.all()}

    n = 0
    for capn, appn, lvl, cov, strn in MAPS:
        if capn in capid and appn in appid:
            if not ApplicationCapabilityMapping.query.filter_by(
                    business_capability_id=capid[capn],
                    application_component_id=appid[appn]).first():
                db.session.add(ApplicationCapabilityMapping(
                    business_capability_id=capid[capn],
                    application_component_id=appid[appn],
                    organization_id=org_id,
                    support_level=lvl, coverage_percentage=cov,
                    relationship_strength=strn))
                n += 1
    db.session.commit()

    overlaps = db.session.query(
        BusinessCapability.name, func.count()
    ).join(ApplicationCapabilityMapping,
           ApplicationCapabilityMapping.business_capability_id == BusinessCapability.id
    ).group_by(BusinessCapability.name).having(func.count() > 1).all()
    print("CAPS_CREATED:", len(capid), "MAPPINGS:", n)
    print("OVERLAPS (cap owned by >1 app):", [o[0] for o in overlaps])
