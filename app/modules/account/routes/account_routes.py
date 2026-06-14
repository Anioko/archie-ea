"""
Account Routes (migrated).

Thin route layer - all business logic lives in AccountService.

Migrated from: app/account/views.py
URL prefix preserved: /account (applied via register() in __init__.py)

Endpoints:
- /login, /register, /logout
- /manage, /manage/info, /manage/change-password, /manage/change-email, /manage/change-email/<token>
- /reset-password, /reset-password/<token>
- /confirm-account, /confirm-account/<token>
- /join-from-invite/<user_id>/<token>
- /unconfirmed
"""
import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.security.audit import audit_logger

_log = logging.getLogger(__name__)
from app.services.rate_limiter import rate_limit

from ..services.account_service import AccountService
from ..forms.account_forms import (
    ChangeEmailForm,
    ChangePasswordForm,
    CreatePasswordForm,
    LoginForm,
    RegistrationForm,
    RequestResetPasswordForm,
    ResetPasswordForm,
)

account_bp = Blueprint("account", __name__)

_svc = AccountService



@account_bp.route("/login", methods=["GET", "POST"])
@rate_limit(10, "1m", methods=("POST",))  # SECURITY: Brute-force protection on credential submits only
def login():
    """Log in an existing user."""
    form = LoginForm()
    if form.validate_on_submit():
        # COM-005: Check email-domain SSO config before password auth.
        # If the user's org has SSO configured and enabled, redirect to IdP.
        try:
            from app.services.sso_service import SSOService

            _sso_svc = SSOService()
            _sso_cfg = _sso_svc.get_config_for_email(form.email.data)
            if _sso_cfg is not None and _sso_cfg.enabled:
                return redirect(
                    url_for("sso.sso_initiate", email=form.email.data)
                )
        except Exception as _sso_exc:
            _log.debug("SSO domain check failed (non-fatal): %s", _sso_exc)

        user = _svc.authenticate(form.email.data, form.password.data)
        if user is not None:
            # Fix Session Fixation: Regenerate session ID after successful authentication
            session.clear()
            session.modified = True
            _svc.login(user, form.remember_me.data)
            session.permanent = True
            try:
                audit_logger.log_authentication(success=True)
            except Exception as _exc:
                _log.warning("Audit log failed on login success: %s", _exc)
            flash("You are now logged in. Welcome back!", "success")
            next_url = request.args.get("next", "")
            # Prevent open redirect: only allow relative URLs
            if not next_url or next_url.startswith("//") or "://" in next_url:
                next_url = url_for("dashboard.overview")
            return redirect(next_url)
        else:
            try:
                audit_logger.log_authentication(success=False)
            except Exception as _exc:
                _log.warning("Audit log failed on login failure: %s", _exc)
            flash("Invalid email or password.", "form-error")
    # Gather configured SSO / SAML providers for the login page buttons
    from app.auth.sso import sso_service

    oidc_providers = []
    if _sso_enabled():
        for key in sso_service.available_providers():
            cfg = sso_service.providers.get(key, {})
            oidc_providers.append({"key": key, "name": cfg.get("name", key.capitalize())})

    return render_template(
        "account/login.html",
        form=form,
        sso_providers=oidc_providers,
        saml_enabled=sso_service.is_saml_enabled(),
    )


@account_bp.route("/register", methods=["GET", "POST"])
@rate_limit(5, "1m", methods=("POST",))  # SECURITY: Anti-abuse on registration submits only
def register():
    """Register a new user, and send them a confirmation email."""
    form = RegistrationForm()
    if form.validate_on_submit():
        user = _svc.register_user(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            password=form.password.data,
        )
        flash("Account created successfully. Welcome to A.R.C.H.I.E.!", "success")
        return redirect(url_for("main.index"))
    return render_template("account/register.html", form=form)


@account_bp.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    try:
        audit_logger.log_logout()
    except Exception as _exc:
        _log.warning("Audit log failed on logout: %s", _exc)
    _svc.logout()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@account_bp.route("/manage", methods=["GET", "POST"])
