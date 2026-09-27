"""M4: /consolidation-list/ showed "Unknown" for a row whose application_id
points at a deleted ApplicationComponent (an orphaned FK) -- indistinguishable
from a real application that simply has no name, or any other data gap.

Fixed in ConsolidationListEntry.to_dict() (app/models/consolidation_list.py):
adds an explicit `application_orphaned` flag and a distinct placeholder name,
which the dashboard template now renders as a labelled "Orphaned" badge.
"""

from types import SimpleNamespace

import pytest


def test_to_dict_flags_orphaned_application_reference():
    """A real orphaned row (application_id pointing at a deleted
    ApplicationComponent) cannot be constructed through the ORM in this test
    DB -- a foreign-key constraint enforces it here, even though production
    has rows that predate the constraint (CLAUDE.md's schema-drift class of
    issue). Exercise ConsolidationListEntry.to_dict() directly against a
    stand-in with `.application = None`, the exact shape a real orphaned row
    produces once its relationship resolves to nothing.
    """
    from app.models.consolidation_list import ConsolidationListEntry

    fake_entry = SimpleNamespace(
        id=1,
        application_id=999_999_999,
        application=None,
        target_application_id=None,
        target_application=None,
        status="pending",
        source_group_id=None,
        source_group_name=None,
        source_type="duplicate_detection",
        recommended_action="retire",
        priority="medium",
        estimated_savings=None,
        savings_verified=False,
        migration_cost=None,
        migration_complexity=None,
        wave=None,
        target_date=None,
        notes=None,
        business_rationale=None,
        risk_assessment=None,
        regulatory_flags=None,
        data_disposition=None,
        assigned_to=None,
        roadmap_item_id=None,
        added_at=None,
    )

    data = ConsolidationListEntry.to_dict(fake_entry)
    assert data["application_orphaned"] is True
    assert data["application_name"] != "Unknown"
    assert "999999999" in data["application_name"]


@pytest.mark.usefixtures("db_session")
def test_to_dict_does_not_flag_a_real_application(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.consolidation_list import ConsolidationListEntry

    org = make_org("m4-real")
    with tenant_ctx(org.id):
        real_app = ApplicationComponent(name="Real App", organization_id=org.id)
        db_session.add(real_app)
        db_session.flush()

        entry = ConsolidationListEntry(application_id=real_app.id, recommended_action="retire")
        db_session.add(entry)
        db_session.commit()

        data = entry.to_dict()
        assert data["application_orphaned"] is False
        assert data["application_name"] == "Real App"
