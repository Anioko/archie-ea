"""
flask seed-sap-products

Expands the "SAP SE" vendor organization from a single generic product record
into the real SAP S/4HANA transformation-era product portfolio, so Application
and Capability views can score against it.

Source: Capgemini SAP S/4HANA Platform Suitability Assessment (10 Sep 2026),
Stage 1 recommendation 5.2/7.1 — the SAP vendor record carried zero associated
products.

No cost/pricing/rating figures are set here — those fields stay NULL and
render as em dash in the UI per the no-fabricated-data rule. Only real,
publicly-known SAP product names and classifications are seeded.

Idempotent: skips any product that already exists (matching on vendor + name).
Safe to run multiple times, including in production.
"""
import click
from flask.cli import with_appcontext

from app import db

_SAP_ORG = {
    "org_name": "SAP SE",
    "org_type": "software_vendor",
}

_SAP_PRODUCTS = [
    {
        "name": "SAP S/4HANA Cloud",
        "product_family": "ERP",
        "deployment_model": "cloud",
        "product_type": "suite",
    },
    {
        "name": "SAP S/4HANA On-Premise",
        "product_family": "ERP",
        "deployment_model": "on_premise",
        "product_type": "suite",
    },
    {
        "name": "SAP Business Technology Platform",
        "product_family": "PLATFORM",
        "deployment_model": "cloud",
        "product_type": "platform",
    },
    {
        "name": "SAP Signavio Process Navigator",
        "product_family": "PROCESS_MINING",
        "deployment_model": "cloud",
        "product_type": "application",
    },
    {
        "name": "SAP SuccessFactors",
        "product_family": "HCM",
        "deployment_model": "cloud",
        "product_type": "suite",
    },
    {
        "name": "SAP Ariba",
        "product_family": "PROCUREMENT",
        "deployment_model": "cloud",
        "product_type": "suite",
    },
    {
        "name": "SAP Concur",
        "product_family": "TRAVEL_EXPENSE",
        "deployment_model": "cloud",
        "product_type": "application",
    },
    {
        "name": "SAP Analytics Cloud",
        "product_family": "ANALYTICS",
        "deployment_model": "cloud",
        "product_type": "application",
    },
    {
        "name": "SAP Fiori",
        "product_family": "UX",
        "deployment_model": "hybrid",
        "product_type": "application",
    },
]


@click.command("seed-sap-products")
@click.option("--dry-run", is_flag=True, help="Print what would be inserted without writing.")
@with_appcontext
def seed_sap_products(dry_run: bool) -> None:
    """Expand the SAP vendor record with the real product portfolio (idempotent)."""
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

    # Match against both the short "SAP" name (the pre-existing generic vendor
    # record this command is meant to expand) and "SAP SE" (in case a future
    # environment seeds under the full legal name), so this never creates a
    # second SAP vendor row alongside the real one — see ADR 0008.
    org = VendorOrganization.query.filter(
        VendorOrganization.name.in_(["SAP", _SAP_ORG["org_name"]])
    ).first()

    if org is None:
        if dry_run:
            click.echo(f"  [dry] Would create org: {_SAP_ORG['org_name']}")
        else:
            org = VendorOrganization(
                name=_SAP_ORG["org_name"],
                display_name=_SAP_ORG["org_name"],
                vendor_type=_SAP_ORG["org_type"],
            )
            db.session.add(org)
            db.session.flush()
            click.echo(f"  Created org: {_SAP_ORG['org_name']} (id={org.id})")
    else:
        click.echo(f"  Existing org: {_SAP_ORG['org_name']} (id={org.id})")

    created_products = 0

    for entry in _SAP_PRODUCTS:
        if dry_run:
            click.echo(f"  [dry] Would create product: {entry['name']}")
            continue

        product = VendorProduct.query.filter(
            VendorProduct.vendor_organization_id == org.id,
            VendorProduct.name == entry["name"],
        ).first()
        if product is None:
            product = VendorProduct(
                vendor_organization_id=org.id,
                name=entry["name"],
                product_family_name=entry["product_family"],
                deployment_model=entry["deployment_model"],
                product_type=entry["product_type"],
            )
            db.session.add(product)
            created_products += 1
            click.echo(f"  Created product: {entry['name']}")
        else:
            click.echo(f"  Existing product: {entry['name']}")

    if not dry_run:
        db.session.commit()
        click.echo(f"\nDone: {created_products} SAP products created.")
    else:
        click.echo("\n[dry-run] No changes written.")
