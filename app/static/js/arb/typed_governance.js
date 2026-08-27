/**
 * arb/typed_governance.js — typed ARB governance workspace interactions
 *
 * Loaded (deferred) by `app/templates/arb/review_detail.html` for the typed
 * review workspace only. Binds to the hooks lane 5 rendered; it invents no
 * markup and reads no server data out of anything but a documented JSON
 * response.
 *
 * Requires: core/00-namespace.js .. core/05-error.js and ui/modal.js, all of
 * which admin_base.html loads ahead of `{% block extra_head_js %}`.
 *
 * ── The hazard this file exists to contain ──────────────────────────────────
 *
 * Capturing condition evidence and submitting it are TWO commands, and capture
 * deliberately does not advance the condition:
 *
 *     POST /arb/api/conditions/<id>/evidence                  -> condition_evidence_id
 *     POST /arb/api/conditions/<id>/evidence/<eid>/submit     (no body)
 *
 * If capture succeeds and submit then fails, the only correct recovery is
 * re-POSTing /submit with the id capture already returned. Re-running capture
 * writes a SECOND immutable evidence record under a different derived command
 * key — two records asserting the same fact, in a system of record, with no
 * way for a later reader to tell which one the reviewer meant.
 *
 * So once capture has returned an id for a condition, this file latches that
 * condition into a captured-not-submitted state: the capture trigger is
 * hidden, `[data-arb-captured-region]` is revealed with the id, and the only
 * remaining control re-submits that exact id. `_capture()` refuses outright to
 * run for a latched condition. There is no path from the latched state back
 * into a fresh capture, including through a stale open modal.
 *
 * ── Request bodies are strictly allow-listed ────────────────────────────────
 *
 * The server rejects any unknown key with 400. Bodies are therefore built
 * field-by-field from named constants below, never by serialising the form:
 * `new FormData(form)` would post the CSRF token as an evidence field. The CSRF
 * token travels in the `X-CSRFToken` header, which Platform.fetch adds.
 *
 * ── Success requires a canonical id ─────────────────────────────────────────
 *
 * A 2xx whose body carries no `condition_evidence_id` / `condition_event_id`
 * is a FAILURE and is reported as one. Displayed governance state is never
 * mutated from a nominal response: on canonical success the page is reloaded
 * so the server re-renders the authoritative card.
 *
 * The one deliberate exception is the captured-not-submitted region, which is
 * revealed from `condition_evidence_id` — a canonical id, and a state the
 * server has not been asked to render yet.
 *
 * Public surface: `window.ArchieTypedARB`
 *   .VERSION                      string
 *   .MESSAGES                     the stable user-facing strings (§13)
 *   .init(root)                   idempotent binding; runs itself on DOMContentLoaded
 *   .capturedEvidenceId(cid)      the latched evidence id for a condition, or null
 *   .isLatched(cid)               true once capture has returned an id
 */

