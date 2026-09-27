"""Capabilities must join the ArchiMate backbone on create.

BusinessCapability is an ArchiMate 3.2 *Capability* (Strategy layer) and the
platform's central concept, yet before 1 Sep 2026 no create path made an
ArchiMateElement for it — `archimate_element_id` stayed NULL and the "the field IS
the element" rule was false for capabilities. An `after_insert` listener now mirrors
every capability into a Strategy-layer Capability element. These tests pin that
invariant so it cannot silently regress.
"""

import pytest

from app.models.archimate_core import ArchiMateElement
from app.models.business_capabilities import BusinessCapability


@pytest.mark.usefixtures("db_session")
def test_creating_capability_creates_archimate_element(db_session, make_org, tenant_ctx):
    org = make_org("cap")
    with tenant_ctx(org.id):
        cap = BusinessCapability(name="Order Management", organization_id=org.id,
                                 description="Handles orders", level=1)
        db_session.add(cap)
        db_session.commit()

        assert cap.archimate_element_id is not None, \
            "capability create must attach an ArchiMate element"
        element = db_session.get(ArchiMateElement, cap.archimate_element_id)
        assert element is not None
        assert element.type == "Capability"
        assert element.layer == "Strategy"
        assert element.organization_id == org.id
        assert element.name == "Order Management"


@pytest.mark.usefixtures("db_session")
def test_long_capability_name_is_truncated_not_fatal(db_session, make_org, tenant_ctx):
    org = make_org("cap")
    long_name = "C" * 200  # BusinessCapability.name is String(256); element is String(100)
    with tenant_ctx(org.id):
        cap = BusinessCapability(name=long_name, organization_id=org.id, level=1)
        db_session.add(cap)
        db_session.commit()  # must not raise on the element insert

        element = db_session.get(ArchiMateElement, cap.archimate_element_id)
        assert element is not None
        assert len(element.name) <= 100
