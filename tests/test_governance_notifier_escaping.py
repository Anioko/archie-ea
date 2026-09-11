"""GovernanceNotifier._email_digest interpolated finding title/severity,
source_label, and url unescaped into an HTML email digest. Found 11 Sep
2026 while triaging the raw-html-escaping gate -- finding titles come from
AI governance analysis of real data (application/capability names), which
carries no character restriction.
"""
from unittest.mock import MagicMock, patch

from app.modules.solutions_strategic.v2.services.governance_notifier import (
    GovernanceNotifier,
)

MALICIOUS = '<img src=x onerror=alert(1)>'


def test_email_digest_escapes_finding_fields(app, db_session, make_org):
    org = make_org("gov-notifier")
    with app.app_context():
        from app.models.user import User

        user = User(
            email="architect@example.com", first_name="A", last_name="B",
            organization_id=org.id, enterprise_role="enterprise_architect",
            confirmed=True,
        )
        user.password = "irrelevant"
        db_session.add(user)
        db_session.flush()

        from flask import g
        g.current_org_id = org.id

        flagged = [{"severity": "critical", "title": MALICIOUS}]

        captured = {}

        def _fake_send(app_, subject, recipients, html):
            captured["html"] = html
            return True

        with patch(
            "app._bootstrap._digest_emails._safe_send_email",
            side_effect=_fake_send,
        ):
            result = GovernanceNotifier._email_digest(MALICIOUS, flagged, MALICIOUS)

        assert result is True
        assert "html" in captured, "_safe_send_email was never called"
        assert MALICIOUS not in captured["html"]
        assert "&lt;img src=x onerror=alert(1)&gt;" in captured["html"]
