"""Admin password reconciliation (OPS-003).

The platform has ONE shared admin account (config ``ADMIN_EMAIL``). Across a
multi-agent / multi-script estate, E2E suites and audit scripts log in as that
account and some of them ROTATE its password to their own value — so the hash
"drifts" and the next login fails. There is no boot seed or scheduler doing it;
it is concurrent clobbering of a single row.

The durable fix is to make the admin password DETERMINISTIC and SELF-HEALING from
a single source of truth: the ``ADMIN_PASSWORD`` environment value. On every boot
(every deploy restarts the app, so this runs on every deploy), reconcile the admin
account's password to that value. Idempotent — it only writes when the stored hash
no longer verifies, so a steady state is a no-op and there is no log spam.

Opt-in by construction: if ``ADMIN_PASSWORD`` is not configured (e.g. local dev),
this is a silent no-op. Fully guarded — a reconciliation problem must never block
application boot.
"""

import logging

logger = logging.getLogger(__name__)


def reconcile_admin_password(app) -> None:
    """Ensure the ADMIN_EMAIL account's password matches ADMIN_PASSWORD.

    Runs once per boot inside an app context. Never raises.
    """
    email = (app.config.get("ADMIN_EMAIL") or "").strip()
    password = app.config.get("ADMIN_PASSWORD")
    if not email or not password:
        logger.debug("admin password reconciliation skipped (ADMIN_EMAIL/ADMIN_PASSWORD not set)")
        return

    try:
        from app import db
        from app.models.user import User

        with app.app_context():
            user = User.find_by_email(email)
            if user is None:
                logger.warning(
                    "admin password reconciliation: no user for ADMIN_EMAIL=%s — nothing to do",
                    email,
                )
                return
            # idempotent: only rewrite when the stored hash no longer verifies
            if user.verify_password(password):
                logger.debug("admin password already in sync for %s", email)
                return
            user.password = password
            db.session.commit()
            logger.warning(
                "admin password reconciled to configured ADMIN_PASSWORD for %s "
                "(drift corrected at boot)",
                email,
            )
    except Exception as exc:  # noqa: BLE001 — reconciliation must never block boot
        logger.error("admin password reconciliation failed (boot unaffected): %s", exc)
        try:
            from app import db
            db.session.rollback()
        except Exception:
            logger.debug("rollback after reconciliation failure also failed", exc_info=True)
