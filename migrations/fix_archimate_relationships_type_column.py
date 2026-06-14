"""
Fix ArchiMate Relationships Table - Add Missing Type Column

Adds the missing 'type' column to archimate_relationships table.
This column is required for relationship type storage (composition, association, etc.)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text, inspect


def fix_archimate_relationships_type_column():
    """Add the missing 'type' column to archimate_relationships table"""
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    with app.app_context():
        print("\nFixing ArchiMate Relationships Table - Adding Type Column")
        print("=" * 60)
        
        try:
            # Check if table exists
            inspector = inspect(db.engine)
            if 'archimate_relationships' not in inspector.get_table_names():
                print("Table 'archimate_relationships' does not exist")
                return False
            
            # Get existing columns
            columns = [col['name'] for col in inspector.get_columns('archimate_relationships')]
            print(f"Existing columns: {columns}")
            
            # Add missing columns that the model expects
            columns_to_add = []
            
            if 'type' not in columns:
                columns_to_add.append(('type', 'VARCHAR(30)'))
            
            if 'source_id' not in columns:
                columns_to_add.append(('source_id', 'INT'))
            
            if 'target_id' not in columns:
                columns_to_add.append(('target_id', 'INT'))
            
            if 'architecture_id' not in columns:
                columns_to_add.append(('architecture_id', 'INT'))
            
            if not columns_to_add:
                print("All required columns already exist")
                return True
            
            print(f"Adding {len(columns_to_add)} missing column(s)...")
            for col_name, col_type in columns_to_add:
                print(f"  Adding column '{col_name}' ({col_type})...")
                try:
                    db.session.execute(text(f"""
                        ALTER TABLE archimate_relationships 
                        ADD COLUMN {col_name} {col_type}
                    """))
                except Exception as e:
                    # Column might already exist, check
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"    Column '{col_name}' already exists, skipping")
                    else:
                        raise
            
            # If source_id/target_id were added, copy data from source_element_id/target_element_id if they exist
            if 'source_id' in [c[0] for c in columns_to_add] and 'source_element_id' in columns:
                print("Copying data from source_element_id to source_id...")
                db.session.execute(text("""
                    UPDATE archimate_relationships 
                    SET source_id = source_element_id 
                    WHERE source_id IS NULL AND source_element_id IS NOT NULL
                """))
            
            if 'target_id' in [c[0] for c in columns_to_add] and 'target_element_id' in columns:
                print("Copying data from target_element_id to target_id...")
                db.session.execute(text("""
                    UPDATE archimate_relationships 
                    SET target_id = target_element_id 
                    WHERE target_id IS NULL AND target_element_id IS NOT NULL
                """))
            
            db.session.commit()
            print("Columns added successfully")
            
            # Verify the columns were added
            inspector = inspect(db.engine)
            columns_after = [col['name'] for col in inspector.get_columns('archimate_relationships')]
            required = ['type', 'source_id', 'target_id', 'architecture_id']
            missing = [c for c in required if c not in columns_after]
            if not missing:
                print(f"Verification successful. Columns now: {columns_after}")
                return True
            else:
                print(f"Some columns were not added: {missing}")
                return False
                
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False


if __name__ == '__main__':
    print("Fixing ArchiMate Relationships Table")
    print("   Adding missing 'type' column")
    print()
    
    success = fix_archimate_relationships_type_column()
    
    if success:
        print("\nMIGRATION COMPLETE!")
        print("'type' column added to archimate_relationships table")
        print("Create Element functionality should now work")
    else:
        print("\nMIGRATION FAILED")
        print("   Check the error messages above")
    
    print("\n" + "=" * 60)

