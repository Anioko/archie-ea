"""Typed ARB condition child routes for HTML form submission.

`typed-arb-ui-blueprint.md` §11 requires, alongside the canonical JSON ingress:

    HTML forms use POST /arb/reviews/<review_item_id>/decision and typed child
    routes POST /arb/reviews/<review_item_id>/conditions/<condition_id>/
    {evidence,verify,waive}.  Each explicitly tenant-loads the review, cycle and
    child and proves exact membership before calling the same services.  Success
    is a 303 redirect to the relevant anchor; validation/conflict rerenders the
    same page with submitted safe values retained.

The three condition child routes are this module.  Before it existed the typed
condition forms in ``arb/partials/_typed_conditions.html`` posted directly at
``/arb/api/conditions/...``: with JavaScript disabled or broken, a native form
submit sent ``application/x-www-form-urlencoded`` to a JSON handler, which read
an empty body and answered a raw JSON 400 in the browser window.  There was no
non-JS path through condition governance at all.

**This module forks no logic.**  Every tenant load, membership proof, evidence
normalisation rule, waiver bound and idempotency-key derivation is imported from
``arb_condition_routes`` and reused verbatim; only the transport differs — a form
body in, a 303 redirect or a flashed rerender out.  If the JSON rules change, the
HTML surface changes with them and cannot drift.

Design notes specific to the HTML transport:

*Two command boundaries, one form.*  §9 requires the HTML handler to mirror the
capture/submit split.  ``POST .../evidence`` therefore calls
``TypedARBConditionEvidenceService.capture`` and then
``TypedARBConditionLifecycleService.submit_evidence`` with distinct derived keys.
When capture succeeds and submission fails, the response says exactly that and
carries the ``condition_evidence_id`` forward so the next attempt re-submits the
*same* record.  It never invites a recapture, which would create a second
immutable evidence row, and it never claims the condition advanced.

*Membership is proved twice, on purpose.*  The URL names a review item as well as
a condition, so this layer also proves ``condition.review_item_id`` equals the
review in the path.  A correct condition id under the wrong review is a 404,
identical to a foreign one, so a probe learns nothing.

*Naive local times.*  A ``datetime-local`` control yields a naive string and the
server cannot know the browser's zone.  With JavaScript the client converts to a
UTC instant before posting JSON.  Without it, this module interprets a naive
value as **UTC**, and the form says so beside the field — a stated interpretation,
not an invented one.  An explicit offset or ``Z`` in the submitted value is
honoured as given.

*Retained values.*  A rejected waiver keeps the operator's reason, scope and
compensating control (never a hash, status or identity) in the session under a
single-read key, so the rerendered page can repopulate the form without the
values travelling through the URL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, request, session, url_for
from flask_login import login_required

from app.modules.architecture.routes import arb_condition_routes as api
from app.modules.transformation_room.arb_condition_evidence_service import (
    TypedARBConditionEvidenceService,
)
from app.modules.transformation_room.arb_condition_lifecycle_service import (
    TypedARBConditionLifecycleService,
)
from app.modules.transformation_room.domain import (
    AuthenticationRequired,
    BlockedByEvidence,
    CommandConflict,
    KnownPreCommitTransient,
    NotAuthorised,
    NotFound,
)


arb_conditions_html_bp = Blueprint(
    "arb_conditions_html", __name__, url_prefix="/arb/reviews"
)


#: Session key holding the safe values of one rejected submission (§11: "rerenders
#: the same page with submitted safe values retained"). Read once, then cleared.
RETAINED_SESSION_KEY = "arb_condition_form_retained"

#: Fields that may be retained and re-rendered. Everything else a form carried —
#: hashes, ids, statuses — is derived or proved server-side and is never echoed.
_RETAINABLE = frozenset({
    "mode", "statement", "observed_at", "source_identity", "source_type",
    "source_version", "expires_at", "value", "reason", "scope",
    "compensating_control",
})

#: One operator-readable sentence per §13 status. The stable reason codes stay in
#: the JSON surface; a person reading a governance page needs the consequence.
_STATUS_MESSAGES = {
    400: "That submission was not accepted. Check the highlighted fields and try again.",
    401: "Your session has expired. Sign in and try again.",
    403: "You are not authorised to take this action on this condition.",
    404: "That condition is no longer available on this review.",
    409: (
        "This review changed before your action was recorded. "
        "Reload the current review and try again."
    ),
    422: "This action was refused because a governance precondition was not met.",
    503: "The command was not confirmed. Retry the action.",
}
_FALLBACK_MESSAGE = "The action could not be completed."


@arb_conditions_html_bp.app_context_processor
def _inject_retained_condition_form():
    """Hand the rejected submission's safe values to the next render, once.

    Popped here rather than in the template so the read is a genuine single use:
    the operator sees their text on the page they were bounced back to, and a
    later unrelated render of the same page does not resurrect it.
    """
    retained = session.pop(RETAINED_SESSION_KEY, None)
    return {"arb_condition_retained": retained if isinstance(retained, dict) else {}}


def _anchor_url(review_item_id, condition_id):
    """Back to the review, landing on this condition's card (§9 anchor contract)."""
    return url_for("arb.review_detail", id=review_item_id) + f"#condition-{condition_id}"


