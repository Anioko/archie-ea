"""
Consulting Partner Seeder

Seeds consulting partners separately from technology vendors.
These are professional services firms that provide implementation,
strategy, and advisory services.

Run with: python manage.py seed-consulting-partners
"""

import json

from app import create_app, db
from app.models.consulting_partner import ConsultingPartner
from app.seed_data.consulting_partners import CONSULTING_PARTNERS
from config import DevelopmentConfig


def seed_consulting_partners():
    """Seed consulting partners from consulting_partners.py"""
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check for existing partners
            existing_count = ConsultingPartner.query.count()
            if existing_count > 0:
                print(
                    f"⚠️  Found {existing_count} existing consulting partners. Clearing and reseeding..."
                )
                ConsultingPartner.query.delete()
                db.session.commit()

            # Seed consulting partners
            partners_created = 0
            for partner_data in CONSULTING_PARTNERS:
                # Check if partner already exists
                existing_partner = ConsultingPartner.query.filter_by(
                    name=partner_data["name"]
                ).first()
                if existing_partner:
                    print(f"  Updating existing partner: {partner_data['name']}")
                    # Update existing partner
                    existing_partner.firm_type = partner_data["firm_type"]
                    existing_partner.headquarters_location = partner_data["headquarters_location"]
                    existing_partner.website = partner_data["website"]
                    existing_partner.market_position = partner_data["market_position"]
                    existing_partner.company_size = partner_data["company_size"]
                    existing_partner.founded_year = partner_data["founded_year"]
                    existing_partner.specialization = partner_data["specialization"]
                    existing_partner.apqc_expertise = partner_data["apqcExpertise"]
                    existing_partner.vendor_partners = partner_data["vendorPartners"]
                    existing_partner.geographic_coverage = partner_data["geographicCoverage"]
                    partners_created += 1
                else:
                    # Create new partner
                    partner = ConsultingPartner(
                        name=partner_data["name"],
                        firm_type=partner_data["firm_type"],
                        headquarters_location=partner_data["headquarters_location"],
                        website=partner_data["website"],
                        market_position=partner_data["market_position"],
                        company_size=partner_data["company_size"],
                        founded_year=partner_data["founded_year"],
                        specialization=partner_data["specialization"],
                        apqc_expertise=partner_data["apqcExpertise"],
                        vendor_partners=partner_data["vendorPartners"],
                        geographic_coverage=partner_data["geographicCoverage"],
                    )
                    db.session.add(partner)
                    partners_created += 1

            db.session.commit()

            print("✅ Consulting partners seeded successfully!")
            print(f"   - Total Partners: {partners_created}")
            print(f"   - Firm Types: CONSULTING, SYSTEM_INTEGRATOR")
            print(f"   - APQC Expertise: Strategic, Operational, Risk Management")
            print(f"   - Vendor Partnerships: SAP, Oracle, Microsoft, ServiceNow, Salesforce")

            # Show summary by firm type
            consulting_partners = ConsultingPartner.query.filter_by(firm_type="CONSULTING").count()
            system_integrators = ConsultingPartner.query.filter_by(
                firm_type="SYSTEM_INTEGRATOR"
            ).count()

            print(f"\n📊 Partner Summary:")
            print(f"   - Consulting Firms: {consulting_partners}")
            print(f"   - System Integrators: {system_integrators}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding consulting partners: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_consulting_partners()
