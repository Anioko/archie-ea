"""An identifier a tenant authors must not be unique across every tenant.

``unique=True`` on a ``TenantMixin`` model is unique platform-wide. Where the
value is one the tenant writes — a vendor name, a data-domain code, an ADR
number, a Jira key — that makes it first-come-first-served: the second
organisation to record "SAP", "CUST" or "AD-001" is refused, and the error it
sees says only that the value is taken.

Walking the SQLAlchemy mapper registry found **60** of these across 46 tables.
Twenty-four were real; the rest were composites anchored on a foreign key
(which cannot collide, because the row they point at is itself tenant-scoped),
one-per-organisation rules, values generated from the primary key, or the login
email. ``app/models/tenant_unique_registry.py`` records which is which and why.

Nothing existing could have caught them: ``raw_sql_tenancy`` reads SQL strings
and these are ORM declarations, and ``schema-drift`` compares models against the
database, where both sides agreed — the constraint was wrong in both. Two of the
three previously-known instances had already been "fixed" once, and
``value_streams.code``'s upgrade command dropped a constraint name that never
existed and reported success.

The behavioural test below is the one that matters: two organisations writing
the same value.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.tenant_unique_registry import GLOBAL_BY_DESIGN, SCOPE_PER_TENANT


# ---------------------------------------------------------------------------
# The declarations
# ---------------------------------------------------------------------------


def test_no_tenant_table_carries_a_platform_wide_unique_constraint(app):
    """The gate's own assertion, so a failure names the table in the test output."""
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/check_tenant_unique.py"],
        cwd=repo, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout[-2000:]


def test_every_scoped_column_actually_carries_the_per_tenant_constraint(app):
    """The registry and the models must not drift apart."""
    from app import db

    with app.app_context():
        tables = {
            mapper.local_table.name: mapper.local_table
            for mapper in db.Model.registry.mappers
            if mapper.local_table is not None
        }

        missing = []
        for table_name, column in SCOPE_PER_TENANT:
            table = tables.get(table_name)
            if table is None:
                missing.append(f"{table_name}: not mapped")
                continue
            if column not in table.c:
                missing.append(f"{table_name}.{column}: no such column")
                continue
            if table.c[column].unique:
                missing.append(f"{table_name}.{column}: still unique=True")
                continue
            # Either spelling counts. A table declared with extend_existing
            # cannot carry UniqueConstraint through __table_args__ — measured on
            # application_components, where they reached the Table not at all —
            # so those are declared as unique Index objects instead.
            scoped = any(
                {"organization_id", column} <= {c.name for c in constraint.columns}
                for constraint in table.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            ) or any(
                index.unique
                and {"organization_id", column} <= {c.name for c in index.columns}
                for index in table.indexes
            )
            if not scoped:
                missing.append(
                    f"{table_name}.{column}: no UniqueConstraint(organization_id, {column})"
                )

        assert not missing, "registry/model drift:\n  " + "\n  ".join(missing)


def test_every_global_exception_carries_a_reason():
    for key, reason in GLOBAL_BY_DESIGN.items():
        assert isinstance(reason, str) and len(reason) > 20, (
            f"{key} is exempted without a reason anybody can check"
        )


def test_the_registry_does_not_contradict_itself():
    overlap = set(SCOPE_PER_TENANT) & set(GLOBAL_BY_DESIGN)
    assert not overlap, f"listed as both tenant-scoped and global: {overlap}"


# ---------------------------------------------------------------------------
# The behaviour
# ---------------------------------------------------------------------------


def test_two_organisations_can_both_record_the_same_vendor(
    db_session, make_org, tenant_ctx
):
    """Every customer runs SAP. This was rejected outright."""
    from app.models.vendor_taxonomy import VendorTaxonomy

    name = f"SAP {uuid.uuid4().hex[:6]}"
    org_a = make_org(f"uniq-vendor-a-{uuid.uuid4().hex[:6]}")
    org_b = make_org(f"uniq-vendor-b-{uuid.uuid4().hex[:6]}")

    with tenant_ctx(org_a.id):
        db_session.add(VendorTaxonomy(canonical_name=name))
        db_session.commit()

    with tenant_ctx(org_b.id):
        db_session.add(VendorTaxonomy(canonical_name=name))
        db_session.commit()

        assert VendorTaxonomy.query.filter_by(canonical_name=name).count() == 1, (
            "each organisation should see exactly its own row"
        )


def test_two_organisations_can_both_use_the_same_data_domain_code(
    db_session, make_org, tenant_ctx
):
    """CUST, PROD, FIN, OPS — the codes in the column's own comment."""
    from app.models.process_data import DataDomain

    code = f"CUST{uuid.uuid4().hex[:4]}"
    name = f"Customer {uuid.uuid4().hex[:6]}"
    org_a = make_org(f"uniq-domain-a-{uuid.uuid4().hex[:6]}")
    org_b = make_org(f"uniq-domain-b-{uuid.uuid4().hex[:6]}")

    for org in (org_a, org_b):
        with tenant_ctx(org.id):
            db_session.add(DataDomain(name=name, code=code))
            db_session.commit()


def test_one_organisation_still_cannot_duplicate_its_own_value(
    db_session, make_org, tenant_ctx
):
    """Scoping the constraint must not remove it."""
    from sqlalchemy.exc import IntegrityError

    from app.models.vendor_taxonomy import VendorTaxonomy

    name = f"Duplicate {uuid.uuid4().hex[:6]}"
    org = make_org(f"uniq-dupe-{uuid.uuid4().hex[:6]}")

    with tenant_ctx(org.id):
        db_session.add(VendorTaxonomy(canonical_name=name))
        db_session.commit()

        db_session.add(VendorTaxonomy(canonical_name=name))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
