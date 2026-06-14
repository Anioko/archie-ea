"""Teams meeting intelligence — Phase 2.

Subscribes to Microsoft Graph callRecords change notifications. When a
meeting ends, fetches the transcript and runs AI Architect analysis to:
  - Extract architectural decisions and application mentions
  - Surface risk and technical debt signals
  - Create in-app Notifications via GovernanceNotifier

Requires M365 credentials already configured at Admin → Connectors → M365.
Extra config stored in APISettings (provider='teams_meetings', key_label='default'):
    jira_url            — Graph subscription ID (written back after creation)
    custom_endpoint_url — Public notification receiver URL
    custom_headers      — JSON: {"transcript_analysis": bool, "signal_creation": bool}
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from app.services.m365_service import GRAPH_BASE, M365Service

logger = logging.getLogger(__name__)

_PROVIDER = "teams_meetings"
_LABEL = "default"
_CLIENT_STATE = "archie-teams-meeting-intelligence"


class TeamsMeetingService:

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def _settings_row(cls):
        try:
            from app.models.models import APISettings
            return APISettings.query.filter_by(provider=_PROVIDER, key_label=_LABEL).first()
        except Exception as exc:
            logger.debug("teams_meetings: settings load error: %s", exc)
            return None

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        row = cls._settings_row()
        extras = {}
        if row:
            try:
                extras = json.loads(row.custom_headers or "{}")
            except Exception:
                pass
        svc = M365Service()
        m365_configured = bool(svc._get_config())
        return {
            "m365_configured": m365_configured,
            "subscription_id": row.jira_url if row else "",
            "notification_url": row.custom_endpoint_url if row else "",
            "transcript_analysis": extras.get("transcript_analysis", True),
            "signal_creation": extras.get("signal_creation", True),
        }

    @classmethod
    def save_config(cls, notification_url: str, transcript_analysis: bool,
                    signal_creation: bool) -> None:
        from app.models.models import APISettings
        from app import db
        row = APISettings.query.filter_by(provider=_PROVIDER, key_label=_LABEL).first()
        extras = json.dumps({"transcript_analysis": transcript_analysis,
                             "signal_creation": signal_creation})
        if row:
            row.custom_endpoint_url = notification_url
            row.custom_headers = extras
        else:
            row = APISettings(
                provider=_PROVIDER,
                key_label=_LABEL,
                api_key="",
                jira_url="",
                custom_endpoint_url=notification_url,
                custom_headers=extras,
                enabled=True,
            )
            db.session.add(row)
        db.session.commit()

    @classmethod
    def _save_subscription_id(cls, subscription_id: str) -> None:
        from app.models.models import APISettings
        from app import db
        row = APISettings.query.filter_by(provider=_PROVIDER, key_label=_LABEL).first()
        if row:
            row.jira_url = subscription_id
            db.session.commit()

    # ------------------------------------------------------------------ #
    # Graph subscription management                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def subscribe_to_call_records(cls, notification_url: str) -> Dict[str, Any]:
        """Register a Graph callRecords change subscription."""
        svc = M365Service()
        config = svc._get_config()
        if not config:
            return {
                "status": "error",
                "error": "M365 is not configured. Set it up at Admin → Connectors → M365 first.",
            }
        token = svc._get_token(config)
        if not token:
            return {"status": "error", "error": "Failed to obtain Graph access token."}

        expiry = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
        body = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": "/communications/callRecords",
            "expirationDateTime": expiry,
            "clientState": _CLIENT_STATE,
        }
        try:
            resp = requests.post(
                f"{GRAPH_BASE}/subscriptions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=15,
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                sub_id = data.get("id", "")
                cls._save_subscription_id(sub_id)
                logger.info("teams_meetings: subscribed, id=%s expiry=%s", sub_id, expiry)
                return {"status": "ok", "subscription_id": sub_id, "expiry": expiry}
            err_msg = data.get("error", {}).get("message") or str(data)
            return {"status": "error", "error": err_msg, "http_status": resp.status_code}
        except Exception as exc:
            logger.error("teams_meetings: subscription request failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    @classmethod
    def renew_subscription(cls, subscription_id: str) -> Dict[str, Any]:
        """Extend an existing subscription by 3 more days."""
        svc = M365Service()
        config = svc._get_config()
        if not config:
            return {"status": "error", "error": "M365 not configured."}
        token = svc._get_token(config)
        if not token:
            return {"status": "error", "error": "Token fetch failed."}
        expiry = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
        try:
            resp = requests.patch(
                f"{GRAPH_BASE}/subscriptions/{subscription_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"expirationDateTime": expiry},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"status": "ok", "expiry": expiry}
            return {"status": "error", "error": resp.text[:200], "http_status": resp.status_code}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @classmethod
    def renew_if_needed(cls) -> Dict[str, Any]:
        """Renew the Graph subscription; re-create it if Graph no longer has it.

        Called by APScheduler twice daily (subscriptions expire every 3 days,
        so each expiry window gets ~6 renewal attempts). No-op when meeting
        intelligence was never set up. Renewal is idempotent — concurrent
        gunicorn workers double-PATCHing is harmless.
        """
        cfg = cls.get_config()
        sub_id = cfg.get("subscription_id")
        if not sub_id:
            return {"status": "skipped", "reason": "no subscription on record"}
        if not cfg.get("m365_configured"):
            return {"status": "skipped", "reason": "M365 not configured"}

        result = cls.renew_subscription(sub_id)
        if result.get("status") == "ok":
            logger.info("teams_meetings: auto-renewed subscription %s until %s",
                        sub_id, result.get("expiry"))
            return result

        # Graph lost the subscription (expired beyond renewal or deleted) —
        # re-create it with the stored notification URL. The admin opted in
        # when they first subscribed; re-creating restores that state.
        if result.get("http_status") == 404 and cfg.get("notification_url"):
            logger.warning("teams_meetings: subscription %s gone on Graph side — re-creating", sub_id)
            recreated = cls.subscribe_to_call_records(cfg["notification_url"])
            if recreated.get("status") == "ok":
                logger.info("teams_meetings: re-created subscription as %s",
                            recreated.get("subscription_id"))
            else:
                logger.error("teams_meetings: re-creation failed: %s", recreated.get("error"))
            return recreated

        logger.error("teams_meetings: auto-renewal failed for %s: %s", sub_id, result.get("error"))
        return result

    # ------------------------------------------------------------------ #
    # Notification handler (called from the webhook receiver route)        #
    # ------------------------------------------------------------------ #

    @classmethod
    def handle_notification(cls, data: Dict) -> None:
        """Process a Graph callRecords change notification payload."""
        cfg = cls.get_config()
        if not cfg.get("transcript_analysis"):
            return
        for notification in data.get("value", []):
            if notification.get("clientState") != _CLIENT_STATE:
                logger.debug("teams_meetings: unexpected clientState, skipping")
                continue
            call_id = cls._extract_call_id(notification)
            if call_id:
                cls._process_call_record(call_id, cfg)

    @staticmethod
    def _extract_call_id(notification: Dict) -> Optional[str]:
        resource_data = notification.get("resourceData", {})
        if resource_data.get("id"):
            return resource_data["id"]
        resource_url = notification.get("resource", "")
        if resource_url:
            return resource_url.rstrip("/").split("/")[-1] or None
        return None

    @classmethod
    def _process_call_record(cls, call_id: str, cfg: Dict) -> None:
        logger.info("teams_meetings: processing call record %s", call_id)
        transcript = cls._fetch_transcript(call_id)
        if not transcript:
            logger.info("teams_meetings: no transcript available for call %s", call_id)
            return
        analysis = cls._analyze_transcript(transcript, call_id)
        if analysis and cfg.get("signal_creation"):
            cls._create_signals(analysis, call_id)

    # ------------------------------------------------------------------ #
    # Transcript fetching                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def _fetch_transcript(cls, call_id: str) -> Optional[str]:
        svc = M365Service()
        config = svc._get_config()
        if not config:
            return None
        token = svc._get_token(config)
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        try:
            # List transcripts for this call
            resp = requests.get(
                f"{GRAPH_BASE}/communications/callRecords/{call_id}/transcripts",
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug("teams_meetings: transcript list %d for %s", resp.status_code, call_id)
                return None
            transcripts = resp.json().get("value", [])
            if not transcripts:
                return None
            transcript_id = transcripts[0].get("id")
            # Fetch VTT content
            vtt = requests.get(
                f"{GRAPH_BASE}/communications/callRecords/{call_id}"
                f"/transcripts/{transcript_id}/content",
                headers=headers,
                timeout=15,
            )
            return vtt.text if vtt.status_code == 200 else None
        except Exception as exc:
            logger.error("teams_meetings: transcript fetch failed for %s: %s", call_id, exc)
            return None

    # ------------------------------------------------------------------ #
    # AI analysis                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _analyze_transcript(cls, transcript: str, call_id: str) -> Optional[Dict]:
        text = transcript[:4000]  # fit within LLM context
        try:
            from app.models.application_portfolio import ApplicationComponent
            from app.modules.ai_chat.services.llm_service_impl import LLMService

            app_names = ", ".join(
                a.name for a in ApplicationComponent.query.with_entities(
                    ApplicationComponent.name
                ).limit(100).all() if a.name
            )
            prompt = (
                "You are an enterprise architecture analyst. Extract architecture signals from "
                "this meeting transcript.\n\n"
                f"Known portfolio applications: {app_names}\n\n"
                "Return JSON with exactly these keys:\n"
                '  "decisions": list of architectural decisions made (strings)\n'
                '  "app_mentions": list of portfolio application names mentioned\n'
                '  "risks": list of risk or technical debt mentions (strings)\n'
                '  "action_items": list of follow-up architecture actions\n\n'
                f"Transcript:\n{text}\n\n"
                "Return only valid JSON. No markdown code fences."
            )
            llm = LLMService()
            raw = (llm._call_llm(prompt, model=None, provider=None,
                                 user_id=None, max_tokens=600) or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
            return json.loads(raw)
        except Exception as exc:
            logger.warning("teams_meetings: analysis failed for %s: %s", call_id, exc)
            return None

    # ------------------------------------------------------------------ #
    # Signal creation                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create_signals(cls, analysis: Dict, call_id: str) -> None:
        decisions = analysis.get("decisions", [])[:3]
        risks = analysis.get("risks", [])[:3]
        app_mentions = analysis.get("app_mentions", [])

        items = (
            [{"title": f"Meeting Decision: {d}", "severity": "info"} for d in decisions]
            + [{"title": f"Meeting Risk: {r}", "severity": "high"} for r in risks]
        )
        if not items:
            return

        # Build a Composer diagram for apps mentioned in the meeting
        source_url = "http://127.0.0.1/dashboard/overview"
        if app_mentions:
            try:
                from app.services.archimate_composer_service import (
                    element_ids_for_apps, create_diagram, full_composer_url,
                )
                el_ids = element_ids_for_apps(app_mentions)
                if el_ids:
                    apps_label = ", ".join(app_mentions[:3])
                    rel = create_diagram(
                        el_ids,
                        name=f"Meeting {call_id[:8]}: {apps_label[:50]}",
                    )
                    if rel:
                        source_url = full_composer_url(rel)
                        logger.info(
                            "teams_meetings: composer diagram created for call %s: %s",
                            call_id[:8], source_url,
                        )
            except Exception as exc:
                logger.debug("teams_meetings: composer diagram skipped: %s", exc)

        try:
            from app.modules.solutions_strategic.v2.services.governance_notifier import (
                GovernanceNotifier,
            )
            GovernanceNotifier.push_findings(
                findings=items,
                source_label=f"Teams Meeting ({call_id[:8]})",
                source_url=source_url,
                send_email=False,
            )
            logger.info("teams_meetings: pushed %d signals for call %s", len(items), call_id)
        except Exception as exc:
            logger.error("teams_meetings: signal push failed: %s", exc)

        # Write architectural decisions to ARBAuditLog so they appear in EA governance trail
        if decisions:
            try:
                from app import db
                from app.models.architecture_review_board import ARBAuditLog
                for decision in decisions:
                    db.session.add(ARBAuditLog(
                        entity_type="meeting_decision",
                        entity_id=0,
                        entity_reference=f"teams_meeting:{call_id[:16]}",
                        action="decision",
                        action_description=decision[:500],
                        new_value={
                            "source": "teams_meeting",
                            "call_id": call_id,
                            "composer_url": source_url if "composer" in source_url else None,
                        },
                    ))
                db.session.commit()
                logger.info("teams_meetings: wrote %d ARB decisions for call %s", len(decisions), call_id[:8])
            except Exception as exc:
                logger.debug("teams_meetings: ARBAuditLog write failed: %s", exc)
                try:
                    from app import db
                    db.session.rollback()
                except Exception:
                    pass
