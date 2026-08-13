"""Tenant isolation for ARB governance + EA-workflow models (wave-4 Phase B).

Wave 3 found ARB review items and EA workflow instances visible across every
tenant — governance data with no ``organization_id`` predicate at all. Wave 4
Phase A added nullable ``organization_id`` columns and backfilled them from
each row's FK parent; this file proves Phase B (``TenantMixin`` on the 11
per-tenant models) actually closes the leak, following the pattern in
``tests/test_tenant_isolation.py``.

The 3 global-reference models (``ARBGovernanceStandard``, ``ARBWorkflowStage``,
``EAWorkflowDefinition``) intentionally do NOT get ``TenantMixin`` — they are
shared catalogs/templates. A test here asserts one of them stays visible to
both orgs, so a future accidental TenantMixin add on a global-reference model
is caught immediately.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id, label):
    from app.models.user import User
    import uuid

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"{label}-{suffix}@example.com",
        first_name="Test",
        last_name=label,
        organization_id=org_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_review_item(db_session, org_id, submitter, label):
    from app.models.architecture_review_board import ARBReviewItem
    import uuid

    item = ARBReviewItem(
        review_number=f"REV-TEST-{uuid.uuid4().hex[:10]}",
        title=f"Review owned by {label}",
        review_type="architecture",
        submitter_id=submitter.id,
        organization_id=org_id,
    )
    db_session.add(item)
    db_session.flush()
    return item


def _make_workflow_definition(db_session, label):
    """Global-reference row — no organization_id set, shared across orgs."""
    from app.models.workflow_models import EAWorkflowDefinition
    import uuid

    defn = EAWorkflowDefinition(
        workflow_code=f"WF-TEST-{uuid.uuid4().hex[:10]}",
        workflow_name=f"Definition for {label}",
        workflow_category="architecture",
        steps=[],
    )
    db_session.add(defn)
    db_session.flush()
    return defn


def _make_workflow_instance(db_session, org_id, definition, label):
    from app.models.workflow_models import EAWorkflowInstance
    import uuid

    instance = EAWorkflowInstance(
        instance_code=f"WFI-TEST-{uuid.uuid4().hex[:10]}",
        workflow_definition_id=definition.id,
        organization_id=org_id,
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def _make_governance_standard(db_session, label):
    """Global-reference row — shared config, not owned by any single org."""
    from app.models.architecture_review_board import ARBGovernanceStandard
    import uuid

    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:10]}",
        name=f"Standard for {label}",
    )
    db_session.add(standard)
    db_session.flush()
    return standard


# --------------------------------------------------------- ARB review items


def test_arb_review_items_are_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """The Wave-3 leak: an org-A request must not see org-B's ARB review items."""
    from app.models.architecture_review_board import ARBReviewItem

    org_a, org_b = make_org("arb-a"), make_org("arb-b")
    user_a = _make_user(db_session, org_a.id, "A")
    user_b = _make_user(db_session, org_b.id, "B")

    a_item = _make_review_item(db_session, org_a.id, user_a, "A")
    b_item = _make_review_item(db_session, org_b.id, user_b, "B")

    with tenant_ctx(org_a.id):
        visible = ARBReviewItem.query.all()
        visible_ids = {row.id for row in visible}

    assert a_item.id in visible_ids, "org A's own review item must be visible in its own context"
    assert b_item.id not in visible_ids, (
        "TENANT LEAK: org A's request returned org B's ARB review item — "
        "the exact governance-data leak Wave 3 found."
    )
    assert all(row.organization_id == org_a.id for row in visible)


def test_arb_review_item_by_id_not_reachable_cross_org(db_session, make_org, tenant_ctx):
    from app.models.architecture_review_board import ARBReviewItem

    org_a, org_b = make_org("arb-a2"), make_org("arb-b2")
    user_b = _make_user(db_session, org_b.id, "B")
    b_item = _make_review_item(db_session, org_b.id, user_b, "B")
    b_item_id = b_item.id

    db_session.expunge_all()

    with tenant_ctx(org_a.id):
        found = ARBReviewItem.query.filter_by(id=b_item_id).first()

    assert found is None, (
        f"TENANT LEAK: org A retrieved org B's ARB review item (id={b_item_id}) by id."
    )


