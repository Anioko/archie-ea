"""
Add architecture_id column to archimate_relationships table
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text

from app import create_app, db


def add_architecture_id_column():
    """Add architecture_id column to archimate_relationships table"""
    app = create_app(os.getenv("FLASK_CONFIG") or "default")

    with app.app_context():
        print("\nAdding architecture_id column to archimate_relationships table")
        print("=" * 60)

        try:
            inspector = inspect(db.engine)
            if "archimate_relationships" not in inspector.get_table_names():
                print("Table 'archimate_relationships' does not exist")
                return False

            columns = [col["name"] for col in inspector.get_columns("archimate_relationships")]
            print(f"Current columns: {columns}")

            if "architecture_id" in columns:
                print("Column 'architecture_id' already exists")
                return True

            print("Adding 'architecture_id' column...")
            db.session.execute(
                text(
                    """
                ALTER TABLE archimate_relationships
                ADD COLUMN architecture_id INTEGER
            """
                )
            )

            db.session.commit()
            print("Column 'architecture_id' added successfully")

            # Verify
            inspector = inspect(db.engine)
            columns_after = [
                col["name"] for col in inspector.get_columns("archimate_relationships")
            ]
            if "architecture_id" in columns_after:
                print(f"Verification successful. Columns now: {columns_after}")
                return True
            else:
                print("Column was not added properly")
                return False

        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback

            traceback.print_exc()
            db.session.rollback()
            return False


if __name__ == "__main__":
    success = add_architecture_id_column()

    if success:
        print("\nMIGRATION COMPLETE!")
        print("'architecture_id' column added to archimate_relationships table")
    else:
        print("\nMIGRATION FAILED")

    print("\n" + "=" * 60)
