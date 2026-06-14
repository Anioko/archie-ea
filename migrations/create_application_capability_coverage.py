"""
Direct SQL Migration for Application Capability Coverage Table

Creates the application_capability_coverage table for CockroachDB
since Flask-Migrate doesn't work with CockroachDB.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app import create_app, db


def create_application_capability_coverage_table():
    """Create the application_capability_coverage table directly via SQL"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")

    with app.app_context():
        print("\nCreating Application Capability Coverage Table")
        print("=" * 60)

        # SQL to create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS application_capability_coverage (
            id INT PRIMARY KEY,
            application_component_id INT NOT NULL,
            capability_id INT NOT NULL,
            support_level STRING DEFAULT 'partial',
            coverage_percentage INT DEFAULT 0,
            maturity_level INT DEFAULT 1,
            is_strategic BOOL DEFAULT FALSE,
            investment_priority STRING,
            start_date DATE,
            end_date DATE,
            is_active BOOL DEFAULT TRUE,
            notes STRING,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_capability
                FOREIGN KEY (capability_id)
                REFERENCES business_capability(id)
        );
        """

        # Add indexes for performance
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_app_cap_coverage_app_id ON application_capability_coverage(application_component_id);",
            "CREATE INDEX IF NOT EXISTS idx_app_cap_coverage_cap_id ON application_capability_coverage(capability_id);",
            "CREATE INDEX IF NOT EXISTS idx_app_cap_coverage_active ON application_capability_coverage(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_app_cap_coverage_strategic ON application_capability_coverage(is_strategic);",
        ]

        try:
            # Create the table
            print("Creating table...")
            db.session.execute(text(create_table_sql))

            # Create indexes
            print("Creating indexes...")
            for index_sql in create_indexes_sql:
                db.session.execute(text(index_sql))

            # Add updated_at trigger
            print("Adding updated_at trigger...")
            trigger_sql = """
            CREATE OR REPLACE TRIGGER update_application_capability_coverage_updated_at
            BEFORE UPDATE ON application_capability_coverage
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """

            # Try to create trigger (may fail if function doesn't exist)
            try:
                db.session.execute(text(trigger_sql))
                print("✅ Trigger created successfully")
            except Exception as e:
                print(f"⚠️ Trigger creation failed (function may not exist): {e}")
                print("   This is not critical - the table will work without the trigger")

            db.session.commit()

            # Verify table exists
            result = db.session.execute(
                text(
                    """
                SELECT COUNT(*) as table_exists
                FROM information_schema.tables
                WHERE table_name = 'application_capability_coverage'
            """
                )
            )

            table_exists = result.fetchone()[0] > 0

            if table_exists:
                print("✅ SUCCESS: application_capability_coverage table created")

                # Show table structure
                result = db.session.execute(
                    text(
                        """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'application_capability_coverage'
                    ORDER BY ordinal_position
                """
                    )
                )

                print("\n📋 Table Structure:")
                for row in result:
                    print(f"   - {row[0]}: {row[1]} (nullable: {row[2]}, default: {row[3]})")

                return True
            else:
                print("❌ ERROR: Table was not created")
                return False

        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            db.session.rollback()
            return False


def verify_table_functionality():
    """Verify the table works with the model"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")

    with app.app_context():
        try:
            from app.models.business_capabilities import ApplicationCapabilityCoverage

            # Test model instantiation
            print("\n🧪 Testing model functionality...")

            # Test creating a record
            test_mapping = ApplicationCapabilityCoverage(
                application_component_id=1,
                capability_id=1,
                support_level="full",
                coverage_percentage=80,
                maturity_level=3,
                is_strategic=True,
                investment_priority="high",
                notes="Test mapping created by migration script",
            )

            db.session.add(test_mapping)
            db.session.commit()

            # Test querying
            count = ApplicationCapabilityCoverage.query.count()
            print(f"✅ Model test successful: {count} records in table")

            # Clean up test record
            ApplicationCapabilityCoverage.query.delete()
            db.session.commit()

            return True

        except Exception as e:
            print(f"❌ Model test failed: {str(e)}")
            return False


if __name__ == "__main__":
    print("🚀 Application Capability Coverage Migration")
    print("   Direct SQL migration for CockroachDB compatibility")
    print()

    # Create the table
    success = create_application_capability_coverage_table()

    if success:
        # Verify functionality
        verify_success = verify_table_functionality()

        if verify_success:
            print("\n🎉 MIGRATION COMPLETE!")
            print("✅ Table created successfully")
            print("✅ Model functionality verified")
            print("✅ Ready for application-capability mapping")
            print("\n📝 Next steps:")
            print("   1. Run: python scripts/seed_application_capability_mappings.py")
            print("   2. Test: python scripts/analyze_capability_gaps.py")
        else:
            print("\n⚠️ MIGRATION PARTIALLY COMPLETE")
            print("✅ Table created")
            print("❌ Model functionality issues")
    else:
        print("\n❌ MIGRATION FAILED")
        print("   Check the error messages above")

    print("\n" + "=" * 60)