@account_bp.route("/manage/info", methods=["GET", "POST"])
@login_required
def manage():
    """Display a user's account information."""
    return render_template("account/manage.html", user=current_user, form=None)


@account_bp.route("/manage/notification-preferences", methods=["POST"])
@login_required
def save_notification_preferences():
    """PLT-017: Save in-app notification preferences for the current user."""
    from app import db

    known_keys = [
        "arb_decisions",
        "solution_updates",
        "assignment_changes",
        "weekly_digest",
        "mention_notifications",
    ]
    prefs = {key: (request.form.get(key) == "on") for key in known_keys}
    try:
        current_user.set_notification_preferences(prefs)
        db.session.add(current_user)
        db.session.commit()
        flash("Notification preferences saved.", "success")
    except Exception as exc:
        _log.error("Failed to save notification preferences for user %s: %s", current_user.id, exc)
        db.session.rollback()
        flash("Could not save preferences. Please try again.", "error")
    return redirect(url_for("account.manage"))


@account_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_request():
    """Respond to existing user's request to reset their password."""
    if not current_user.is_anonymous:
        return redirect(url_for("main.index"))
    form = RequestResetPasswordForm()
    if form.validate_on_submit():
        _svc.request_password_reset(form.email.data)
        flash("A password reset link has been sent to {}.".format(form.email.data), "warning")
        return redirect(url_for("account.login"))
    return render_template("account/reset_password.html", form=form)


