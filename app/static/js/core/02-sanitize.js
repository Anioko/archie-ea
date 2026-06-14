/**
 * core/02-sanitize.js — Unified HTML sanitization and escaping
 *
 * Requires: core/00-namespace.js, core/01-logger.js
 *
 * Replaces:
 *   - app/static/js/safe_html.js          (safeHTML, safeText, escapeHtml globals)
 *   - Inline escapeHtml() in toast-notifications.js
 *   - Inline escapeHtml() in modal_manager.js
 *   - Any direct innerHTML assignments across feature modules
 *
 * Rules:
 *   - NEVER use innerHTML directly — always go through Platform.sanitize.html()
 *   - NEVER trust user-supplied strings in template literals without escapeHtml()
 *   - DOMPurify is the primary sanitizer; a safe fallback is provided if absent
 *
 * Usage:
 *   Platform.sanitize.html(element, '<b>user content</b>');
 *   Platform.sanitize.text(element, 'raw user text');
 *   const safe = Platform.sanitize.escape('user <input>');
 *   const clean = Platform.sanitize.purify('<script>alert(1)</script><b>ok</b>');
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before core/02-sanitize.js');
    }

    let log = global.Platform.log
        ? global.Platform.log.child('sanitize')
        : { warn: function (m) { if (global.console) global.console.warn(m); } };

    // ── DOMPurify config ─────────────────────────────────────────────────────
    // Allow standard HTML but strip all event handlers and dangerous protocols.
    let PURIFY_CONFIG = {
        ALLOWED_TAGS: [
            'a', 'abbr', 'b', 'blockquote', 'br', 'button', 'caption',
            'cite', 'code', 'col', 'colgroup', 'dd', 'del', 'details',
            'dfn', 'div', 'dl', 'dt', 'em', 'figcaption', 'figure',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
            'input', 'ins', 'kbd', 'label', 'li', 'mark', 'ol', 'p',
            'pre', 'q', 's', 'samp', 'section', 'select', 'small',
            'span', 'strong', 'sub', 'summary', 'sup', 'table',
            'tbody', 'td', 'textarea', 'tfoot', 'th', 'thead', 'time',
            'tr', 'u', 'ul', 'var', 'wbr',
            // Lucide icon host
            'svg', 'path', 'circle', 'rect', 'line', 'polyline',
            'polygon', 'g', 'defs', 'use', 'symbol'
        ],
        ALLOWED_ATTR: [
            'aria-*', 'class', 'data-*', 'disabled', 'for', 'href',
            'id', 'name', 'placeholder', 'readonly', 'role', 'src',
            'style', 'tabindex', 'target', 'title', 'type', 'value',
            // SVG
            'd', 'fill', 'stroke', 'stroke-width', 'stroke-linecap',
            'stroke-linejoin', 'viewBox', 'xmlns', 'width', 'height',
            'cx', 'cy', 'r', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
            'points', 'transform'
        ],
        FORBID_TAGS:  ['script', 'style', 'iframe', 'object', 'embed', 'form'],
        FORBID_ATTR:  ['onerror', 'onload', 'onclick', 'onmouseover'],
        ALLOW_DATA_ATTR: true
    };

    /**
     * Sanitize an HTML string using DOMPurify.
     * Falls back to stripping all tags if DOMPurify is unavailable.
     * @param {string} html
     * @returns {string} Safe HTML string
     */
    function purify(html) {
        if (typeof html !== 'string') {
            return '';
        }
        if (global.DOMPurify && typeof global.DOMPurify.sanitize === 'function') {
            return global.DOMPurify.sanitize(html, PURIFY_CONFIG);
        }
        // Fallback: strip all tags (safe but lossy)
        log.warn('DOMPurify not loaded — stripping all HTML tags as fallback');
        let tmp = global.document.createElement('div');
        tmp.textContent = html;
        return tmp.innerHTML;
    }

    /**
     * Set innerHTML of an element using sanitized HTML.
     * This is the ONLY approved way to set innerHTML on the platform.
     * @param {HTMLElement} el
     * @param {string} html
     */
    // Table-context tags whose children (tr/td) need a table wrapper for
    // DOMPurify to parse correctly.  Without the wrapper the browser's HTML
    // parser strips <tr>/<td> because they are invalid inside a <div>.
    let TABLE_CONTEXT_TAGS = { TBODY: 1, THEAD: 1, TFOOT: 1 };

    function html(el, htmlString) {
        if (!el || !(el instanceof global.Element)) {
            log.warn('sanitize.html: target is not a DOM element', el);
            return;
        }

        // When the target is a table section, wrap the fragment so DOMPurify
        // parses <tr>/<td> in a valid table context, then extract the rows.
        if (TABLE_CONTEXT_TAGS[el.tagName]) {
            let wrapper = '<table><tbody>' + htmlString + '</tbody></table>';
            let clean = purify(wrapper);
            // Extract inner content from the sanitized <table><tbody>…</tbody></table>
            let tmp = global.document.createElement('div');
            tmp.innerHTML = clean;
            let innerTbody = tmp.querySelector('tbody');
            el.innerHTML = innerTbody ? innerTbody.innerHTML : clean;
            return;
        }

        el.innerHTML = purify(htmlString);
    }

    /**
     * Set textContent of an element (always safe — never parses HTML).
     * @param {HTMLElement} el
     * @param {string|null|undefined} text
     */
    function text(el, value) {
        if (!el || !(el instanceof global.Element)) {
            log.warn('sanitize.text: target is not a DOM element', el);
            return;
        }
        el.textContent = String(value !== null && value !== undefined ? value : '');
    }

    /**
     * Escape a string for safe embedding inside a template-literal HTML string.
     * Use this when building HTML strings that will be passed to sanitize.html().
     * @param {string|null|undefined} value
     * @returns {string}
     */
    function escape(value) {
        if (value === null || value === undefined) return '';
        let div = global.document.createElement('div');
        div.textContent = String(value);
        return div.innerHTML;
    }

    let sanitize = {
        html:   html,
        text:   text,
        escape: escape,
        purify: purify
    };

    // ── Legacy global shims (backward-compat, read-only) ────────────────────
    // Existing code that calls safeHTML(), safeText(), escapeHtml() directly
    // will continue to work. New code must use Platform.sanitize.*
    if (typeof global.safeHTML === 'undefined') {
        global.safeHTML = html;
    }
    if (typeof global.safeText === 'undefined') {
        global.safeText = text;
    }
    if (typeof global.escapeHtml === 'undefined') {
        global.escapeHtml = escape;
    }

    global.Platform.register('sanitize', sanitize);

}(window));
