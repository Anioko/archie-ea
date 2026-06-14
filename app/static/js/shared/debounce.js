/**
 * Shared debounce and throttle utilities.
 *
 * Loaded globally via _scripts_common.html after api-fetch.js.
 * Both functions are idempotent — safe to load multiple times.
 *
 * Usage:
 *   var handler = debounce(function(e) { console.log(e); }, 300);
 *   input.addEventListener('input', handler);
 *
 *   var scroller = throttle(function() { console.log('scroll'); }, 200);
 *   window.addEventListener('scroll', scroller);
 */

/**
 * Returns a debounced version of `fn` that delays invocation until `ms`
 * milliseconds have elapsed since the last call. Preserves `this` context
 * and forwards all arguments.
 *
 * @param {Function} fn  - The function to debounce
 * @param {number}   ms  - Delay in milliseconds (default 250)
 * @returns {Function} Debounced function
 */
if (typeof window.debounce === 'undefined') {
    window.debounce = function debounce(fn, ms) {
        let timerId = null;
        if (typeof ms !== 'number' || ms < 0) {
            ms = 250;
        }
        return function debounced() {
            const context = this;
            const args = arguments;
            if (timerId !== null) {
                clearTimeout(timerId);
            }
            timerId = setTimeout(function() {
                timerId = null;
                fn.apply(context, args);
            }, ms);
        };
    };
}

/**
 * Returns a throttled version of `fn` that invokes at most once every `ms`
 * milliseconds. Uses a timestamp comparison so the first call fires
 * immediately. Preserves `this` context and forwards all arguments.
 *
 * @param {Function} fn  - The function to throttle
 * @param {number}   ms  - Minimum interval in milliseconds (default 250)
 * @returns {Function} Throttled function
 */
if (typeof window.throttle === 'undefined') {
    window.throttle = function throttle(fn, ms) {
        let lastRun = 0;
        if (typeof ms !== 'number' || ms < 0) {
            ms = 250;
        }
        return function throttled() {
            const now = Date.now();
            if (now - lastRun >= ms) {
                lastRun = now;
                fn.apply(this, arguments);
            }
        };
    };
}