@account_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset an existing user's password."""
    if not current_user.is_anonymous:
        return redirect(url_for("main.index"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        success, message = _svc.reset_password(token, form.email.data, form.new_password.data)
        flash_cat = "form-success" if success else "form-error"
        flash(message, flash_cat)
        if success:
            return redirect(url_for("account.login"))
        return redirect(url_for("main.index"))
    return render_template("account/reset_password.html", form=form)


@account_bp.route("/manage/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change an existing user's password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        success, message = _svc.change_password(
            current_user, form.old_password.data, form.new_password.data
        )
        flash_cat = "form-success" if success else "form-error"
        flash(message, flash_cat)
        if success:
            return redirect(url_for("main.index"))
    return render_template("account/manage.html", form=form)


@account_bp.route("/manage/change-email", methods=["GET", "POST"])
@login_required
def change_email_request():
    """Respond to existing user's request to change their email."""
    form = ChangeEmailForm()
    if form.validate_on_submit():
        success, message = _svc.request_email_change(
            current_user, form.email.data, form.password.data
        )
        flash_cat = "warning" if success else "form-error"
        flash(message, flash_cat)
        if success:
            return redirect(url_for("main.index"))
    return render_template("account/manage.html", form=form)


@account_bp.route("/manage/change-email/<token>", methods=["GET", "POST"])
@login_required
def change_email(token):
    """Change existing user's email with provided token."""
    success, message = _svc.confirm_email_change(current_user, token)
    flash_cat = "success" if success else "error"
    flash(message, flash_cat)
    return redirect(url_for("main.index"))


@account_bp.route("/confirm-account")
@login_required
def confirm_request():
    """Respond to new user's request to confirm their account."""
    _svc.send_confirmation_email(current_user)
    flash("A new confirmation link has been sent to {}.".format(current_user.email), "warning")
    return redirect(url_for("main.index"))


@account_bp.route("/confirm-account/<token>")
@login_required
def confirm(token):
    """Confirm new user's account with provided token."""
    if current_user.confirmed:
        return redirect(url_for("main.index"))
    success, message = _svc.confirm_account(current_user, token)
    flash_cat = "success" if success else "error"
    flash(message, flash_cat)
    return redirect(url_for("main.index"))


@account_bp.route("/join-from-invite/<int:user_id>/<token>", methods=["GET", "POST"])
def join_from_invite(user_id, token):
    """Confirm new user's account with provided token and prompt them to set a password."""
    if current_user is not None and current_user.is_authenticated:
        flash("You are already logged in.", "error")
        return redirect(url_for("main.index"))

    new_user, token_valid, message = _svc.join_from_invite(user_id, token)

    if new_user is None:
        return redirect(404)

    if not token_valid and new_user.password_hash is not None:
        flash(message, "error")
        return redirect(url_for("main.index"))

    if token_valid:
        form = CreatePasswordForm()
        if form.validate_on_submit():
            _svc.set_password(new_user, form.password.data)
            flash(
                "Your password has been set. After you log in, you can "
                'go to the "Your Account" page to review your account '
                "information and settings.",
                "success",
            )
            return redirect(url_for("account.login"))
        return render_template("account/join_invite.html", form=form)
    else:
        flash(message, "error")
    return redirect(url_for("main.index"))


@account_bp.before_app_request
def before_request():
    """Force user to confirm email before accessing login-required routes."""
    if (
        current_user.is_authenticated
        and not current_user.confirmed
        and request.endpoint[:8] != "account."
        and request.endpoint != "static"
    ):
        return redirect(url_for("account.unconfirmed"))


@account_bp.route("/unconfirmed")
def unconfirmed():
    """Catch users with unconfirmed emails."""
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for("main.index"))
    return render_template("account/unconfirmed.html")


# =========================================================================
# SSO / Enterprise Identity Routes (S0-01)
# Feature-flagged behind FeatureFlag(key='sso_authentication')
# =========================================================================


def _get_sso_oauth():
    """Lazy-init Authlib OAuth registry (returns None if authlib not installed)."""
    try:
        from authlib.integrations.flask_client import OAuth
    except ImportError:
        return None

    from flask import current_app

    if not hasattr(current_app, "_sso_oauth"):
        oauth = OAuth(current_app)
        providers = current_app.config.get("SSO_PROVIDERS", {})
        for name, cfg in providers.items():
            if cfg.get("client_id"):
                oauth.register(name, **cfg)
        current_app._sso_oauth = oauth

    return current_app._sso_oauth


def _sso_enabled():
    """Check if SSO feature flag is active."""
    try:
        from app.models.feature_flags import FeatureFlag

        flag = FeatureFlag.query.filter_by(key="sso_authentication").first()
        return flag is not None and flag.is_active
    except Exception as e:
        _log.debug("SSO feature flag check failed: %s", e)
        return False


@account_bp.route("/sso/<provider>")
def sso_login(provider):
    """Initiate SSO login flow for the given provider."""
    from flask import abort, current_app

    if not _sso_enabled():
        abort(404)

    oauth = _get_sso_oauth()
    if oauth is None:
        flash("SSO is not available. Please install authlib.", "error")
        return redirect(url_for("account.login"))

    client = oauth.create_client(provider)
    if client is None:
        abort(404)

    # Anti-CSRF: generate state parameter
    import secrets

    state = secrets.token_urlsafe(32)
    session["sso_state"] = state
    session["sso_provider"] = provider

    callback_url = url_for("account.sso_callback", provider=provider, _external=True)
    return client.authorize_redirect(callback_url, state=state)


@account_bp.route("/sso/callback/<provider>")
def sso_callback(provider):
    """Handle SSO callback from identity provider."""
    from flask import abort, current_app

    if not _sso_enabled():
        abort(404)

    # Validate anti-CSRF state parameter
    expected_state = session.pop("sso_state", None)
    received_state = request.args.get("state")
    if not expected_state or expected_state != received_state:
        flash("SSO authentication failed: invalid state parameter.", "error")
        return redirect(url_for("account.login"))

    session.pop("sso_provider", None)

    oauth = _get_sso_oauth()
    if oauth is None:
        flash("SSO is not available.", "error")
        return redirect(url_for("account.login"))

    client = oauth.create_client(provider)
    if client is None:
        abort(404)

    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo")
        if userinfo is None:
            userinfo = client.userinfo()
    except Exception as e:
        current_app.logger.error("SSO callback error for %s: %s", provider, e)
        flash("SSO authentication failed. Please try again.", "error")
        return redirect(url_for("account.login"))

    # Extract user identity from OIDC claims
    external_id = userinfo.get("sub", "")
    email = userinfo.get("email", "")
    first_name = userinfo.get("given_name", "")
    last_name = userinfo.get("family_name", "")

    if not external_id or not email:
        flash("SSO provider did not return required user information.", "error")
        return redirect(url_for("account.login"))

    # Find or create user by external_id
    from app import db
    from app.models.user import User

    user = User.query.filter_by(external_id=external_id, sso_provider=provider).first()
    if user is None:
        # Try matching by email for existing password-auth users linking SSO
        user = User.find_by_email(email)
        if user is not None:
            user.external_id = external_id
            user.sso_provider = provider
        else:
            # Create new user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                external_id=external_id,
                sso_provider=provider,
                confirmed=True,
            )
            db.session.add(user)

        db.session.commit()

    # Establish Flask-Login session (same as password login)
    session.clear()
    session.modified = True
    from flask_login import login_user

    login_user(user, remember=True)
    session.permanent = True

    flash("Successfully signed in via SSO.", "success")
    return redirect(url_for("main.index"))


