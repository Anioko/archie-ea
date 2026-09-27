"""Wave 4: every ARB + EA-workflow model has a nullable, indexed
organization_id FK to organizations.id (Phase A / Task 1).

Phase B (Task 3) then enabled TenantMixin on the 11 PER-TENANT models —
ARBReviewItem, ARBException, ARBBoardMember, ARBReviewComment,
ARBCapabilityImpact, ARBAuditLog, ARBDocument, EAWorkflowInstance,
EAWorkflowStepExecution, EAWorkflowSchedule, EAWorkflowNotification — after
the backfill (Task 2) had populated organization_id on every existing row.
The 3 GLOBAL-REFERENCE models — ARBGovernanceStandard, ARBWorkflowStage,
EAWorkflowDefinition — intentionally stay plain db.Model: they are shared
catalogs/templates, and TenantMixin would hide them from every org.
"""

import pytest

from app.models.architecture_review_board import (
    ARBAuditLog,
    ARBBoardMember,
    ARBCapabilityImpact,
    ARBException,
    ARBGovernanceStandard,
    ARBReviewComment,
    ARBReviewItem,
    ARBWorkflowStage,
)
from app.models.workflow_models import (
    EAWorkflowDefinition,
    EAWorkflowInstance,
    EAWorkflowNotification,
    EAWorkflowSchedule,
    EAWorkflowStepExecution,
)
from app.models.mixins import TenantMixin

try:
    from app.models.architecture_review_board import ARBDocument
except ImportError:
    ARBDocument = None

MODELS = [
    ARBReviewItem,
    ARBException,
    ARBWorkflowStage,
    ARBBoardMember,
    ARBReviewComment,
    ARBCapabilityImpact,
    ARBGovernanceStandard,
    ARBAuditLog,
    EAWorkflowDefinition,
    EAWorkflowInstance,
    EAWorkflowStepExecution,
    EAWorkflowSchedule,
    EAWorkflowNotification,
]
if ARBDocument is not None:
    MODELS.append(ARBDocument)


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_model_has_nullable_organization_id_fk(model):
    columns = model.__table__.columns
    assert "organization_id" in columns, f"{model.__name__} is missing organization_id"
    col = columns["organization_id"]
    assert col.nullable is True, f"{model.__name__}.organization_id must be nullable (Phase A)"
    fk_targets = {str(fk.target_fullname) for fk in col.foreign_keys}
    assert "organizations.id" in fk_targets, (
        f"{model.__name__}.organization_id must FK to organizations.id, got {fk_targets}"
    )


def test_arb_document_present_when_not_fast_init():
    """ARBDocument is conditionally defined (guarded by APP_FAST_INIT). When
    it IS defined in this test run, it must carry the same column."""
    if ARBDocument is None:
        pytest.skip("ARBDocument not defined under APP_FAST_INIT=1")
    columns = ARBDocument.__table__.columns
    assert "organization_id" in columns
    assert columns["organization_id"].nullable is True


PER_TENANT_MODELS = [
    ARBReviewItem,
    ARBException,
    ARBBoardMember,
    ARBReviewComment,
    ARBCapabilityImpact,
    ARBAuditLog,
    EAWorkflowInstance,
    EAWorkflowStepExecution,
    EAWorkflowSchedule,
    EAWorkflowNotification,
]
if ARBDocument is not None:
    PER_TENANT_MODELS.append(ARBDocument)

GLOBAL_REFERENCE_MODELS = [
    ARBGovernanceStandard,
    ARBWorkflowStage,
    EAWorkflowDefinition,
]


@pytest.mark.parametrize("model", PER_TENANT_MODELS, ids=lambda m: m.__name__)
def test_phase_b_per_tenant_models_have_tenant_mixin(model):
    """Phase B (Task 3): the 11 per-tenant models are TenantMixin — the
    backfill (Task 2) already populated organization_id on every row, so
    auto-filtering no longer hides pre-existing data."""
    assert issubclass(model, TenantMixin), (
        f"{model.__name__} must have TenantMixin (Phase B) — it is a per-tenant governance model"
    )


@pytest.mark.parametrize("model", GLOBAL_REFERENCE_MODELS, ids=lambda m: m.__name__)
def test_global_reference_models_do_not_have_tenant_mixin(model):
    """Global-reference catalogs/templates stay shared across every org —
    TenantMixin would silently hide them from every tenant."""
    assert not issubclass(model, TenantMixin), (
        f"{model.__name__} is global-reference data and must NOT have TenantMixin"
    )
