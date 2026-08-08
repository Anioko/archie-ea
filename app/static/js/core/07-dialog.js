/**
 * core/07-dialog.js — Platform.confirm / Platform.alert
 *
 * Branded, accessible replacements for the browser's native confirm() and
 * alert(), which DESIGN.md bans and which 72 call sites still used.
 *
 * Why they are banned is worth restating, because "it works" is the usual
 * defence:
 *   - They block the entire browser thread. Nothing renders, no timer fires,
 *     and any automation driving the page stops dead until a human clicks.
 *   - They cannot be styled, so a Fortune 500 buyer sees a Chrome dialog
 *     saying "127.0.0.1 says" in the middle of an enterprise product.
 *   - They are not translatable and ignore the page's dark/light theme.
 *   - Chrome suppresses them entirely in cross-origin iframes and after
 *     repeated use, so the "Are you sure?" that guards a delete can silently
 *     stop appearing.
 *
 * API — promise-based, so an await or a .then reads like the original:
 *
 *     // was:  if (confirm('Delete this?')) { doDelete(); }
 *     Platform.confirm('Delete this?').then(function (ok) { if (ok) doDelete(); });
 *
 *     // or, in an async handler:
 *     if (await Platform.confirm('Delete this?')) doDelete();
 *
 *     Platform.alert('Saved.');                       // informational
 *     Platform.confirm({ title: 'Delete application?',
 *                        message: 'This cannot be undone.',
 *                        confirmText: 'Delete', variant: 'destructive' });
 *
 * Falls back to the native dialog only if the DOM is unavailable, so a caller
 * can never end up with a promise that never settles.
 */
(function (global) {
    'use strict';

    var ACTIVE = null;

    function _opts(input, defaults) {
        var o = (typeof input === 'string' || input == null)
            ? { message: input || '' }
            : (input || {});
        return {
            title: o.title || defaults.title,
            message: o.message || '',
            confirmText: o.confirmText || defaults.confirmText,
            cancelText: o.cancelText || defaults.cancelText,
            variant: o.variant || defaults.variant,
            showCancel: defaults.showCancel,
        };
    }

    function _el(tag, className, text) {
        var node = global.document.createElement(tag);
        if (className) node.className = className;
        // textContent, never innerHTML: the message can carry a record name
        // typed by a user, and this dialog is not an XSS sink.
        if (text != null) node.textContent = text;
        return node;
    }

    function _open(options) {
        var doc = global.document;
        if (!doc || !doc.body) {
            // No DOM to render into. Fall back rather than hang forever.
            var native = options.showCancel ? global.confirm : global.alert;
            return Promise.resolve(!!native.call(global, options.message));
        }

        // Only one at a time; a second call resolves the first as cancelled.
        if (ACTIVE) ACTIVE.settle(false);

        return new Promise(function (resolve) {
            var previouslyFocused = doc.activeElement;

            var overlay = _el('div',
                'fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4');
            var panel = _el('div',
                'w-full max-w-md rounded-lg border border-border bg-card text-card-foreground shadow-lg p-6');
            panel.setAttribute('role', 'alertdialog');
            panel.setAttribute('aria-modal', 'true');

            var heading = _el('h2', 'text-lg font-semibold text-foreground', options.title);
            var headingId = 'platform-dialog-title';
            heading.id = headingId;
            panel.setAttribute('aria-labelledby', headingId);
            panel.appendChild(heading);

            if (options.message) {
                var body = _el('p', 'mt-2 text-sm text-muted-foreground', options.message);
                body.id = 'platform-dialog-desc';
                panel.setAttribute('aria-describedby', body.id);
                panel.appendChild(body);
            }

            var actions = _el('div', 'mt-6 flex justify-end gap-2');
            var confirmClass = options.variant === 'destructive'
                ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                : 'bg-primary text-primary-foreground hover:bg-primary/90';

            var cancelBtn = null;
            if (options.showCancel) {
                cancelBtn = _el('button',
                    'inline-flex items-center justify-center rounded-md border border-input bg-background ' +
                    'px-4 py-2 text-sm font-medium hover:bg-accent transition-colors',
                    options.cancelText);
                cancelBtn.type = 'button';
                actions.appendChild(cancelBtn);
            }

            var confirmBtn = _el('button',
                'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium ' +
                'transition-colors ' + confirmClass, options.confirmText);
            confirmBtn.type = 'button';
            actions.appendChild(confirmBtn);
            panel.appendChild(actions);
            overlay.appendChild(panel);
            doc.body.appendChild(overlay);

            function settle(result) {
                if (!overlay.parentNode) return;
                doc.removeEventListener('keydown', onKey, true);
                overlay.parentNode.removeChild(overlay);
                ACTIVE = null;
                if (previouslyFocused && previouslyFocused.focus) {
                    // Best-effort focus restore: element may have been removed from the DOM
                    // while the dialog was open, in which case there is nothing to focus.
                    try { previouslyFocused.focus(); } catch (e) { /* detached */ }
                }
                resolve(result);
            }

            function onKey(event) {
                if (event.key === 'Escape') { event.preventDefault(); settle(false); return; }
                if (event.key !== 'Tab') return;
                // Keep focus inside the dialog: a modal the keyboard can walk
                // out of is not modal, and screen-reader users end up on the
                // page behind it with no way back.
                var focusable = panel.querySelectorAll('button');
                if (!focusable.length) return;
                var first = focusable[0];
                var last = focusable[focusable.length - 1];
                if (event.shiftKey && doc.activeElement === first) {
                    event.preventDefault(); last.focus();
                } else if (!event.shiftKey && doc.activeElement === last) {
                    event.preventDefault(); first.focus();
                }
            }

            confirmBtn.addEventListener('click', function () { settle(true); });
            if (cancelBtn) cancelBtn.addEventListener('click', function () { settle(false); });
            overlay.addEventListener('click', function (event) {
                if (event.target === overlay) settle(false);
            });
            doc.addEventListener('keydown', onKey, true);

            ACTIVE = { settle: settle };
            (cancelBtn || confirmBtn).focus();
        });
    }

    var dialog = {
        confirm: function (input) {
            return _open(_opts(input, {
                title: 'Are you sure?',
                confirmText: 'Confirm',
                cancelText: 'Cancel',
                variant: 'default',
                showCancel: true,
            }));
        },
        alert: function (input) {
            return _open(_opts(input, {
                title: 'Notice',
                confirmText: 'OK',
                cancelText: '',
                variant: 'default',
                showCancel: false,
            }));
        },
    };

    global.Platform.register('confirm', dialog.confirm);
    global.Platform.register('alert', dialog.alert);

}(window));
