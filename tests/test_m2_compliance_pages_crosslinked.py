"""M2: /procurement/compliance (License Compliance) and /dashboard/compliance
(Regulatory Compliance) are two intentionally distinct pages -- per this
finding's acceptance criteria they are NOT to be merged, only cross-linked
and clearly labelled. Both already had distinct <title> text; this pins the
new reciprocal links and the explicit "includes decommissioned" label on
/application-management/'s Total Applications tile (which otherwise silently
disagreed with /applications/'s default active-portfolio count).
"""


def test_license_compliance_links_to_regulatory_compliance(app):
    body = open(
        "app/modules/procurement/templates/procurement/compliance_dashboard.html",
        encoding="utf-8",
    ).read()
    assert "Regulatory Compliance" in body
    assert "application_mgmt.compliance_frameworks_dashboard" in body


def test_regulatory_compliance_links_to_license_compliance(app):
    body = open("app/templates/compliance/frameworks_dashboard.html", encoding="utf-8").read()
    assert "License Compliance" in body
    assert "procurement.compliance_dashboard" in body


def test_application_management_total_labels_decommissioned_inclusion(app):
    body = open("app/templates/applications/dashboard.html", encoding="utf-8").read()
    assert "Includes decommissioned applications" in body
    assert "unified_applications.application_list" in body
