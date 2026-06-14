"""
Create ValueStream and ValueStreamStage tables

This migration creates the missing value_streams and value_stream_stages tables
that are required by the ValueStream and ValueStreamStage models.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text

from app import create_app, db


def create_value_stream_tables():
    """Create value_streams and value_stream_stages tables"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")

    with app.app_context():
        print("\nCreating ValueStream and ValueStreamStage tables")
        print("=" * 60)

        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()

            # Create value_streams table if it doesn't exist
            if "value_streams" not in existing_tables:
                print("Creating 'value_streams' table...")
                db.session.execute(
                    text(
                        """
                    CREATE TABLE value_streams (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        code VARCHAR(50) UNIQUE,
                        description TEXT,
                        stream_type VARCHAR(50),
                        value_category VARCHAR(100),
                        value_proposition TEXT,
                        value_delivered TEXT,
                        customer_segment VARCHAR(200),
                        stakeholder_value TEXT,
                        competitive_differentiation BOOLEAN DEFAULT FALSE,
                        trigger_event VARCHAR(255),
                        start_trigger VARCHAR(200),
                        end_condition VARCHAR(255),
                        end_outcome VARCHAR(200),
                        cycle_time_target_days FLOAT,
                        cycle_time_actual_days FLOAT,
                        cycle_time_days INTEGER,
                        lead_time_days FLOAT,
                        process_time_days FLOAT,
                        throughput_per_month INTEGER,
                        success_rate_percentage FLOAT,
                        efficiency_percentage FLOAT,
                        customer_satisfaction_score FLOAT,
                        cost_per_instance NUMERIC(10, 2),
                        value_per_instance NUMERIC(10, 2),
                        annual_volume INTEGER,
                        annual_revenue NUMERIC(15, 2),
                        annual_cost NUMERIC(15, 2),
                        total_annual_value NUMERIC(15, 2),
                        roi_percentage FLOAT,
                        required_capability_ids TEXT,
                        maturity_level VARCHAR(50),
                        primary_process_id INTEGER REFERENCES business_processes(id),
                        supporting_process_ids TEXT,
                        archimate_element_id INTEGER REFERENCES archimate_elements(id),
                        archimate_layer VARCHAR(20) DEFAULT 'Strategy',
                        stream_owner_id INTEGER REFERENCES business_actors(id),
                        owner_id INTEGER REFERENCES users(id),
                        review_frequency VARCHAR(20),
                        last_reviewed_date DATE,
                        status VARCHAR(50),
                        is_active BOOLEAN DEFAULT TRUE,
                        health_status VARCHAR(20),
                        improvement_initiatives TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by_id INTEGER REFERENCES users(id)
                    )
                """
                    )
                )
                db.session.execute(
                    text("CREATE INDEX idx_value_streams_name ON value_streams(name)")
                )
                db.session.execute(
                    text("CREATE INDEX idx_value_streams_code ON value_streams(code)")
                )
                db.session.commit()
                print("Table 'value_streams' created successfully")
            else:
                print("Table 'value_streams' already exists")

            # Create value_stream_stages table if it doesn't exist
            if "value_stream_stages" not in existing_tables:
                print("Creating 'value_stream_stages' table...")
                db.session.execute(
                    text(
                        """
                    CREATE TABLE value_stream_stages (
                        id SERIAL PRIMARY KEY,
                        value_stream_id INTEGER NOT NULL REFERENCES value_streams(id) ON DELETE CASCADE,
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        sequence_order INTEGER NOT NULL,
                        sequence INTEGER,
                        duration_days INTEGER,
                        wait_time_days FLOAT,
                        automation_percentage FLOAT,
                        error_rate_percentage FLOAT,
                        rework_percentage FLOAT,
                        trigger_event VARCHAR(500),
                        expected_outcome VARCHAR(500),
                        process_id INTEGER REFERENCES business_processes(id),
                        capability_id INTEGER REFERENCES business_capability(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                    )
                )
                db.session.execute(
                    text(
                        "CREATE INDEX idx_value_stream_stages_value_stream_id ON value_stream_stages(value_stream_id)"
                    )
                )
                db.session.commit()
                print("Table 'value_stream_stages' created successfully")
            else:
                print("Table 'value_stream_stages' already exists")

            # Verify tables were created
            inspector = inspect(db.engine)
            final_tables = inspector.get_table_names()

            if "value_streams" in final_tables and "value_stream_stages" in final_tables:
                print("\nVerification successful. Both tables are present.")
                return True
            else:
                missing = []
                if "value_streams" not in final_tables:
                    missing.append("value_streams")
                if "value_stream_stages" not in final_tables:
                    missing.append("value_stream_stages")
                print(f"\nSome tables are still missing: {missing}")
                return False

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            import traceback

            traceback.print_exc()
            db.session.rollback()
            return False


if __name__ == "__main__":
    print("Creating ValueStream and ValueStreamStage tables")
    print()

    success = create_value_stream_tables()

    if success:
        print("\nMIGRATION COMPLETE!")
        print("Tables 'value_streams' and 'value_stream_stages' are now available")
    else:
        print("\nMIGRATION FAILED")
        print("   Check the error messages above")

    print("\n" + "=" * 60)