# =========================================================================
# SAML 2.0 Routes (PLT-030)
# Coexists with OIDC SSO routes above.  Feature-flagged behind the same
# FeatureFlag(key='sso_authentication') + SAML_IDP_SSO_URL config.
# =========================================================================


def _saml_available():
    """Return True when SAML is configured and the SSO feature flag is on."""
    from app.auth.sso import sso_service

    return sso_service.is_saml_enabled()


@account_bp.route("/saml/login")
def saml_login():
    """Initiate SAML 2.0 SSO — redirect user to IdP with SAMLRequest.

    GET /account/saml/login
    """
    from flask import abort, current_app

    from app.auth.sso import SSOError, sso_service

    if not _saml_available():
        abort(404)

    try:
        redirect_url = sso_service.build_saml_authn_request_url()
    except SSOError as exc:
        current_app.logger.error("SAML login initiation failed: %s", exc)
        flash("SAML SSO is not available. Please contact your administrator.", "error")
        return redirect(url_for("account.login"))

    return redirect(redirect_url)


@account_bp.route("/saml/acs", methods=["POST"])
def saml_acs():
    """SAML Assertion Consumer Service — receive SAML Response from IdP.

    POST /account/saml/acs
    The IdP posts a base64-encoded SAMLResponse form field here after
    authenticating the user.
    """
    from flask import abort, current_app

    from app.auth.sso import SSOError, sso_service

    if not _saml_available():
        abort(404)

    saml_response = request.form.get("SAMLResponse", "")
    if not saml_response:
        _log.warning("SAML ACS called with no SAMLResponse field")
        flash("SAML authentication failed: missing response. Please try again.", "error")
        return redirect(url_for("account.login"))

    try:
        user = sso_service.handle_saml_callback(saml_response)
    except SSOError as exc:
        current_app.logger.error("SAML ACS error: %s", exc)
        flash("SAML authentication failed. Please try again or contact your administrator.", "error")
        return redirect(url_for("account.login"))

    # Establish Flask-Login session
    session.clear()
    session.modified = True
    from flask_login import login_user

    login_user(user, remember=True)
    session.permanent = True

    # Honor RelayState redirect when present and safe
    relay_state = request.form.get("RelayState", "")
    next_url = url_for("main.index")
    if relay_state and relay_state.startswith("/") and not relay_state.startswith("//"):
        next_url = relay_state

    flash("Successfully signed in via SAML SSO.", "success")
    return redirect(next_url)


@account_bp.route("/saml/metadata")
def saml_metadata():
    """Return SP (Service Provider) SAML metadata XML.

    GET /account/saml/metadata
    IdP administrators import this XML to configure the trust relationship.
    """
    from flask import Response, abort, current_app

    from app.auth.sso import SSOError, sso_service

    if not _saml_available():
        abort(404)

    try:
        xml = sso_service.build_sp_metadata_xml()
    except SSOError as exc:
        current_app.logger.error("SAML metadata generation failed: %s", exc)
        abort(500)

    return Response(xml, mimetype="application/samlmetadata+xml")
