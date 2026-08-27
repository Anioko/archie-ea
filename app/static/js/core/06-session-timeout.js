/**
 * core/06-session-timeout.js — Client-side session expiry warning
 *
 * Requires: core/00-namespace.js through core/05-error.js, ui/modal.js
 *
 * Courtesy warning ahead of the SERVER-enforced idle timeout
 * (app/_bootstrap/session_policy.py). The server is authoritative; this file
 * exists so the user sees it coming instead of losing unsaved work silently.
 *
 * Timer resets on genuine activity (keydown / click / scroll / touchstart /
 * visibilitychange) and on every fetch, and the idle window is read from
 * <body data-session-idle-seconds> so the two halves cannot drift apart.
 *
 * Registered as Platform.sessionTimeout with reset / extend / logout methods.
 */
(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before core/06-session-timeout.js');
    }

    const log = global.Platform.log
        ? global.Platform.log.child('session')
        : { debug: function(){}, warn: function(){}, error: function(){} };

    // --- Configuration (all values in milliseconds) ---
    // F-07: the timer below is an IDLE timer, not an absolute-lifetime timer.
    // It previously counted down 8 hours from page load, reset on nothing, and
    // so implemented no timeout of any kind. The authoritative control is the
    // server's before_request check in app/_bootstrap/session_policy.py; this
    // is a courtesy warning that must agree with it, so the window is read
    // from the value the server rendered into <body data-session-idle-seconds>
    // and only falls back to the default if that attribute is missing.
    const DEFAULT_IDLE_MS    = 30 * 60 * 1000;        // matches SESSION_IDLE_TIMEOUT

    function readIdleWindow() {
        try {
            const el = global.document.body;
            const raw = el && el.getAttribute('data-session-idle-seconds');
            const secs = raw ? parseInt(raw, 10) : NaN;
            if (!isNaN(secs) && secs > 0) return secs * 1000;
        } catch (e) {
            log.debug('idle window attribute unreadable; using default');
        }
        return DEFAULT_IDLE_MS;
    }

    let IDLE_WINDOW          = DEFAULT_IDLE_MS;
    const WARNING_BEFORE     = 2 * 60 * 1000;         // warn 2 min before the server cuts it
    const AUTO_LOGOUT_GRACE  = 2 * 60 * 1000;         // then stop pretending it is alive
    const LOGIN_URL          = '/account/login';
    const KEEPALIVE_URL      = '/account/session/keepalive';
    // Ignore bursts of activity: at most one keep-alive ping per interval.
    const ACTIVITY_THROTTLE  = 60 * 1000;

    // Derived, recomputed whenever the idle window is (re)read.
    let WARNING_DELAY        = Math.max(IDLE_WINDOW - WARNING_BEFORE, 5000);
    let LOGOUT_DELAY         = IDLE_WINDOW + AUTO_LOGOUT_GRACE;

    // --- State ---
    let warningTimerId  = null;
    let logoutTimerId   = null;
    let modalId         = null;
    let countdownId     = null;

    // --- Helpers ---

    function formatCountdown(totalSeconds) {
        const min = Math.floor(totalSeconds / 60);
        const sec = totalSeconds % 60;
        if (min > 0) {
            return min + ' min ' + (sec < 10 ? '0' : '') + sec + ' sec';
        }
        return sec + ' sec';
    }

    function clearAllTimers() {
        if (warningTimerId !== null) {
            clearTimeout(warningTimerId);
            warningTimerId = null;
        }
        if (logoutTimerId !== null) {
            clearTimeout(logoutTimerId);
            logoutTimerId = null;
        }
        if (countdownId !== null) {
            clearInterval(countdownId);
            countdownId = null;
        }
    }

    function autoLogout() {
        clearAllTimers();
        dismissWarning();
        // By now the server has already invalidated the session (its window is
        // the shorter of the two), so surface the same non-dismissable prompt
        // a failed write would, rather than a bare redirect.
        forceReauth('Your session expired after a period of inactivity.');
    }

    function dismissWarning() {
        if (modalId && global.Platform.modal) {
            try {
                global.Platform.modal.destroy(modalId);
            } catch (e) {
                log.debug('modal already dismissed');
            }
            modalId = null;
        }
    }

    function resetTimer() {
        clearAllTimers();
        dismissWarning();
        IDLE_WINDOW   = readIdleWindow();
        WARNING_DELAY = Math.max(IDLE_WINDOW - WARNING_BEFORE, 5000);
        LOGOUT_DELAY  = IDLE_WINDOW + AUTO_LOGOUT_GRACE;
        warningTimerId = setTimeout(showWarning, WARNING_DELAY);
        logoutTimerId  = setTimeout(autoLogout,  LOGOUT_DELAY);
        log.debug('idle timer reset');
    }

    // --- F-07: genuine-activity listeners ---
    // The audited version of this file registered none, so nothing ever reset
    // the countdown and nothing ever expired on inactivity. These reset the
    // client timer on real interaction; they do NOT extend the server session
    // by themselves — the server's stamp only moves when a request is made,
    // which is why keep-alive below is throttled rather than fired per event.
    let lastActivityPing = 0;

    async function onActivity() {
        const now = Date.now();
        resetTimer();
        if (now - lastActivityPing < ACTIVITY_THROTTLE) return;
        lastActivityPing = now;
        // A same-origin GET is enough to move the server-side last-activity
        // stamp; /health is exempt from the server check precisely so that a
        // background poll cannot keep an abandoned tab alive, so ping the
        // login page's cheap sibling instead only when the user really acted.
        try {
            await Platform.fetch.get(KEEPALIVE_URL, null, { silent: true });
        } catch (e) {
            log.debug('keepalive ping failed (non-fatal)');
        }
    }

    function registerActivityListeners() {
        const doc = global.document;
        ['keydown', 'click', 'scroll', 'touchstart'].forEach(function (evt) {
            doc.addEventListener(evt, onActivity, { passive: true });
        });
        doc.addEventListener('visibilitychange', function () {
            if (!doc.hidden) onActivity();
        });
    }

    function showWarning() {
        // Guard: Platform.modal may not be loaded yet
        if (!global.Platform.modal || typeof global.Platform.modal.create !== 'function') {
            log.warn('Platform.modal not available — skipping warning');
            return;
        }

        dismissWarning();

        let remainingSeconds = Math.floor(AUTO_LOGOUT_GRACE / 1000);

        modalId = global.Platform.modal.create({
            id: 'session-timeout-warning',
            title: 'Session Expiring Soon',
            size: 'sm',
            content:
                '<div class="text-center space-y-4">' +
                    '<div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-amber-500/10 mb-4">' +
                        '<svg class="h-6 w-6 text-amber-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">' +
                            '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />' +
                        '</svg>' +
                    '</div>' +
                    '<p class="text-sm text-muted-foreground">' +
                        'Your session will expire in <strong id="session-countdown">' +
                        formatCountdown(remainingSeconds) +
                        '</strong>. Extend your session to avoid losing unsaved work.' +
                    '</p>' +
                '</div>',
            backdrop: false,
            keyboard: false,
            buttons: [
                {
                    label: 'Log Out',
                    variant: 'outline',
                    handler: function () {
                        clearAllTimers();
                        global.location.href = LOGIN_URL;
                    },
                    closeOnClick: false
                },
                {
                    label: 'Extend Session',
                    variant: 'primary',
                    handler: function () {
                        extendSession();
                    },
                    closeOnClick: false
                }
            ]
        });

        global.Platform.modal.open(modalId);
        log.debug('warning shown');

        // Live countdown
        countdownId = setInterval(function () {
            remainingSeconds -= 1;
            if (remainingSeconds <= 0) {
                clearInterval(countdownId);
                countdownId = null;
                return;
            }
            const el = global.document.getElementById('session-countdown');
            if (el) {
                el.textContent = formatCountdown(remainingSeconds);
            }
        }, 1000);
    }

    async function extendSession() {
        try {
            await Platform.fetch.get(KEEPALIVE_URL, null, { silent: true });
            dismissWarning();
            resetTimer();
            log.debug('session extended');
            if (global.Platform.toast) {
                global.Platform.toast.success('Session extended');
            }
        } catch (e) {
            dismissWarning();
            resetTimer();
            log.warn('health ping failed — timer reset anyway');
        }
    }

    // --- A-08: reactive re-auth prompt ---
    // Called by core/03-fetch.js the moment a write actually fails because
    // the server-side session/CSRF token is no longer valid (e.g. after a
    // server restart) — distinct from the proactive 30-minutes-before
    // warning above, which fires on a client-side clock that has no idea
    // the server already invalidated the session early. Unlike
    // showWarning(), this prompt is non-dismissable (no backdrop click, no
    // Escape, no "stay logged in" option) because the session is already
    // gone, not merely expiring — offering to "extend" it would just fail
    // again on the next write.
    let reauthShown = false;

    function forceReauth(message) {
        clearAllTimers();
        dismissWarning();

        if (reauthShown) return; // already prompting; don't stack modals
        reauthShown = true;

        if (global.Platform.toast) {
            global.Platform.toast.error(message || 'Your session has expired. Please log in again.');
        }

        const nextUrl = global.location.pathname + global.location.search;
        const loginHref = LOGIN_URL + '?expired=1&next=' + global.encodeURIComponent(nextUrl);

        if (global.Platform.modal && typeof global.Platform.modal.create === 'function') {
            modalId = global.Platform.modal.create({
                id: 'session-expired-reauth',
                title: 'Session Expired',
                size: 'sm',
                content:
                    '<div class="text-center space-y-4">' +
                        '<div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-destructive/10 mb-4">' +
                            '<svg class="h-6 w-6 text-destructive" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />' +
                            '</svg>' +
                        '</div>' +
                        '<p class="text-sm text-muted-foreground">' +
                            'Your session is no longer valid, most likely because it expired or the server restarted. ' +
                            'Any change you just tried to make was not saved. Please log in again to continue.' +
                        '</p>' +
                    '</div>',
                backdrop: false,
                keyboard: false,
                buttons: [
                    {
                        label: 'Log In Again',
                        variant: 'primary',
                        handler: function () {
                            global.location.href = loginHref;
                        },
                        closeOnClick: false
                    }
                ]
            });
            global.Platform.modal.open(modalId);
            log.warn('session invalid — re-auth prompt shown');
        } else {
            // Modal system unavailable — the toast above already told the
            // user; still redirect rather than leaving them stuck.
            global.location.href = loginHref;
        }
    }

    // --- Hook into fetch to reset timer on every request ---
    // Platform.fetch calls global.fetch internally, so wrapping global.fetch
    // catches both Platform.fetch and any direct fetch() usage.  // raw-fetch-ok: this IS the fetch hook -- it wraps global.fetch so every request resets the idle timer
    function hookFetch() {
        if (typeof global.fetch !== 'function') return;
        const nativeFetch = global.fetch;
        global.fetch = function () {
            const result = nativeFetch.apply(this, arguments);
            // Best-effort activity ping: a failure here must never break the caller's fetch.
            try { resetTimer(); } catch (e) { /* swallow-ok: this wraps every fetch on the site; an idle-timer failure must never surface as an error on the caller's unrelated request */ }
            return result;
        };
    }

    // --- Initialization ---
    function init() {
        hookFetch();
        registerActivityListeners();
        resetTimer();
        log.debug('initialized');
    }

    if (global.document.readyState === 'loading') {
        global.document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // --- Public API ---
    const sessionTimeout = {
        reset:       resetTimer,
        extend:      extendSession,
        logout:      autoLogout,
        forceReauth: forceReauth
    };

    global.Platform.register('sessionTimeout', sessionTimeout);

}(window));
