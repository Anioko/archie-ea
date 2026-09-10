"""Server-side error aggregation — the in-built telemetry answer to "how do
we know when the system has silently degraded?"

Before this, a WARNING/ERROR log record went to stdout and nowhere else.
`docker compose logs` was the only way to discover a route was 500-ing for
every caller, and that only happened when someone thought to look. This
attaches a ``logging.Handler`` to the root logger that turns every WARNING+
record app-wide into a deduplicated row in ``error_events`` (see
``app/models/error_event.py``), viewable at ``/admin/errors``.

Design constraints that shaped this:

* **Must never break the request it is reporting on.** A logging handler runs
  synchronously, inline, on the thread that just hit the error. If it raises,
  or if it uses the request's own (possibly poisoned/rolled-back) SQLAlchemy
  session, one exception becomes a cascading second one. So this opens its
  own short-lived connection via ``db.engine`` and wraps the entire body in a
  bare ``except Exception: pass`` — self-hosted telemetry that could itself
  take the site down would be worse than no telemetry.
* **Must not amplify a storm.** A misbehaving loop can emit thousands of
  identical WARNINGs in a second; without dedup that is a thousand-row insert
  storm on top of whatever is already failing. Fingerprinting + an UPSERT-style
  update means a repeating error is one row with a growing counter.
* **No paid/third-party telemetry** — ADR 0005's air-gap posture and the
  project's no-paid-infra constraint rule out Sentry/Rollbar/Datadog; this is
  the self-hosted equivalent of just enough of one.
"""

import hashlib
import logging

_EXCLUDED_LOGGERS = {
    # Its own logger: reporting a failure to report a failure is the
    # infinite-recursion case this module exists to avoid.
    "error_tracking",
    "csp_violations",  # already has its own sink (see routes.py _register_csp_report)
}


def _fingerprint(logger_name, message):
    # Deliberately coarse: strip nothing dynamic (ids, counts) out of message
    # here because that would need per-call-site knowledge this handler
    # doesn't have. logger_name + the first ~120 chars of the message is
    # enough to group "the same log line fired repeatedly" without trying to
    # be a full stack-trace-based fingerprinter server-side errors don't
    # reliably have (many app.logger.error calls have no traceback attached).
    basis = "%s:%s" % (logger_name, str(message)[:120])
    return hashlib.sha256(basis.encode("utf-8", "replace")).hexdigest()[:32]


class _ErrorAggregationHandler(logging.Handler):
    """Deduplicate WARNING+ log records into ``error_events``."""

    def __init__(self, app):
        super().__init__(level=logging.WARNING)
        self._app = app

    def emit(self, record):
        if record.name in _EXCLUDED_LOGGERS:
            return
        try:
            self._persist(record)
        except Exception:  # noqa: BLE001 — telemetry must never break the app
            pass

    def _persist(self, record):
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        fingerprint = _fingerprint(record.name, message)
        location = "%s:%s" % (record.module, record.lineno)
        stack = self.format(record) if record.exc_info else None

        from datetime import datetime

        from app import db
        from app.models.error_event import ErrorEvent

        with self._app.app_context():
            # A fresh, short-lived session-free connection: the request that
            # triggered this may have a rolled-back/poisoned session, and
            # reusing db.session here would inherit that state.
            conn = db.engine.connect()
            try:
                trans = conn.begin()
                table = ErrorEvent.__table__
                existing = conn.execute(
                    db.select(table.c.id, table.c.occurrence_count)
                    .where(table.c.fingerprint == fingerprint, table.c.resolved.is_(False))
                ).first()
                now = datetime.utcnow()
                if existing:
                    conn.execute(
                        table.update()
                        .where(table.c.id == existing.id)
                        .values(
                            occurrence_count=existing.occurrence_count + 1,
                            last_seen_at=now,
                            stack=stack if stack else table.c.stack,
                        )
                    )
                else:
                    conn.execute(
                        table.insert().values(
                            fingerprint=fingerprint,
                            source="server",
                            level=record.levelname,
                            message=message[:4000],
                            location=location,
                            stack=stack,
                            occurrence_count=1,
                            first_seen_at=now,
                            last_seen_at=now,
                            resolved=False,
                        )
                    )
                trans.commit()
            finally:
                conn.close()


def init_error_tracking(app):
    """Attach the aggregation handler to the root logger.

    Attached to the root logger (not just ``app.logger``) so it also catches
    warnings/errors from library loggers (``sqlalchemy``, ``werkzeug``, an
    LLM client) — the same "degraded but not crashed" signal the owner asked
    how to detect.
    """
    handler = _ErrorAggregationHandler(app)
    logging.getLogger().addHandler(handler)
    app.extensions["error_aggregation_handler"] = handler
