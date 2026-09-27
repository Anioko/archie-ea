"""TestAlertService.send_email_alert interpolated alert type/message/value/
threshold unescaped into an HTML email body. Found 11 Sep 2026 while
triaging the raw-html-escaping gate. Uses a mocked smtplib.SMTP to capture
the actual email content without sending anything.
"""
from unittest.mock import MagicMock, patch

from app.services.test_health_service import TestAlertService

MALICIOUS = '<img src=x onerror=alert(1)>'


def test_send_email_alert_escapes_alert_fields(monkeypatch):
    monkeypatch.setenv("TEST_ALERT_EMAILS", "ops@example.com")
    svc = TestAlertService()

    alert = {
        "type": MALICIOUS, "severity": "critical", "message": MALICIOUS,
        "value": MALICIOUS, "threshold": MALICIOUS,
    }

    sent_message = {}

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server

    def fake_sendmail(from_addr, to_addrs, msg_string):
        sent_message["body"] = msg_string

    mock_server.sendmail.side_effect = fake_sendmail

    with patch("smtplib.SMTP", return_value=mock_server):
        svc.send_email_alert(alert)

    assert "body" in sent_message, "sendmail was never called"
    full_message = sent_message["body"]
    # The plain-text part legitimately contains the raw payload (it isn't
    # HTML), so isolate the HTML part before asserting on escaping.
    html_part = full_message.split('Content-Type: text/html', 1)[1]
    assert MALICIOUS not in html_part
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_part
