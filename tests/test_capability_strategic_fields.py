"""Capability create/edit must persist strategic importance and business value.

Both columns existed on BusinessCapability but no endpoint wrote them and no form
exposed them, so an architect could never record why a capability matters. These
tests pin the validation and persistence added to _apply_optional_capability_fields.
"""

import pytest

from app.models.business_capabilities import BusinessCapability
from app.modules.capabilities.routes.enterprise_crud_routes import (
    _apply_optional_capability_fields,
)


@pytest.mark.usefixtures("db_session")
def test_strategic_fields_persist(db_session, make_org, tenant_ctx):
    org = make_org("cap")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Pricing", organization_id=org.id, level=1)
        errors = _apply_optional_capability_fields(
            cap, {"strategic_importance": "Critical", "business_value": "9"}
        )
        assert errors == []
        assert cap.strategic_importance == "critical"  # normalised to lower-case
        assert cap.business_value == 9
        db_session.add(cap)
        db_session.commit()
        reloaded = db_session.get(BusinessCapability, cap.id)
        assert reloaded.strategic_importance == "critical"
        assert reloaded.business_value == 9


def test_strategic_fields_validation():
    cap = BusinessCapability(name="X")
    assert "Strategic importance must be critical, high, medium or low" in \
        _apply_optional_capability_fields(cap, {"strategic_importance": "urgent"})
    assert "Business value must be between 1 and 10" in \
        _apply_optional_capability_fields(cap, {"business_value": "50"})
    assert "Business value must be a number" in \
        _apply_optional_capability_fields(cap, {"business_value": "high"})


def test_strategic_fields_clearable():
    cap = BusinessCapability(name="X", strategic_importance="high", business_value=5)
    errors = _apply_optional_capability_fields(
        cap, {"strategic_importance": "", "business_value": ""}
    )
    assert errors == []
    assert cap.strategic_importance is None
    assert cap.business_value is None