# ---------------------------------------------------------- EA workflow instances


def test_ea_workflow_instances_are_scoped_to_current_org(db_session, make_org, tenant_ctx):
    """The Wave-3 leak, EA side: an org-A request must not see org-B's workflow instances."""
    from app.models.workflow_models import EAWorkflowInstance

    org_a, org_b = make_org("ea-a"), make_org("ea-b")
    definition = _make_workflow_definition(db_session, "shared")

    a_instance = _make_workflow_instance(db_session, org_a.id, definition, "A")
    b_instance = _make_workflow_instance(db_session, org_b.id, definition, "B")

    with tenant_ctx(org_a.id):
        visible = EAWorkflowInstance.query.all()
        visible_ids = {row.id for row in visible}

    assert a_instance.id in visible_ids, "org A's own workflow instance must be visible"
    assert b_instance.id not in visible_ids, (
        "TENANT LEAK: org A's request returned org B's EA workflow instance."
    )
    assert all(row.organization_id == org_a.id for row in visible)


def test_ea_workflow_instance_by_id_not_reachable_cross_org(db_session, make_org, tenant_ctx):
    from app.models.workflow_models import EAWorkflowInstance

    org_a, org_b = make_org("ea-a2"), make_org("ea-b2")
    definition = _make_workflow_definition(db_session, "shared2")
    b_instance = _make_workflow_instance(db_session, org_b.id, definition, "B")
    b_instance_id = b_instance.id

    db_session.expunge_all()

    with tenant_ctx(org_a.id):
        found = EAWorkflowInstance.query.filter_by(id=b_instance_id).first()

    assert found is None, (
        f"TENANT LEAK: org A retrieved org B's EA workflow instance (id={b_instance_id}) by id."
    )


# ---------------------------------------------------------- global-reference models


def test_global_reference_governance_standard_visible_to_both_orgs(db_session, make_org, tenant_ctx):
    """ARBGovernanceStandard is a shared catalog — TenantMixin would wrongly hide it."""
    from app.models.architecture_review_board import ARBGovernanceStandard

    org_a, org_b = make_org("std-a"), make_org("std-b")
    standard = _make_governance_standard(db_session, "shared")

    with tenant_ctx(org_a.id):
        seen_by_a = ARBGovernanceStandard.query.filter_by(id=standard.id).first()

    with tenant_ctx(org_b.id):
        seen_by_b = ARBGovernanceStandard.query.filter_by(id=standard.id).first()

    assert seen_by_a is not None, (
        "Global-reference ARBGovernanceStandard must remain visible to org A — "
        "it is shared config, not tenant data."
    )
    assert seen_by_b is not None, (
        "Global-reference ARBGovernanceStandard must remain visible to org B — "
        "it is shared config, not tenant data."
    )


def test_global_reference_workflow_definition_visible_to_both_orgs(db_session, make_org, tenant_ctx):
    """EAWorkflowDefinition is a shared template — TenantMixin would wrongly hide it."""
    from app.models.workflow_models import EAWorkflowDefinition

    org_a, org_b = make_org("def-a"), make_org("def-b")
    definition = _make_workflow_definition(db_session, "shared3")

    with tenant_ctx(org_a.id):
        seen_by_a = EAWorkflowDefinition.query.filter_by(id=definition.id).first()

    with tenant_ctx(org_b.id):
        seen_by_b = EAWorkflowDefinition.query.filter_by(id=definition.id).first()

    assert seen_by_a is not None
    assert seen_by_b is not None


# ------------------------------------------------- background-thread writes
#
# Wave-4 whole-branch review: `_run_workflow_in_background` and
# `resume_workflow` execute steps under a bare `self.app.app_context()` — an
# APP context, not a REQUEST context, so `g.current_org_id` is never set and
# TenantMixin's before_flush auto-set is a no-op. Rows created by
# `_execute_step` (EAWorkflowStepExecution) and `_handle_notification`
# (EAWorkflowNotification) would be born with organization_id=NULL and
# become invisible to their owning org once TenantMixin filtering is active.
# This test reproduces that exact call path — no tenant_ctx active — and
# must fail without the explicit `organization_id=instance.organization_id`
# stamps added to both creation sites in app/services/ea_workflow_engine.py.


