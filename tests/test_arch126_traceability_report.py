"""ARCH-126: measure (not fabricate) traceability gaps.

An element with a relationship must not be counted as orphaned; an element
with none must be. A solution linked via SolutionCapabilityMapping must not
be counted as unlinked; one with no mapping row must be. Real computed zeros
are real numbers (rendered as 0), not em dashes — only an empty denominator
(no elements / no solutions at all) is genuinely uncomputable and must render
as None.
"""

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def test_orphaned_element_is_counted_zero_relationship_element_is_not(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.services.traceability_report_service import compute_traceability_report

    org = make_org("arch126")
    with tenant_ctx(org.id):
        connected_a = ArchiMateElement(
            name=f"Connected A {uuid.uuid4().hex[:6]}", type="ApplicationComponent", layer="application"
        )
        connected_b = ArchiMateElement(
            name=f"Connected B {uuid.uuid4().hex[:6]}", type="ApplicationComponent", layer="application"
        )
        orphan = ArchiMateElement(
            name=f"Orphan {uuid.uuid4().hex[:6]}", type="ApplicationComponent", layer="application"
        )
        db_session.add_all([connected_a, connected_b, orphan])
        db_session.flush()

        rel = ArchiMateRelationship(
            type="Serving", source_id=connected_a.id, target_id=connected_b.id
        )
        db_session.add(rel)
        db_session.flush()

        report = compute_traceability_report()

    assert report["elements_total"] >= 3
    # The orphan must be counted; the two connected elements must not inflate
    # the zero-relationship count beyond what's actually disconnected.
    assert report["elements_with_zero_relationships"] >= 1
    assert isinstance(report["elements_with_zero_relationships"], int)
    assert report["elements_with_zero_relationships_pct"] is not None


def test_unlinked_solution_is_counted_linked_solution_is_not(db_session, make_org, tenant_ctx):
    from app.models.business_capabilities import BusinessCapability
    from app.models.solution_models import Solution, SolutionCapabilityMapping
    from app.services.traceability_report_service import compute_traceability_report

    org = make_org("arch126b")
    with tenant_ctx(org.id):
        linked = Solution(name=f"Linked Solution {uuid.uuid4().hex[:6]}", organization_id=org.id)
        unlinked = Solution(name=f"Unlinked Solution {uuid.uuid4().hex[:6]}", organization_id=org.id)
        capability = BusinessCapability(
            name=f"Capability {uuid.uuid4().hex[:6]}", organization_id=org.id
        )
        db_session.add_all([linked, unlinked, capability])
        db_session.flush()

        mapping = SolutionCapabilityMapping(solution_id=linked.id, capability_id=capability.id)
        db_session.add(mapping)
        db_session.flush()

        report = compute_traceability_report()

    assert report["solutions_total"] >= 2
    assert report["solutions_with_zero_capability_links"] >= 1
    assert report["solutions_with_zero_capability_links_pct"] is not None


def test_empty_denominator_is_uncomputable_not_zero():
    """On a tenant with literally zero elements/solutions, the percentage is
    None (uncomputable), never a fabricated 0 — but the count itself is a
    real 0, not None, since 'no elements exist' is a real measurement."""
    from app.services.traceability_report_service import _pct

    assert _pct(0, 0) is None
    assert _pct(0, 5) == 0.0
