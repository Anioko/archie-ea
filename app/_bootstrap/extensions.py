import logging

logger = logging.getLogger(__name__)
"""
Extension initialization — called early in create_app().
"""


def init_extensions(app):
    """Call init_app() on every Flask extension."""
    from app.extensions import compress, csrf, db, login_manager, mail

    mail.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)

    # JSON 401 for API endpoints instead of redirect
    @login_manager.unauthorized_handler
    def _unauthorized():
        from flask import jsonify, redirect, request, url_for

        wants_json = (
            "/api/" in request.path
            or "/ai-chat/" in request.path
            or request.content_type == "application/json"
            or request.accept_mimetypes.best == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        if wants_json:
            resp = jsonify({"success": False, "error": "Authentication required"})
            resp.status_code = 401
            return resp
        return redirect(url_for("account.login", next=request.url))

    csrf.init_app(app)

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        import logging
        from flask import request as _req, session, render_template, jsonify
        _log = logging.getLogger(__name__)
        _log.error(
            "CSRF FAILURE: reason=%r | method=%s path=%s | "
            "form_keys=%s | has_csrf_token_field=%s | "
            "session_keys=%s | cookie_names=%s",
            e.description,
            _req.method,
            _req.path,
            list(_req.form.keys()),
            bool(_req.form.get("csrf_token")),
            list(session.keys()),
            list(_req.cookies.keys()),
        )
        # Return JSON for AJAX/API requests instead of HTML login page
        wants_json = (
            "/api/" in _req.path
            or "/ai-chat/" in _req.path
            or _req.content_type == "application/json"
            or _req.accept_mimetypes.best == "application/json"
            or _req.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        if wants_json:
            return jsonify({
                "success": False,
                "error": "Your session has expired. Please refresh the page and try again.",
                "error_type": "csrf",
            }), 400
        from flask import flash
        flash("Your session has expired. Please try again.", "form-error")
        from app.modules.account.forms.account_forms import LoginForm
        form = LoginForm()
        return render_template("account/login.html", form=form), 400

    from werkzeug.exceptions import HTTPException

    @app.errorhandler(HTTPException)
    def handle_http_exception_on_api(e):
        """An /api/ path must answer in JSON even when it is refusing.

        A front end that asks for JSON and receives an HTML error page fails at
        JSON.parse, so the user sees a generic script error instead of "you do
        not have access" - the refusal is correct and the explanation is lost.
        Flask-Login's unauthorized_handler already does this for the routes it
        guards, but abort(401)/abort(403) raised by a role decorator bypasses it
        and renders HTML.

        Everything outside /api/ is returned untouched, so ordinary pages keep
        their existing error templates. Blueprint-level handlers are more
        specific than this one and still win where they are registered.
        """
        from flask import jsonify, request

        if "/api/" not in request.path:
            return e
        return jsonify({
            "success": False,
            "error": e.description,
            "error_type": (e.name or "error").lower().replace(" ", "_"),
        }), e.code

    from sqlalchemy.orm.exc import StaleDataError

    @app.errorhandler(StaleDataError)
    def handle_stale_data_error(e):
        """Someone else saved this record first — say so, don't show a crash.

        Optimistic locking turns a silent overwrite into a refused write, which
        is only an improvement if the person who was refused understands what
        happened. Without this handler they get a 500 and no idea their work was
        rejected, which reads as the product being broken rather than as the
        product protecting a colleague's edit.

        409 Conflict is the accurate status: the request was well-formed and the
        user is allowed to make it — it lost a race. The record on screen is
        stale, so reloading is genuinely the fix, and the message says that
        rather than asking the user to guess.
        """
        from flask import flash, jsonify, redirect, render_template, request

        db.session.rollback()
        logger.warning(
            "optimistic lock conflict: method=%s path=%s user=%s",
            request.method, request.path,
            getattr(getattr(request, "user", None), "id", "anonymous"),
        )
        message = (
            "Someone else saved changes to this record while you were editing it. "
            "Your changes were not saved. Reload the page to see their version, "
            "then re-apply your edits."
        )
        wants_json = (
            "/api/" in request.path
            or request.content_type == "application/json"
            or request.accept_mimetypes.best == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        if wants_json:
            return jsonify({
                "success": False,
                "error": message,
                "error_type": "conflict",
                "conflict": True,
            }), 409
        flash(message, "warning")
        # Back to the record they were editing, which now reloads the saved
        # version — a redirect rather than a re-render, so a refresh does not
        # resubmit the losing write.
        referrer = request.referrer
        if referrer and request.host_url.rstrip("/") in referrer:
            return redirect(referrer)
        return render_template(
            "errors/generic_error.html",
            status_code=409,
            error={
                "error": "Someone else saved changes to this record while you "
                         "were editing it, so your changes were not saved.",
                "recovery_action": "Reload the page to see their version, then "
                                   "re-apply your edits.",
            },
        ), 409

    compress.init_app(app)

    # Optional: Flask-Migrate
    try:
        from flask_migrate import Migrate
        Migrate(app, db)
    except ImportError:
        pass

    # Optional: Flask-RQ
    try:
        from flask_rq import RQ
        RQ(app)
    except ImportError:
        pass

    # Optional: Flask-Babel (S2-01 i18n — date/number/currency formatting)
    try:
        from flask_babel import Babel

        def get_locale():
            from flask import request, session

            # 1. Explicit session override
            locale = session.get("locale")
            if locale:
                return locale
            # 2. Accept-Language header
            return request.accept_languages.best_match(
                ["en", "de", "fr", "es", "ja", "zh"],
                default=app.config.get("BABEL_DEFAULT_LOCALE", "en"),
            )

        def get_timezone():
            from flask import session

            tz = session.get("timezone")
            if tz:
                return tz
            return app.config.get("BABEL_DEFAULT_TIMEZONE", "UTC")

        # Flask-Babel >=3.0 uses constructor kwargs; older versions use decorators
        try:
            babel = Babel(app, locale_selector=get_locale, timezone_selector=get_timezone)
        except TypeError:
            babel = Babel(app)
            babel.localeselector(get_locale)
            babel.timezoneselector(get_timezone)

    except ImportError:
        app.logger.info("Flask-Babel not installed — i18n formatting unavailable")

    # Redis cache manager
    try:
        from app.extensions.cache import cache_manager
        cache_manager.init_app(app)
    except Exception as e:
        app.logger.warning(f"Redis cache initialization failed (non-critical): {e}")


def init_scheduler(app):
    """Initialize APScheduler for background workflow execution."""
    if app.testing:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        import atexit

        scheduler = BackgroundScheduler()

        def run_scheduled_workflows():
            """APScheduler job: execute due EA workflow schedules."""
            with app.app_context():
                try:
                    from app.services.ea_workflow_engine import EAWorkflowEngine
                    engine = EAWorkflowEngine()
                    result = engine.run_due_schedules()
                    if result["schedules_run"] > 0:
                        import logging
                        logging.getLogger(__name__).info(
                            "APScheduler: ran %d EA workflow schedules", result["schedules_run"]
                        )
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error("APScheduler ea-workflows error: %s", exc)

        scheduler.add_job(
            func=run_scheduled_workflows,
            trigger=IntervalTrigger(minutes=5),
            id="ea_workflow_scheduler",
            name="EA Workflow Schedule Runner",
            replace_existing=True,
            max_instances=1,
        )

        # PLT-009: Weekly data maturity digest (Monday 8am UTC)
        def run_data_maturity_digest():
            with app.app_context():
                try:
                    from app._bootstrap._digest_emails import send_data_maturity_digest
                    send_data_maturity_digest(app)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error(
                        "APScheduler data-maturity-digest error: %s", exc
                    )

        from apscheduler.triggers.cron import CronTrigger

        scheduler.add_job(
            func=run_data_maturity_digest,
            trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
            id="data_maturity_digest",
            name="PLT-009 Weekly Data Maturity Digest",
            replace_existing=True,
            max_instances=1,
        )

        # PLT-031: Weekly executive summary (Monday 7am UTC)
        def run_executive_summary():
            with app.app_context():
                try:
                    from app._bootstrap._digest_emails import send_executive_summary
                    send_executive_summary(app)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error(
                        "APScheduler executive-summary error: %s", exc
                    )

        scheduler.add_job(
            func=run_executive_summary,
            trigger=CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="executive_summary",
            name="PLT-031 Weekly Executive Summary",
            replace_existing=True,
            max_instances=1,
        )

        # Teams meeting intelligence: Graph callRecords subscriptions expire
        # every 3 days — renew twice daily; renew_if_needed re-creates the
        # subscription if Graph has already dropped it. No-op when the
        # integration was never configured.
        def run_teams_subscription_renewal():
            with app.app_context():
                try:
                    from app.services.teams_meeting_service import TeamsMeetingService
                    result = TeamsMeetingService.renew_if_needed()
                    if result.get("status") == "ok":
                        import logging
                        logging.getLogger(__name__).info(
                            "APScheduler: Teams subscription renewed until %s",
                            result.get("expiry"),
                        )
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).error(
                        "APScheduler teams-renewal error: %s", exc
                    )

        scheduler.add_job(
            func=run_teams_subscription_renewal,
            trigger=IntervalTrigger(hours=12),
            id="teams_subscription_renewal",
            name="Teams Meeting Graph Subscription Renewal",
            replace_existing=True,
            max_instances=1,
        )

        # Typed ARB waiver expiry is opt-in and tenant-explicit. The database
        # advisory lock in the batch service prevents duplicate Gunicorn
        # schedulers from processing the same deployment concurrently.
        arb_expiry_registered = False
        if app.config.get("ARB_CONDITION_EXPIRY_ORGANIZATION_IDS"):
            def run_arb_waiver_expiry():
                with app.app_context():
                    try:
                        from app.modules.transformation_room.arb_waiver_expiry_batch_service import (
                            ARBWaiverExpiryBatchService,
                        )

                        result = ARBWaiverExpiryBatchService.run_configured()
                        import logging
                        log = logging.getLogger(__name__)
                        if result.failed_count:
                            log.error(
                                "APScheduler typed ARB waiver expiry partial failure: %s",
                                result.as_dict(),
                            )
                        elif result.selected_count or not result.lock_acquired:
                            log.info(
                                "APScheduler typed ARB waiver expiry: %s",
                                result.as_dict(),
                            )
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).error(
                            "APScheduler typed ARB waiver expiry error: %s", exc
                        )

            try:
                expiry_interval_minutes = int(
                    app.config["ARB_CONDITION_EXPIRY_INTERVAL_MINUTES"]
                )
                if expiry_interval_minutes <= 0:
                    raise ValueError("interval must be positive")
                scheduler.add_job(
                    func=run_arb_waiver_expiry,
                    trigger=IntervalTrigger(minutes=expiry_interval_minutes),
                    id="typed_arb_waiver_expiry",
                    name="Typed ARB Condition Waiver Expiry",
                    replace_existing=True,
                    max_instances=1,
                )
                arb_expiry_registered = True
            except (KeyError, TypeError, ValueError) as exc:
                app.logger.error(
                    "Typed ARB waiver expiry scheduler disabled by invalid interval: %s",
                    exc,
                )

        scheduler.start()

        def _shutdown_scheduler():
            try:
                scheduler.pause()  # stop new jobs from firing before shutdown
                scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.debug("suppressed error in init_scheduler._shutdown_scheduler (app/_bootstrap/extensions.py): %s", exc)  # prevent atexit race from crashing gunicorn master

        atexit.register(_shutdown_scheduler)
        app.extensions["ea_workflow_scheduler"] = scheduler
        scheduled_jobs = (
            "EA workflows (5 min), maturity digest (Mon 8am), "
            "executive summary (Mon 7am), Teams subscription renewal (12h)"
        )
        if arb_expiry_registered:
            scheduled_jobs += ", typed ARB waiver expiry (configured)"
        app.logger.info("APScheduler started: %s", scheduled_jobs)
    except ImportError:
        app.logger.warning("APScheduler not available — EA workflow schedules disabled")
    except Exception as exc:
        app.logger.error("APScheduler init failed: %s", exc)