def _see_other(review_item_id, condition_id):
    return redirect(_anchor_url(review_item_id, condition_id), code=303)


def _retain(form):
    """Stash only the operator's own free text for the rerender."""
    kept = {
        name: value
        for name, value in form.items()
        if name in _RETAINABLE and isinstance(value, str) and value.strip()
    }
    if kept:
        session[RETAINED_SESSION_KEY] = kept


def _aware_isoformat(raw):
    """Normalise one form datetime to an aware ISO instant, or return it unchanged.

    A ``datetime-local`` value is naive; this reads it as UTC (the form says so).
    A value that already carries an offset or ``Z`` is returned untouched so the
    shared validator sees exactly what the client meant. An unparseable value is
    also returned untouched, so the single rejection path stays in the validator
    rather than being duplicated here with a different code.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw
    candidate = raw.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return candidate
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _evidence_body(form):
    """Form fields -> the JSON body the shared normaliser already validates.

    Only fields the JSON surface allow-lists are forwarded, and only when the
    operator actually filled them in: an empty text input must look absent, not
    like a submitted empty string, or the shared validator would reject the form
    for a field the operator was never asked to complete.
    """
    mode = (form.get("mode") or "").strip()
    body = {"mode": mode}
    if mode == "source_backed":
        names = ("source_identity", "source_type", "source_version",
                 "observed_at", "expires_at", "value")
    else:
        names = ("statement", "observed_at")
    for name in names:
        value = form.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        if name in ("observed_at", "expires_at"):
            body[name] = _aware_isoformat(value)
        else:
            body[name] = value
    return body


def _waiver_body(form):
    body = {}
    for name in ("reason", "scope", "compensating_control", "expires_at"):
        value = form.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        body[name] = _aware_isoformat(value) if name == "expires_at" else value
    return body


def _positive_int(form, name):
    raw = (form.get(name) or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _fail(review_item_id, condition_id, status, message=None):
    flash(message or _STATUS_MESSAGES.get(status, _FALLBACK_MESSAGE), "error")
    return _see_other(review_item_id, condition_id), status


def _handle(review_item_id, condition_id, view):
    """Run a form handler, mapping every known failure onto §13 + a flashed line."""
    request_id = api._request_id()
    try:
        return view(request_id)
    except api._RequestRejected as rejected:
        _retain(request.form)
        return _fail(review_item_id, condition_id, rejected.status)
    except AuthenticationRequired:
        return _fail(review_item_id, condition_id, 401)
    except NotFound:
        return _fail(review_item_id, condition_id, 404)
    except NotAuthorised:
        return _fail(review_item_id, condition_id, 403)
    except BlockedByEvidence:
        _retain(request.form)
        return _fail(review_item_id, condition_id, 422)
    except CommandConflict:
        _retain(request.form)
        return _fail(review_item_id, condition_id, 409)
    except KnownPreCommitTransient:
        _retain(request.form)
        return _fail(review_item_id, condition_id, 503)
    except Exception:
        current_app.logger.exception(
            "[ARB] typed condition HTML command failed request_id=%s", request_id
        )
        _retain(request.form)
        return _fail(review_item_id, condition_id, 500)


def _resolve(request_id, review_item_id, condition_id):
    """Shared tenant load plus the extra proof that the URL's review is the right one."""
    actor = api._actor(request_id)
    condition, decision, cycle, review = api._resolve_condition_graph(
        actor, condition_id
    )
    if review.id != review_item_id:
        # A real condition reached through the wrong review is answered exactly
        # like a foreign one, so the pairing cannot be probed.
        raise NotFound("arb_condition_not_found")
    return actor, condition, decision, cycle, review


