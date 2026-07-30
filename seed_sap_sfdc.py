# -*- coding: utf-8 -*-
"""Seed a realistic in-flight S/4HANA + Salesforce transformation landscape so the
SAP+SFDC solution-architect guide has live, working examples. Run inside the
server container:  docker compose exec server python /app/seed_sap_sfdc.py"""
from manage import app
from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.vendor.vendor_organization import VendorOrganization

# (name, description, application_type, lifecycle_status)  — lifecycle codes drive the KPI cards
APPS = [
    ("SAP S/4HANA", "Target core ERP — finance, order management and billing system of record.", "application", "2.1 strategic"),
    ("SAP BTP", "Business Technology Platform — extensions, side-by-side apps, master-data hub.", "platform", "2.1 strategic"),
    ("SAP Integration Suite (CPI)", "SAP-side cloud integration — iFlows to Salesforce and MuleSoft.", "integration", "2.1 strategic"),
    ("Salesforce Sales Cloud", "Lead-to-opportunity, accounts/contacts, pipeline — system of engagement.", "application", "2.1 strategic"),
    ("Salesforce Service Cloud", "Case and service management, customer support.", "application", "2.1 strategic"),
    ("Salesforce Experience Cloud", "Partner and customer self-service portals.", "application", "2.1 strategic"),
    ("Salesforce CPQ", "Configure-price-quote front end for Quote-to-Cash.", "application", "2.1 strategic"),
    ("MuleSoft Anypoint Platform", "Enterprise integration hub — the SAP <-> Salesforce seam.", "integration", "2.1 strategic"),
    ("SAP SuccessFactors", "Core HR and talent (SaaS satellite).", "application", "2.1 strategic"),
    ("SAP Ariba", "Source-to-pay procurement (SaaS satellite).", "application", "2.2 tactical"),
    ("SAP PI/PO", "Legacy middleware kept alive during the MuleSoft migration (coexistence).", "integration", "2.2 tactical"),
    ("Legacy Order Portal", "Interim order-capture front end retained through cutover.", "application", "2.2 tactical"),
    ("SAP Concur", "Travel and expense (SaaS satellite).", "application", "2.2 tactical"),
    ("SAP ECC 6.0", "Legacy ERP core being replaced by S/4HANA.", "application", "3. sunset"),
    ("Bespoke Quote Tool", "Custom quoting satellite — Salesforce CPQ replaces it.", "application", "3. sunset"),
    ("Siebel CRM", "Legacy CRM — Salesforce Sales/Service will absorb.", "application", "4.2 decom planned"),
    ("Legacy Billing Engine", "Standalone billing — S/4HANA absorbs it.", "application", "4.2 decom planned"),
    ("Lotus Notes CRM", "Retired post-cutover.", "application", "5. decommissioned"),
]

VENDORS = [
    ("SAP", "ERP", "S/4HANA, BTP, SuccessFactors, Ariba, Concur, Integration Suite.", "https://sap.com", "Walldorf, Germany"),
    ("Salesforce", "SaaS / CRM", "Sales/Service/Experience Cloud, CPQ, MuleSoft.", "https://salesforce.com", "San Francisco, USA"),
    ("MuleSoft", "Integration", "Anypoint Platform — API-led integration (Salesforce-owned).", "https://mulesoft.com", "San Francisco, USA"),
    ("Accenture", "Systems Integrator", "Transformation delivery partner — SAP + Salesforce practice.", "https://accenture.com", "Dublin, Ireland"),
    ("Deloitte", "Systems Integrator", "Programme assurance and SI capacity.", "https://deloitte.com", "London, UK"),
]

with app.app_context():
    # Reset the application portfolio to the SAP+SFDC narrative (demo apps have no junctions)
    try:
        n_del = ApplicationComponent.query.delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback(); n_del = "skip(" + str(e)[:40] + ")"
    for name, desc, atype, lc in APPS:
        db.session.add(ApplicationComponent(
            name=name, description=desc, component_type=atype,
            application_type=atype, lifecycle_status=lc))
    db.session.commit()

    for name, vtype, desc, web, hq in VENDORS:
        if not VendorOrganization.query.filter_by(name=name).first():
            db.session.add(VendorOrganization(
                name=name, vendor_type=vtype, description=desc,
                website=web, headquarters_location=hq, status="active"))
    db.session.commit()

    apps = ApplicationComponent.query.count()
    from sqlalchemy import func
    by_lc = dict(db.session.query(ApplicationComponent.lifecycle_status, func.count()).group_by(ApplicationComponent.lifecycle_status).all())
    print("APPS:", apps, "(deleted", n_del, ")")
    print("BY_LIFECYCLE:", by_lc)
    print("VENDORS:", VendorOrganization.query.count())
