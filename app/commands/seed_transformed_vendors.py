"""
Seed Transformed Vendors

Seeds the transformed vendor-product data into the existing vendor catalogue
using the established vendor seed pattern.

Run with: python manage.py seed-transformed-vendors
"""

import json

from app import create_app, db
from app.models.vendor.vendor_organization import VendorOrganization
from app.models.vendor.vendor_product import VendorProduct
from config import DevelopmentConfig


def seed_transformed_vendors():
    """Seed transformed vendors using existing vendor seed pattern."""
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Load transformed rich vendor data
            with open("app/seed_data/transformed_rich_vendor_seeds.json", "r") as f:
                transformed_vendors = json.load(f)

            # Check for existing vendors
            existing_count = VendorOrganization.query.count()
            if existing_count > 0:
                print(
                    f"⚠️  Found {existing_count} existing vendor organizations. Adding transformed vendors..."
                )

            # Seed vendor organizations and products
            vendors_created = 0
            products_created = 0

            for vendor_data in transformed_vendors:
                # Check if vendor organization already exists
                existing_vendor = VendorOrganization.query.filter_by(
                    name=vendor_data["name"]
                ).first()

                if existing_vendor:
                    print(f"  Updating existing vendor: {vendor_data['name']}")
                    vendor_org = existing_vendor
                else:
                    # Create new vendor organization
                    vendor_org = VendorOrganization(
                        name=vendor_data["name"],
                        vendor_type=vendor_data["vendorType"],
                        headquarters_location=vendor_data["headquarters"],
                        website=vendor_data["website"],
                    )
                    db.session.add(vendor_org)
                    db.session.flush()  # Get ID without committing
                    vendors_created += 1

                # Add or update vendor products
                for product_name, product_data in vendor_data["products"].items():
                    existing_product = VendorProduct.query.filter_by(
                        vendor_organization_id=vendor_org.id, name=product_name
                    ).first()

                    if existing_product:
                        print(f"    Updating existing product: {product_name}")
                        existing_product.product_category = product_data["category"]
                        existing_product.deployment_models = product_data["deploymentModel"]
                        existing_product.license_model = product_data["licenseModel"]
                        existing_product.apqc_process_mappings = product_data["apqcProcesses"]
                        existing_product.description = product_data["description"]
                        # Add capabilities if supported by model
                        if "capabilities" in product_data:
                            existing_product.capabilities = product_data["capabilities"]
                    else:
                        # Create new vendor product
                        product = VendorProduct(
                            vendor_organization_id=vendor_org.id,
                            name=product_name,
                            product_category=product_data["category"],
                            deployment_models=product_data["deploymentModel"],
                            license_model=product_data["licenseModel"],
                            apqc_process_mappings=product_data["apqcProcesses"],
                            description=product_data["description"],
                            target_market=product_data.get("targetMarket", "Enterprise"),
                            maturity_level=product_data.get("maturityLevel", "MANAGED"),
                        )
                        # Add capabilities if supported by model
                        if "capabilities" in product_data:
                            product.capabilities = product_data["capabilities"]
                        db.session.add(product)
                        products_created += 1

            db.session.commit()

            print("✅ Rich transformed vendors seeded successfully!")
            print(f"   - Vendor Organizations: {vendors_created} created/updated")
            print(f"   - Vendor Products: {products_created} created/updated")
            print(f"   - Total Vendors: {len(transformed_vendors)}")
            print(
                f"   - APQC Process Coverage: {len(set([p for v in transformed_vendors for p in v['apqcProcesses']]))} processes"
            )
            print(
                f"   - Total Capabilities: {len(set([c for v in transformed_vendors for c in v.get('capabilities', [])]))} capabilities"
            )

            # Show vendor type distribution
            vendor_types = {}
            for vendor in transformed_vendors:
                vtype = vendor["vendorType"]
                vendor_types[vtype] = vendor_types.get(vtype, 0) + 1

            print(f"\n📊 Vendor Type Distribution:")
            for vtype, count in vendor_types.items():
                print(f"   - {vtype}: {count}")

            # Show APQC coverage by level
            apqc_coverage = {}
            for vendor in transformed_vendors:
                for process in vendor["apqcProcesses"]:
                    level = process.split(".")[0]
                    apqc_coverage[level] = apqc_coverage.get(level, 0) + 1

            print(f"\n📈 APQC Coverage by Level:")
            for level in sorted(apqc_coverage.keys()):
                print(f"   - Level {level}: {apqc_coverage[level]} process mappings")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding transformed vendors: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_transformed_vendors()
