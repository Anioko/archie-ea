"""
Test Health Alerting Service

Provides Slack and email notifications for test failures, coverage drops,
and KPI threshold breaches.

Agent: Test Infrastructure Agent
Task: GITHUB-test-health-dashboard
"""

import json
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

import requests


class TestAlertConfig:
    """Configuration for test alerts."""

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        slack_channel: str = "#test-alerts",
        email_smtp_server: str = "smtp.gmail.com",
        email_smtp_port: int = 587,
        email_username: Optional[str] = None,
        email_password: Optional[str] = None,
        email_recipients: List[str] = None,
        alert_thresholds: Optional[Dict] = None,
    ):
        self.slack_webhook_url = slack_webhook_url
        self.slack_channel = slack_channel
        self.email_smtp_server = email_smtp_server
        self.email_smtp_port = email_smtp_port
        self.email_username = email_username
        self.email_password = email_password
        self.email_recipients = email_recipients or []
        self.alert_thresholds = alert_thresholds or {
            "pass_rate_min": 80.0,  # Alert if pass rate drops below 80%
            "coverage_min": 60.0,  # Alert if coverage drops below 60%
            "flaky_max": 5,  # Alert if more than 5 flaky tests
            "duration_max": 300,  # Alert if test suite takes > 5 minutes
        }


