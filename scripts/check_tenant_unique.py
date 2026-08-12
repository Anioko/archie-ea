#!/usr/bin/env python3
"""Find unique constraints on tenant-scoped tables that omit organization_id.

A column declared ``unique=True`` on a ``TenantMixin`` model is unique across
*every* organisation. Where the value is one the tenant authors — a vendor name,
a data-domain code, an ADR number, a Jira key — that turns it into a
first-come-first-served resource: the second organisation to record "SAP",
"CUST" or "AD-001" is refused, and the message it sees says only that the value
is taken. Nothing about the declaration looks wrong, which is why 60 of them
accumulated across 46 tables before anybody counted.

Two other gates nearly cover this and do not. ``raw_sql_tenancy`` reads SQL
strings, and these are ORM declarations. ``schema-drift`` compares the models to
the database, and both sides agreed — the constraint was wrong in both.

What is allowed, and why each is a judgement rather than a silence:

* anything in ``GLOBAL_BY_DESIGN`` in ``app/models/tenant_unique_registry.py``,
  which records a reason per entry — a login identity, a one-per-organisation
  rule, or a value generated from the primary key;
* a composite made only of foreign keys, which cannot collide across
  organisations because the rows it references cannot;
* ``unique=True`` on ``organization_id`` itself, which *is* a tenancy rule.

Adding a genuinely global identifier means adding it to ``GLOBAL_BY_DESIGN``
with the reason. That is the escape hatch, and it is reviewable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def scan():
    sys.path.insert(0, str(REPO))
    os.environ.setdefault("FLASK_ENV", "development")

    from sqlalchemy import UniqueConstraint

    from manage import app  # noqa: PLC0415 - booting the app is how we get the mappers

    findings = []
    with app.app_context():
        from app import db  # noqa: PLC0415
        from app.models.mixins import TenantMixin  # noqa: PLC0415
        from app.models.tenant_unique_registry import GLOBAL_BY_DESIGN  # noqa: PLC0415

        seen_tables = set()
        for mapper in db.Model.registry.mappers:
            cls = mapper.class_
            table = mapper.local_table
            if table is None:
                continue
            if not (issubclass(cls, TenantMixin) or "organization_id" in table.c):
                continue
            if table.name in seen_tables:
                continue
            seen_tables.add(table.name)

            def tenant_scoped_fk(column):
                """Does this column point at a table that is itself tenant-scoped?

                The safety of a composite rests entirely on this. A foreign key
                into a *tenant* table means two organisations reach different
                parents, so the pair cannot collide — which is what makes
                (architecture_model_id, adr_number) safe while a bare adr_number
                is not. A foreign key into a **global reference** table gives no
                such separation: (framework_id, code) would still be one code per
                framework across every organisation.
                """
                for fk in column.foreign_keys:
                    try:
                        target = fk.column.table
                    except Exception:  # noqa: BLE001 - unresolvable FK proves nothing
                        continue
                    if "organization_id" in target.c:
                        return True
                return False

            def allowed(columns, _table=table):
                if list(columns) == ["organization_id"]:
                    return True  # a one-per-organisation rule
                if "organization_id" in columns:
                    return True
                if len(columns) > 1 and any(
                    tenant_scoped_fk(_table.c[c]) for c in columns
                ):
                    return True
                return all((_table.name, c) in GLOBAL_BY_DESIGN for c in columns)

            for column in table.c:
                if column.primary_key or not column.unique:
                    continue
                if allowed([column.name]):
                    continue
                findings.append({
                    "table": table.name, "model": cls.__name__,
                    "columns": [column.name], "kind": "column",
                })

            for constraint in table.constraints:
                if not isinstance(constraint, UniqueConstraint):
                    continue
                names = [c.name for c in constraint.columns]
                if not names or set(names) == {"id"} or allowed(names):
                    continue
                findings.append({
                    "table": table.name, "model": cls.__name__,
                    "columns": names, "kind": "constraint",
                })

            for index in table.indexes:
                if not index.unique:
                    continue
                names = [c.name for c in index.columns]
                if allowed(names):
                    continue
                if len(names) == 1 and table.c[names[0]].unique:
                    continue  # already counted as a column
                findings.append({
                    "table": table.name, "model": cls.__name__,
                    "columns": names, "kind": "index",
                })

    return sorted(findings, key=lambda f: (f["table"], f["columns"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--count", action="store_true", help="print only the count")
    args = parser.parse_args()

    findings = scan()

    if args.count:
        print(len(findings))
        return 0
    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, indent=2))
    else:
        for f in findings:
            columns = ", ".join(f["columns"])
            print(
                f"{f['table']}({columns}) — unique across every organisation "
                f"[{f['model']}, {f['kind']}]"
            )
        print(f"\n{len(findings)} cross-tenant unique constraint(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
