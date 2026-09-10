"""Unresolved-error digest: read-only notification, not an autonomous fix.

Covers app/_bootstrap/_digest_emails.send_error_digest -- the watermark
mechanism (only new-since-last-run events are reported), the empty case
(no email attempted when nothing is new), and that resolved events never
appear. Uses the shared db_session fixture (tests/conftest.py) so nothing
here leaves residue in the persistent test database.
"""

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def _clean_watermark(db_session):
    from app.models.system_setting import SystemSetting
    from app._bootstrap._digest_emails import _ERROR_DIGEST_WATERMARK_KEY

    SystemSetting.query.filter_by(key=_ERROR_DIGEST_WATERMARK_KEY).delete()
    db_session.commit()
    yield
    SystemSetting.query.filter_by(key=_ERROR_DIGEST_WATERMARK_KEY).delete()
    db_session.commit()


@pytest.fixture
def _watermark_now(_clean_watermark):
    """Seed the watermark to "now", the realistic steady state in production
    (None only ever happens once, on a system's very first digest run).

    The shared test database accumulates ErrorEvent rows across every test/
    smoke run in this repo (server warnings logged during any app boot get
    captured too) with no cleanup -- a real gap, but not this test's to fix.
    Seeding the watermark scopes assertions to events created after it,
    exactly as send_error_digest's own filter does, instead of assuming an
    empty table that will never actually be empty here.
    """
    from app._bootstrap._digest_emails import _set_watermark
    _set_watermark(datetime.utcnow())


def _make_event(db_session, fingerprint, resolved=False, first_seen_at=None):
    from app.models.error_event import ErrorEvent

    now = first_seen_at or datetime.utcnow()
    e = ErrorEvent(
        fingerprint=fingerprint, source="server", level="ERROR",
        message="digest unit test %s" % fingerprint, location="test:1",
        occurrence_count=1, first_seen_at=now, last_seen_at=now,
        resolved=resolved,
    )
    db_session.add(e)
    db_session.commit()
    return e


def test_digest_reports_new_unresolved_events_and_advances_watermark(app, db_session, _clean_watermark):
    from app._bootstrap._digest_emails import send_error_digest

    with app.app_context():
        _make_event(db_session, "digest-unit-a")
        result = send_error_digest(app)
        assert result["new_events"] >= 1

        # Immediately re-running must not re-report the same event: the
        # watermark should have advanced past it.
        result2 = send_error_digest(app)
        from app.models.error_event import ErrorEvent
        still_there = ErrorEvent.query.filter_by(fingerprint="digest-unit-a").first()
        assert still_there is not None  # sanity: event itself wasn't touched
        # A second immediate run must not re-count an event whose
        # first_seen_at is at or before the watermark just set.
        from app._bootstrap._digest_emails import _get_watermark
        wm = _get_watermark()
        assert wm is not None
        assert still_there.first_seen_at <= wm


def test_digest_skips_resolved_events(app, db_session, _watermark_now):
    from app._bootstrap._digest_emails import send_error_digest

    with app.app_context():
        _make_event(db_session, "digest-unit-resolved", resolved=True)
        result = send_error_digest(app)
        # A resolved-only new event must not count as something to report.
        assert result["new_events"] == 0


def test_digest_noop_when_nothing_new(app, db_session, _watermark_now):
    from app._bootstrap._digest_emails import send_error_digest, _get_watermark

    with app.app_context():
        wm_before = _get_watermark()
        result = send_error_digest(app)
        assert result["new_events"] == 0
        # No email attempted -> no reason to have moved the watermark either.
        assert _get_watermark() == wm_before
