"""Contract coverage for the typed ARB governance interactions (lane 6).

Source-level assertions in the style of ``tests/test_broken_surface_fetch_contracts.py``.

These are deliberately static rather than behavioural. The defects they guard
against are all *shapes* in the shipped script, and every one of them is
invisible to a route test and to a rendered-template test:

* a native ``confirm()`` on a governance command, which no Playwright run can
  dismiss and which bypasses the platform modal's focus contract;
* a raw ``fetch()``, which does not reject on 4xx/5xx, so a 409 conflict reads
  as a success;
* a ``console.error`` standing in for a user-visible message, so the failure is
  reported to nobody;
* a body key the server's allow-list rejects with 400 — most dangerously
  ``organization_id`` or ``condition_revision``, which would let the browser
  choose tenancy or governance state;
* and the capture/submit hazard: a fallback from the captured-not-submitted
  state back into a fresh capture, which silently writes a SECOND immutable
  evidence record for the same fact.

The last one is the reason this file exists. Nothing else in the stack can
detect it: both requests succeed, both return 201, and the ledger simply grows
a duplicate that no later reader can adjudicate.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app" / "static" / "js" / "arb" / "typed_governance.js"
CONDITIONS_TEMPLATE = (
    ROOT / "app" / "templates" / "arb" / "partials" / "_typed_conditions.html"
)
REVIEW_DETAIL = ROOT / "app" / "templates" / "arb" / "review_detail.html"


@pytest.fixture(scope="module")
def source():
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def code(source):
    """The script with its comment lines removed.

    Every prohibition below is about what the browser EXECUTES. The file
    documents the hazards it guards in prose, so ``alert``, ``console`` and
    ``fetch(`` all appear legitimately in comments; asserting against the raw
    text would either fail on the documentation or force the documentation out.
    """
    kept = []
    in_block = False
    for line in source.splitlines():
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block = True
            continue
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        kept.append(line)
    return "\n".join(kept)


# ── the file is actually shipped ────────────────────────────────────────────


def test_script_exists_and_is_the_one_the_template_loads():
    """A renamed file is a silently dead workspace: every handler disappears."""
    assert SCRIPT.is_file()
    detail = REVIEW_DETAIL.read_text(encoding="utf-8")
    assert "js/arb/typed_governance.js" in detail


def test_exposes_a_named_public_surface(code):
    assert "global.ArchieTypedARB = api" in code
    for member in ("VERSION", "MESSAGES", "init", "isLatched", "capturedEvidenceId"):
        assert member in code


# ── platform-only interaction contract ──────────────────────────────────────


@pytest.mark.parametrize("banned", ["alert(", "confirm(", "prompt("])
def test_no_native_dialogs(code, banned):
    """Native dialogs bypass Platform.modal's focus trap and Escape contract."""
    assert banned not in code


def test_no_console_calls(code):
    """The console-reporting gate is at 0 on main and must stay there.

    A console line is also not a user-visible error: §13 requires the failure
    to remain inline, next to the control that failed.
    """
    for banned in ("console.log", "console.error", "console.warn", "console.debug"):
        assert banned not in code


def test_no_inline_event_handlers_or_jquery(code):
    for banned in ("onclick=", "onsubmit=", "jQuery", "$(document)", "$.ajax"):
        assert banned not in code


def test_no_manual_inner_html_for_server_data(code):
    """Server data reaches the page through textContent only."""
    assert "innerHTML" not in code
    assert "textContent" in code


def test_every_request_goes_through_platform_fetch(code):
    """A raw fetch() does not reject on 4xx/5xx, so a 409 would read as success."""
    assert "Platform.fetch(" in code
    # No bare fetch call: every occurrence must be the Platform one.
    assert code.count("fetch(") == code.count("Platform.fetch(")
    assert "XMLHttpRequest" not in code


def test_toast_is_never_the_only_error_channel(code):
    """Errors render inline; toast confirms success only.

    ``silent: true`` is what stops Platform.fetch toasting the raw server
    message on top of the inline, field-associated rendering.
    """
    assert "silent: true" in code
    assert "Platform.toast.success" in code
    assert "function showError(" in code
    assert "data-arb-error" in code


# ── the capture / submit hazard ─────────────────────────────────────────────


def test_capture_refuses_to_run_for_a_latched_condition(code):
    """Once capture has returned an id, capture must be unreachable.

    Re-running it writes a second immutable evidence record for the same fact
    under a different derived command key.
    """
    handler = code.split("async function handleCapture(", 1)[1]
    handler = handler.split("async function handleRetrySubmit(", 1)[0]
    guard = handler.split("clearError(root)", 1)[0]
    assert "latchedEntry(conditionId)" in guard
    assert "MESSAGES.alreadyCaptured" in guard
    assert "return;" in guard


def test_retry_path_resubmits_the_stored_id_and_never_captures(code):
    """The recovery control re-POSTs /submit with the returned id.

    It must not fall back to a capture when the id cannot be found — an
    unrecoverable state reported honestly is correct; a duplicate record is not.
    """
    handler = code.split("async function handleRetrySubmit(", 1)[1]
    handler = handler.split("async function handleVerify(", 1)[0]
    assert "resolveEvidenceId(root, conditionId)" in handler
    assert "submitCaptured(" in handler
    # The whole point: no capture anywhere on the recovery path.
    assert "handleCapture" not in handler
    assert "buildEvidenceBody" not in handler
    assert "/evidence'" not in handler


def test_retry_reuses_the_same_idempotency_key(code):
    """A retry of an unconfirmed command must not be able to record it twice."""
    handler = code.split("async function handleRetrySubmit(", 1)[1]
    handler = handler.split("async function handleVerify(", 1)[0]
    assert "entry ? entry.key : mintKey()" in handler


def test_latching_hides_the_capture_trigger(code):
    """Hidden, not merely disabled: no route back into a fresh capture."""
    latch = code.split("function latch(", 1)[1].split("function latchedEntry(", 1)[0]
    assert "data-arb-capture-trigger" in latch
    assert "trigger.hidden = true" in latch
    assert "data-arb-captured-region" in latch
    assert "region.hidden = false" in latch


def test_a_server_rendered_captured_region_relatches_on_load(code):
    """After a reload the captured state must still block a fresh capture."""
    init = code.split("function init(", 1)[1]
    assert "[data-arb-captured-region]:not([hidden])" in init
    assert "trigger.hidden = true" in init


def test_submit_and_verify_send_no_body(code):
    """The server rejects ANY key on /submit and /verify with 400."""
    submit = code.split("async function submitCaptured(", 1)[1]
    submit = submit.split("async function handleCapture(", 1)[0]
    assert "post(url, null, key)" in submit

    verify = code.split("async function handleVerify(", 1)[1]
    verify = verify.split("async function handleWaive(", 1)[0]
    # Was post(form.getAttribute('action'), ...). Each condition form now
    # declares two transports: `action` is the HTML child route a native submit
    # uses when this script is absent, and `data-json-action` is the JSON route
    # this script posts to. commandUrl() picks the JSON one. Posting a null
    # body to `action` would send JSON at the HTML handler.
    assert "post(commandUrl(form), null, key)" in verify


def test_json_transport_never_posts_to_the_html_child_route(code):
    """The two transports must not be crossed.

    A native submit sends form-encoded fields to `action`; this script sends
    JSON to `data-json-action`. If commandUrl() ever preferred `action`, every
    scripted command would arrive at the HTML handler as JSON -- which is the
    mirror image of the defect the HTML routes were added to fix, where a
    native submit reached the JSON handler and got a raw 400 back.
    """
    picker = code.split("function commandUrl(", 1)[1].split("}", 1)[0]

    assert "data-json-action" in picker
    json_at = picker.index("data-json-action")
    action_at = picker.index("'action'")
    assert json_at < action_at, (
        "data-json-action must be preferred; 'action' is only the fallback for "
        "a form that declares a single URL"
    )


# ── strictly allow-listed request bodies ────────────────────────────────────


REJECTED_FIELDS = [
    "organization_id",
    "actor_id",
    "user_id",
    "decided_by_id",
    "condition_status",
    "status",
    "cycle_id",
    "review_cycle_id",
    "review_id",
    "review_item_id",
    "decision_id",
    "content_hash",
    "source_checksum",
    "freshness_status",
    "freshness_rule_version",
    "condition_revision",
]


@pytest.mark.parametrize("field", REJECTED_FIELDS)
def test_no_allow_list_rejected_field_is_ever_sent(code, field):
    """Each of these returns 400, and several would let the browser pick tenancy.

    The check is scoped to body construction: the same names are read back OUT
    of responses, which is correct and must stay possible.
    """
    builders = ""
    for marker, end in (
        ("function buildEvidenceBody(", "function buildWaiverBody("),
        ("function buildWaiverBody(", "function pick("),
    ):
        builders += code.split(marker, 1)[1].split(end, 1)[0]
    assert field not in builders


def test_bodies_are_built_from_named_allow_lists_not_from_formdata(code):
    """new FormData(form) would post the CSRF token as an evidence field."""
    assert "new FormData" not in code
    assert "ATTESTATION_FIELDS" in code
    assert "SOURCE_BACKED_FIELDS" in code
    assert "WAIVER_FIELDS" in code
    # Every body passes the final pick() guard.
    assert "function pick(source, allowed)" in code
    # One per body builder: capture (mode-dependent list) and waiver.
    assert code.count("pick(body,") == 2


def test_allow_lists_match_the_server(code):
    """Drift here is a 400 the user cannot act on."""
    assert (
        "var ATTESTATION_FIELDS = ['mode', 'statement', 'observed_at']" in code
    )
    for field in (
        "source_identity",
        "source_type",
        "source_version",
        "observed_at",
        "expires_at",
        "value",
    ):
        source_backed = code.split("var SOURCE_BACKED_FIELDS", 1)[1].split("]", 1)[0]
        assert field in source_backed
    waiver = code.split("var WAIVER_FIELDS", 1)[1].split("]", 1)[0]
    for field in ("reason", "expires_at", "scope", "compensating_control"):
        assert field in waiver


def test_waiver_scope_is_sent_as_a_description_object(code):
    builder = code.split("function buildWaiverBody(", 1)[1].split("function pick(", 1)[0]
    assert "scope: { description: scope }" in builder


def test_datetimes_are_sent_timezone_aware(code):
    """A `datetime-local` value is naive; the server rejects naive with 400."""
    assert "function isoInstant(" in code
    assert "toISOString()" in code
    builder = code.split("function buildEvidenceBody(", 1)[1].split("function pick(", 1)[0]
    assert "isoInstant(fieldValue(form, 'observed_at'))" in builder


def test_one_idempotency_key_per_user_action(code):
    """The server derives :capture / :submit / :verify / :waive from one key."""
    assert "'Idempotency-Key': key" in code
    assert "function commandKey(" in code
    assert "data-command-key" in code


# ── §13 status handling, distinctly ─────────────────────────────────────────


@pytest.fixture(scope="module")
def classifier(code):
    return code.split("function describeFailure(", 1)[1].split(
        "function reportFailure(", 1
    )[0]


def test_409_is_handled_distinctly_and_shows_no_success(classifier, code):
    assert "status === 409" in classifier
    assert "MESSAGES.conflict" in classifier
    conflict = code.split("conflict:", 1)[1].split("',", 1)[0]
    assert "changed before your action was recorded" in conflict
    assert "Reload the current review and try again" in conflict


def test_409_keeps_the_users_typed_content(code):
    """The modal is not closed and no field is cleared on a failure path.

    Only the canonical-success paths call closeModal(), so a conflict leaves
    the rationale, waiver reason and evidence statement exactly as typed.
    """
    for handler, following in (
        ("async function handleWaive(", "function handleDecisionSubmit("),
        ("async function handleVerify(", "async function handleWaive("),
    ):
        body = code.split(handler, 1)[1].split(following, 1)[0]
        catch = body.split("} catch (error) {", 1)[1]
        assert "closeModal" not in catch
        assert "reset()" not in catch
        assert ".value = ''" not in catch


def test_422_renders_the_exact_stable_blocker_list(classifier, code):
    assert "status === 422" in classifier
    assert "MESSAGES.blocked" in classifier
    assert "reason_codes" in classifier
    assert "field_errors" in classifier
    assert "missing_evidence" in classifier
    # The stable code is always shown, not only a paraphrase of it.
    render = code.split("function renderError(", 1)[1].split(
        "function showError(", 1
    )[0]
    assert "String(codes[i])" in render
    for documented in (
        "arb_condition_evidence_source_expired",
        "waiver_expiry_in_past",
        "waiver_expiry_too_far",
    ):
        assert documented in code


def test_422_field_errors_are_associated_with_their_field(code):
    render = code.split("function renderError(", 1)[1].split(
        "function showError(", 1
    )[0]
    assert "aria-invalid" in render
    assert "aria-describedby" in render


def test_503_and_network_failure_are_unconfirmed_not_failed(classifier, code):
    assert "status === 503" in classifier
    assert "NetworkError" in classifier
    assert "MESSAGES.unconfirmed" in classifier
    unconfirmed = code.split("unconfirmed:", 1)[1].split("',", 1)[0]
    assert "was not confirmed" in unconfirmed
    assert "Retry" in unconfirmed


def test_the_three_statuses_produce_three_different_messages(code):
    messages = code.split("var MESSAGES = {", 1)[1].split("};", 1)[0]
    for key in ("conflict:", "unconfirmed:", "blocked:"):
        assert key in messages
    assert messages.count("MESSAGES") == 0  # no aliasing between them


# ── canonical id required for success ───────────────────────────────────────


def test_success_requires_a_canonical_id(code):
    """A 2xx with no canonical id is a failure, never optimistic success."""
    assert code.count("condition_evidence_id") >= 1
    assert "MESSAGES.noCanonicalId" in code
    for handler, following in (
        ("async function submitCaptured(", "async function handleCapture("),
        ("async function handleVerify(", "async function handleWaive("),
        ("async function handleWaive(", "function handleDecisionSubmit("),
    ):
        body = code.split(handler, 1)[1].split(following, 1)[0]
        assert "condition_event_id" in body
        assert "MESSAGES.noCanonicalId" in body

    capture = code.split("async function handleCapture(", 1)[1].split(
        "async function handleRetrySubmit(", 1
    )[0]
    assert "captured.condition_evidence_id" in capture
    assert "MESSAGES.noCanonicalId" in capture


def test_displayed_state_is_never_mutated_from_a_nominal_response(code):
    """On canonical success the server re-renders; this file does not guess."""
    succeed = code.split("function succeed(", 1)[1].split(
        "async function submitCaptured(", 1
    )[0]
    assert "location.reload()" in succeed


def test_the_decision_form_is_not_hijacked_into_fetch(code):
    """It answers with a redirect and a flash, not JSON.

    Fetching it would leave this file asserting success from an HTML body with
    no decision_event_id in it — the exact optimistic-success failure §13 bans.
    """
    handler = code.split("function handleDecisionSubmit(", 1)[1].split(
        "async function handleCopy(", 1
    )[0]
    assert "preventDefault" not in handler
    assert "Platform.fetch" not in handler
    # It still gets the busy affordance and a double-submit guard.
    assert "data-arb-decision-busy" in handler
    assert "aria-busy" in handler
    assert "disabled = true" in handler


# ── accessibility contract (§14) ────────────────────────────────────────────


def test_async_regions_set_aria_busy(code):
    setter = code.split("function setBusy(", 1)[1].split("function errorRegion(", 1)[0]
    assert "aria-busy" in setter
    assert "removeAttribute('aria-busy')" in setter


def test_one_polite_live_region_for_results(code):
    region = code.split("function liveRegion(", 1)[1].split("function announce(", 1)[0]
    assert "aria-live" in region
    assert "'polite'" in region
    assert "getElementById(LIVE_REGION_ID)" in region  # reused, never duplicated


def test_focus_moves_to_the_updated_condition_heading_after_success(code):
    focus = code.split("function focusCondition(", 1)[1].split(
        "var RELOAD_ANNOUNCE_MS", 1
    )[0]
    assert "condition-heading-" in focus


def test_a_failure_is_shown_inside_the_open_modal_as_well_as_the_card(code):
    """On 409/422 the modal stays open, so a card-only message is behind it."""
    dispatch = code.split("function showError(", 1)[1].split(
        "function describeFailure(", 1
    )[0]
    assert "renderError(errorRegion(root)" in dispatch
    assert "renderError(formErrorRegion(form)" in dispatch
    mirror = code.split("function formErrorRegion(", 1)[1].split(
        "function clearError(", 1
    )[0]
    assert "'role', 'alert'" in mirror


def test_the_submitting_form_is_disabled_during_the_round_trip(code):
    """The modals are siblings of the card, not descendants of it.

    Disabling only the card's controls would leave the modal's own submit
    button live for the whole request — a second click, a second command.
    """
    setter = code.split("function setBusy(", 1)[1].split("function errorRegion(", 1)[0]
    assert "if (form) scopes.push(form)" in setter
    for handler, following in (
        ("async function handleCapture(", "async function handleRetrySubmit("),
        ("async function handleVerify(", "async function handleWaive("),
        ("async function handleWaive(", "function handleDecisionSubmit("),
    ):
        body = code.split(handler, 1)[1].split(following, 1)[0]
        assert "setBusy(root, true, form)" in body
        assert "setBusy(root, false, form)" in body


def test_errors_are_announced_as_well_as_rendered(code):
    dispatch = code.split("function showError(", 1)[1].split(
        "function describeFailure(", 1
    )[0]
    assert "announce(headline)" in dispatch


# ── the markup contract this file binds to ──────────────────────────────────


HOOKS = [
    "data-arb-condition",
    "data-condition-id",
    "data-arb-capture-trigger",
    "data-arb-captured-region",
    "data-arb-captured-evidence-id",
    "data-arb-retry-submit",
    "data-submit-url-template",
    "data-arb-error",
    "data-arb-evidence-form",
    "data-arb-verify-form",
    "data-arb-waive-form",
    "data-command-key",
]


@pytest.mark.parametrize("hook", HOOKS)
def test_every_hook_bound_here_exists_in_the_markup(code, hook):
    """A rename on either side leaves a control that looks live and is dead."""
    markup = CONDITIONS_TEMPLATE.read_text(encoding="utf-8")
    assert hook in markup
    assert hook in code


def test_the_error_region_is_role_alert_in_the_markup():
    markup = CONDITIONS_TEMPLATE.read_text(encoding="utf-8")
    error_line = [
        line
        for line in markup.splitlines()
        if "data-arb-error" in line and line.lstrip().startswith("<")
    ]
    assert error_line
    assert 'role="alert"' in error_line[0]


def test_the_submit_url_template_placeholder_matches_the_substitution(code):
    markup = CONDITIONS_TEMPLATE.read_text(encoding="utf-8")
    assert "__EVIDENCE_ID__" in markup
    assert "'__EVIDENCE_ID__'" in code
