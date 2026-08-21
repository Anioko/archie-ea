"""Browser-facing contract for the evidence-gated ARB submission journey."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _template(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_blueprint_submission_keeps_blockers_visible_and_links_only_canonical_success():
    template = _template("app/templates/solutions/partials/_blueprint_governance.html")

    assert 'data-testid="arb-evidence-dossier"' in template
    assert 'data-testid="arb-missing-evidence"' in template
    assert "submission.missingEvidence" in template
    assert "Try submission again" in template
    assert "submission.reviewItemId && submission.reviewNumber" in template
    assert "'/arb/reviews/' + submission.reviewItemId" in template
    assert "Platform.toast.success('Submitted to ARB')" not in template


def test_journey_submission_exposes_recovery_and_requires_canonical_review_identity():
    template = _template(
        "app/templates/architecture_assistant/journey_v2_steps/_step6_review.html"
    )

    assert 'data-testid="arb-evidence-dossier"' in template
    assert 'data-testid="arb-submission-error"' in template
    assert "arbSubmissionError.body.missing_evidence" in template
    assert "Try submission again" in template
    assert "arbSubmitResult.review_item_id && arbSubmitResult.review_number" in template
    assert "'/arb/reviews/' + arbSubmitResult.review_item_id" in template
    assert "review_number ? arbSubmitResult.review_number : '—'" not in template
