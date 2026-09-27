"""TestAlertManager._send_email_alert interpolated alert message/type/
severity/timestamp unescaped into an HTML email body. Found 11 Sep 2026
while triaging the raw-html-escaping gate. Uses a mocked smtplib.SMTP to
capture the actual email content without sending anything or requiring
real SMTP credentials.
"""
from unittest.mock import MagicMock, patch

from app.services.test_alert_service import TestAlertConfig, TestAlertManager

MALICIOUS = '<img src=x onerror=alert(1)>'


def test_send_email_alert_escapes_alert_fields():
    config = TestAlertConfig(
        email_username="ci@example.com",
        email_password="unused",
        email_recipients=["ops@example.com"],
    )
    manager = TestAlertManager(config)

    alert = {
        "type": MALICIOUS, "severity": "critical", "message": MALICIOUS,
        "timestamp": MALICIOUS,
    }

    sent_message = {}
    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    mock_server.sendmail.side_effect = lambda f, t, m: sent_message.update(body=m)

    with patch("smtplib.SMTP", return_value=mock_server):
        manager._send_email_alert(alert)

    assert "body" in sent_message, "sendmail was never called"
    full_message = sent_message["body"]
    # The Subject header legitimately contains the raw payload (it isn't
    # HTML), so isolate the HTML part before asserting on escaping.
    html_part = full_message.split('Content-Type: text/html', 1)[1]
    assert MALICIOUS not in html_part
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_part
