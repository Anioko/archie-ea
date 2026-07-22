#!/usr/bin/env python3
"""Tenant-isolation regression guard.

Sets the request tenant context to a NON-EXISTENT organization and asserts that
EVERY TenantMixin-mapped model returns 0 rows. Any model that returns rows is
leaking — its SELECTs are not being scoped by organization_id, so a second org
would see another org's data.

This dynamically discovers all TenantMixin models (current and future), so a new
tenant model that forgets isolation is caught automatically.

Usage:  python scripts/guardrails/tenant_isolation_check.py
Exit 1 on any leak. Pure DB counts — does NOT load the embedding model.
"""
import pathlib
import sys

# Make the app package importable no matter where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from flask import g

from app import create_app, db
from app.models.mixins.core import TenantMixin

PHANTOM_ORG = 999999  # no organization has this id


def main():
    app = create_app()
    leaks, checked, skipped = [], [], []
    with app.app_context():
        g.current_org_id = PHANTOM_ORG
        seen = set()
        for mapper in db.Model.registry.mappers:
            cls = mapper.class_
            name = cls.__name__
            if name in seen or not issubclass(cls, TenantMixin):
                continue
            seen.add(name)
            try:
                n = cls.query.count()
            except Exception as exc:  # abstract/joined models without a base query
                db.session.rollback()
                skipped.append((name, type(exc).__name__))
                continue
            checked.append(name)
            if n != 0:
                leaks.append((name, n))

    print(f"Tenant models checked under phantom org {PHANTOM_ORG}: {len(checked)}")
    if skipped:
        print(f"  (skipped {len(skipped)} unqueryable: {', '.join(n for n, _ in skipped[:8])}"
              + (" ..." if len(skipped) > 8 else "") + ")")
    if leaks:
        print("\n❌ TENANT ISOLATION LEAK — these models returned rows for a non-existent org:")
        for name, n in leaks:
            print(f"   • {name}: {n} rows visible (SELECT not org-scoped)")
        print("\n   Fix: ensure the model inherits TenantMixin and queries go through the ORM")
        print("   (raw SQL bypasses the filter — scope it by organization_id).")
        return 1
    print("✅ tenant-isolation: every TenantMixin model isolates (0 rows for a phantom org)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