def test_background_thread_step_execution_and_notification_stamp_org(
    db_session, make_org, tenant_ctx
):
    from app.models.workflow_models import (
        EAWorkflowInstance,
        EAWorkflowNotification,
        EAWorkflowStepExecution,
    )
    from app.services.ea_workflow_engine import EAWorkflowEngine

    org_a, org_b = make_org("bg-a"), make_org("bg-b")

    # Set up the instance the way `start_workflow` would — inside a request
    # context, so it is correctly born with org_a's organization_id.
    with tenant_ctx(org_a.id):
        definition = _make_workflow_definition(db_session, "bg-shared")
        instance = _make_workflow_instance(db_session, org_a.id, definition, "A")
        user_a = _make_user(db_session, org_a.id, "A")
        instance_id = instance.id
        user_a_id = user_a.id

    # Simulate `_run_workflow_in_background`: no tenant_ctx, no
    # g.current_org_id — only the bare app_context that db_session already
    # holds open, exactly like `with self.app.app_context():`.
    #
    # NOTE: `tenant_ctx` above uses `app.test_request_context()`, which does
    # NOT push a fresh AppContext when one for the same app is already
    # active (Flask reuses the current one) — and db_session's fixture holds
    # exactly such an AppContext open for the whole test. So `g` here is the
    # *same* g object `tenant_ctx` mutated, and `g.current_org_id` would
    # otherwise leak from org_a's block above even after that `with` exits.
    # Clear it explicitly so this really has no tenant context, matching
    # the background thread's fresh, empty `g`.
    from flask import g
    g.pop("current_org_id", None)
    assert not hasattr(g, "current_org_id") or g.current_org_id is None

    db_session.expunge_all()
    instance = db_session.get(EAWorkflowInstance, instance_id)
    assert instance is not None, "instance must be loadable outside any tenant context"

    engine = EAWorkflowEngine()
    step_def = {
        "step_id": "bg-notify-step",
        "step_name": "Background Notify",
        "step_type": "automated",
        "handler": "notification",
        "config": {"recipients": [user_a_id]},
    }
    result = engine._execute_step(instance, step_def, 0)
    assert result.get("status") == "completed", result

    step_exec = EAWorkflowStepExecution.query.filter_by(
        instance_id=instance_id, step_id="bg-notify-step"
    ).first()
    notif = EAWorkflowNotification.query.filter_by(
        workflow_instance_id=instance_id
    ).first()

    assert step_exec is not None, "background step execution must have been persisted"
    assert notif is not None, "background notification must have been persisted"

    assert step_exec.organization_id == org_a.id, (
        "TENANT LEAK: EAWorkflowStepExecution created in the background thread "
        f"has organization_id={step_exec.organization_id!r} instead of org_a "
        f"({org_a.id}) — it would be invisible to its owning org."
    )
    assert notif.organization_id == org_a.id, (
        "TENANT LEAK: EAWorkflowNotification created in the background thread "
        f"has organization_id={notif.organization_id!r} instead of org_a "
        f"({org_a.id}) — it would be invisible to its owning org."
    )

    # org_a's tenant context sees both background-created rows...
    with tenant_ctx(org_a.id):
        seen_step = EAWorkflowStepExecution.query.filter_by(
            instance_id=instance_id, step_id="bg-notify-step"
        ).first()
        seen_notif = EAWorkflowNotification.query.filter_by(
            workflow_instance_id=instance_id
        ).first()
    assert seen_step is not None, "org A must see its own background-created step execution"
    assert seen_notif is not None, "org A must see its own background-created notification"

    # ...org_b's does not.
    with tenant_ctx(org_b.id):
        hidden_step = EAWorkflowStepExecution.query.filter_by(
            instance_id=instance_id, step_id="bg-notify-step"
        ).first()
        hidden_notif = EAWorkflowNotification.query.filter_by(
            workflow_instance_id=instance_id
        ).first()
    assert hidden_step is None, (
        "TENANT LEAK: org B can see org A's background-created step execution."
    )
    assert hidden_notif is None, (
        "TENANT LEAK: org B can see org A's background-created notification."
    )
