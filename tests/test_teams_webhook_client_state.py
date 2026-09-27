"""
The Teams change-notification webhook's shared secret.

/api/webhooks/teams/notifications takes no authentication and is csrf-exempt by
necessity — Microsoft Graph cannot send a CSRF token. Driving all 1708 write
routes signed out, it is one of only eight that accept an anonymous request, and
the only one of those three webhooks whose route body contains no signature check
at all. The check exists, one layer down, in TeamsMeetingService.handle_notification.

That check compared against a literal:

    _CLIENT_STATE = "archie-teams-meeting-intelligence"

hardcoded in a public AGPL repository. The single value proving a notification
came from Graph was readable by anyone who could read the source, and the
`transcript_analysis` gate in front of it defaults to True, so it blocks nothing.
A forged notification passing that check reaches _process_call_record(), which
fetches a transcript for an attacker-chosen call id using the application's own
Graph credentials.

The secret is now derived from SECRET_KEY, so it differs per install, and compared
with hmac.compare_digest. These tests pin the properties that matter rather than
the derivation itself, which is free to change.
"""

import hashlib
import hmac
import os

import pytest

OLD_HARDCODED_SECRET = "archie-teams-meeting-intelligence"


@pytest.fixture(scope="module")
def app():
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    return application


def _client_state(app):
    from app.services.teams_meeting_service import _client_state

    with app.app_context():
        return _client_state()


class TestTheSecretIsNoLongerPublic:
    def test_the_old_hardcoded_value_is_gone_from_the_source(self):
        """Guard against it being reintroduced as a convenient default."""
        import inspect

        from app.services import teams_meeting_service

        source = inspect.getsource(teams_meeting_service)
        # The value may appear in prose explaining why it was removed; what must
        # never return is an assignment or comparison using it.
        import re as _re

        offenders = _re.findall(
            r"(?:=|==|!=)\s*[\"']" + _re.escape(OLD_HARDCODED_SECRET) + r"[\"']", source
        )
        assert not offenders, (
            f"the old hardcoded clientState is being assigned or compared again: {offenders}"
        )

    def test_derived_secret_is_not_the_old_one(self, app):
        assert _client_state(app) != OLD_HARDCODED_SECRET

    def test_secret_depends_on_secret_key(self, app):
        """Two installs with different SECRET_KEYs must not share a secret."""
        from app.services.teams_meeting_service import _client_state

        with app.app_context():
            app.config["SECRET_KEY"] = "install-one"
            first = _client_state()
            app.config["SECRET_KEY"] = "install-two"
            second = _client_state()
        assert first and second and first != second

    def test_explicit_override_wins(self, app, monkeypatch):
        monkeypatch.setenv("TEAMS_WEBHOOK_CLIENT_STATE", "explicitly-configured")
        assert _client_state(app) == "explicitly-configured"


class TestVerification:
    @staticmethod
    def _notify(payload_state):
        return {"value": [{"clientState": payload_state,
                           "resourceData": {"id": "call-123"}}]}

    def test_forged_notification_using_the_old_secret_is_rejected(self, app, monkeypatch):
        """The exact attack the hardcoded value enabled."""
        from app.services import teams_meeting_service as svc

        processed = []
        monkeypatch.setattr(svc.TeamsMeetingService, "get_config",
                            classmethod(lambda cls: {"transcript_analysis": True,
                                                     "signal_creation": True}))
        monkeypatch.setattr(svc.TeamsMeetingService, "_process_call_record",
                            classmethod(lambda cls, call_id, cfg: processed.append(call_id)))
        with app.app_context():
            svc.TeamsMeetingService.handle_notification(self._notify(OLD_HARDCODED_SECRET))
        assert processed == [], "a notification forged with the published secret was processed"

    def test_a_correct_notification_is_processed(self, app, monkeypatch):
        """The negative tests would pass trivially if nothing were ever processed."""
        from app.services import teams_meeting_service as svc

        processed = []
        monkeypatch.setattr(svc.TeamsMeetingService, "get_config",
                            classmethod(lambda cls: {"transcript_analysis": True,
                                                     "signal_creation": True}))
        monkeypatch.setattr(svc.TeamsMeetingService, "_process_call_record",
                            classmethod(lambda cls, call_id, cfg: processed.append(call_id)))
        with app.app_context():
            good = svc._client_state()
            svc.TeamsMeetingService.handle_notification(self._notify(good))
        assert processed == ["call-123"]

    @pytest.mark.parametrize("state", [None, "", "wrong", "archie", OLD_HARDCODED_SECRET])
    def test_bad_states_are_all_rejected(self, app, monkeypatch, state):
        from app.services import teams_meeting_service as svc

        processed = []
        monkeypatch.setattr(svc.TeamsMeetingService, "get_config",
                            classmethod(lambda cls: {"transcript_analysis": True,
                                                     "signal_creation": True}))
        monkeypatch.setattr(svc.TeamsMeetingService, "_process_call_record",
                            classmethod(lambda cls, call_id, cfg: processed.append(call_id)))
        with app.app_context():
            svc.TeamsMeetingService.handle_notification(self._notify(state))
        assert processed == []

    def test_fails_closed_with_no_secret_available(self, app, monkeypatch):
        """No configured secret must mean nothing is trusted, not everything."""
        from app.services import teams_meeting_service as svc

        processed = []
        monkeypatch.delenv("TEAMS_WEBHOOK_CLIENT_STATE", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setattr(svc.TeamsMeetingService, "get_config",
                            classmethod(lambda cls: {"transcript_analysis": True,
                                                     "signal_creation": True}))
        monkeypatch.setattr(svc.TeamsMeetingService, "_process_call_record",
                            classmethod(lambda cls, call_id, cfg: processed.append(call_id)))
        with app.app_context():
            app.config["SECRET_KEY"] = None
            svc.TeamsMeetingService.handle_notification(self._notify(""))
            svc.TeamsMeetingService.handle_notification(self._notify("anything"))
        assert processed == []


class TestSubscriptionAndVerificationAgree:
    def test_the_same_value_is_registered_and_checked(self, app):
        """If these diverged, every genuine notification would be silently dropped."""
        import inspect

        from app.services import teams_meeting_service as svc

        source = inspect.getsource(svc)
        assert '"clientState": _client_state()' in source, (
            "subscription creation must register the same secret verification expects"
        )
