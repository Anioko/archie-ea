"""
Webhook service for Enterprise Architecture Platform
Provides event-driven notifications and integrations
"""

import hashlib
import hmac
import json
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app import csrf
from app.decorators import audit_log, require_auth
from app.services.webhook_service import WebhookService
webhook_bp = Blueprint("webhook", __name__, url_prefix="/api/webhooks")


# IP-based rate limiter for the public webhook receiver endpoint
class _WebhookRateLimiter:
    """Rate limiter for unauthenticated webhook receiver (IP-based)."""

    def __init__(self, max_requests=30, window_seconds=60):
        self._requests = defaultdict(list)
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    def is_allowed(self, ip_address):
        now = datetime.utcnow()
        # Prune old entries
        self._requests[ip_address] = [
            ts for ts in self._requests[ip_address]
            if (now - ts).total_seconds() < self._window_seconds
        ]
        if len(self._requests[ip_address]) >= self._max_requests:
            return False
        self._requests[ip_address].append(now)
        return True


_webhook_rate_limiter = _WebhookRateLimiter(max_requests=30, window_seconds=60)


def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature for security"""
    if not secret:
        return True  # No secret configured

    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@webhook_bp.route("/subscriptions", methods=["GET"])
@require_auth
@audit_log("webhook_subscriptions_list")
def list_subscriptions():
    """List webhook subscriptions for the authenticated user"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        service = WebhookService()

        subscriptions = service.get_user_subscriptions(user_id)
        return jsonify(
            {"success": True, "data": [sub.to_dict() for sub in subscriptions]}
        )
    except Exception as e:
        current_app.logger.error(f"Error listing webhook subscriptions: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to list webhook subscriptions"}
        ), 500


@webhook_bp.route("/subscriptions", methods=["POST"])
@require_auth
@audit_log("webhook_subscription_create")
def create_subscription():
    """Create a new webhook subscription"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        required_fields = ["url", "events"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"success": False, "error": f"Missing required field: {field}"}
                ), 400

        service = WebhookService()
        subscription = service.create_subscription(
            user_id=user_id,
            url=data["url"],
            events=data["events"],
            secret=data.get("secret"),
            description=data.get("description"),
            filters=data.get("filters", {}),
            headers=data.get("headers", {}),
        )

        return jsonify({"success": True, "data": subscription.to_dict()}), 201

    except Exception as e:
        current_app.logger.error(f"Error creating webhook subscription: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to create webhook subscription"}
        ), 500


@webhook_bp.route("/subscriptions/<subscription_id>", methods=["GET"])
@require_auth
@audit_log("webhook_subscription_get")
def get_subscription(subscription_id):
    """Get a specific webhook subscription"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        service = WebhookService()

        subscription = service.get_subscription(subscription_id, user_id)
        if not subscription:
            return jsonify({"success": False, "error": "Subscription not found"}), 404

        return jsonify({"success": True, "data": subscription.to_dict()})
    except Exception as e:
        current_app.logger.error(f"Error getting webhook subscription: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to get webhook subscription"}
        ), 500


@webhook_bp.route("/subscriptions/<subscription_id>", methods=["PUT"])
@require_auth
@audit_log("webhook_subscription_update")
def update_subscription(subscription_id):
    """Update a webhook subscription"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        service = WebhookService()
        subscription = service.update_subscription(
            subscription_id=subscription_id, user_id=user_id, updates=data
        )

        if not subscription:
            return jsonify({"success": False, "error": "Subscription not found"}), 404

        return jsonify({"success": True, "data": subscription.to_dict()})
    except Exception as e:
        current_app.logger.error(f"Error updating webhook subscription: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to update webhook subscription"}
        ), 500


@webhook_bp.route("/subscriptions/<subscription_id>", methods=["DELETE"])
@require_auth
@audit_log("webhook_subscription_delete")
def delete_subscription(subscription_id):
    """Delete a webhook subscription"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        service = WebhookService()

        success = service.delete_subscription(subscription_id, user_id)
        if not success:
            return jsonify({"success": False, "error": "Subscription not found"}), 404

        return jsonify(
            {"success": True, "message": "Subscription deleted successfully"}
        )
    except Exception as e:
        current_app.logger.error(f"Error deleting webhook subscription: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to delete webhook subscription"}
        ), 500


