"""DEF-077, Capgemini dry-run: with no review items linked to a session,
"Draft agenda" always failed via an LLM round-trip whose response could
never be validated (nothing to summarise), surfacing the internal pipeline
message "LLM response contained no usable items after dropping invented
reviews" -- describing implementation, not the user's situation. Short-
circuits with a real, actionable reason before ever calling the LLM.
"""

import pytest


@pytest.mark.usefixtures("db_session")
def test_ai_agenda_with_no_review_items_gives_actionable_message(app, db_session, make_org, tenant_ctx):
    from app.models.architecture_review_board import ArchitectureReviewBoard
    from app.modules.architecture.services.arb_queue_ai_service import (
        ARBQueueAIError,
        generate_session_agenda,
    )
    from datetime import datetime, timedelta

    org = make_org("def077-arb-agenda")
    with tenant_ctx(org.id):
        session_row = ArchitectureReviewBoard(
            name="ZZ-VERIFY Empty Session",
            board_number=ArchitectureReviewBoard.generate_board_number(),
            scheduled_date=datetime.utcnow() + timedelta(days=7),
            organization_id=org.id,
        )
        db_session.add(session_row)
        db_session.commit()

        with app.app_context():
            with pytest.raises(ARBQueueAIError) as exc_info:
                generate_session_agenda(session_row)

            message = str(exc_info.value)
            assert "dropping invented reviews" not in message
            assert "no review items" in message.lower()
