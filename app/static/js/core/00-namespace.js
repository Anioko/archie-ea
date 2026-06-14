/**
 * core/00-namespace.js — Platform namespace + load-order guard
 *
 * MUST be the FIRST script loaded on every page (before any other platform JS).
 *
 * Establishes the single global namespace `window.Platform` so that all
 * subsequent modules attach to it instead of polluting `window` directly.
 *
 * Load-order contract
 * -------------------
 * 00-namespace  → defines Platform + registry
 * 01-logger     → Platform.log
 * 02-sanitize   → Platform.sanitize
 * 03-fetch      → Platform.fetch
 * 04-toast      → Platform.toast
 * 05-error      → Platform.error
 * ui/modal      → Platform.modal
 * ui/pagination → Platform.pagination
 * ui/filter     → Platform.filter
 * ui/selection  → Platform.selection
 * ui/table      → Platform.table
 *
 * Feature modules (app/static/js/<domain>/*.js) load after all core + ui.
 *
 * Rules enforced here
 * -------------------
 * 1. Only ONE instance of Platform may exist per page.
 * 2. Each module calls Platform.register(name, api) exactly once.
 * 3. Duplicate registration throws in development, warns in production.
 * 4. No module may attach directly to window (except the Platform alias).
 */

(function (global) {
    'use strict';

    // ── Guard: only initialise once ─────────────────────────────────────────
    if (global.Platform) {
        // Already loaded — do not re-initialise.
        return;
    }

    // ── Environment detection ────────────────────────────────────────────────
    const isDev = (
        global.location &&
        (global.location.hostname === 'localhost' ||
         global.location.hostname === '127.0.0.1' ||
         global.location.hostname.endsWith('.local'))
    );

    // ── Module registry ──────────────────────────────────────────────────────
    const _registry = Object.create(null);

    /**
     * Register a named module on the Platform namespace.
     * @param {string} name  - Unique module name (e.g. 'log', 'fetch', 'modal')
     * @param {object} api   - Public API object to expose as Platform[name]
     */
    function register(name, api) {
        if (typeof name !== 'string' || !name) {
            throw new TypeError('[Platform] register: name must be a non-empty string');
        }
        if (_registry[name]) {
            const msg = '[Platform] Duplicate module registration: "' + name + '". ' +
                      'Each module must register exactly once.';
            if (isDev) {
                throw new Error(msg);
            } else {
                // Production: warn but don't crash
                if (global.console && global.console.warn) {
                    global.console.warn(msg);
                }
                return;
            }
        }
        _registry[name] = true;
        Platform[name] = api;
    }

    /**
     * Check whether a module has been registered.
     * @param {string} name
     * @returns {boolean}
     */
    function has(name) {
        return Boolean(_registry[name]);
    }

    /**
     * Assert that a required module is loaded. Throws if missing.
     * Feature modules call this to declare their dependencies.
     * @param {...string} names - Module names that must already be registered
     */
    function require(/* ...names */) {
        const names = Array.prototype.slice.call(arguments);
        names.forEach(function (name) {
            if (!_registry[name]) {
                throw new Error(
                    '[Platform] Required module "' + name + '" is not loaded. ' +
                    'Check your script load order.'
                );
            }
        });
    }

    // ── Version ──────────────────────────────────────────────────────────────
    const VERSION = '1.0.0';

    // ── Public Platform object ───────────────────────────────────────────────
    const Platform = {
        VERSION:  VERSION,
        isDev:    isDev,
        register: register,
        has:      has,
        require:  require,

        // Convenience: emit a CustomEvent on document (used by all modules)
        emit: function (eventName, detail) {
            const ev = new CustomEvent(eventName, {
                detail:  detail || {},
                bubbles: true
            });
            global.document.dispatchEvent(ev);
        },

        // Convenience: subscribe to a document-level CustomEvent
        on: function (eventName, handler) {
            global.document.addEventListener(eventName, handler);
        },

        // Convenience: unsubscribe
        off: function (eventName, handler) {
            global.document.removeEventListener(eventName, handler);
        }
    };

    // ── Expose globally ──────────────────────────────────────────────────────
    global.Platform = Platform;

    // Legacy shim: pages that still reference `window.Platform` directly
    // will find it. No other global is created by this file.

}(window));
