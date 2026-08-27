/**
 * core/05-error.js — Unified error handling module
 *
 * Requires: core/00-namespace.js, core/01-logger.js, core/04-toast.js
 *
 * Replaces:
 *   - Scattered try/catch with console.error across all feature modules
 *   - alert() calls used as error UI
 *   - Inconsistent error shapes (some have .message, some .error, some .detail)
 *   - No global unhandled-rejection handler
 *
 * Design:
 *   - Platform.error.handle(err, context)  — central handler for caught errors
 *   - Platform.error.boundary(fn, context) — wraps async functions safely
 *   - Platform.error.normalise(err)        — extracts a clean message from any error shape
 *   - Global window.onerror + unhandledrejection listeners log silently in prod
 *
 * Usage:
 *   // Wrap an async handler
 *   button.addEventListener('click', Platform.error.boundary(async () => {
 *       const data = await Platform.fetch.post('/api/save', payload);
 *       Platform.toast.success('Saved!');
 *   }, 'save-button'));
 *
 *   // Handle a caught error explicitly
 *   try {
 *       await riskyOperation();
 *   } catch (err) {
 *       Platform.error.handle(err, 'riskyOperation');
 *   }
 *
 *   // Normalise any error shape to a string
 *   const msg = Platform.error.normalise(err);
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before core/05-error.js');
    }

    const log = global.Platform.log
        ? global.Platform.log.child('error')
        : { warn: function(){}, error: function(){} };

    // ── Normalise any error shape to a human-readable string ─────────────────
    /**
     * Extract a clean message from any error-like value.
     * Handles: Error objects, fetch response shapes, Flask JSON error bodies,
     *          plain strings, and unknown objects.
     * @param {*} err
     * @returns {string}
     */
    function normalise(err) {
        if (!err) return 'An unknown error occurred';

        // Standard Error object
        if (err instanceof Error) {
            return err.message || err.toString();
        }

        // String
        if (typeof err === 'string') return err;

        // Flask/API JSON body shapes
        if (typeof err === 'object') {
            return (
                err.message  ||
                err.error    ||
                err.detail   ||
                err.msg      ||
                (err.errors && JSON.stringify(err.errors)) ||
                JSON.stringify(err)
            );
        }

        return String(err);
    }

    // ── Central error handler ────────────────────────────────────────────────
    /**
     * Handle a caught error: log it and show a toast (unless it was already
     * shown by Platform.fetch).
     *
     * @param {*}      err      - The error to handle
     * @param {string} [context] - Descriptive label for logging (e.g. function name)
     * @param {object} [options]
     * @param {boolean} [options.silent]   - Suppress toast (default: false)
     * @param {string}  [options.toastMsg] - Override toast message
     */
    function handle(err, context, options) {
        options = options || {};
        const msg = normalise(err);
        const label = context ? ('[' + context + '] ') : '';

        log.error(label + msg, err);

        // Platform.fetch already shows a toast for HttpError / NetworkError.
        // Avoid double-toasting those.
        const alreadyToasted = (
            err &&
            (err.type === 'HttpError' || err.type === 'NetworkError')
        );

        if (!options.silent && !alreadyToasted && global.Platform.toast) {
            global.Platform.toast.error(options.toastMsg || msg);
        }
    }

    // ── Async boundary wrapper ───────────────────────────────────────────────
    /**
     * Wrap an async function so that any thrown error is automatically handled.
     * Returns a synchronous function suitable for event listeners.
     *
     * @param {Function} fn       - Async function to wrap
     * @param {string}   [context] - Context label for error logging
     * @param {object}   [options] - Passed to handle()
     * @returns {Function}
     */
    function boundary(fn, context, options) {
        return function () {
            const args = arguments;
            const self = this;
            let result;
            try {
                result = fn.apply(self, args);
            } catch (syncErr) {
                handle(syncErr, context, options);
                return;
            }
            // If fn returned a Promise, catch async errors
            if (result && typeof result.then === 'function') {
                result.catch(function (asyncErr) {
                    handle(asyncErr, context, options);
                });
            }
            return result;
        };
    }

    // ── Global unhandled error listeners ────────────────────────────────────
    // Log silently — do NOT show toasts for unhandled errors (too noisy).
    //
    // P-07: these handlers used to pass the raw Error/rejection value
    // straight to log.error() as a positional arg. The browser devtools log itself
    // renders an Error fine interactively, but anything downstream that
    // stringifies the arguments (log capture, a headless test harness
    // reading console text, a future log-shipping hook) calls String()/
    // JSON.stringify() on it — and Error.message/.stack are *non-enumerable*,
    // so both produce the literal word "Object" / "[object Object]" with the
    // real diagnostic content silently dropped. Serialise explicitly instead
    // so the logged string always carries message, stack, and context.
    function _serialiseRejectionReason(reason) {
        if (reason instanceof Error) {
            return {
                message: reason.message || String(reason),
                stack: reason.stack || null,
                name: reason.name || 'Error'
            };
        }
        if (reason && typeof reason === 'object') {
            try {
                return { message: normalise(reason), stack: null, detail: JSON.parse(JSON.stringify(reason)) };
            } catch (e) {
                return { message: normalise(reason), stack: null };
            }
        }
        return { message: String(reason), stack: null };
    }

    // Alpine rejects a transition promise with {isFromCancelledTransition: true}
    // whenever one transition supersedes another -- a toast replacing a toast, an
    // x-show toggled twice before the first finished. That is Alpine's internal
    // "superseded" signal, not a failure: nothing went wrong and there is nothing
    // for anyone to act on. Reporting it as [Platform][error] invents an error
    // that did not happen, which is the same sin as inventing data, and it buries
    // real rejections in noise that scales with how much the UI is used.
    function _isCancelledAlpineTransition(reason) {
        return Boolean(reason)
            && typeof reason === 'object'
            && reason.isFromCancelledTransition === true;
    }

    global.window.addEventListener('unhandledrejection', function (event) {
        if (_isCancelledAlpineTransition(event.reason)) {
            // Always prevented, dev included. The usual reason to let a rejection
            // through in dev is so devtools still shows it -- but there is nothing
            // here worth showing, and leaving it unprevented surfaces a bare
            // "Object" in the console and in Playwright's pageerror channel, which
            // is what made the browser gates fail on pages that merely animate.
            event.preventDefault();
            return;
        }
        const serialised = _serialiseRejectionReason(event.reason);
        log.error(
            'Unhandled promise rejection: ' + serialised.message,
            'stack=' + (serialised.stack || 'n/a'),
            serialised.detail !== undefined ? serialised.detail : ''
        );
        // Prevent the browser from logging a duplicate uncaught error
        // only in development (so devtools still shows it).
        if (!global.Platform.isDev) {
            event.preventDefault();
        }
    });

    const _origOnError = global.window.onerror;
    global.window.onerror = function (message, source, lineno, colno, error) {
        const loc = source + ':' + lineno + ':' + colno;
        const stack = (error && error.stack) ? error.stack : 'n/a';
        log.error('Uncaught error: ' + message, 'at ' + loc, 'stack=' + stack);
        if (typeof _origOnError === 'function') {
            return _origOnError.apply(this, arguments);
        }
        return false;
    };

    // ── Public API ───────────────────────────────────────────────────────────
    const errorModule = {
        normalise: normalise,
        handle:    handle,
        boundary:  boundary
    };

    global.Platform.register('error', errorModule);

}(window));
