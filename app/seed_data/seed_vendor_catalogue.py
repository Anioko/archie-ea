import os

from app import db
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.seed_data.vendor_catalogue import VENDOR_CATALOGUE  # type: ignore

DEV_FLAG = os.environ.get("DEV_SEED_VENDOR_CATALOG", "0") == "1"

CATEGORY_TO_DOMAIN = {
    "ERP": "erp",
    "ITSM": "itsm",
    "GRC": "grc",
    "SECURITY": "security",
    "CLOUD_PLATFORM": "cloud",
    "DEVOPS": "devops",
    "CRM": "crm",
    "HCM": "hcm",
    "SCM": "scm",
    "ANALYTICS": "analytics",
    "INTEGRATION": "integration",
    "COLLABORATION": "collaboration",
    "PLM": "plm",
    "EAM": "eam",
    "DATABASE": "database",
    "MDM": "mdm",
    "EA_TOOLS": "other",
    "APM": "itsm",
    "BPM": "other",
    "DATA_GOVERNANCE": "mdm",
    "ITAM": "eam",
    "OTHER": "other",
}

_KNOWN_PRODUCT_NAMES = {
    "SAP": {"ERP": "SAP S/4HANA ERP"},
    "Oracle": {"ERP": "Oracle Fusion Cloud ERP"},
    "NetSuite": {"ERP": "NetSuite ERP"},
    "Microsoft": {"ERP": "Microsoft Dynamics 365 ERP"},
    "Workday": {"ERP": "Workday Enterprise Management", "HCM": "Workday HCM"},
}

_CATEGORY_PRODUCT_SUFFIX = {
    "ITSM": "Service Management Platform",
    "GRC": "Governance & Compliance Suite",
    "SECURITY": "Security Platform",
    "CLOUD_PLATFORM": "Cloud Platform",
    "DEVOPS": "DevOps Platform",
    "CRM": "CRM Platform",
    "HCM": "HCM Suite",
    "SCM": "Supply Chain Platform",
    "ANALYTICS": "Analytics Platform",
    "ERP": "ERP Suite",
}


def _generate_product_name(vendor_name, category):
    """Generate a product name for a vendor based on category."""
    known = _KNOWN_PRODUCT_NAMES.get(vendor_name, {})
    if category in known:
        return known[category]
    suffix = _CATEGORY_PRODUCT_SUFFIX.get(category, "Platform")
    return f"{vendor_name} {suffix}"


def _normalize_vendor_type(vendor_type):
    """Normalize vendor type to standard values."""
    if not vendor_type:
        return "software_vendor"
    vendor_type_upper = vendor_type.upper()
    if vendor_type_upper in ("SAAS", "SOFTWARE", "CLOUD_SERVICE"):
        return "software_vendor"
    if vendor_type_upper in ("MANAGED_SERVICE", "CONSULTING"):
        return "systems_integrator"
    return "software_vendor"


def seed_vendor_catalogue():
    if not DEV_FLAG:
        print("DEV: seed_vendor_catalogue() skipped (DEV_SEED_VENDOR_CATALOG not enabled)")
        return {"skipped": True, "vendors_created": 0, "products_created": 0}

    vendors_created = 0
    products_created = 0
    count_before = VendorOrganization.query.count()
    for entry in VENDOR_CATALOGUE:
        name = entry.get("name") or entry.get("vendor_name")
        if not name:
            continue
        exists = VendorOrganization.query.filter(VendorOrganization.name == name).first()
        if exists:
            continue
        vendor_type = entry.get("vendorType") or entry.get("vendor_type")
        headquarters = entry.get("headquarters") or entry.get("headquarters_location")
        website = entry.get("website")
        description = entry.get("description")
        founded = entry.get("founded") or entry.get("year_founded")
        public_company = entry.get("publicCompany", entry.get("public_company", True))

        vo = VendorOrganization(
            name=name,
            display_name=name,
            vendor_type=_normalize_vendor_type(vendor_type),
            headquarters_location=headquarters,
            website=website,
            description=description,
            year_founded=founded,
            public_company=bool(public_company) if public_company is not None else True,
        )
        db.session.add(vo)
        vendors_created += 1

        category = entry.get("category", "OTHER")
        product_name = _generate_product_name(name, category)
        domain = CATEGORY_TO_DOMAIN.get(category, "other")
        vp = VendorProduct(
            name=product_name,
            vendor_organization=vo,
            description=description or f"{name} {category} product",
        )
        db.session.add(vp)
        products_created += 1

    db.session.commit()
    count_after = VendorOrganization.query.count()
    print(f"DEV seed_vendor_catalogue: seeded {count_after - count_before} vendor(s)")
    return {"skipped": False, "vendors_created": vendors_created, "products_created": products_created}
