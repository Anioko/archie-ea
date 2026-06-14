/**
 * core/06-session-timeout.js — Client-side session expiry warning
 *
 * Requires: core/00-namespace.js through core/05-error.js, ui/modal.js
 *
 * Shows a warning modal 30 minutes before the 8-hour session expires.
 * Offers "Extend Session" (pings /health to refresh cookie) and "Log Out".
 * Auto-redirects to login after 5 minutes if the user does not respond.
 *
 * Timer resets on every Platform.fetch call (piggybacks on the global fetch
 * wrapper) and on explicit user interaction via extend.
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
    const SESSION_DURATION   = 8 * 60 * 60 * 1000;   // 8 hours
    const WARNING_BEFORE     = 30 * 60 * 1000;        // 30 minutes before expiry
    const AUTO_LOGOUT_GRACE  = 5 * 60 * 1000;         // 5 minutes after warning
    const LOGIN_URL          = '/account/login';
    const HEALTH_URL         = '/health';

    // Derived
    const WARNING_DELAY      = SESSION_DURATION - WARNING_BEFORE; // 7.5 hours
    const LOGOUT_DELAY       = WARNING_DELAY + AUTO_LOGOUT_GRACE; // 7 hours 35 min

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
        global.location.href = LOGIN_URL + '?timeout=1';
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
        warningTimerId = setTimeout(showWarning, WARNING_DELAY);
        logoutTimerId  = setTimeout(autoLogout,  LOGOUT_DELAY);
        log.debug('timer reset');
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

    function extendSession() {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', HEALTH_URL, true);
        xhr.onload = function () {
            dismissWarning();
            resetTimer();
            log.debug('session extended');
            if (global.Platform.toast) {
                global.Platform.toast.success('Session extended');
            }
        };
        xhr.onerror = function () {
            dismissWarning();
            resetTimer();
            log.warn('health ping failed — timer reset anyway');
        };
        xhr.send();
    }

    // --- Hook into fetch to reset timer on every request ---
    // Platform.fetch calls global.fetch internally, so wrapping global.fetch
    // catches both Platform.fetch and any direct fetch() usage.
    function hookFetch() {
        if (typeof global.fetch !== 'function') return;
        const nativeFetch = global.fetch;
        global.fetch = function () {
            const result = nativeFetch.apply(this, arguments);
            try { resetTimer(); } catch (e) { /* swallow */ }
            return result;
        };
    }

    // --- Initialization ---
    function init() {
        hookFetch();
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
        reset:  resetTimer,
        extend: extendSession,
        logout: autoLogout
    };

    global.Platform.register('sessionTimeout', sessionTimeout);

}(window));
