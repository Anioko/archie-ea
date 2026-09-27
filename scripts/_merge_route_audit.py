"""Merge route_verification.json (overwritten each pytest run) into an accumulator file."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "route_verification.json"
ACCUM = REPO / "route_verification.accum.json"

run_data = set(json.loads(RUN.read_text())) if RUN.exists() else set()
accum_data = set(json.loads(ACCUM.read_text())) if ACCUM.exists() else set()
merged = sorted(run_data | accum_data)
ACCUM.write_text(json.dumps(merged, indent=0))
print(f"chunk exercised {len(run_data)}, accumulator now {len(merged)}")
