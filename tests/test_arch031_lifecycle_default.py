"""ARCH-031: an application created with only a name must not get a fabricated
"operational" lifecycle_status, and unset lifecycle should never render a
green badge.
"""
from __future__ import annotations


def test_new_application_lifecycle_status_defaults_to_none(db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent

    org = make_org("arch031")

    with tenant_ctx(org.id):
        app = ApplicationComponent(name="Bare Minimum App", organization_id=org.id)
        db_session.add(app)
        db_session.flush()

        assert app.lifecycle_status is None, (
            "ARCH-031: lifecycle_status must default to None (unassessed), "
            "not a fabricated 'operational' value."
        )


def test_status_map_renders_not_set_for_null_lifecycle():
    """The list_simple.html STATUS_MAP fallback for a null lifecycle_status
    (and null deployment_status) must be 'Not set', never 'planned' (a real,
    distinct status value it used to fabricate) nor a green badge class."""
    import re

    template_path = "app/templates/applications/list_simple.html"
    with open(template_path, encoding="utf-8") as f:
        content = f.read()

    # The old fabricated fallback must be gone.
    assert "or app.deployment_status or 'planned').lower()" not in content

    # Both render sites must fall back to the neutral "Not set" label.
    matches = re.findall(r"or app\.deployment_status or '([^']*)'", content)
    not_set_labels = [m for m in matches if m == "Not set"]
    assert len(not_set_labels) >= 2, (
        "Expected at least 2 occurrences (desktop table + mobile cards) of the "
        "'Not set' fallback label for null lifecycle/deployment status."
    )
