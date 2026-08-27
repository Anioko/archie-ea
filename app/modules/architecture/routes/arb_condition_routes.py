"""Typed ARB condition evidence, verification and waiver HTTP ingress.

`typed-arb-route-audit.md` recorded that **no HTTP/template/JS route currently
calls typed condition evidence or lifecycle services** — the commands existed
and only their tests invoked them.  This module is that missing ingress, built
to `typed-arb-ui-blueprint.md` §9 (interaction contract), §11 (route table and
payloads) and §13 (status codes).

Four routes, one per command boundary:

    POST /arb/api/conditions/<condition_id>/evidence
    POST /arb/api/conditions/<condition_id>/evidence/<evidence_id>/submit
    POST /arb/api/conditions/<condition_id>/evidence/<evidence_id>/verify
    POST /arb/api/conditions/<condition_id>/waive

Design rules this module is responsible for, none of which the services can
enforce on the caller's behalf:

*Tenancy.*  Every row is loaded with an explicit ``(id, organization_id)``
predicate through ``session.execute(select(...))``.  ``Query.get()`` and
``Session.get()`` are deliberately **not** used: per AGENTS.md they are tenant
scoped only on an identity-map miss, and return the cached object with no SQL
and therefore no tenant filter on a hit.  Exact membership (this condition
belongs to that cycle, that review and that decision event; this evidence
record belongs to that condition) is proved here before any service is called,
so a mismatch is answered by this layer rather than discovered mid-command.

*No client-selected state.*  Request bodies are strictly allow-listed.  The
browser never supplies ``organization_id``, an actor id, a condition status, a
review/cycle/decision id inside the evidence object, a content hash or a
freshness outcome.  ``ActorContext`` is constructed from the authenticated
session alone.

*Separation of duties.*  The routes never offer a way around it — there is no
"verify as" or "decide as" input — and a forged POST still fails, because the
lifecycle service re-checks the authenticated actor inside the locked command
and raises ``NotAuthorised``, which maps to 403 here.

*Idempotency.*  Capture and lifecycle submission are two distinct command
boundaries (§9), so they take related but distinct keys derived from one
client ``Idempotency-Key``.  Capture never chains into submission: a successful
capture returns ``status="captured"``, ``lifecycle_transitioned=false`` and
claims nothing about the condition having advanced, so a failed submission is
retried against the *same* ``condition_evidence_id`` without recapturing.

*Honest evidence modes.*  ``manual_attestation`` is recorded as an attestation
(``freshness_status=not_applicable``, ``arb-condition-not-applicable-v1``) and
is never dressed up as a measurement; a source-backed record must carry a
source identity, type, version, observed time and expiry, and an expired source
is rejected.

CSRF is the global ``CSRFProtect``.  No route here is exempt.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import select

from app.extensions import db
from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
from app.models.arb_decision_event import ARBCondition, ARBDecisionEvent
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.modules.transformation_room.arb_condition_evidence_service import (
    TypedARBConditionEvidenceService,
)
from app.modules.transformation_room.arb_condition_lifecycle_service import (
    TypedARBConditionLifecycleService,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    AuthenticationRequired,
    BlockedByEvidence,
    CommandConflict,
    KnownPreCommitTransient,
    NotAuthorised,
    NotFound,
)


arb_conditions_api_bp = Blueprint(
    "arb_conditions_api", __name__, url_prefix="/arb/api/conditions"
)


MAX_WAIVER_TEXT = 2000
MAX_WAIVER_DAYS = 365
MAX_ATTESTATION_CHARS = 4000
MAX_IDEMPOTENCY_KEY = 200

# Conflict and authorisation reasons that are safe to hand back verbatim: each
# names a state of the caller's own tenant and reveals nothing about another.
_SAFE_CONFLICT_REASONS = frozenset({
    "arb_condition_revision_changed",
    "arb_condition_not_pending",
    "arb_condition_transition_invalid",
    "arb_condition_evidence_membership_mismatch",
    "arb_condition_evidence_hash_round_trip_failed",
    "arb_condition_waiver_not_expired",
    "arb_condition_waiver_state_invalid",
    "arb_condition_command_identity_mismatch",
    "arb_condition_membership_mismatch",
})
_SAFE_AUTHORISATION_REASONS = frozenset({
    "arb_condition_verification_separation_required",
    "arb_condition_evidence_not_authorised",
    "arb_condition_transition_not_authorised",
    "arb_decision_not_authorised",
    "arb_decision_separation_of_duties",
})

_ATTESTATION_SOURCE_TYPE = "manual_attestation"
_ATTESTATION_RULE = TypedARBConditionEvidenceService.NOT_APPLICABLE_RULE
_SOURCE_BACKED_RULE = TypedARBConditionEvidenceService.FRESH_RULE


# ── request/response envelope ────────────────────────────────────────────────


class _RequestRejected(Exception):
    """A route-level validation failure with a stable, field-associated code."""

    def __init__(self, status, *reason_codes, field_errors=None):
        super().__init__(reason_codes[0] if reason_codes else "invalid_request")
        self.status = status
        self.reason_codes = list(reason_codes)
        self.field_errors = list(field_errors or ())


def _request_id():
    return uuid.uuid4().hex


def _failure(status, reason_codes, *, request_id, field_errors=None,
             missing_evidence=None):
    """The §13 failure envelope. Never raw exception text, never another tenant."""
    payload = {
        "success": False,
        "reason_codes": list(reason_codes),
        "request_id": request_id,
    }
    if field_errors:
        payload["field_errors"] = list(field_errors)
    if missing_evidence:
        payload["missing_evidence"] = list(missing_evidence)
    return jsonify(payload), status


def _reject(status, *reason_codes, field_errors=None):
    raise _RequestRejected(status, *reason_codes, field_errors=field_errors)


def _service_failure(error, request_id):
    """Map a typed-command domain error onto §13 without leaking its text."""
    if isinstance(error, AuthenticationRequired):
        return _failure(401, ["not_authenticated"], request_id=request_id)
    if isinstance(error, NotFound):
        # Deliberately one opaque code for a foreign *or* missing row, so a
        # cross-tenant probe cannot tell the two apart.
        return _failure(404, ["arb_condition_not_found"], request_id=request_id)
    if isinstance(error, NotAuthorised):
        reason = error.reason if error.reason in _SAFE_AUTHORISATION_REASONS else (
            "arb_condition_not_authorised"
        )
        return _failure(403, [reason], request_id=request_id)
    if isinstance(error, BlockedByEvidence):
        codes = error.details.get("reason_codes")
        missing = error.details.get("missing_evidence")
        return _failure(
            422,
            list(codes) if isinstance(codes, list) else ["arb_condition_blocked"],
            request_id=request_id,
            missing_evidence=list(missing) if isinstance(missing, list) else None,
        )
    if isinstance(error, CommandConflict):
        reason = error.reason if error.reason in _SAFE_CONFLICT_REASONS else (
            "arb_condition_conflict"
        )
        return _failure(409, [reason], request_id=request_id)
    if isinstance(error, KnownPreCommitTransient):
        return _failure(503, ["arb_condition_command_unconfirmed"],
                        request_id=request_id)
    return _failure(400, ["arb_condition_request_invalid"], request_id=request_id)


# ── authenticated actor ──────────────────────────────────────────────────────


def _actor(request_id):
    """ActorContext from the session only — never from the request body."""
    if not getattr(current_user, "is_authenticated", False):
        raise AuthenticationRequired("not_authenticated")
    organization_id = getattr(current_user, "organization_id", None)
    user_id = getattr(current_user, "id", None)
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise AuthenticationRequired("not_authenticated")
    if (
        not isinstance(organization_id, int)
        or isinstance(organization_id, bool)
        or organization_id <= 0
    ):
        # An authenticated principal with no tenant cannot address a tenant row.
        raise NotAuthorised("arb_condition_not_authorised")
    role = getattr(current_user, "enterprise_role", None)
    roles = frozenset({role}) if isinstance(role, str) and role else frozenset()
    return ActorContext(user_id, organization_id, roles, request_id)


# ── strictly allow-listed request bodies ─────────────────────────────────────


def _json_body():
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        _reject(400, "request_body_invalid")
    return body


def _allow_only(body, allowed):
    unknown = sorted(set(body) - set(allowed))
    if unknown:
        _reject(
            400,
            "request_field_not_accepted",
            field_errors=[
                {"field": name, "code": "field_not_accepted"} for name in unknown
            ],
        )


def _no_body(body):
    """submit/verify take no state or identity body at all (§11)."""
    if body:
        _reject(
            400,
            "request_field_not_accepted",
            field_errors=[
                {"field": name, "code": "field_not_accepted"}
                for name in sorted(body)
            ],
        )


def _text(body, field, limit, *, required=True):
    value = body.get(field)
    if value is None and not required:
        return None
    if not isinstance(value, str):
        _reject(400, f"{field}_invalid",
                field_errors=[{"field": field, "code": "required"}])
    collapsed = " ".join(value.split())
    if not collapsed:
        _reject(400, f"{field}_invalid",
                field_errors=[{"field": field, "code": "required"}])
    if len(collapsed) > limit:
        _reject(400, f"{field}_too_long",
                field_errors=[{"field": field, "code": "too_long",
                               "limit": limit}])
    return collapsed


def _aware_datetime(body, field):
    value = body.get(field)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    else:
        parsed = None
    if parsed is None:
        _reject(400, f"{field}_invalid",
                field_errors=[{"field": field, "code": "invalid_datetime"}])
    if parsed.tzinfo is None:
        _reject(400, f"{field}_not_timezone_aware",
                field_errors=[{"field": field, "code": "timezone_required"}])
    return parsed.astimezone(timezone.utc)


def _idempotency_key(request_id, suffix):
    """One client key, two related-but-distinct command keys.

    Capture and lifecycle submission are separate command boundaries, so they
    must not collide on one key; deriving both from the client's key keeps a
    retry of either half addressable without recapturing evidence.
    """
    supplied = request.headers.get("Idempotency-Key")
    if supplied is None:
        base = request_id
    else:
        base = supplied.strip()
        if (
            not base
            or len(base) > MAX_IDEMPOTENCY_KEY
            or any(ord(character) < 32 or ord(character) == 127 for character in base)
        ):
            _reject(400, "idempotency_key_invalid",
                    field_errors=[{"field": "Idempotency-Key",
                                   "code": "invalid"}])
    return f"{base}:{suffix}"


# ── tenant resolution and exact membership ───────────────────────────────────


def _load_scoped(model, object_id, organization_id):
    """Explicit ``(id, organization_id)`` load. Never ``Session.get()``."""
    return db.session.execute(
        select(model).where(
            model.id == object_id,
            model.organization_id == organization_id,
        )
    ).scalar_one_or_none()


def _resolve_condition_graph(actor, condition_id):
    """Resolve condition, decision event, cycle and review inside the tenant.

    Returns ``(condition, decision, cycle, review)``. Raises ``NotFound`` for a
    foreign or missing row — one indistinguishable answer, so a cross-tenant
    probe learns nothing — and ``CommandConflict`` when the rows exist in this
    tenant but do not form one exact typed graph.
    """
    condition = _load_scoped(ARBCondition, condition_id, actor.organization_id)
    if condition is None:
        raise NotFound("arb_condition_not_found")
    cycle = _load_scoped(
        ARBReviewCycle, condition.review_cycle_id, actor.organization_id
    )
    review = _load_scoped(
        ARBReviewItem, condition.review_item_id, actor.organization_id
    )
    decision = _load_scoped(
        ARBDecisionEvent, condition.decision_event_id, actor.organization_id
    )
    if cycle is None or review is None or decision is None:
        raise NotFound("arb_condition_not_found")
    if (
        condition.review_cycle_id != cycle.id
        or condition.review_item_id != review.id
        or condition.decision_event_id != decision.id
        or decision.review_cycle_id != cycle.id
        or decision.review_item_id != review.id
        or cycle.organization_id != actor.organization_id
        or review.organization_id != actor.organization_id
    ):
        raise CommandConflict("arb_condition_membership_mismatch")
    return condition, decision, cycle, review


def _resolve_evidence(actor, condition, decision, cycle, review, evidence_id):
    """Prove this evidence record belongs to exactly this condition graph."""
    evidence = _load_scoped(
        ARBConditionEvidenceRecord, evidence_id, actor.organization_id
    )
    if evidence is None:
        raise NotFound("arb_condition_not_found")
    if (
        evidence.condition_id != condition.id
        or evidence.decision_event_id != decision.id
        or evidence.review_cycle_id != cycle.id
        or evidence.review_item_id != review.id
    ):
        raise CommandConflict("arb_condition_evidence_membership_mismatch")
    return evidence


# ── evidence normalisation: two honest modes (§9) ────────────────────────────


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _derived_checksum(value):
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalise_evidence(body, actor, now):
    """Build the trusted evidence object the capture service accepts.

    The caller supplies only what a human can honestly know: which mode, the
    statement or the source coordinates, the observed time and (source-backed)
    the expiry.  Identity for an attestation, both checksums, the freshness
    outcome and the schema version are all derived here.
    """
    mode = body.get("mode")
    if mode == _ATTESTATION_SOURCE_TYPE:
        return _normalise_attestation(body, actor, now)
    if mode == "source_backed":
        return _normalise_source_backed(body, now)
    _reject(400, "evidence_mode_invalid",
            field_errors=[{"field": "mode", "code": "unsupported"}])


def _normalise_attestation(body, actor, now):
    _allow_only(body, {"mode", "statement", "observed_at"})
    statement = _text(body, "statement", MAX_ATTESTATION_CHARS)
    observed_at = _aware_datetime(body, "observed_at")
    if observed_at > now:
        _reject(400, "observed_at_in_future",
                field_errors=[{"field": "observed_at", "code": "in_future"}])
    # The stored value states plainly that this is a person's assertion. It is
    # never shaped like a measured reading.
    value_json = {
        "evidence_mode": _ATTESTATION_SOURCE_TYPE,
        "statement": statement,
        "attested_by_user_id": actor.user_id,
        "attested_at": observed_at.isoformat().replace("+00:00", "Z"),
    }
    return {
        "source_identity": f"manual-attestation:user:{actor.user_id}",
        "source_type": _ATTESTATION_SOURCE_TYPE,
        "source_version": "1",
        "source_checksum": _derived_checksum(value_json),
        "value_json": value_json,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "freshness_rule_version": _ATTESTATION_RULE,
        "freshness_status": "not_applicable",
        "freshness_expires_at": None,
    }


def _normalise_source_backed(body, now):
    _allow_only(body, {
        "mode", "source_identity", "source_type", "source_version",
        "observed_at", "expires_at", "value",
    })
    source_identity = _text(body, "source_identity", 1024)
    source_type = _text(body, "source_type", 80)
    source_version = _text(body, "source_version", 512)
    if source_type == _ATTESTATION_SOURCE_TYPE:
        # An attestation must be submitted as one. Letting a caller label a
        # source-backed record "manual_attestation" would present a person's
        # assertion as a measurement, or the reverse.
        _reject(400, "source_type_reserved",
                field_errors=[{"field": "source_type", "code": "reserved"}])
    value = body.get("value")
    if not isinstance(value, (dict, list)) or not value:
        _reject(400, "value_invalid",
                field_errors=[{"field": "value", "code": "required"}])
    observed_at = _aware_datetime(body, "observed_at")
    if observed_at > now:
        _reject(400, "observed_at_in_future",
                field_errors=[{"field": "observed_at", "code": "in_future"}])
    expires_at = _aware_datetime(body, "expires_at")
    if expires_at <= now:
        # An expired source is not evidence of anything current. 422: the
        # request is well-formed, the evidence itself is the blocker.
        _reject(422, "arb_condition_evidence_source_expired",
                field_errors=[{"field": "expires_at", "code": "expired"}])
    if expires_at <= observed_at:
        _reject(400, "expires_at_before_observed_at",
                field_errors=[{"field": "expires_at",
                               "code": "before_observed_at"}])
    return {
        "source_identity": source_identity,
        "source_type": source_type,
        "source_version": source_version,
        "source_checksum": _derived_checksum(value),
        "value_json": value,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "freshness_rule_version": _SOURCE_BACKED_RULE,
        "freshness_status": "fresh",
        "freshness_expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }


def _normalise_waiver(body, now):
    """§9/§11 waiver validation, entirely ahead of the command.

    A rejected waiver must write no condition event, so every bound is checked
    here rather than inside the transaction.
    """
    _allow_only(body, {"reason", "expires_at", "scope", "compensating_control"})
    reason = _text(body, "reason", MAX_WAIVER_TEXT)
    control = _text(body, "compensating_control", MAX_WAIVER_TEXT)
    scope_value = body.get("scope")
    if isinstance(scope_value, dict):
        if set(scope_value) != {"description"}:
            _reject(400, "scope_invalid",
                    field_errors=[{"field": "scope", "code": "unsupported"}])
        description = _text(scope_value, "description", MAX_WAIVER_TEXT)
    elif isinstance(scope_value, str):
        description = _text(body, "scope", MAX_WAIVER_TEXT)
    else:
        _reject(400, "scope_invalid",
                field_errors=[{"field": "scope", "code": "required"}])
    expires_at = _aware_datetime(body, "expires_at")
    if expires_at <= now:
        _reject(422, "waiver_expiry_in_past",
                field_errors=[{"field": "expires_at", "code": "in_past"}])
    if expires_at > now + timedelta(days=MAX_WAIVER_DAYS):
        _reject(422, "waiver_expiry_too_far",
                field_errors=[{"field": "expires_at", "code": "too_far",
                               "limit_days": MAX_WAIVER_DAYS}])
    return {
        "reason": reason,
        "expires_at": expires_at,
        "scope": {"description": description},
        "compensating_control": control,
    }


def _server_now():
    return datetime.now(timezone.utc)


# ── success payloads (§11) ───────────────────────────────────────────────────


def _capture_payload(result, request_id):
    response = dict(result.response)
    return {
        "success": True,
        "condition_id": response.get("condition_id"),
        "condition_evidence_id": response.get("condition_evidence_id"),
        "review_cycle_id": response.get("review_cycle_id"),
        "condition_revision": response.get("condition_revision"),
        "status": "captured",
        # Capture is one command boundary. It never claims the condition moved.
        "lifecycle_transitioned": False,
        "idempotent": bool(result.idempotent),
        "request_id": request_id,
    }


def _lifecycle_payload(result, request_id):
    response = dict(result.response)
    return {
        "success": True,
        "condition_id": response.get("condition_id"),
        "condition_event_id": response.get("condition_event_id"),
        "condition_revision": response.get("condition_revision"),
        "review_cycle_id": response.get("review_cycle_id"),
        "review_item_id": response.get("review_item_id"),
        "status": response.get("status"),
        "projection_status": response.get("projection_status"),
        "idempotent": bool(result.idempotent),
        "request_id": request_id,
    }


def _handle(view):
    """Run a route body, converting every known failure into the §13 envelope."""
    request_id = _request_id()
    try:
        return view(request_id)
    except _RequestRejected as rejected:
        return _failure(rejected.status, rejected.reason_codes,
                        request_id=request_id,
                        field_errors=rejected.field_errors)
    except (AuthenticationRequired, NotFound, NotAuthorised, BlockedByEvidence,
            CommandConflict, KnownPreCommitTransient) as error:
        return _service_failure(error, request_id)
    except (ValueError, TypeError):
        current_app.logger.warning(
            "[ARB] typed condition command rejected input request_id=%s",
            request_id, exc_info=True,
        )
        return _failure(400, ["arb_condition_request_invalid"],
                        request_id=request_id)
    except Exception:
        current_app.logger.exception(
            "[ARB] typed condition command failed request_id=%s", request_id
        )
        return _failure(500, ["arb_condition_command_failed"],
                        request_id=request_id)


# ── routes ───────────────────────────────────────────────────────────────────


@arb_conditions_api_bp.route("/<int:condition_id>/evidence", methods=["POST"])
def capture_condition_evidence(condition_id):
    """Capture immutable evidence. Does not submit it — that is a second command."""

    def view(request_id):
        actor = _actor(request_id)
        condition, _decision, _cycle, _review = _resolve_condition_graph(
            actor, condition_id
        )
        body = _json_body()
        evidence = _normalise_evidence(body, actor, _server_now())
        command_key = _idempotency_key(request_id, "capture")
        result = TypedARBConditionEvidenceService.capture(
            actor=actor,
            command_key=command_key,
            condition_id=condition.id,
            evidence=evidence,
        )
        payload = _capture_payload(result, request_id)
        return jsonify(payload), (200 if result.idempotent else 201)

    return _handle(view)


@arb_conditions_api_bp.route(
    "/<int:condition_id>/evidence/<int:evidence_id>/submit", methods=["POST"]
)
def submit_condition_evidence(condition_id, evidence_id):
    """Submit already-captured evidence. Retryable without recapturing."""

    def view(request_id):
        actor = _actor(request_id)
        condition, decision, cycle, review = _resolve_condition_graph(
            actor, condition_id
        )
        evidence = _resolve_evidence(
            actor, condition, decision, cycle, review, evidence_id
        )
        _no_body(_json_body())
        command_key = _idempotency_key(request_id, "submit")
        result = TypedARBConditionLifecycleService.submit_evidence(
            actor=actor,
            command_key=command_key,
            condition_id=condition.id,
            condition_evidence_id=evidence.id,
        )
        return jsonify(_lifecycle_payload(result, request_id)), 200

    return _handle(view)


@arb_conditions_api_bp.route(
    "/<int:condition_id>/evidence/<int:evidence_id>/verify", methods=["POST"]
)
def verify_condition_evidence(condition_id, evidence_id):
    """Verify submitted evidence. Separation of duties is enforced by the command."""

    def view(request_id):
        actor = _actor(request_id)
        condition, decision, cycle, review = _resolve_condition_graph(
            actor, condition_id
        )
        evidence = _resolve_evidence(
            actor, condition, decision, cycle, review, evidence_id
        )
        _no_body(_json_body())
        command_key = _idempotency_key(request_id, "verify")
        result = TypedARBConditionLifecycleService.verify(
            actor=actor,
            command_key=command_key,
            condition_id=condition.id,
            condition_evidence_id=evidence.id,
        )
        return jsonify(_lifecycle_payload(result, request_id)), 200

    return _handle(view)


@arb_conditions_api_bp.route("/<int:condition_id>/waive", methods=["POST"])
def waive_condition(condition_id):
    """Grant a time-bound waiver. Decision authority only; there is no undo."""

    def view(request_id):
        actor = _actor(request_id)
        condition, _decision, _cycle, _review = _resolve_condition_graph(
            actor, condition_id
        )
        waiver = _normalise_waiver(_json_body(), _server_now())
        command_key = _idempotency_key(request_id, "waive")
        result = TypedARBConditionLifecycleService.waive(
            actor=actor,
            command_key=command_key,
            condition_id=condition.id,
            reason=waiver["reason"],
            expires_at=waiver["expires_at"],
            scope=waiver["scope"],
            compensating_control=waiver["compensating_control"],
        )
        return jsonify(_lifecycle_payload(result, request_id)), 200

    return _handle(view)


__all__ = ["arb_conditions_api_bp"]
