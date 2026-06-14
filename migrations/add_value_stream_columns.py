"""
Add missing columns to value_streams and value_stream_stages tables

This migration adds all missing columns to match the model definitions.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text

from app import create_app, db


def add_missing_columns():
    """Add missing columns to value_streams and value_stream_stages tables"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")

    with app.app_context():
        print("\nAdding missing columns to value_streams and value_stream_stages tables")
        print("=" * 60)

        try:
            inspector = inspect(db.engine)

            # Get existing columns for value_streams
            if "value_streams" in inspector.get_table_names():
                existing_cols = [col["name"] for col in inspector.get_columns("value_streams")]
                print(f"Existing value_streams columns: {len(existing_cols)}")

                # Columns to add (from model definition)
                columns_to_add = [
                    ("code", "VARCHAR(50)"),
                    ("stream_type", "VARCHAR(50)"),
                    ("value_category", "VARCHAR(100)"),
                    ("value_proposition", "TEXT"),
                    ("value_delivered", "TEXT"),
                    ("customer_segment", "VARCHAR(200)"),
                    ("stakeholder_value", "TEXT"),
                    ("competitive_differentiation", "BOOLEAN DEFAULT FALSE"),
                    ("trigger_event", "VARCHAR(255)"),
                    ("start_trigger", "VARCHAR(200)"),
                    ("end_condition", "VARCHAR(255)"),
                    ("end_outcome", "VARCHAR(200)"),
                    ("cycle_time_target_days", "FLOAT"),
                    ("cycle_time_actual_days", "FLOAT"),
                    ("cycle_time_days", "INTEGER"),
                    ("lead_time_days", "FLOAT"),
                    ("process_time_days", "FLOAT"),
                    ("throughput_per_month", "INTEGER"),
                    ("success_rate_percentage", "FLOAT"),
                    ("efficiency_percentage", "FLOAT"),
                    ("customer_satisfaction_score", "FLOAT"),
                    ("cost_per_instance", "NUMERIC(10, 2)"),
                    ("value_per_instance", "NUMERIC(10, 2)"),
                    ("annual_volume", "INTEGER"),
                    ("annual_revenue", "NUMERIC(15, 2)"),
                    ("annual_cost", "NUMERIC(15, 2)"),
                    ("total_annual_value", "NUMERIC(15, 2)"),
                    ("roi_percentage", "FLOAT"),
                    ("required_capability_ids", "TEXT"),
                    ("maturity_level", "VARCHAR(50)"),
                    ("primary_process_id", "INTEGER"),
                    ("supporting_process_ids", "TEXT"),
                    ("archimate_element_id", "INTEGER"),
                    ("archimate_layer", "VARCHAR(20) DEFAULT 'Strategy'"),
                    ("stream_owner_id", "INTEGER"),
                    ("owner_id", "INTEGER"),
                    ("review_frequency", "VARCHAR(20)"),
                    ("last_reviewed_date", "DATE"),
                    ("status", "VARCHAR(50)"),
                    ("is_active", "BOOLEAN DEFAULT TRUE"),
                    ("health_status", "VARCHAR(20)"),
                    ("improvement_initiatives", "TEXT"),
                    ("created_by_id", "INTEGER"),
                ]

                added_count = 0
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_cols:
                        try:
                            db.session.execute(
                                text(
                                    f"""
                                ALTER TABLE value_streams
                                ADD COLUMN {col_name} {col_type}
                            """
                                )
                            )
                            print(f"  Added column: {col_name}")
                            added_count += 1
                        except Exception as e:
                            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                                print(f"  Column already exists: {col_name}")
                            else:
                                print(f"  Error adding {col_name}: {str(e)[:100]}")

                if added_count > 0:
                    db.session.commit()
                    print(f"\nAdded {added_count} columns to value_streams table")
                else:
                    print("\nAll columns already exist in value_streams table")

            # Get existing columns for value_stream_stages
            if "value_stream_stages" in inspector.get_table_names():
                existing_cols = [
                    col["name"] for col in inspector.get_columns("value_stream_stages")
                ]
                print(f"\nExisting value_stream_stages columns: {len(existing_cols)}")

                # Columns to add (from model definition)
                columns_to_add = [
                    ("name", "VARCHAR(200) NOT NULL DEFAULT ''"),
                    ("description", "TEXT"),
                    ("sequence_order", "INTEGER NOT NULL DEFAULT 0"),
                    ("sequence", "INTEGER"),
                    ("duration_days", "INTEGER"),
                    ("wait_time_days", "FLOAT"),
                    ("automation_percentage", "FLOAT"),
                    ("error_rate_percentage", "FLOAT"),
                    ("rework_percentage", "FLOAT"),
                    ("trigger_event", "VARCHAR(500)"),
                    ("expected_outcome", "VARCHAR(500)"),
                    ("process_id", "INTEGER"),
                    ("capability_id", "INTEGER"),
                    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                    ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ]

                added_count = 0
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_cols:
                        try:
                            db.session.execute(
                                text(
                                    f"""
                                ALTER TABLE value_stream_stages
                                ADD COLUMN {col_name} {col_type}
                            """
                                )
                            )
                            print(f"  Added column: {col_name}")
                            added_count += 1
                        except Exception as e:
                            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                                print(f"  Column already exists: {col_name}")
                            else:
                                print(f"  Error adding {col_name}: {str(e)[:100]}")

                if added_count > 0:
                    db.session.commit()
                    print(f"\nAdded {added_count} columns to value_stream_stages table")
                else:
                    print("\nAll columns already exist in value_stream_stages table")

            # Add indexes
            try:
                db.session.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_value_streams_code ON value_streams(code)")
                )
                db.session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_value_stream_stages_stream_id ON value_stream_stages(value_stream_id)"
                    )
                )
                db.session.commit()
                print("\nIndexes created/verified")
            except Exception as e:
                print(f"  Note on indexes: {str(e)[:100]}")

            print("\n" + "=" * 60)
            print("MIGRATION COMPLETE!")
            return True

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            import traceback

            traceback.print_exc()
            db.session.rollback()
            return False


if __name__ == "__main__":
    success = add_missing_columns()
    sys.exit(0 if success else 1)