@webhook_bp.route("/subscriptions/<subscription_id>/test", methods=["POST"])
@require_auth
@audit_log("webhook_subscription_test")
def test_subscription(subscription_id):
    """Test a webhook subscription by sending a test event"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        service = WebhookService()

        result = service.test_subscription(subscription_id, user_id)
        if not result:
            return (
                jsonify(
                    {"success": False, "error": "Subscription not found or test failed"}
                ),
                404,
            )

        return jsonify(
            {
                "success": True,
                "message": "Test webhook sent successfully",
                "data": result,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error testing webhook subscription: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to test webhook subscription"}
        ), 500


@webhook_bp.route("/events", methods=["GET"])
@require_auth
@audit_log("webhook_events_list")
def list_events():
    """List webhook events (for debugging/admin purposes)"""
    try:
        service = WebhookService()

        # Only allow admins to list all events
        if not hasattr(request, "user_roles") or "admin" not in current_user_roles:
            return jsonify({"success": False, "error": "Admin access required"}), 403

        events = service.get_events(
            limit=request.args.get("limit", 50, type=int),
            offset=request.args.get("offset", 0, type=int),
        )

        return jsonify({"success": True, "data": [event.to_dict() for event in events]})
    except Exception as e:
        current_app.logger.error(f"Error listing webhook events: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to list webhook events"}
        ), 500


@webhook_bp.route("/events/<event_id>/retry", methods=["POST"])
@require_auth
@audit_log("webhook_event_retry")
def retry_event(event_id):
    """Retry sending a failed webhook event"""
    try:
        service = WebhookService()

        # Only allow admins to retry events
        if not hasattr(request, "user_roles") or "admin" not in current_user_roles:
            return jsonify({"success": False, "error": "Admin access required"}), 403

        success = service.retry_event(event_id)
        if not success:
            return jsonify(
                {"success": False, "error": "Event not found or retry failed"}
            ), 404

        return jsonify(
            {"success": True, "message": "Event retry initiated successfully"}
        )
    except Exception as e:
        current_app.logger.error(f"Error retrying webhook event: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retry webhook event"}
        ), 500


# Public webhook receiver endpoint (no user auth — secured by signature + rate limiting)
@webhook_bp.route("/receiver/<subscription_id>", methods=["POST"])
# csrf.exempt: webhook receiver — external systems cannot include CSRF tokens
@csrf.exempt
def receive_webhook(subscription_id):
    """Receive webhook from external services (for two-way integrations)"""
    try:
        # Rate limit by IP address
        client_ip = request.remote_addr or "unknown"
        if not _webhook_rate_limiter.is_allowed(client_ip):
            current_app.logger.warning(
                "Webhook rate limit exceeded for IP %s on subscription %s",
                client_ip, subscription_id
            )
            return jsonify({"success": False, "error": "Rate limit exceeded"}), 429

        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get("X-Webhook-Signature")

        service = WebhookService()

        # Verify subscription exists
        subscription = service.get_subscription_by_id(subscription_id)
        if not subscription:
            # Do not reveal whether subscription exists — use generic message
            current_app.logger.warning(
                "Webhook received for non-existent subscription %s from IP %s",
                subscription_id, client_ip
            )
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        # Enforce signature verification when a secret is configured
        if subscription.secret:
            if not signature:
                current_app.logger.warning(
                    "Webhook missing signature for subscription %s from IP %s",
                    subscription_id, client_ip
                )
                return jsonify({"success": False, "error": "Missing signature"}), 401
            if not verify_webhook_signature(payload, signature, subscription.secret):
                current_app.logger.warning(
                    "Webhook invalid signature for subscription %s from IP %s",
                    subscription_id, client_ip
                )
                return jsonify({"success": False, "error": "Invalid signature"}), 401

        # Parse payload
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"raw_payload": payload.decode("utf-8")}

        # Process the incoming webhook
        result = service.process_incoming_webhook(
            subscription_id=subscription_id, payload=data, headers=dict(request.headers)
        )

        return jsonify(
            {
                "success": True,
                "message": "Webhook received successfully",
                "data": result,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error processing incoming webhook: {str(e)}")
        return jsonify({"success": False, "error": "Failed to process webhook"}), 500


# ---------------------------------------------------------------------------
# Slack Events API receiver
# ---------------------------------------------------------------------------

@webhook_bp.route("/slack/events", methods=["POST"])
# csrf.exempt: external Slack platform cannot include CSRF tokens
@csrf.exempt
def slack_events():
    """Receive Slack Events API payloads (URL verification + event dispatch)."""
    try:
        from app.services.slack_architect_service import SlackArchitectService

        raw_body = request.get_data()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        cfg = SlackArchitectService.get_config()
        signing_secret = cfg.get("signing_secret", "")

        if signing_secret:
            if not SlackArchitectService.verify_signature(raw_body, timestamp, signature, signing_secret):
                current_app.logger.warning("slack: invalid request signature from %s", request.remote_addr)
                return jsonify({"error": "Invalid signature"}), 401

        payload = request.get_json(silent=True) or {}

        # Slack URL verification handshake
        if payload.get("type") == "url_verification":
            return jsonify({"challenge": payload.get("challenge", "")})

        # Dispatch event asynchronously to avoid Slack's 3s timeout
        import threading
        threading.Thread(
            target=SlackArchitectService.handle_event,
            args=(payload,),
            daemon=True,
        ).start()

        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.error("slack events receiver error: %s", exc)
        return jsonify({"ok": False}), 500


# ---------------------------------------------------------------------------
# Microsoft Teams / Graph change notification receiver
# ---------------------------------------------------------------------------

@webhook_bp.route("/teams/notifications", methods=["POST"])
# csrf.exempt: Microsoft Graph cannot include CSRF tokens
@csrf.exempt
def teams_notifications():
    """Receive Microsoft Graph callRecords change notifications."""
    try:
        from app.services.teams_meeting_service import TeamsMeetingService

        # Graph sends a validationToken query param for subscription validation
        validation_token = request.args.get("validationToken")
        if validation_token:
            # Echo the token back as plain text to confirm the endpoint
            from flask import Response
            return Response(validation_token, content_type="text/plain")

        payload = request.get_json(silent=True) or {}

        import threading
        threading.Thread(
            target=TeamsMeetingService.handle_notification,
            args=(payload,),
            daemon=True,
        ).start()

        return "", 202
    except Exception as exc:
        current_app.logger.error("teams notifications receiver error: %s", exc)
        return "", 500


@webhook_bp.route("/public/events", methods=["POST"])
@require_auth
@audit_log("webhook_event_publish")
def publish_event():
    """Publish a custom event to all subscribed webhooks"""
    try:
        user_id = str(current_user.id)  # webhook tables store user_id as String(36)
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        required_fields = ["event_type", "payload"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"success": False, "error": f"Missing required field: {field}"}
                ), 400

        service = WebhookService()
        event = service.publish_event(
            event_type=data["event_type"],
            payload=data["payload"],
            user_id=user_id,
            metadata=data.get("metadata", {}),
        )

        return jsonify({"success": True, "data": event.to_dict()}), 201

    except Exception as e:
        current_app.logger.error(f"Error publishing webhook event: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to publish webhook event"}
        ), 500
