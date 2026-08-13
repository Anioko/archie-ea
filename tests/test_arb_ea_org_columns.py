"""Phase A (Wave 4 Task 1): every ARB + EA-workflow model has a nullable,
indexed organization_id FK to organizations.id.

COLUMN ONLY — these models must NOT have TenantMixin yet (that's Phase B /
Task 3). Adding TenantMixin now would silently hide every existing NULL-org
row from every org before the backfill has run.
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


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_phase_a_models_do_not_yet_have_tenant_mixin(model):
    """Phase A is column-only. TenantMixin comes in Phase B (Task 3) after
    the backfill runs — adding it early would hide NULL-org rows."""
    assert not issubclass(model, TenantMixin), (
        f"{model.__name__} must NOT have TenantMixin yet (Phase A is column-only)"
    )
