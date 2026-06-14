"""Test ValueStream and ValueStreamStage models"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["FLASK_CONFIG"] = "default"

from sqlalchemy import inspect

from app import create_app, db
from app.models import ValueStream, ValueStreamStage

app = create_app("default")
app.app_context().push()

print("Testing ValueStream and ValueStreamStage models...")
print("=" * 60)

# Check if tables exist
inspector = inspect(db.engine)
tables = inspector.get_table_names()
print(f"value_streams in tables: {'value_streams' in tables}")
print(f"value_stream_stages in tables: {'value_stream_stages' in tables}")

# Try to query
try:
    count1 = ValueStream.query.count()
    print(f"ValueStream count: {count1}")
except Exception as e:
    print(f"ValueStream query error: {str(e)[:300]}")
    import traceback

    traceback.print_exc()

try:
    count2 = ValueStreamStage.query.count()
    print(f"ValueStreamStage count: {count2}")
except Exception as e:
    print(f"ValueStreamStage query error: {str(e)[:300]}")
    import traceback

    traceback.print_exc()

print("=" * 60)
