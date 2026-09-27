"""DEF-037, Capgemini dry-run (pass 2): recording an ARB decision only
checked `current_user.can(Permission.GENERAL)` — the bar every non-viewer
account clears — so a Solution Architect with no board seat could decide any
submitted review. Fixed by requiring an ARB-decision-eligible enterprise_role
(arb_member/cto/enterprise_architect/platform_admin).
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_non_board_member_cannot_record_arb_decision(app, db_session, make_org, tenant_ctx):
    from app.models.architecture_review_board import ARBReviewItem
    from app.models.user import User
    from app.services.arb_governance_service import ARBDecisionError, ARBGovernanceService

    org = make_org("arb-decision-authz")
    with tenant_ctx(org.id):
        submitter = User(email=f"submitter-{org.id}@example.com", organization_id=org.id,
                          enterprise_role="solution_architect", confirmed=True)
        solution_architect = User(email=f"sa-{org.id}@example.com", organization_id=org.id,
                                   enterprise_role="solution_architect", confirmed=True)
        arb_member = User(email=f"arb-{org.id}@example.com", organization_id=org.id,
                           enterprise_role="arb_member", confirmed=True)
        db_session.add_all([submitter, solution_architect, arb_member])
        db_session.commit()

        item = ARBReviewItem(
            review_number=f"REV-TEST-{org.id}", title="Test review",
            review_type="architecture_change", status="submitted",
            submitter_id=submitter.id, organization_id=org.id,
        )
        db_session.add(item)
        db_session.commit()

        with app.app_context():
            service = ARBGovernanceService()

            # A solution architect with no board seat is refused.
            with pytest.raises(ARBDecisionError):
                service.record_decision(
                    review_item_id=item.id, decision="approved",
                    rationale="looks fine", decided_by_id=solution_architect.id,
                )
            reloaded = db_session.get(ARBReviewItem, item.id)
            assert reloaded.status == "submitted"
            assert reloaded.decision is None

            # An ARB member succeeds.
            result = service.record_decision(
                review_item_id=item.id, decision="approved",
                rationale="approved by board", decided_by_id=arb_member.id,
            )
            assert result.status == "approved"
            assert result.decided_by_id == arb_member.id
