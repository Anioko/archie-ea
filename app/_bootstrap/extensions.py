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

        scheduler.start()

        def _shutdown_scheduler():
            try:
                scheduler.pause()  # stop new jobs from firing before shutdown
                scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.debug("suppressed error in init_scheduler._shutdown_scheduler (app/_bootstrap/extensions.py): %s", exc)  # prevent atexit race from crashing gunicorn master

        atexit.register(_shutdown_scheduler)
        app.extensions["ea_workflow_scheduler"] = scheduler
        app.logger.info(
            "APScheduler started: EA workflows (5 min), "
            "maturity digest (Mon 8am), executive summary (Mon 7am), "
            "Teams subscription renewal (12h)"
        )
    except ImportError:
        app.logger.warning("APScheduler not available — EA workflow schedules disabled")
    except Exception as exc:
        app.logger.error("APScheduler init failed: %s", exc)
