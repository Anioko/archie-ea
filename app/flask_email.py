import logging
import os
import smtplib

from flask import current_app, render_template
from flask_mail import Connection, Message

from app import create_app, mail

_log = logging.getLogger(__name__)


def mail_sender(app=None):
    """The From address account mail goes out under, or None when unset."""
    app = app or current_app
    return app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME") or None


def mail_available(app=None):
    """True when this server has somewhere to send mail and someone to send it as.

    ``MAIL_SERVER`` carries a default, so a server is always named; what an
    unconfigured install lacks is a sender. Every account flow asks this before
    it promises the user a message, so "no mail server" is said out loud rather
    than discovered when nothing arrives.
    """
    app = app or current_app
    return bool(app.config.get("MAIL_SERVER")) and bool(mail_sender(app))


class _BoundedConnection(Connection):
    """Flask-Mail's connection with a socket timeout on the SMTP session."""

    def configure_host(self):
        timeout = current_app.config.get("MAIL_TIMEOUT") or 15
        if self.mail.use_ssl:
            host = smtplib.SMTP_SSL(self.mail.server, self.mail.port, timeout=timeout)
        else:
            host = smtplib.SMTP(self.mail.server, self.mail.port, timeout=timeout)
        host.set_debuglevel(int(self.mail.debug))
        if self.mail.use_tls:
            host.starttls()
        if self.mail.username and self.mail.password:
            host.login(self.mail.username, self.mail.password)
        return host


def deliver_email(recipient, subject, template, **kwargs):
    """Render and send one message now, through the configured Flask-Mail settings.

    Returns ``(delivered, error)``. ``error`` is a short reason when the
    message did not go out, so the caller can tell the user what happened
    instead of assuming it arrived. Under TESTING, Flask-Mail suppresses the
    SMTP session and records the message instead (``mail.record_messages``).
    """
    app = current_app._get_current_object()
    if not mail_available(app):
        return False, "E-mail is not available on this server."
    try:
        msg = Message(
            app.config.get("EMAIL_SUBJECT_PREFIX", "") + " " + subject,
            sender=mail_sender(app),
            recipients=[recipient],
        )
        msg.body = render_template(template + ".txt", **kwargs)
        msg.html = render_template(template + ".html", **kwargs)
        with _BoundedConnection(app.extensions["mail"]) as conn:
            conn.send(msg)
        return True, None
    except Exception as exc:
        _log.error("account mail %r to recipient failed: %s", subject, exc, exc_info=True)
        return False, "The mail server did not accept the message ({}).".format(
            type(exc).__name__
        )


def send_email(recipient, subject, template, **kwargs):
    app = create_app(os.getenv("FLASK_CONFIG") or "default")
    with app.app_context():
        msg = Message(
            app.config["EMAIL_SUBJECT_PREFIX"] + " " + subject,
            sender=app.config["EMAIL_SENDER"],
            recipients=[recipient],
        )
        msg.body = render_template(template + ".txt", **kwargs)
        msg.html = render_template(template + ".html", **kwargs)
        mail.send(msg)