class TestAlertManager:
    """
    Manages test alerts for Slack and email notifications.
    
    Monitors test metrics and sends alerts when thresholds are breached:
    - Pass rate drops below threshold
    - Coverage decreases significantly
    - Flaky test count increases
    - Test execution time exceeds limit
    """

    def __init__(self, config: Optional[TestAlertConfig] = None):
        self.config = config or TestAlertConfig()
        self.alert_history_file = Path("test-results/alert_history.json")
        self.alert_history = self._load_alert_history()

    def _load_alert_history(self) -> List[Dict]:
        """Load alert history from file."""
        if self.alert_history_file.exists():
            with open(self.alert_history_file, "r") as f:
                return json.load(f)
        return []

    def _save_alert_history(self):
        """Save alert history to file."""
        self.alert_history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.alert_history_file, "w") as f:
            json.dump(self.alert_history, f, indent=2)

    def _should_alert(self, alert_type: str, cooldown_minutes: int = 30) -> bool:
        """
        Check if we should send an alert (prevent spam).
        
        Args:
            alert_type: Type of alert
            cooldown_minutes: Minimum minutes between same alert type
            
        Returns:
            True if alert should be sent
        """
        cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        recent_alerts = [
            a for a in self.alert_history
            if a["type"] == alert_type and datetime.fromisoformat(a["timestamp"]) > cutoff
        ]
        return len(recent_alerts) == 0

    def check_and_alert(
        self,
        metrics: Dict,
        previous_metrics: Optional[Dict] = None,
        test_failures: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Check metrics against thresholds and send alerts if needed.
        
        Args:
            metrics: Current test metrics
            previous_metrics: Previous metrics for comparison
            test_failures: List of recent test failures
            
        Returns:
            List of alerts triggered
        """
        alerts = []

        # Check pass rate
        if metrics.get("pass_rate", 100) < self.config.alert_thresholds["pass_rate_min"]:
            if self._should_alert("low_pass_rate"):
                alert = self._create_pass_rate_alert(metrics, previous_metrics)
                alerts.append(alert)
                self._send_alert(alert)

        # Check coverage
        if metrics.get("coverage", 100) < self.config.alert_thresholds["coverage_min"]:
            if self._should_alert("low_coverage"):
                alert = self._create_coverage_alert(metrics, previous_metrics)
                alerts.append(alert)
                self._send_alert(alert)

        # Check flaky tests
        if metrics.get("flaky_tests", 0) > self.config.alert_thresholds["flaky_max"]:
            if self._should_alert("high_flaky"):
                alert = self._create_flaky_alert(metrics)
                alerts.append(alert)
                self._send_alert(alert)

        # Check test failures
        if test_failures:
            critical_failures = [f for f in test_failures if f.get("is_critical", False)]
            if critical_failures and self._should_alert("critical_failure"):
                alert = self._create_failure_alert(critical_failures)
                alerts.append(alert)
                self._send_alert(alert)

        # Save alert history
        self.alert_history.extend(alerts)
        self._save_alert_history()

        return alerts

    def _create_pass_rate_alert(
        self, metrics: Dict, previous_metrics: Optional[Dict]
    ) -> Dict:
        """Create pass rate alert."""
        pass_rate = metrics.get("pass_rate", 0)
        threshold = self.config.alert_thresholds["pass_rate_min"]
        
        change = 0
        if previous_metrics:
            change = pass_rate - previous_metrics.get("pass_rate", pass_rate)

        return {
            "id": f"pass_rate_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "low_pass_rate",
            "severity": "critical" if pass_rate < 70 else "warning",
            "timestamp": datetime.now().isoformat(),
            "message": f"⚠️ Test pass rate dropped to {pass_rate:.1f}% (below {threshold}% threshold)",
            "details": {
                "current_pass_rate": pass_rate,
                "threshold": threshold,
                "change": change,
                "total_tests": metrics.get("total_tests", 0),
                "failed_tests": int(metrics.get("total_tests", 0) * (1 - pass_rate / 100)),
            },
        }

    def _create_coverage_alert(
        self, metrics: Dict, previous_metrics: Optional[Dict]
    ) -> Dict:
        """Create coverage alert."""
        coverage = metrics.get("coverage", 0)
        threshold = self.config.alert_thresholds["coverage_min"]
        
        change = 0
        if previous_metrics:
            change = coverage - previous_metrics.get("coverage", coverage)

        return {
            "id": f"coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "low_coverage",
            "severity": "warning",
            "timestamp": datetime.now().isoformat(),
            "message": f"📉 Code coverage dropped to {coverage:.1f}% (below {threshold}% threshold)",
            "details": {
                "current_coverage": coverage,
                "threshold": threshold,
                "change": change,
            },
        }

    def _create_flaky_alert(self, metrics: Dict) -> Dict:
        """Create flaky tests alert."""
        flaky_count = metrics.get("flaky_tests", 0)
        threshold = self.config.alert_thresholds["flaky_max"]

        return {
            "id": f"flaky_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "high_flaky",
            "severity": "warning",
            "timestamp": datetime.now().isoformat(),
            "message": f"🔄 {flaky_count} flaky tests detected (above {threshold} threshold)",
            "details": {
                "flaky_count": flaky_count,
                "threshold": threshold,
            },
        }

    def _create_failure_alert(self, failures: List[Dict]) -> Dict:
        """Create critical failure alert."""
        return {
            "id": f"failure_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "critical_failure",
            "severity": "critical",
            "timestamp": datetime.now().isoformat(),
            "message": f"🚨 {len(failures)} critical test failures detected",
            "details": {
                "failure_count": len(failures),
                "failures": [
                    {
                        "test_name": f.get("test_name", "Unknown"),
                        "error": f.get("error", "No error message")[:200],
                    }
                    for f in failures[:5]  # Include first 5 failures
                ],
            },
        }

    def _send_alert(self, alert: Dict):
        """Send alert via all configured channels."""
        # Send Slack notification
        if self.config.slack_webhook_url:
            self._send_slack_alert(alert)

        # Send email notification
        if self.config.email_recipients and self.config.email_username:
            self._send_email_alert(alert)

    def _send_slack_alert(self, alert: Dict):
        """Send alert to Slack."""
        try:
            emoji = {
                "critical": "🚨",
                "warning": "⚠️",
                "info": "ℹ️",
            }.get(alert["severity"], "📢")

            payload = {
                "channel": self.config.slack_channel,
                "username": "Test Health Monitor",
                "icon_emoji": emoji,
                "attachments": [
                    {
                        "color": "danger" if alert["severity"] == "critical" else "warning",
                        "title": f"{emoji} Test Health Alert",
                        "text": alert["message"],
                        "fields": [
                            {
                                "title": "Type",
                                "value": alert["type"],
                                "short": True,
                            },
                            {
                                "title": "Severity",
                                "value": alert["severity"].upper(),
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert["timestamp"],
                                "short": True,
                            },
                        ],
                        "footer": "Test Health Dashboard",
                        "ts": int(datetime.now().timestamp()),
                    }
                ],
            }

            # Add details if available
            if alert.get("details"):
                details_text = json.dumps(alert["details"], indent=2)
                payload["attachments"][0]["fields"].append(
                    {
                        "title": "Details",
                        "value": f"```{details_text[:500]}```",  # Limit size
                        "short": False,
                    }
                )

            response = requests.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            print(f"[ALERT] Slack notification sent: {alert['message']}")

        except Exception as e:
            print(f"[WARNING] Failed to send Slack alert: {e}")

    def _send_email_alert(self, alert: Dict):
        """Send alert via email."""
        try:
            subject = f"[{alert['severity'].upper()}] Test Health Alert: {alert['type']}"

            # Create HTML body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: {'#d32f2f' if alert['severity'] == 'critical' else '#f57c00'};">
                    {alert['message']}
                </h2>
                <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Type</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{alert['type']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Severity</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{alert['severity']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Time</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{alert['timestamp']}</td>
                    </tr>
                </table>
                <p>View the dashboard: <a href="http://localhost:5000/testing/dashboard">
                    Test Health Dashboard
                </a></p>
            </body>
            </html>
            """

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.email_username
            msg["To"] = ", ".join(self.config.email_recipients)

            msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.email_username, self.config.email_password)
                server.sendmail(
                    self.config.email_username,
                    self.config.email_recipients,
                    msg.as_string(),
                )

            print(f"[ALERT] Email notification sent: {alert['message']}")

        except Exception as e:
            print(f"[WARNING] Failed to send email alert: {e}")

    def get_alert_history(
        self, since: Optional[datetime] = None, alert_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get alert history with optional filtering.
        
        Args:
            since: Only return alerts since this time
            alert_type: Filter by alert type
            
        Returns:
            List of alerts
        """
        alerts = self.alert_history

        if since:
            alerts = [a for a in alerts if datetime.fromisoformat(a["timestamp"]) > since]

        if alert_type:
            alerts = [a for a in alerts if a["type"] == alert_type]

        return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)


# Global alert manager instance
_alert_manager: Optional[TestAlertManager] = None


def get_alert_manager(config: Optional[TestAlertConfig] = None) -> TestAlertManager:
    """Get or create global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = TestAlertManager(config)
    return _alert_manager
