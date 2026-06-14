"""
Billing routes — subscription management for admin users.

Blueprint: billing_bp
URL prefix: /admin/billing  (registered in app/modules/admin/__init__.py)

Routes:
  GET  /admin/billing          — show current plan, usage, upgrade options
  POST /admin/billing/upgrade  — initiate Stripe checkout session
  POST /admin/billing/webhook  — Stripe webhook (no auth, sig verified in service)
  GET  /admin/billing/portal   — redirect to Stripe customer portal
"""

import logging

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import csrf, db

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__)


def _get_or_create_subscription(org):
    """Return the org's Subscription row, creating a free-tier stub if absent."""
    from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus

    sub = Subscription.query.filter_by(organization_id=org.id).first()
    if sub is None:
        sub = Subscription(
            organization_id=org.id,
            plan=SubscriptionPlan.free,
            status=SubscriptionStatus.active,
            seats_purchased=5,
        )
        db.session.add(sub)
        db.session.commit()
    return sub


@billing_bp.route("/")
@login_required
def billing_index():
    from app.models.user import User

    org = getattr(current_user, "organization", None)
    if org is None:
        return render_template(
            "admin/billing.html",
            subscription=None,
            seats_used=0,
            error="No organisation found for your account.",
        )

    sub = _get_or_create_subscription(org)
    seats_used = User.query.filter_by(organization_id=org.id).count()

    return render_template(
        "admin/billing.html",
        subscription=sub,
        seats_used=seats_used,
        org=org,
        stripe_configured=_stripe_is_configured(),
    )


@billing_bp.route("/upgrade", methods=["POST"])
@login_required
def billing_upgrade():
    """Initiate a Stripe Checkout session for an upgrade."""
    plan = request.form.get("plan", "pro")
    seats = int(request.form.get("seats", 5))

    org = getattr(current_user, "organization", None)
    if org is None:
        return jsonify({"error": "No organisation found"}), 400

    from app.services.billing_service import BillingService

    sub_id = BillingService.create_subscription(org, plan, seats)
    if sub_id:
        return redirect(url_for("billing.billing_index"))

    # Stripe not configured or error — fall back gracefully
    return redirect(url_for("billing.billing_index"))


@billing_bp.route("/portal")
@login_required
def billing_portal():
    """Redirect to the Stripe customer portal for self-service billing."""
    org = getattr(current_user, "organization", None)
    if org is None:
        return redirect(url_for("billing.billing_index"))

    from app.services.billing_service import BillingService

    return_url = request.host_url.rstrip("/") + url_for("billing.billing_index")
    portal_url = BillingService.get_portal_url(org, return_url=return_url)
    if portal_url:
        return redirect(portal_url)

    return redirect(url_for("billing.billing_index"))


@billing_bp.route("/webhook", methods=["POST"])
@csrf.exempt
def billing_webhook():
    """Stripe webhook endpoint — signature verified inside BillingService."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    from app.services.billing_service import BillingService

    result = BillingService.handle_webhook(payload, sig_header)
    if result.get("ok"):
        return jsonify({"received": True}), 200
    return jsonify({"error": result.get("error", "Webhook processing failed")}), 400


def _stripe_is_configured() -> bool:
    import os

    return bool(os.environ.get("STRIPE_SECRET_KEY"))
