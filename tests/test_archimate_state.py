"""As-is / to-be state on ArchiMate elements.

A transformation programme needs a baseline (as-is) and a target (to-be)
architecture. ArchiMateElement.plateau existed but no create/edit path ever wrote
it. `_apply_architecture_state` maps the form's `architecture_state` to plateau,
set-only so an unrelated edit can never silently clear it. These tests pin that.
"""

import pytest

from app.models.archimate_core import ArchiMateElement
from app.models.business_capabilities import BusinessCapability
from app.modules.architecture.routes.archimate_crud.routes import (
    _apply_architecture_state,
)


@pytest.mark.usefixtures("db_session")
def test_state_applies_to_linked_element(db_session, make_org, tenant_ctx):
    org = make_org("state")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Billing", organization_id=org.id, level=1)
        db_session.add(cap)
        db_session.commit()  # listener creates the linked ArchiMateElement
        _apply_architecture_state(cap, {"architecture_state": "Target"})
        db_session.commit()
        ae = db_session.get(ArchiMateElement, cap.archimate_element_id)
        assert ae.togaf_plateau == "Target"  # To-Be


@pytest.mark.usefixtures("db_session")
def test_state_applies_to_native_element(db_session, make_org, tenant_ctx):
    org = make_org("state")
    with tenant_ctx(org.id):
        ae = ArchiMateElement(name="Legacy CRM", type="ApplicationComponent",
                              layer="Application", organization_id=org.id)
        db_session.add(ae)
        db_session.commit()
        _apply_architecture_state(ae, {"architecture_state": "Baseline"})
        db_session.commit()
        assert db_session.get(ArchiMateElement, ae.id).togaf_plateau == "Baseline"  # As-Is


@pytest.mark.usefixtures("db_session")
def test_blank_or_unknown_state_never_clears(db_session, make_org, tenant_ctx):
    org = make_org("state")
    with tenant_ctx(org.id):
        ae = ArchiMateElement(name="X", type="Node", layer="Technology",
                              organization_id=org.id, togaf_plateau="Target")
        db_session.add(ae)
        db_session.commit()
        for payload in ({}, {"architecture_state": ""}, {"architecture_state": "bogus"}):
            _apply_architecture_state(ae, payload)
        db_session.commit()
        assert db_session.get(ArchiMateElement, ae.id).togaf_plateau == "Target"  # unchanged