@arb_conditions_html_bp.route(
    "/<int:review_item_id>/conditions/<int:condition_id>/evidence", methods=["POST"]
)
@login_required
def submit_condition_evidence(review_item_id, condition_id):
    """Capture evidence, then submit it — two commands, honestly reported."""

    def view(request_id):
        actor, condition, _decision, _cycle, _review = _resolve(
            request_id, review_item_id, condition_id
        )
        already = _positive_int(request.form, "condition_evidence_id")
        if already is None:
            body = api._normalise_evidence(
                _evidence_body(request.form), actor, api._server_now()
            )
            captured = TypedARBConditionEvidenceService.capture(
                actor=actor,
                command_key=api._idempotency_key(request_id, "capture"),
                condition_id=condition.id,
                evidence=body,
            )
            evidence_id = dict(captured.response).get("condition_evidence_id")
        else:
            # Retry path: the record already exists and is immutable. Prove it
            # belongs to this graph, then re-submit that exact id.
            evidence_id = already
        if not isinstance(evidence_id, int) or evidence_id <= 0:
            flash(
                "The server did not return an evidence identifier, so nothing "
                "was recorded. Try again.",
                "error",
            )
            return _see_other(review_item_id, condition_id), 502

        actor, condition, decision, cycle, review = _resolve(
            request_id, review_item_id, condition_id
        )
        evidence = api._resolve_evidence(
            actor, condition, decision, cycle, review, evidence_id
        )
        try:
            TypedARBConditionLifecycleService.submit_evidence(
                actor=actor,
                command_key=api._idempotency_key(request_id, "submit"),
                condition_id=condition.id,
                condition_evidence_id=evidence.id,
            )
        except (BlockedByEvidence, CommandConflict, KnownPreCommitTransient,
                NotAuthorised):
            # Capture succeeded; only the lifecycle half failed. Say exactly that
            # and carry the id forward — a recapture would create a second row.
            session[RETAINED_SESSION_KEY] = {"condition_evidence_id": str(evidence.id)}
            flash(
                "Evidence captured, not submitted. The evidence record exists and "
                f"is immutable (ID {evidence.id}). Retry the submission — capturing "
                "again would create a second evidence record.",
                "warning",
            )
            return _see_other(review_item_id, condition_id), 409

        flash("Evidence submitted for verification.", "success")
        return _see_other(review_item_id, condition_id)

    return _handle(review_item_id, condition_id, view)


@arb_conditions_html_bp.route(
    "/<int:review_item_id>/conditions/<int:condition_id>/verify", methods=["POST"]
)
@login_required
def verify_condition_evidence(review_item_id, condition_id):
    """Verify submitted evidence. Separation of duties is enforced by the command."""

    def view(request_id):
        actor, condition, decision, cycle, review = _resolve(
            request_id, review_item_id, condition_id
        )
        evidence_id = _positive_int(request.form, "condition_evidence_id")
        if evidence_id is None:
            api._reject(
                400, "condition_evidence_id_invalid",
                field_errors=[{"field": "condition_evidence_id", "code": "required"}],
            )
        evidence = api._resolve_evidence(
            actor, condition, decision, cycle, review, evidence_id
        )
        TypedARBConditionLifecycleService.verify(
            actor=actor,
            command_key=api._idempotency_key(request_id, "verify"),
            condition_id=condition.id,
            condition_evidence_id=evidence.id,
        )
        flash("Evidence verified.", "success")
        return _see_other(review_item_id, condition_id)

    return _handle(review_item_id, condition_id, view)


@arb_conditions_html_bp.route(
    "/<int:review_item_id>/conditions/<int:condition_id>/waive", methods=["POST"]
)
@login_required
def waive_condition(review_item_id, condition_id):
    """Grant a time-bound waiver. It does not remove the condition and has no undo."""

    def view(request_id):
        actor, condition, _decision, _cycle, _review = _resolve(
            request_id, review_item_id, condition_id
        )
        waiver = api._normalise_waiver(_waiver_body(request.form), api._server_now())
        TypedARBConditionLifecycleService.waive(
            actor=actor,
            command_key=api._idempotency_key(request_id, "waive"),
            condition_id=condition.id,
            reason=waiver["reason"],
            expires_at=waiver["expires_at"],
            scope=waiver["scope"],
            compensating_control=waiver["compensating_control"],
        )
        flash("Waiver granted. It expires automatically and does not remove the condition.",
              "success")
        return _see_other(review_item_id, condition_id)

    return _handle(review_item_id, condition_id, view)


__all__ = ["arb_conditions_html_bp", "RETAINED_SESSION_KEY"]
