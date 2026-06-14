"""
Migration: Add Excel Template Fields to ApplicationComponent

Adds all missing fields from the Excel template (Uploads/Appliations Template.xlsx)
to the application_components table.
"""

import os
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db


def add_application_import_fields():
    """Add missing fields to application_components table"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")
    with app.app_context():
        print("\nAdding Excel Template Fields to application_components table")
        print("=" * 60)

        try:
            inspector = inspect(db.engine)

            table_name = "application_components"
            if table_name not in inspector.get_table_names():
                print(f"Table '{table_name}' does not exist. Skipping column additions.")
                return False

            current_columns = [col["name"] for col in inspector.get_columns(table_name)]
            print(f"Existing columns: {len(current_columns)}")

            # Fields to add (from Excel template)
            fields_to_add = [
                ("app_id", "VARCHAR(100) UNIQUE"),
                ("managed_type", "VARCHAR(100)"),
                ("access_mode", "VARCHAR(100)"),
                ("lifecycle_status", "VARCHAR(100)"),
                ("application_weight", "NUMERIC(10, 2)"),
                ("technology_status", "VARCHAR(100)"),
                ("vendor_maintenance_risk", "VARCHAR(100)"),
                ("cloud_suitability", "VARCHAR(100)"),
                ("major_program_impact", "VARCHAR(500)"),
                ("priority_for_action", "VARCHAR(100)"),
                ("time_destiny", "VARCHAR(100)"),
                ("deployment_scope", "VARCHAR(500)"),
                ("usage_frequency", "VARCHAR(100)"),
                ("functional_complexity", "VARCHAR(100)"),
                ("main_url", "TEXT"),
                ("user_satisfaction", "VARCHAR(100)"),
                ("hosting_environment", "VARCHAR(200)"),
                ("identity_provider", "VARCHAR(200)"),
                ("based_on", "VARCHAR(500)"),
                ("sgec_landing_zone", "VARCHAR(200)"),
                ("sgec_cloud_pattern", "VARCHAR(200)"),
                ("sg_data_center", "VARCHAR(200)"),
                ("sg_managed_platform", "VARCHAR(200)"),
                ("application_platform", "VARCHAR(200)"),
                ("other_hosting_details", "TEXT"),
                ("interfaces_description", "TEXT"),
                ("development_type", "VARCHAR(100)"),
                ("level_of_customization", "VARCHAR(100)"),
                ("development_provider", "VARCHAR(500)"),
                ("package_name", "VARCHAR(200)"),
                ("package_vendor", "VARCHAR(200)"),
                ("source_code_availability", "VARCHAR(100)"),
                ("technical_complexity", "VARCHAR(100)"),
                ("risk_level", "VARCHAR(100)"),
                ("availability_of_documentation", "VARCHAR(100)"),
                ("availability_of_knowledge", "VARCHAR(100)"),
                ("drp_status", "VARCHAR(100)"),
                ("support_hours", "VARCHAR(100)"),
                ("support_level", "VARCHAR(100)"),
                ("support_region", "VARCHAR(200)"),
                ("maintenance_provider", "VARCHAR(500)"),
                ("cost_currency", "VARCHAR(10)"),
                ("total_run_cost", "NUMERIC(15, 2)"),
                ("hardware_cost", "NUMERIC(15, 2)"),
                ("software_cost", "NUMERIC(15, 2)"),
                ("facilities_utilities_cost", "NUMERIC(15, 2)"),
                ("internal_labor_cost", "NUMERIC(15, 2)"),
                ("external_labor_cost", "NUMERIC(15, 2)"),
                ("external_services_cost", "NUMERIC(15, 2)"),
                ("internal_services_cost", "NUMERIC(15, 2)"),
                ("telecom_services_cost", "NUMERIC(15, 2)"),
                ("other_costs", "NUMERIC(15, 2)"),
                ("it_unit_managing_app", "VARCHAR(500)"),
                ("application_manager", "VARCHAR(500)"),
                ("app_business_owner", "VARCHAR(500)"),
                ("it_security_officer", "VARCHAR(500)"),
                ("business_security_officer", "VARCHAR(500)"),
                ("business_unit_owner", "VARCHAR(500)"),
                ("countries_where_used", "TEXT"),
                ("apps_portal_url", "TEXT"),
                ("psat_status", "VARCHAR(100)"),
                ("certified", "BOOLEAN DEFAULT FALSE"),
                ("risk_assessment_status", "VARCHAR(100)"),
                ("core_data_ok", "BOOLEAN DEFAULT FALSE"),
                ("operational_data_ok", "BOOLEAN DEFAULT FALSE"),
                ("data_quality_analysis", "TEXT"),
                ("certified_at", "DATE"),
                ("certified_by", "VARCHAR(500)"),
            ]

            added_count = 0
            for col_name, col_type in fields_to_add:
                if col_name not in current_columns:
                    try:
                        db.session.execute(
                            text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                        )
                        db.session.commit()
                        print(f"  Added column: {col_name}")
                        added_count += 1
                    except Exception as e:
                        db.session.rollback()
                        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                            print(f"  Column already exists: {col_name}")
                        else:
                            print(f"  Error adding column {col_name}: {e}")
                            current_columns = [
                                col["name"] for col in inspector.get_columns(table_name)
                            ]
                            if col_name not in current_columns:
                                raise
                else:
                    print(f"  Column already exists: {col_name}")

            if added_count > 0:
                print(f"\nAdded {added_count} columns to {table_name} table")

            # Add index on app_id if it was added
            if "app_id" in [f[0] for f in fields_to_add]:
                try:
                    db.session.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS idx_application_components_app_id ON application_components(app_id)"
                        )
                    )
                    db.session.commit()
                    print("Created index on app_id")
                except Exception as e:
                    print(f"Note: Index creation skipped: {e}")

            # Create application_import_history table if it doesn't exist
            print("\nCreating application_import_history table...")
            db.session.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS application_import_history (
                    id SERIAL PRIMARY KEY,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    imported_by_id INTEGER REFERENCES users(id),
                    imported_by_name VARCHAR(256),
                    import_source VARCHAR(50) NOT NULL,
                    file_name VARCHAR(500),
                    file_size INTEGER,
                    total_records INTEGER DEFAULT 0,
                    records_created INTEGER DEFAULT 0,
                    records_updated INTEGER DEFAULT 0,
                    records_skipped INTEGER DEFAULT 0,
                    records_failed INTEGER DEFAULT 0,
                    duplicate_mode VARCHAR(50),
                    import_settings TEXT,
                    status VARCHAR(50) DEFAULT 'completed',
                    error_summary TEXT,
                    error_details TEXT
                )
            """
                )
            )
            db.session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_import_history_imported_at ON application_import_history(imported_at)"
                )
            )
            db.session.commit()
            print("application_import_history table created/verified")

            print("\n============================================================")
            print("MIGRATION COMPLETE!")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"\nERROR during migration: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = add_application_import_fields()
    sys.exit(0 if success else 1)
