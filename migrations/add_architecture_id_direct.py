"""
Add architecture_id column to archimate_relationships table - Direct SQL approach
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

# Get database URL from environment
db_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
if not db_url:
    # Construct from individual components
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "flask_base")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}"

print(f"Connecting to database...")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("\nAdding architecture_id column to archimate_relationships table")
    print("=" * 60)

    try:
        inspector = inspect(engine)
        if "archimate_relationships" not in inspector.get_table_names():
            print("Table 'archimate_relationships' does not exist")
            exit(1)

        columns = [col["name"] for col in inspector.get_columns("archimate_relationships")]
        print(f"Current columns: {columns}")

        if "architecture_id" in columns:
            print("Column 'architecture_id' already exists")
            exit(0)

        print("Adding 'architecture_id' column...")
        conn.execute(
            text(
                """
            ALTER TABLE archimate_relationships
            ADD COLUMN architecture_id INTEGER
        """
            )
        )
        conn.commit()
        print("Column 'architecture_id' added successfully")

        # Verify
        inspector = inspect(engine)
        columns_after = [col["name"] for col in inspector.get_columns("archimate_relationships")]
        if "architecture_id" in columns_after:
            print(f"Verification successful. Columns now: {columns_after}")
            print("\nMIGRATION COMPLETE!")
        else:
            print("Column was not added properly")
            exit(1)

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        conn.rollback()
        exit(1)

print("\n" + "=" * 60)
