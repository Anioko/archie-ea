# -*- coding: utf-8 -*-
"""Trigger salesforce-apex codegen via in-container test client (CSRF disabled, session set)."""
import json, sys
from manage import app
from app import db

SOL = int(sys.argv[1]) if len(sys.argv) > 1 else 11
app.config["WTF_CSRF_ENABLED"] = False
# neutralize the custom require_csrf validator for this in-container build harness
import app.utils.csrf_helper as _ch
_ch.validate_csrf = lambda *a, **k: True

with app.app_context():
    from app.models.user import User
    user = (User.query.filter_by(email="demo@archiedemo.com").first()
            or User.query.filter(User.email.ilike("%admin%")).first()
            or User.query.first())
    uid = user.id
    print("ACTING_AS", user.email, "id", uid)

c = app.test_client()
with c.session_transaction() as sess:
    sess["_user_id"] = str(uid)
    sess["_fresh"] = True

body = {"language": "salesforce-apex", "generation_mode": "deterministic",
        "generation_policy": "scaffold", "package_mode": "unmanaged"}
r = c.post(f"/solutions/{SOL}/codegen/generate", json=body, headers={"X-CSRFToken": "build-harness"})
print("STATUS", r.status_code)
try:
    data = r.get_json()
except Exception:
    print("NONJSON", r.data[:500]); sys.exit(1)
if data is None:
    print("NODATA", r.data[:500]); sys.exit(1)

files = data.get("generated_files") or data.get("files") or []
print("SUCCESS", data.get("success"), "NFILES", len(files), "QUALITY", data.get("quality_score"))
if not files:
    print("RESP", json.dumps(data)[:900]); sys.exit(0)

# persist the generated package to disk for inspection + demo
import os
outdir = f"/tmp/generated_sfdc_sol{SOL}"
os.makedirs(outdir, exist_ok=True)
paths = []
for f in files:
    if isinstance(f, dict):
        p = f.get("path"); content = f.get("content", "")
    else:
        p = f; content = ""
    paths.append(p)
    if p:
        fp = os.path.join(outdir, p.lstrip("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(content or "")
print("WROTE_TO", outdir)
print("ALL_PATHS:")
for p in paths:
    print("  ", p)