(function (global) {
    'use strict';

    var doc = global.document;
    var Platform = global.Platform;

    var VERSION = '1.0.0';

    // ── Stable user-facing copy (blueprint §13) ─────────────────────────────
    var MESSAGES = {
        conflict:
            'This review changed before your action was recorded. ' +
            'Reload the current review and try again.',
        unconfirmed:
            'The command was not confirmed. Retry — your entry has been kept and ' +
            'the same idempotency key is reused, so a retry cannot record the action twice.',
        notAuthorised:
            'You are not authorised to take this action on this condition.',
        notFound:
            'This condition is no longer available to you. Reload the review.',
        noCanonicalId:
            'The server did not return a canonical identifier, so this action is ' +
            'not confirmed as recorded. Nothing has been changed on screen. Reload ' +
            'the review to see its true state before retrying.',
        alreadyCaptured:
            'Evidence for this condition has already been captured and is waiting to ' +
            'be submitted. Retry the submission — capturing again would create a ' +
            'second evidence record.',
        blocked: 'This action was refused:',
        invalid: 'This request was not accepted:',
        failed: 'The action could not be completed.',
        capturedNotSubmitted:
            'Evidence was captured but its submission failed. The evidence record ' +
            'exists and is immutable; retry the submission below.'
    };

    // A stable, human-readable line for each documented blocker code. A code
    // with no entry is shown verbatim: an invented paraphrase of a governance
    // refusal is worse than the exact code the server chose.
    var BLOCKER_TEXT = {
        arb_condition_evidence_source_expired:
            'That source record has already expired, so it is not evidence of ' +
            'anything current.',
        waiver_expiry_in_past: 'The waiver expiry must be in the future.',
        waiver_expiry_too_far:
            'A waiver may not run for more than 365 days.',
        expires_at_before_observed_at:
            'The expiry must be later than the observed time.',
        observed_at_in_future: 'The observed time cannot be in the future.',
        source_type_reserved:
            'Use the manual attestation mode to record a person’s statement.',
        request_field_not_accepted:
            'A field was sent that this command does not accept.'
    };

    // Field-level codes the server returns alongside `field_errors[].field`.
    var FIELD_CODE_TEXT = {
        required: 'This is required.',
        too_long: 'This is longer than the permitted length.',
        invalid_datetime: 'Enter a valid date and time.',
        timezone_required: 'A timezone-aware date and time is required.',
        in_future: 'This cannot be in the future.',
        in_past: 'This must be in the future.',
        too_far: 'This is further ahead than the permitted window.',
        expired: 'This has already expired.',
        before_observed_at: 'This must be later than the observed time.',
        reserved: 'This value is reserved.',
        unsupported: 'This value is not supported.',
        field_not_accepted: 'This field is not accepted by this command.',
        invalid: 'This value is not valid.'
    };

    // Allow-listed body keys, mirroring app/modules/architecture/routes/
    // arb_condition_routes.py. Nothing outside these lists is ever sent.
    var ATTESTATION_FIELDS = ['mode', 'statement', 'observed_at'];
    var SOURCE_BACKED_FIELDS = [
        'mode', 'source_identity', 'source_type', 'source_version',
        'observed_at', 'expires_at', 'value'
    ];
    var WAIVER_FIELDS = ['reason', 'expires_at', 'scope', 'compensating_control'];

    // Per-condition latch. conditionId -> { evidenceId, key }
    var latched = Object.create(null);

    var LIVE_REGION_ID = 'arb-typed-governance-live-region';
    var BOUND_FLAG = '__arbTypedGovernanceBound';

    // ── Platform access. This file never falls back to a native dialog, a raw
    //    fetch or the console; if the platform is absent the page is
    //    server-rendered and read-only, which is the honest outcome. ─────────
    function platformReady() {
        return !!(Platform && Platform.fetch);
    }

    function toastSuccess(message) {
        if (Platform && Platform.toast && Platform.toast.success) {
            Platform.toast.success(message);
        }
    }

    function closeModal(id) {
        if (id && Platform && Platform.modal && Platform.modal.close) {
            Platform.modal.close(id);
        }
    }

    // ── Small DOM helpers. Server data only ever reaches the page through
    //    textContent — never innerHTML. ──────────────────────────────────────
    function conditionRoot(conditionId) {
        return doc.querySelector(
            '[data-arb-condition][data-condition-id="' + String(conditionId) + '"]'
        );
    }

    function conditionIdOf(el) {
        var root = el && el.closest ? el.closest('[data-arb-condition]') : null;
        return root ? root.getAttribute('data-condition-id') : null;
    }

    function liveRegion() {
        var region = doc.getElementById(LIVE_REGION_ID);
        if (region) return region;
        region = doc.createElement('div');
        region.id = LIVE_REGION_ID;
        region.setAttribute('role', 'status');
        region.setAttribute('aria-live', 'polite');
        region.setAttribute('aria-atomic', 'true');
        region.className = 'sr-only';
        doc.body.appendChild(region);
        return region;
    }

    function announce(message) {
        liveRegion().textContent = message;
    }

    /**
     * `aria-busy` on the async region, plus a double-submit guard.
     *
     * The modals live OUTSIDE `[data-arb-condition]` in lane 5's markup — they
     * are siblings of the card's `<li>`, not descendants — so disabling only
     * the card's controls would leave the modal's own submit button live for
     * the whole round trip. The submitting form is therefore disabled
     * explicitly rather than by containment.
     */
    function setBusy(root, busy, form) {
        if (!root) return;
        if (busy) {
            root.setAttribute('aria-busy', 'true');
        } else {
            root.removeAttribute('aria-busy');
        }
        var scopes = [root];
        if (form) scopes.push(form);
        for (var s = 0; s < scopes.length; s += 1) {
            if (busy) {
                scopes[s].setAttribute('aria-busy', 'true');
            } else if (scopes[s] !== root) {
                scopes[s].removeAttribute('aria-busy');
            }
            var controls = scopes[s].querySelectorAll(
                'button[type="submit"], [data-arb-retry-submit]'
            );
            for (var i = 0; i < controls.length; i += 1) {
                controls[i].disabled = !!busy;
            }
        }
    }

    function errorRegion(root) {
        return root ? root.querySelector('[data-arb-error]') : null;
    }

    /**
     * A modal-local mirror of the card's error region.
     *
     * Lane 5 renders `[data-arb-error]` inside the condition card only, and on
     * a 409 or 422 the modal deliberately stays open so the user's typed
     * content survives — which would leave the message rendered behind the
     * modal backdrop, i.e. reported to nobody. The failure is therefore shown
     * in both places: the card region is the durable record that survives the
     * modal closing, this one is what the user is actually looking at.
     *
     * (Lane 5 rendering `[data-arb-error]` inside each modal form would let
     * this be dropped; the runtime region is the correct behaviour meanwhile,
     * not a workaround for a missing hook.)
     */
    function formErrorRegion(form) {
        if (!form) return null;
        var existing = form.querySelector('[data-arb-form-error]');
        if (existing) return existing;
        var region = doc.createElement('div');
        region.setAttribute('data-arb-form-error', '');
        region.setAttribute('role', 'alert');
        region.className =
            'rounded-lg border border-destructive/30 bg-destructive/10 p-3 ' +
            'text-sm text-destructive-emphasis';
        region.hidden = true;
        form.insertBefore(region, form.firstChild);
        return region;
    }

    function clearError(root, form) {
        var regions = [errorRegion(root), form ? formErrorRegion(form) : null];
        for (var r = 0; r < regions.length; r += 1) {
            if (!regions[r]) continue;
            regions[r].textContent = '';
            regions[r].hidden = true;
        }
        var scopes = form ? [root, form] : [root];
        for (var s = 0; s < scopes.length; s += 1) {
            if (!scopes[s]) continue;
            var flagged = scopes[s].querySelectorAll('[aria-invalid="true"]');
            for (var i = 0; i < flagged.length; i += 1) {
                flagged[i].removeAttribute('aria-invalid');
            }
        }
    }

    function appendLine(parent, text, className) {
        var node = doc.createElement('p');
        if (className) node.className = className;
        node.textContent = text;
        parent.appendChild(node);
        return node;
    }

    /**
     * Render an inline, role=alert failure into one region. Errors are NEVER
     * toast-only: the region stays visible until the next attempt, next to the
     * control that failed and next to the form content the user must not lose.
     */
    function renderError(region, headline, detail) {
        if (!region) return;
        region.textContent = '';
        region.hidden = false;

        appendLine(region, headline, 'font-medium');

        var codes = (detail && detail.reasonCodes) || [];
        var fieldErrors = (detail && detail.fieldErrors) || [];
        var missing = (detail && detail.missingEvidence) || [];

        if (codes.length) {
            var list = doc.createElement('ul');
            list.className = 'mt-1 list-disc space-y-1 pl-5';
            for (var i = 0; i < codes.length; i += 1) {
                var item = doc.createElement('li');
                var text = BLOCKER_TEXT[codes[i]];
                item.textContent = text ? text : String(codes[i]);
                if (text) {
                    var code = doc.createElement('code');
                    code.className = 'ml-1 font-mono text-xs opacity-80';
                    code.textContent = String(codes[i]);
                    item.appendChild(code);
                }
                list.appendChild(item);
            }
            region.appendChild(list);
        }

        if (missing.length) {
            appendLine(region, 'Evidence still required:', 'mt-2 font-medium');
            var missingList = doc.createElement('ul');
            missingList.className = 'mt-1 list-disc space-y-1 pl-5';
            for (var m = 0; m < missing.length; m += 1) {
                var missingItem = doc.createElement('li');
                missingItem.textContent = typeof missing[m] === 'string'
                    ? missing[m]
                    : JSON.stringify(missing[m]);
                missingList.appendChild(missingItem);
            }
            region.appendChild(missingList);
        }

        for (var f = 0; f < fieldErrors.length; f += 1) {
            var entry = fieldErrors[f] || {};
            var fieldName = entry.field;
            var codeText = FIELD_CODE_TEXT[entry.code] || String(entry.code || 'invalid');
            appendLine(region, String(fieldName) + ': ' + codeText, 'mt-1 text-xs');
            var lineId = region.id || (region.id = 'arb-error-' + Math.random().toString(36).slice(2));
            var input = detail && detail.form
                ? detail.form.querySelector('[name="' + String(fieldName).replace(/"/g, '') + '"]')
                : null;
            if (input) {
                input.setAttribute('aria-invalid', 'true');
                var described = (input.getAttribute('aria-describedby') || '').split(/\s+/);
                if (described.indexOf(lineId) === -1) {
                    described.push(lineId);
                    input.setAttribute('aria-describedby', described.join(' ').trim());
                }
            }
        }

        if (detail && detail.requestId) {
            appendLine(
                region,
                'Request ' + String(detail.requestId),
                'mt-2 break-all font-mono text-xs opacity-80'
            );
        }
    }

    /** Show the failure in the card AND, when one is open, in the modal form. */
    function showError(root, headline, detail) {
        var form = detail && detail.form ? detail.form : null;
        renderError(errorRegion(root), headline, detail);
        if (form) {
            renderError(formErrorRegion(form), headline, detail);
        }
        announce(headline);
    }

    /** Classify a thrown Platform.fetch error into the §13 outcomes. */
    function describeFailure(error, form) {
        var data = (error && error.data) || {};
        var detail = {
            reasonCodes: Array.isArray(data.reason_codes) ? data.reason_codes : [],
            fieldErrors: Array.isArray(data.field_errors) ? data.field_errors : [],
            missingEvidence: Array.isArray(data.missing_evidence) ? data.missing_evidence : [],
            requestId: data.request_id || null,
            form: form || null
        };
        var status = error ? error.status : undefined;
        var isNetwork = !!(error && error.type === 'NetworkError');

        if (isNetwork || status === 503) {
            // Unconfirmed, not failed. The same idempotency key must be reused
            // so a retry cannot record the command twice.
            return { headline: MESSAGES.unconfirmed, detail: detail, retryable: true };
        }
        if (status === 409) {
            // The user's typed content is deliberately left in the form and the
            // modal is left open: no success is shown and nothing is cleared.
            return { headline: MESSAGES.conflict, detail: detail, retryable: false };
        }
        if (status === 422) {
            return { headline: MESSAGES.blocked, detail: detail, retryable: false };
        }
        if (status === 400) {
            return { headline: MESSAGES.invalid, detail: detail, retryable: false };
        }
        if (status === 401 || status === 403) {
            return { headline: MESSAGES.notAuthorised, detail: detail, retryable: false };
        }
        if (status === 404) {
            return { headline: MESSAGES.notFound, detail: detail, retryable: false };
        }
        return { headline: MESSAGES.failed, detail: detail, retryable: true };
    }

    function reportFailure(root, error, form) {
        var described = describeFailure(error, form);
        showError(root, described.headline, described.detail);
        return described;
    }

    // ── Idempotency ─────────────────────────────────────────────────────────
    // One client key per user action; the server derives :capture / :submit /
    // :verify / :waive from it. The template's `data-command-key` is preferred
    // because it is stable across reloads, so a retry after a refresh still
    // addresses the same command.
    function mintKey() {
        if (global.crypto && typeof global.crypto.randomUUID === 'function') {
            return global.crypto.randomUUID();
        }
        return 'arb-' + Date.now().toString(36) + '-' +
            Math.random().toString(36).slice(2, 12);
    }

    function commandKey(form) {
        var supplied = form ? (form.getAttribute('data-command-key') || '').trim() : '';
        return supplied || mintKey();
    }

    function post(url, body, key) {
        var options = { method: 'POST', silent: true, headers: { 'Idempotency-Key': key } };
        if (body !== undefined && body !== null) {
            options.body = body;
        }
        return Platform.fetch(url, options);
    }

    // ── Field reading and validation ────────────────────────────────────────
    function fieldValue(form, name) {
        var input = form.querySelector('[name="' + name + '"]');
        if (!input) return '';
        return typeof input.value === 'string' ? input.value.trim() : '';
    }

    /**
     * A `datetime-local` control yields a NAIVE local string; the server
     * rejects a naive timestamp with 400 `<field>_not_timezone_aware`. The
     * browser's own offset is the only honest interpretation of what the user
     * typed, so convert through Date and emit UTC.
     */
    function isoInstant(value) {
        if (!value) return null;
        var parsed = new Date(value);
        if (isNaN(parsed.getTime())) return null;
        return parsed.toISOString();
    }

    function fieldError(field, code) {
        return { field: field, code: code };
    }

    /** Build the allow-listed capture body, or a list of field errors. */
    function buildEvidenceBody(form) {
        var modeInput = form.querySelector('[name="mode"]:checked');
        var mode = modeInput ? modeInput.value : 'manual_attestation';
        var errors = [];
        var body;

        if (mode === 'manual_attestation') {
            var statement = fieldValue(form, 'statement');
            var observed = isoInstant(fieldValue(form, 'observed_at'));
            if (!statement) errors.push(fieldError('statement', 'required'));
            if (!observed) errors.push(fieldError('observed_at', 'invalid_datetime'));
            body = { mode: 'manual_attestation', statement: statement, observed_at: observed };
        } else {
            var identity = fieldValue(form, 'source_identity');
            var sourceType = fieldValue(form, 'source_type');
            var sourceVersion = fieldValue(form, 'source_version');
            var observedAt = isoInstant(fieldValue(form, 'observed_at'));
            var expiresAt = isoInstant(fieldValue(form, 'expires_at'));
            var rawValue = fieldValue(form, 'value');

            if (!identity) errors.push(fieldError('source_identity', 'required'));
            if (!sourceType) errors.push(fieldError('source_type', 'required'));
            if (!sourceVersion) errors.push(fieldError('source_version', 'required'));
            if (!observedAt) errors.push(fieldError('observed_at', 'invalid_datetime'));
            if (!expiresAt) errors.push(fieldError('expires_at', 'invalid_datetime'));

            // The server requires a non-empty object or array. If the reviewer
            // typed JSON, send it as typed; otherwise carry the exact text they
            // entered under one named key. Neither path invents a value.
            var structured = null;
            if (rawValue) {
                try {
                    structured = JSON.parse(rawValue);
                } catch (parseError) {
                    structured = null;
                }
                var usable = structured !== null && typeof structured === 'object' &&
                    (Array.isArray(structured) ? structured.length > 0
                        : Object.keys(structured).length > 0);
                if (!usable) {
                    structured = { reported_value: rawValue };
                }
            } else {
                errors.push(fieldError('value', 'required'));
            }

            body = {
                mode: 'source_backed',
                source_identity: identity,
                source_type: sourceType,
                source_version: sourceVersion,
                observed_at: observedAt,
                expires_at: expiresAt,
                value: structured
            };
        }

        return {
            body: pick(body, mode === 'manual_attestation' ? ATTESTATION_FIELDS : SOURCE_BACKED_FIELDS),
            errors: errors
        };
    }

    function buildWaiverBody(form) {
        var errors = [];
        var reason = fieldValue(form, 'reason');
        var scope = fieldValue(form, 'scope');
        var control = fieldValue(form, 'compensating_control');
        var expires = isoInstant(fieldValue(form, 'expires_at'));

        if (!reason) errors.push(fieldError('reason', 'required'));
        if (!scope) errors.push(fieldError('scope', 'required'));
        if (!control) errors.push(fieldError('compensating_control', 'required'));
        if (!expires) errors.push(fieldError('expires_at', 'invalid_datetime'));

        var body = {
            reason: reason,
            expires_at: expires,
            scope: { description: scope },
            compensating_control: control
        };
        return { body: pick(body, WAIVER_FIELDS), errors: errors };
    }

    /** Final guard: only allow-listed keys leave the browser. */
    function pick(source, allowed) {
        var out = {};
        for (var i = 0; i < allowed.length; i += 1) {
            var key = allowed[i];
            if (Object.prototype.hasOwnProperty.call(source, key)) {
                out[key] = source[key];
            }
        }
        return out;
    }

    // ── The captured-not-submitted latch ────────────────────────────────────
    function latch(conditionId, evidenceId, key) {
        latched[String(conditionId)] = { evidenceId: String(evidenceId), key: key };
        var root = conditionRoot(conditionId);
        if (!root) return;

        var trigger = root.querySelector('[data-arb-capture-trigger]');
        if (trigger) {
            // Hidden, not merely disabled: there is no route from this state
            // back into a fresh capture.
            trigger.hidden = true;
        }
        var region = root.querySelector('[data-arb-captured-region]');
        if (region) {
            var slot = region.querySelector('[data-arb-captured-evidence-id]');
            if (slot) slot.textContent = String(evidenceId);
            region.hidden = false;
        }
    }

    function latchedEntry(conditionId) {
        return latched[String(conditionId)] || null;
    }

    /**
     * Recover the latched evidence id. The in-memory latch is authoritative;
     * the DOM slot lane 5 rendered is the fallback for a state re-rendered by
     * the server. Capture is never a fallback.
     */
    function resolveEvidenceId(root, conditionId) {
        var entry = latchedEntry(conditionId);
        if (entry) return entry.evidenceId;
        var slot = root ? root.querySelector('[data-arb-captured-evidence-id]') : null;
        var text = slot ? (slot.textContent || '').trim() : '';
        return text || null;
    }

    function focusCondition(conditionId) {
        // The card is re-rendered by the server on reload; addressing the
        // heading by fragment moves focus to it there rather than guessing at
        // the state of a card this file did not write.
        var heading = 'condition-heading-' + String(conditionId);
        try {
            global.location.hash = heading;
        } catch (hashError) {
            void hashError;
        }
    }

    /**
     * Canonical success. Nothing on screen is mutated from the response: the
     * page is reloaded so the server renders the authoritative card. The delay
     * exists only so the polite live region is read before navigation.
     */
    var RELOAD_ANNOUNCE_MS = 700;

    function succeed(conditionId, message) {
        announce(message);
        toastSuccess(message);
        focusCondition(conditionId);
        global.setTimeout(function () { global.location.reload(); }, RELOAD_ANNOUNCE_MS);
    }

    // ── Commands ────────────────────────────────────────────────────────────

    /** POST /submit for an ALREADY-CAPTURED evidence id. Never captures. */
    async function submitCaptured(root, conditionId, evidenceId, key, form) {
        var control = root.querySelector('[data-arb-retry-submit]');
        var template = control ? control.getAttribute('data-submit-url-template') : null;
        var url = template
            ? template.replace('__EVIDENCE_ID__', encodeURIComponent(String(evidenceId)))
            : '/arb/api/conditions/' + encodeURIComponent(String(conditionId)) +
              '/evidence/' + encodeURIComponent(String(evidenceId)) + '/submit';

        // NO body: the server rejects any key here with 400.
        var result = await post(url, null, key);
        if (!result || !result.condition_event_id) {
            showError(root, MESSAGES.noCanonicalId, { form: form || null,
                requestId: result ? result.request_id : null });
            return false;
        }
        succeed(conditionId, 'Evidence submitted. Condition updated.');
        return true;
    }

    async function handleCapture(form, event) {
        event.preventDefault();
        var conditionId = form.getAttribute('data-condition-id');
        var root = conditionRoot(conditionId);
        if (!root) return;

        // The hazard guard. A latched condition can only be re-submitted.
        if (latchedEntry(conditionId)) {
            closeModal(form.closest('.modal-root') ? form.closest('.modal-root').id : null);
            showError(root, MESSAGES.alreadyCaptured, { form: form });
            return;
        }

        clearError(root, form);
        var built = buildEvidenceBody(form);
        if (built.errors.length) {
            showError(root, MESSAGES.invalid, { fieldErrors: built.errors, form: form });
            return;
        }

        var key = commandKey(form);
        var modalId = form.closest('.modal-root') ? form.closest('.modal-root').id : null;
        setBusy(root, true, form);
        try {
            var captured = await post(form.getAttribute('action'), built.body, key);
            if (!captured || !captured.condition_evidence_id) {
                showError(root, MESSAGES.noCanonicalId, {
                    form: form, requestId: captured ? captured.request_id : null
                });
                return;
            }
            // Capture succeeded. From here the condition is latched whatever
            // happens next: the evidence record exists and is immutable.
            latch(conditionId, captured.condition_evidence_id, key);
            closeModal(modalId);
            await submitCaptured(root, conditionId, captured.condition_evidence_id, key, form);
        } catch (error) {
            if (latchedEntry(conditionId)) {
                // Capture landed; only the submission failed. Report it against
                // the latched region, which is now the only way forward.
                var described = reportFailure(root, error, form);
                announce(MESSAGES.capturedNotSubmitted + ' ' + described.headline);
            } else {
                reportFailure(root, error, form);
            }
        } finally {
            setBusy(root, false, form);
        }
    }

    async function handleRetrySubmit(control, event) {
        event.preventDefault();
        var conditionId = conditionIdOf(control);
        var root = conditionRoot(conditionId);
        if (!root) return;
        var evidenceId = resolveEvidenceId(root, conditionId);
        if (!evidenceId) {
            // Deliberately does NOT fall back to a capture.
            showError(root, MESSAGES.notFound, {});
            return;
        }
        var entry = latchedEntry(conditionId);
        // The same key is reused, so a retry of an unconfirmed command cannot
        // record it twice.
        var key = entry ? entry.key : mintKey();
        if (!entry) latched[String(conditionId)] = { evidenceId: evidenceId, key: key };

        clearError(root);
        setBusy(root, true);
        try {
            await submitCaptured(root, conditionId, evidenceId, key, null);
        } catch (error) {
            reportFailure(root, error, null);
        } finally {
            setBusy(root, false);
        }
    }

    async function handleVerify(form, event) {
        event.preventDefault();
        var conditionId = form.getAttribute('data-condition-id');
        var root = conditionRoot(conditionId);
        if (!root) return;
        clearError(root, form);
        var key = commandKey(form);
        var modalId = form.closest('.modal-root') ? form.closest('.modal-root').id : null;
        setBusy(root, true, form);
        try {
            // NO body: verify accepts none.
            var result = await post(form.getAttribute('action'), null, key);
            if (!result || !result.condition_event_id) {
                showError(root, MESSAGES.noCanonicalId, {
                    form: form, requestId: result ? result.request_id : null
                });
                return;
            }
            closeModal(modalId);
            succeed(conditionId, 'Evidence verified. Condition updated.');
        } catch (error) {
            reportFailure(root, error, form);
        } finally {
            setBusy(root, false, form);
        }
    }

    async function handleWaive(form, event) {
        event.preventDefault();
        var conditionId = form.getAttribute('data-condition-id');
        var root = conditionRoot(conditionId);
        if (!root) return;
        clearError(root, form);
        var built = buildWaiverBody(form);
        if (built.errors.length) {
            showError(root, MESSAGES.invalid, { fieldErrors: built.errors, form: form });
            return;
        }
        var key = commandKey(form);
        var modalId = form.closest('.modal-root') ? form.closest('.modal-root').id : null;
        setBusy(root, true, form);
        try {
            var result = await post(form.getAttribute('action'), built.body, key);
            if (!result || !result.condition_event_id) {
                showError(root, MESSAGES.noCanonicalId, {
                    form: form, requestId: result ? result.request_id : null
                });
                return;
            }
            closeModal(modalId);
            succeed(conditionId, 'Waiver granted. It expires automatically.');
        } catch (error) {
            // On 409 the modal stays open and the typed reason is untouched.
            reportFailure(root, error, form);
        } finally {
            setBusy(root, false, form);
        }
    }

    /**
     * The decision form is a server-rendered POST that answers with a redirect
     * and a flash — not JSON. Intercepting it with fetch would leave this file
     * asserting success from an HTML body with no `decision_event_id` in it,
     * which is exactly the optimistic-success failure §13 forbids. So the
     * native submit is left alone and only the busy affordance and the
     * double-submit guard are added.
     */
    function handleDecisionSubmit(form) {
        var section = doc.getElementById('decision');
        var busy = doc.querySelector('[data-arb-decision-busy]');
        if (busy) busy.hidden = false;
        if (section) section.setAttribute('aria-busy', 'true');
        var buttons = form.querySelectorAll('button[type="submit"]');
        for (var i = 0; i < buttons.length; i += 1) {
            buttons[i].disabled = true;
        }
        announce('Recording decision.');
    }

    async function handleCopy(control) {
        var value = control.getAttribute('data-arb-copy');
        if (!value) return;
        var label = control.getAttribute('aria-label') || 'Value';
        try {
            if (global.navigator && global.navigator.clipboard &&
                global.navigator.clipboard.writeText) {
                await global.navigator.clipboard.writeText(value);
                announce(label + ': copied.');
                toastSuccess('Copied to the clipboard.');
                return;
            }
        } catch (clipboardError) {
            void clipboardError;
        }
        // No silent failure: say so, and leave the value selectable.
        announce(label + ': the clipboard is not available. Select the value to copy it.');
        if (Platform && Platform.toast && Platform.toast.error) {
            Platform.toast.error('The clipboard is not available in this browser. ' +
                'Select the value to copy it.');
        }
    }

    // ── Binding ─────────────────────────────────────────────────────────────
    function init(root) {
        var scope = root || doc;
        if (!platformReady()) return;
        if (scope[BOUND_FLAG]) return;
        scope[BOUND_FLAG] = true;

        // Re-latch from the server render: a page that already shows the
        // captured-not-submitted region must not offer capture again.
        var regions = scope.querySelectorAll('[data-arb-captured-region]:not([hidden])');
        for (var r = 0; r < regions.length; r += 1) {
            var cid = conditionIdOf(regions[r]);
            var slot = regions[r].querySelector('[data-arb-captured-evidence-id]');
            var existing = slot ? (slot.textContent || '').trim() : '';
            if (cid && existing && !latchedEntry(cid)) {
                latched[String(cid)] = { evidenceId: existing, key: mintKey() };
                var trigger = conditionRoot(cid);
                trigger = trigger ? trigger.querySelector('[data-arb-capture-trigger]') : null;
                if (trigger) trigger.hidden = true;
            }
        }

        scope.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form || !form.matches) return;
            if (form.matches('[data-arb-evidence-form]')) {
                handleCapture(form, event);
            } else if (form.matches('[data-arb-verify-form]')) {
                handleVerify(form, event);
            } else if (form.matches('[data-arb-waive-form]')) {
                handleWaive(form, event);
            } else if (form.matches('[data-arb-decision-form]')) {
                handleDecisionSubmit(form);
            }
        }, true);

        scope.addEventListener('click', function (event) {
            var target = event.target;
            if (!target || !target.closest) return;
            var retry = target.closest('[data-arb-retry-submit]');
            if (retry) {
                handleRetrySubmit(retry, event);
                return;
            }
            var copy = target.closest('[data-arb-copy]');
            if (copy) {
                event.preventDefault();
                handleCopy(copy);
            }
        });
    }

    var api = {
        VERSION: VERSION,
        MESSAGES: MESSAGES,
        init: init,
        isLatched: function (conditionId) { return !!latchedEntry(conditionId); },
        capturedEvidenceId: function (conditionId) {
            var entry = latchedEntry(conditionId);
            return entry ? entry.evidenceId : null;
        }
    };

    global.ArchieTypedARB = api;

    if (doc.readyState === 'loading') {
        doc.addEventListener('DOMContentLoaded', function () { init(doc); });
    } else {
        init(doc);
    }
})(window);
