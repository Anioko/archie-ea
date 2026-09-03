"""DEF-055, Capgemini dry-run: /arb/sessions rendered "ARB Session" for
every session regardless of its real name — the template read
session.title, but ArchitectureReviewBoard's real column is `name`
(ARBReviewItem, the review-item model shown on the same page in "reviews"
mode, genuinely does have `title`). Every session's actual name was
silently discarded.
"""

from datetime import datetime, timedelta

import pytest


@pytest.mark.usefixtures("db_session")
def test_arb_sessions_list_shows_real_session_name(app, db_session, make_org, tenant_ctx):
    from app.models.architecture_review_board import ArchitectureReviewBoard
    from app.models.user import User

    org = make_org("def055-arb-session-name")
    with tenant_ctx(org.id):
        session_row = ArchitectureReviewBoard(
            name="ZZ-VERIFY Constellation ARB — SCADE retirement go/no-go",
            board_number=ArchitectureReviewBoard.generate_board_number(),
            scheduled_date=datetime.utcnow() + timedelta(days=7),
            organization_id=org.id,
        )
        db_session.add(session_row)
        user = User(email=f"def055-{org.id}@example.com", organization_id=org.id,
                    enterprise_role="enterprise_architect", confirmed=True)
        db_session.add(user)
        db_session.commit()

        from tests.test_ba_tenant_and_authz import _login
        c = app.test_client()
        with app.app_context():
            _login(c, user.id)
            resp = c.get("/arb/sessions")
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert "ZZ-VERIFY Constellation ARB" in html
