"""
SSO federation routes (COM-005).

Blueprint: ``sso``

Routes
------
GET  /auth/sso/initiate?email=...    Look up domain config; redirect to IdP.
GET  /auth/sso/callback/oidc         Handle OIDC callback; provision user; login.
GET  /auth/sso/callback/saml         SAML stub (HTTP 501 until python3-saml added).
GET  /admin/sso                      Show SSO config form (admin only).
POST /admin/sso                      Save SSO config (admin only).
"""

import logging

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user

from app.decorators import admin_required
from app.services.sso_service import SSONotConfiguredError, SSOService

_log = logging.getLogger(__name__)

sso_bp = Blueprint("sso", __name__)
_svc = SSOService()


# ---------------------------------------------------------------------------
# Public SSO initiation & callback
# ---------------------------------------------------------------------------


@sso_bp.route("/auth/sso/initiate")
def sso_initiate():
    """Initiate SSO login for the given email address.

    Query params:
        email (str): The user's email address.

    On success redirects to the IdP. On misconfiguration returns JSON error.
    """
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"error": "email parameter required"}), 400

    config = _svc.get_config_for_email(email)
    if config is None or not config.enabled:
        return jsonify({"error": "No SSO configured for this email domain"}), 404

    redirect_uri = url_for("sso.sso_callback_oidc", _external=True)

    try:
        if config.protocol == "oidc":
            result = _svc.initiate_oidc_flow(config, redirect_uri)
            session["sso_state"] = result["state"]
            session["sso_org_id"] = config.organization_id
            session["sso_email"] = email
            return redirect(result["redirect_url"])
        elif config.protocol == "saml":
            _svc.initiate_saml_flow(config)
        else:
            return jsonify({"error": f"Unknown SSO protocol: {config.protocol}"}), 400
    except SSONotConfiguredError as exc:
        _log.warning("SSO initiation failed for %s: %s", email, exc)
        return jsonify({"error": str(exc)}), 503


@sso_bp.route("/auth/sso/callback/oidc")
def sso_callback_oidc():
    """Handle the OIDC callback from the IdP.

    Validates the anti-CSRF ``state``, exchanges the code, provisions the
    user, logs them in, then redirects to /dashboard.
    """
    code = request.args.get("code", "")
    state = request.args.get("state", "")

    # Validate anti-CSRF state
    expected_state = session.pop("sso_state", None)
    if not expected_state or expected_state != state:
        flash("SSO authentication failed: invalid state parameter.", "error")
        return redirect(url_for("account.login"))

    org_id = session.pop("sso_org_id", None)
    session.pop("sso_email", None)

    try:
        from app.models.organization import Organization

        org = Organization.query.get(org_id) if org_id else None
        if org is None:
            flash("SSO configuration error: organisation not found.", "error")
            return redirect(url_for("account.login"))

        config = org.sso_config
        if config is None or not config.enabled:
            flash("SSO is not enabled for this organisation.", "error")
            return redirect(url_for("account.login"))

        redirect_uri = url_for("sso.sso_callback_oidc", _external=True)
        userinfo = _svc.handle_oidc_callback(config, code, state, redirect_uri)
        user = _svc.provision_user(org, userinfo)

        session.clear()
        session.modified = True
        login_user(user)
        session.permanent = True

        return redirect(url_for("dashboard.overview"))

    except SSONotConfiguredError as exc:
        _log.error("OIDC callback failed: %s", exc)
        flash(f"SSO login failed: {exc}", "error")
        return redirect(url_for("account.login"))
    except Exception as exc:
        _log.exception("Unexpected error during OIDC callback")
        flash("SSO login failed due to an unexpected error.", "error")
        return redirect(url_for("account.login"))


@sso_bp.route("/auth/sso/callback/saml")
def sso_callback_saml():
    """SAML 2.0 callback stub.

    Returns HTTP 501 until python3-saml is installed and wired.
    """
    return (
        jsonify(
            {
                "error": "SAML 2.0 callback not yet implemented",
                "message": (
                    "SAML federation requires the python3-saml library. "
                    "Install with: pip install python3-saml"
                ),
            }
        ),
        501,
    )


# ---------------------------------------------------------------------------
# Admin SSO configuration
# ---------------------------------------------------------------------------


@sso_bp.route("/admin/sso", methods=["GET", "POST"])
@admin_required
def admin_sso():
    """Show and save SSO configuration for the current user's organisation."""
    from app import db
    from app.models.sso_config import SSOConfig

    org_id = getattr(current_user, "organization_id", None)
    config = SSOConfig.query.filter_by(organization_id=org_id).first() if org_id else None

    if request.method == "POST":
        protocol = request.form.get("protocol", "oidc")
        email_domain = request.form.get("email_domain", "").strip()
        idp_metadata_url = request.form.get("idp_metadata_url", "").strip()
        client_id = request.form.get("client_id", "").strip()
        client_secret_raw = request.form.get("client_secret", "").strip()
        enabled = request.form.get("enabled") == "on"

        if config is None:
            if not org_id:
                flash("Cannot save SSO config: no organisation associated.", "error")
                return redirect(url_for("sso.admin_sso"))
            config = SSOConfig(organization_id=org_id)
            db.session.add(config)

        config.protocol = protocol
        config.email_domain = email_domain
        config.idp_metadata_url = idp_metadata_url
        config.client_id = client_id
        if client_secret_raw:
            config.client_secret = client_secret_raw
        config.enabled = enabled

        try:
            db.session.commit()
            flash("SSO configuration saved.", "success")
        except Exception as exc:
            db.session.rollback()
            _log.error("Failed to save SSO config: %s", exc)
            flash("Failed to save SSO configuration.", "error")

        return redirect(url_for("sso.admin_sso"))

    return render_template("admin/sso.html", config=config)
