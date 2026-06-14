"""
flask seed-minimal-vendor-products

Create the minimum vendor organizations + products needed for E2E tests to pass:
  - SAP SE org + SAP S/4HANA 2025 product  (VT-02 — template auto-population)
  - Microsoft Corporation org + Microsoft Power Platform product  (MVT-04)
  - Amazon Web Services org + AWS Cloud Platform product  (VT-04 — non-ERP test)

Idempotent: skips any entry that already exists (matching on name).
Safe to run multiple times in production.
"""
import click
from flask.cli import with_appcontext

from app import db


_VENDOR_SEED = [
    {
        "org_name": "SAP SE",
        "org_type": "software_vendor",
        "product_name": "SAP S/4HANA 2025",
        "product_family": "ERP",
    },
    {
        "org_name": "Microsoft Corporation",
        "org_type": "software_vendor",
        "product_name": "Microsoft Power Platform",
        "product_family": "COLLABORATION",
    },
    {
        "org_name": "Amazon Web Services",
        "org_type": "cloud_provider",
        "product_name": "AWS Cloud Platform",
        "product_family": "CLOUD_PLATFORM",
    },
]


@click.command("seed-minimal-vendor-products")
@click.option("--dry-run", is_flag=True, help="Print what would be inserted without writing.")
@with_appcontext
def seed_minimal_vendor_products(dry_run: bool) -> None:
    """Create minimal vendor orgs + products needed for E2E tests (idempotent)."""
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct

    created_orgs = 0
    created_products = 0

    for entry in _VENDOR_SEED:
        org = VendorOrganization.query.filter(
            VendorOrganization.name == entry["org_name"]
        ).first()
        if org is None:
            if dry_run:
                click.echo(f"  [dry] Would create org: {entry['org_name']}")
            else:
                org = VendorOrganization(
                    name=entry["org_name"],
                    display_name=entry["org_name"],
                    vendor_type=entry["org_type"],
                )
                db.session.add(org)
                db.session.flush()
                created_orgs += 1
                click.echo(f"  Created org: {entry['org_name']} (id={org.id})")
        else:
            click.echo(f"  Existing org: {entry['org_name']} (id={org.id})")

        if dry_run:
            click.echo(f"  [dry] Would create product: {entry['product_name']}")
            continue

        product = VendorProduct.query.filter(
            VendorProduct.vendor_organization_id == org.id,
            VendorProduct.name == entry["product_name"],
        ).first()
        if product is None:
            product = VendorProduct(
                vendor_organization_id=org.id,
                name=entry["product_name"],
                product_family_name=entry["product_family"],
            )
            db.session.add(product)
            created_products += 1
            click.echo(f"  Created product: {entry['product_name']}")
        else:
            click.echo(f"  Existing product: {entry['product_name']}")

    if not dry_run:
        db.session.commit()
        click.echo(f"\nDone: {created_orgs} orgs created, {created_products} products created.")
    else:
        click.echo("\n[dry-run] No changes written.")
