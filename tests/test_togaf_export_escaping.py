"""TOGAFDeliverableExportService interpolated user-authored freeform text
(stakeholder name/concern, constraint key/value) directly into a ReportLab
Paragraph() string with no escaping. Found 11 Sep 2026 while triaging the
raw-html-escaping gate.

ReportLab's Paragraph text is parsed as a restricted XML-like markup
language (that's why <b> works). Unescaped '<'/'>'/'&' in freeform text
corrupts that markup -- verified here by capturing the actual string passed
to Paragraph() rather than asserting on PDF bytes (which are unreliable to
inspect directly: ReportLab tolerates malformed markup by silently mangling
the rendered text rather than raising, so a "must not crash" assertion does
not actually catch this regression -- confirmed by running this test against
the pre-fix code, which passed for the wrong reason).
"""
from unittest.mock import MagicMock, patch

from app.services.togaf_deliverable_export_service import (
    TOGAFDeliverableExportService,
)

MALICIOUS = "R&D <Lead> Stakeholder"


def test_export_vision_to_pdf_escapes_stakeholder_and_constraint_text():
    svc = TOGAFDeliverableExportService()
    vision_doc = MagicMock()
    vision_doc.title = "Test Vision"
    vision_doc.scope_summary = None
    vision_doc.stakeholder_concerns = [{"name": MALICIOUS, "concern": MALICIOUS}]
    vision_doc.business_goals = []
    vision_doc.architecture_principles = []
    vision_doc.constraints = {MALICIOUS: MALICIOUS}
    vision_doc.assumptions = []
    vision_doc.risks = []

    captured_texts = []

    def fake_paragraph(text, *args, **kwargs):
        captured_texts.append(text)
        return MagicMock()

    with patch(
        "app.services.togaf_deliverable_export_service.Paragraph",
        side_effect=fake_paragraph,
    ):
        svc.export_vision_to_pdf(vision_doc)

    assert any("&amp;D &lt;Lead&gt;" in t for t in captured_texts), (
        "expected an escaped occurrence of the malicious stakeholder/constraint "
        "text somewhere in the Paragraph() calls; got: %r" % captured_texts
    )
    # And the raw, unescaped payload must never reach Paragraph().
    assert not any(MALICIOUS in t for t in captured_texts)
