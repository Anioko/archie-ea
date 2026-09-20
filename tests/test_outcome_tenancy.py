"""Outcome must be tenant-scoped in both the normal-runtime and fast-init classes.

Live-reported-by-audit bug (not a fast-init-only trap like the rest of
docs/buckets/model-class-deduplication/): Outcome (app/models/models.py) had
no organization_id at all, in the class that runs in production every day.
Any authenticated user of any tenant could read every other tenant's
outcomes, and any Outcome created outside a request context (CLI, scheduler)
had no tenant to attach to. Fixed by adding TenantMixin to both the
normal-runtime class and its fast-init twin in motivation_extended.py, with
organization_id overridden nullable (reconcile-schema is ADD-only) --
same pattern as Principle. See app/commands/backfill_outcome_org.py for the
existing-database follow-up.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_outcome_is_tenant_scoped_in_normal_runtime():
    """The class that runs in production today must carry TenantMixin."""
    from app.models.models import Outcome
    from app.models.mixins import TenantMixin

    assert issubclass(Outcome, TenantMixin), (
        "Outcome must carry TenantMixin -- without it, every tenant's outcomes "
        "are readable by every other tenant, and nothing raises"
    )
    assert "organization_id" in Outcome.__table__.c


def test_outcome_is_tenant_scoped_under_fast_init():
    """The fast-init twin must match, so tenancy semantics don't diverge if
    the fast-init flag is ever set (see test_fast_init_model_tenancy.py for
    the sibling asymmetry bugs this same mechanism produced elsewhere)."""
    script = textwrap.dedent(
        """
        from app.models.motivation_extended import Outcome
        from app.models.mixins import TenantMixin

        assert issubclass(Outcome, TenantMixin), (
            "fast-init Outcome must carry TenantMixin"
        )
        assert "organization_id" in Outcome.__table__.c
        """
    )
    env = os.environ.copy()
    env["APP_FAST_INIT"] = "1"
    env["FLASK_CONFIG"] = "testing"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_outcome_organization_id_is_auto_set_on_insert(db_session, make_org, tenant_ctx):
    """The ORM event that makes TenantMixin actually work, not just the column."""
    from app.models.models import Outcome

    org = make_org("outcome-tenancy-insert")
    with tenant_ctx(org.id):
        outcome = Outcome(name="Reduce churn", kpi_metric="Churn rate")
        db_session.add(outcome)
        db_session.flush()
        assert outcome.organization_id == org.id, (
            "TenantMixin's before_flush hook must auto-set organization_id on "
            "insert; if this is None, the mixin isn't actually wired for this model"
        )


def test_outcome_select_is_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """The core invariant: org A must not see org B's outcomes."""
    from app.models.models import Outcome

    org_a, org_b = make_org("outcome-a"), make_org("outcome-b")

    with tenant_ctx(org_a.id):
        db_session.add(Outcome(name="A's outcome", kpi_metric="Revenue"))
        db_session.flush()

    with tenant_ctx(org_b.id):
        b_outcome = Outcome(name="B's outcome", kpi_metric="NPS")
        db_session.add(b_outcome)
        db_session.flush()
        b_outcome_id = b_outcome.id

    with tenant_ctx(org_a.id):
        visible_ids = {row.id for row in Outcome.query.all()}

    assert b_outcome_id not in visible_ids, (
        "TENANT LEAK: a query in org A's context returned org B's outcome. "
        "The do_orm_execute filter in app/middleware/tenant_isolation.py is not applying."
    )
