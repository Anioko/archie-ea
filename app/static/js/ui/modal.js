/**
 * ui/modal.js — Unified modal controller
 *
 * Requires: core/00-namespace.js through core/05-error.js
 *
 * Replaces ALL of the following (do NOT load them alongside this file):
 *   - app/static/js/modal_manager.js      (ModalManager class, window.modalManager)
 *   - app/static/js/modal-system.js       (ModalSystem class, window.Modal)
 *   - Inline <script> modal open/close in modal.html, modal_form.html
 *   - window.openModal / window.closeModal scattered helpers
 *   - window.openAddApplicationsModal, window.closeAddApplicationsModal, etc.
 *   - window.openUnifiedMappingModal, window.openUnifiedMappingModalDiscovery
 *   - window.openDrawer / window.closeDrawer
 *
 * Architecture:
 *   - Single source of truth: Platform.modal
 *   - HTML modals are authored with data-modal-id="my-modal"
 *   - Triggers use data-modal-open="my-modal" / data-modal-close="my-modal"
 *   - JS API: Platform.modal.open(id, payload) / .close(id, result)
 *   - Promise API: await Platform.modal.prompt(id, payload)
 *   - Dynamic modals: Platform.modal.create({...}) / .destroy(id)
 *   - Drawer support: Platform.modal.openDrawer(id) / .closeDrawer(id)
 *   - Alpine.js store integration: Alpine.store('modal')
 *   - Focus trapping + Escape key + backdrop click
 *   - LIFO stacking (last opened = first closed)
 *
 * HTML contract:
 *   <div id="my-modal"
 *        class="hidden fixed inset-0 z-50 ..."
 *        role="dialog"
 *        aria-modal="true"
 *        aria-labelledby="my-modal-title"
 *        data-modal-backdrop="true">
 *     ...
 *   </div>
 *
 *   <!-- Trigger (no inline JS needed) -->
 *   <button data-modal-open="my-modal">Open</button>
 *   <button data-modal-close="my-modal">Close</button>
 *
 * JS usage:
 *   Platform.modal.open('my-modal', { userId: 42 });
 *   Platform.modal.close('my-modal');
 *   Platform.modal.resolve('my-modal', { saved: true });
 *   const result = await Platform.modal.prompt('my-modal', payload);
 *   const id = Platform.modal.create({ title: 'Confirm', content: '<p>Sure?</p>' });
 *   Platform.modal.destroy(id);
 *   Platform.modal.on('my-modal', 'open',  (payload) => {});
 *   Platform.modal.on('my-modal', 'close', (result)  => {});
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before ui/modal.js');
    }

    const log      = global.Platform.log      ? global.Platform.log.child('modal')      : { debug: function(){}, warn: function(){}, error: function(){} };
    const sanitize = global.Platform.sanitize || { html: function(el, h){ el.innerHTML = h; }, escape: function(s){ return String(s||''); } };

    // ── State ────────────────────────────────────────────────────────────────
    const _registry  = Object.create(null);  // id → { element, config, isOpen, hooks, resolver, prevFocus }
    const _stack     = [];                   // open modal ids, LIFO
    // prevFocus is stored per-entry in _registry[id].prevFocus (not a shared module variable)
    // to support multiple simultaneously-opened modals each restoring their own trigger.

    // ── Default config ───────────────────────────────────────────────────────
    const DEFAULTS = {
        backdrop: true,   // click backdrop to close
        keyboard: true,   // Escape key closes
        focus:    true,   // trap focus inside modal
        size:     'md'    // sm | md | lg | xl | full
    };

    const SIZE_CLASSES = {
        sm:   'max-w-md',
        md:   'max-w-2xl',
        lg:   'max-w-4xl',
        xl:   'max-w-6xl',
        full: 'max-w-full mx-4'
    };

    // ── Helpers ──────────────────────────────────────────────────────────────
    function _getEl(id) {
        return global.document.getElementById(id);
    }

    function _focusableIn(el) {
        const candidates = Array.prototype.slice.call(el.querySelectorAll(
            'button:not([disabled]), [href], area[href], input:not([disabled]), select:not([disabled]), ' +
            'textarea:not([disabled]), [contenteditable="true"], [tabindex]:not([tabindex="-1"])'
        ));
        return candidates.filter(function (node) {
            if (!node) return false;
            if (node.getAttribute && node.getAttribute('aria-hidden') === 'true') return false;
            if (node.hasAttribute && node.hasAttribute('inert')) return false;
            if (typeof node.tabIndex === 'number' && node.tabIndex < 0) return false;
            const style = global.getComputedStyle ? global.getComputedStyle(node) : null;
            if (style && (style.display === 'none' || style.visibility === 'hidden')) return false;
            if (style && style.position !== 'fixed' && node.offsetParent === null) return false;
            return true;
        });
    }

    function _trapFocus(el, id) {
        const focusable = _focusableIn(el);
        if (!focusable.length) return;
        // Store prevFocus per-entry so parallel modals each restore their own trigger
        if (_registry[id]) {
            _registry[id].prevFocus = global.document.activeElement;
        }
        setTimeout(function () { focusable[0].focus(); }, 50);

        function onKeyDown(e) {
            if (e.key !== 'Tab') return;
            const focusable2 = _focusableIn(el);
            if (!focusable2.length) {
                e.preventDefault();
                return;
            }
            const first = focusable2[0];
            const last  = focusable2[focusable2.length - 1];
            const active = global.document.activeElement;
            if (focusable2.indexOf(active) === -1) {
                e.preventDefault();
                (e.shiftKey ? last : first).focus();
                return;
            }
            if (e.shiftKey) {
                if (global.document.activeElement === first) { e.preventDefault(); last.focus(); }
            } else {
                if (global.document.activeElement === last)  { e.preventDefault(); first.focus(); }
            }
        }
        el._modalFocusTrap = onKeyDown;
        el.addEventListener('keydown', onKeyDown);
    }

    function _releaseFocus(el, id) {
        if (el._modalFocusTrap) {
            el.removeEventListener('keydown', el._modalFocusTrap);
            delete el._modalFocusTrap;
        }
        const entry = _registry[id];
        if (entry && entry.prevFocus && typeof entry.prevFocus.focus === 'function') {
            entry.prevFocus.focus();
            entry.prevFocus = null;
        }
    }

    function _runHooks(id, event, data) {
        const entry = _registry[id];
        if (!entry || !entry.hooks || !entry.hooks[event]) return;
        entry.hooks[event].forEach(function (fn) {
            try { fn(data); } catch(e) { log.error('Hook error', id, event, e); }
        });
    }

    // ── Screen-reader announcer (VIOLATION-8) ────────────────────────────────
    /**
     * Announce modal open/close to screen readers via the Alpine $store.announcer
     * (defined in admin_base.html). Falls back silently if Alpine is not loaded.
     */
    function _announceModal(id, isOpen) {
        try {
            const el = _getEl(id);
            const labelId = el && el.getAttribute('aria-labelledby');
            const titleEl = labelId && global.document.getElementById(labelId);
            const title = titleEl ? titleEl.textContent.trim() : id;
            const message = isOpen ? (title + ' dialog opened') : (title + ' dialog closed');
            if (typeof Alpine !== 'undefined' && Alpine.store) {
                const announcer = Alpine.store('announcer');
                if (announcer && typeof announcer.assertive === 'function') {
                    announcer.assertive(message);
                }
            }
        } catch(e) { /* announcer unavailable — fail silently */ }
    }

    // ── Background inert management (VIOLATION-10) ───────────────────────────
    /**
     * Set/unset the `inert` attribute on all direct children of <body> that are
     * NOT the currently open modal, so that screen readers and keyboard navigation
     * cannot reach content behind the modal.
     *
     * @param {string|null} activeModalId  - modal currently on top (null when restoring)
     * @param {boolean}     inertBackground - true = add inert, false = remove inert
     */
    function _setBackgroundInert(activeModalId, inertBackground) {
        try {
            const activeModalEl = activeModalId ? _getEl(activeModalId) : null;
            const children = global.document.body.children;
            for (let i = 0; i < children.length; i++) {
                const child = children[i];
                // Never inert the active modal element itself or aria-live regions
                const isModal = !!(
                    activeModalEl &&
                    (child === activeModalEl || child.contains(activeModalEl))
                );
                const isLiveRegion = child.getAttribute('aria-live') || child.getAttribute('role') === 'status';
                const isScript = child.tagName === 'SCRIPT' || child.tagName === 'STYLE';
                if (!isModal && !isLiveRegion && !isScript) {
                    if (inertBackground) {
                        child.setAttribute('inert', '');
                        child.setAttribute('data-modal-inert', '1');
                    } else if (child.getAttribute('data-modal-inert') === '1') {
                        child.removeAttribute('inert');
                        child.removeAttribute('data-modal-inert');
                    }
                }
            }
        } catch(e) { log.warn('inert management failed', e); }
    }

    // ── Alpine store sync ────────────────────────────────────────────────────
    function _syncAlpine(id, isOpen, payload) {
        if (typeof Alpine !== 'undefined' && Alpine.store) {
            try {
                const store = Alpine.store('modal');
                if (store) {
                    // Update _openIds array so $store.modal.isOpen(id) works correctly
                    if (!store._openIds) store._openIds = [];
                    const idx = store._openIds.indexOf(id);
                    if (isOpen && idx === -1) {
                        store._openIds.push(id);
                    } else if (!isOpen && idx !== -1) {
                        store._openIds.splice(idx, 1);
                    }
                    // Also set dynamic property for direct access: $store.modal['my-modal']
                    store[id] = isOpen;
                    if (payload !== undefined) store[id + '_payload'] = payload;
                }
            } catch(e) {}
        }
    }

    // ── Register ─────────────────────────────────────────────────────────────
    function register(id, config) {
        const el = _getEl(id);
        if (!el) { log.warn('register: element not found', id); return false; }
        if (_registry[id]) return true; // already registered

        _registry[id] = {
            element:   el,
            config:    Object.assign({}, DEFAULTS, config || {}),
            isOpen:    false,
            hooks:     Object.create(null),
            resolver:  null,
            prevFocus: null   // captured on open, restored on close (per-entry for multi-modal safety)
        };
        log.debug('registered', id);
        return true;
    }

    // ── Open ─────────────────────────────────────────────────────────────────
    function open(id, payload) {
        if (!_registry[id]) {
            // Auto-register if element exists
            if (!register(id)) return false;
        }
        const entry = _registry[id];
        if (entry.isOpen) { log.warn('already open', id); return false; }

        const el = entry.element;
        el.removeAttribute('hidden');         // native HTML hidden attribute (modal.html macro)
        el.classList.remove('hidden');         // Tailwind .hidden class
        el.classList.remove('modal-hidden');   // legacy modal-system compat
        el.style.display = '';                 // clear inline display:none (legacy compat)
        el.classList.add('flex');
        el.setAttribute('aria-hidden', 'false');
        global.document.body.classList.add('overflow-hidden');

        _stack.push(id);
        entry.isOpen = true;

        if (entry.config.focus) _trapFocus(el, id);
        if (entry.config.keyboard) _bindEscape(id);

        _syncAlpine(id, true, payload);
        _runHooks(id, 'open', payload);
        global.Platform.emit('modal:open', { id: id, payload: payload });

        // VIOLATION-8 FIX: Announce modal open to screen readers via Alpine announcer store
        _announceModal(id, true);

        // VIOLATION-10 FIX: Make background page content inert so screen readers
        // and keyboard navigation cannot reach content behind the modal.
        _setBackgroundInert(id, true);

        // Re-init Lucide icons inside modal
        if (global.lucide && typeof global.lucide.createIcons === 'function') {
            setTimeout(function () { global.lucide.createIcons(); }, 50);
        }

        log.debug('opened', id);
        return true;
    }

    // ── Close ────────────────────────────────────────────────────────────────
    function close(id, result) {
        const entry = _registry[id];
        if (!entry || !entry.isOpen) return false;

        const el = entry.element;
        el.setAttribute('hidden', '');         // native HTML hidden attribute
        el.classList.add('hidden');             // Tailwind .hidden class
        el.classList.add('modal-hidden');       // legacy modal-system compat
        el.classList.remove('flex');
        el.setAttribute('aria-hidden', 'true');

        const idx = _stack.indexOf(id);
        if (idx !== -1) _stack.splice(idx, 1);
        entry.isOpen = false;

        // Restore body scroll only when no more modals are open
        if (_stack.length === 0) {
            global.document.body.classList.remove('overflow-hidden');
        }

        _releaseFocus(el, id);
        _unbindEscape(id);
        _syncAlpine(id, false);

        // VIOLATION-8 FIX: Announce modal close to screen readers
        _announceModal(id, false);

        // VIOLATION-10 FIX: Restore inert on background only when no more modals are open
        if (_stack.length === 0) {
            _setBackgroundInert(null, false);
        }

        // Resolve promise if prompt() is waiting
        if (entry.resolver) {
            entry.resolver(result);
            entry.resolver = null;
        }

        _runHooks(id, 'close', result);
        global.Platform.emit('modal:close', { id: id, result: result });
        log.debug('closed', id);
        return true;
    }

    // ── Resolve (close with data) ────────────────────────────────────────────
    function resolve(id, result) {
        return close(id, result);
    }

    // ── Promise-based prompt ─────────────────────────────────────────────────
    function prompt(id, payload) {
        return new Promise(function (resolve_) {
            if (!_registry[id]) register(id);
            const entry = _registry[id];
            if (entry) entry.resolver = resolve_;
            open(id, payload);
        });
    }

    // ── Close all ────────────────────────────────────────────────────────────
    function closeAll() {
        const ids = _stack.slice().reverse();
        ids.forEach(function (id) { close(id); });
    }

    // ── Lifecycle hooks ──────────────────────────────────────────────────────
    function on(id, event, fn) {
        if (!_registry[id]) register(id);
        const entry = _registry[id];
        if (!entry) return;
        if (!entry.hooks[event]) entry.hooks[event] = [];
        entry.hooks[event].push(fn);
    }

    function off(id, event, fn) {
        const entry = _registry[id];
        if (!entry || !entry.hooks[event]) return;
        entry.hooks[event] = entry.hooks[event].filter(function (h) { return h !== fn; });
    }

    // ── Escape key binding ───────────────────────────────────────────────────
    const _escHandlers = Object.create(null);

    function _bindEscape(id) {
        const handler = function (e) {
            if (e.key === 'Escape' && _stack[_stack.length - 1] === id) {
                close(id);
            }
        };
        _escHandlers[id] = handler;
        global.document.addEventListener('keydown', handler);
    }

    function _unbindEscape(id) {
        if (_escHandlers[id]) {
            global.document.removeEventListener('keydown', _escHandlers[id]);
            delete _escHandlers[id];
        }
    }

    // ── Dynamic modal creation ───────────────────────────────────────────────
    /**
     * Create a modal element dynamically and register it.
     * @param {object} options
     * @param {string} [options.id]
     * @param {string} [options.title]
     * @param {string} [options.content]  - Safe HTML string (will be sanitized)
     * @param {'sm'|'md'|'lg'|'xl'|'full'} [options.size]
     * @param {Array}  [options.buttons]  - [{ label, variant, resolve, handler }]
     * @param {boolean} [options.backdrop]
     * @param {boolean} [options.keyboard]
     * @returns {string} modal id
     */
    function create(options) {
        options = options || {};
        const id      = options.id      || ('modal-dyn-' + Date.now());
        const title   = sanitize.escape(options.title   || '');
        const size    = SIZE_CLASSES[options.size] || SIZE_CLASSES.md;
        const content = options.content || '';

        let buttonsHtml = '';
        if (options.buttons && options.buttons.length) {
            const variantMap = {
                primary:     'bg-primary text-primary-foreground hover:bg-primary/90',
                secondary:   'bg-secondary text-secondary-foreground hover:bg-secondary/80',
                destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
                outline:     'border border-input bg-background hover:bg-accent'
            };
            buttonsHtml = '<div class="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">';
            (options.buttons || []).forEach(function (btn, i) {
                const cls = variantMap[btn.variant] || variantMap.secondary;
                buttonsHtml +=
                    '<button type="button" ' +
                    'class="inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors ' + cls + '" ' +
                    'data-modal-btn="' + i + '">' +
                    sanitize.escape(btn.label || 'OK') +
                    '</button>';
            });
            buttonsHtml += '</div>';
        }

        const el = global.document.createElement('div');
        el.id = id;
        el.className = 'hidden fixed inset-0 z-50 items-center justify-center';
        el.setAttribute('role', 'dialog');
        el.setAttribute('aria-modal', 'true');
        el.setAttribute('aria-labelledby', id + '-title');
        el.setAttribute('aria-hidden', 'true');

        // Backdrop
        const backdropEl = global.document.createElement('div');
        backdropEl.className = 'absolute inset-0 bg-black/50';
        backdropEl.setAttribute('data-modal-backdrop', id);
        el.appendChild(backdropEl);

        // Panel
        const panel = global.document.createElement('div');
        panel.className = 'relative bg-background rounded-lg shadow-xl w-full ' + size + ' max-h-[90vh] overflow-hidden flex flex-col z-10';

        const headerHtml =
            '<div class="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">' +
            '<h3 id="' + id + '-title" class="text-lg font-semibold text-foreground">' + title + '</h3>' +
            '<button type="button" class="text-muted-foreground hover:text-foreground transition-colors" data-modal-close="' + id + '" aria-label="Close">' +
            '<i data-lucide="x" class="w-5 h-5"></i></button>' +
            '</div>';

        const bodyHtml =
            '<div class="px-6 py-4 overflow-y-auto flex-1">' + content + '</div>';

        sanitize.html(panel, headerHtml + bodyHtml + buttonsHtml);
        el.appendChild(panel);
        global.document.body.appendChild(el);

        register(id, {
            backdrop: options.backdrop !== false,
            keyboard: options.keyboard !== false
        });

        // Bind dynamic buttons
        if (options.buttons && options.buttons.length) {
            options.buttons.forEach(function (btn, i) {
                const btnEl = panel.querySelector('[data-modal-btn="' + i + '"]');
                if (!btnEl) return;
                btnEl.addEventListener('click', function () {
                    if (typeof btn.handler === 'function') btn.handler();
                    if (btn.resolve !== undefined) resolve(id, btn.resolve);
                    else if (btn.closeOnClick !== false) close(id);
                });
            });
        }

        log.debug('created', id);
        return id;
    }

    // ── Destroy dynamic modal ────────────────────────────────────────────────
    function destroy(id) {
        close(id);
        delete _registry[id];
        const el = _getEl(id);
        if (el && el.parentNode) el.parentNode.removeChild(el);
        log.debug('destroyed', id);
    }

    // ── Confirm dialog ───────────────────────────────────────────────────────
    /**
     * Show a styled confirmation dialog and return a Promise<boolean>.
     * Replaces native browser confirm() for enterprise-grade UX.
     *
     * @param {string} message - Question to display to the user
     * @param {object} [options]
     * @param {string}  [options.title]         - Dialog title (default: 'Confirm')
     * @param {string}  [options.confirmLabel]  - Confirm button text (default: 'Confirm')
     * @param {string}  [options.cancelLabel]   - Cancel button text (default: 'Cancel')
     * @param {boolean} [options.destructive]   - Use destructive (red) button (default: true)
     * @returns {Promise<boolean>} Resolves true if confirmed, false if cancelled/dismissed
     *
     * @example
     *   if (await Platform.modal.confirm('Remove this item?', { destructive: true })) {
     *       await deleteItem(id);
     *   }
     */
    function confirmDialog(message, options) {
        options = options || {};
        const id = 'modal-confirm-' + Date.now();
        create({
            id:      id,
            title:   options.title || 'Confirm',
            size:    'sm',
            content: '<p class="text-sm text-muted-foreground">' + sanitize.escape(String(message || '')) + '</p>',
            backdrop: false,
            keyboard: true,
            buttons: [
                {
                    label:   options.cancelLabel  || 'Cancel',
                    variant: 'outline',
                    resolve: false
                },
                {
                    label:   options.confirmLabel || 'Confirm',
                    variant: options.destructive === false ? 'primary' : 'destructive',
                    resolve: true
                }
            ]
        });
        return prompt(id).then(function (result) {
            setTimeout(function () { destroy(id); }, 300);
            return result === true;
        });
    }

    // ── Drawer helpers ───────────────────────────────────────────────────────
    function openDrawer(drawerId) {
        global.window.dispatchEvent(new CustomEvent('open-drawer-' + drawerId));
    }
    function closeDrawer(drawerId) {
        global.window.dispatchEvent(new CustomEvent('close-drawer-' + drawerId));
    }

    // ── Global event delegation ──────────────────────────────────────────────
    global.document.addEventListener('click', function (e) {
        // data-modal-open
        const openTrigger = e.target.closest('[data-modal-open]');
        if (openTrigger) {
            const targetId = openTrigger.getAttribute('data-modal-open');
            if (targetId) { open(targetId); return; }
        }

        // data-modal-close
        const closeTrigger = e.target.closest('[data-modal-close]');
        if (closeTrigger) {
            const closeId = closeTrigger.getAttribute('data-modal-close');
            if (closeId) { close(closeId); return; }
        }

        // Backdrop click
        const backdropTrigger = e.target.closest('[data-modal-backdrop]');
        if (backdropTrigger && e.target === backdropTrigger) {
            const modalId = backdropTrigger.getAttribute('data-modal-backdrop');
            const entry   = _registry[modalId];
            if (entry && entry.config.backdrop && entry.isOpen) {
                close(modalId);
            }
        }
    });

    // ── Visibility observer for Alpine x-show fallback (GLB-028) ──────────
    // If a role="dialog" element becomes visible outside Platform.modal.open(),
    // automatically apply focus trap, escape key, and focus restoration.
    // This covers modals opened via Alpine x-show or any non-Platform path.
    let _observedDialogs = Object.create(null);  // id → { prevFocus, escHandler }

    function _autoTrapDialog(el) {
        let id = el.id;
        if (!id) return;
        // Skip if already managed by Platform.modal registry
        if (_registry[id] && _registry[id].isOpen) return;
        // Skip if already observed
        if (_observedDialogs[id]) return;

        let prevFocus = global.document.activeElement;
        _observedDialogs[id] = { prevFocus: prevFocus, escHandler: null };

        // Focus the first focusable element
        let focusable = _focusableIn(el);
        if (focusable.length) {
            setTimeout(function () { focusable[0].focus(); }, 50);
        }

        // Attach focus-trap keydown handler
        function onKeyDown(e) {
            if (e.key === 'Tab') {
                let f = _focusableIn(el);
                if (!f.length) { e.preventDefault(); return; }
                let first = f[0];
                let last = f[f.length - 1];
                let active = global.document.activeElement;
                if (f.indexOf(active) === -1) {
                    e.preventDefault();
                    (e.shiftKey ? last : first).focus();
                    return;
                }
                if (e.shiftKey && active === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus(); }
            }
        }
        el.addEventListener('keydown', onKeyDown);
        el._autoFocusTrap = onKeyDown;

        // Attach escape handler
        function onEsc(e) {
            if (e.key === 'Escape') {
                // Hide the dialog (Alpine x-show will react to data change)
                // Dispatch a close event that Alpine can listen to
                el.dispatchEvent(new CustomEvent('modal-escape', { bubbles: true }));
            }
        }
        _observedDialogs[id].escHandler = onEsc;
        global.document.addEventListener('keydown', onEsc);

        // Set background inert
        _setBackgroundInert(id, true);

        // Announce to screen readers
        _announceModal(id, true);

        log.debug('auto-trapped dialog', id);
    }

    function _autoReleaseDialog(el) {
        let id = el.id;
        if (!id) return;
        let observed = _observedDialogs[id];
        if (!observed) return;

        // Remove focus trap handler
        if (el._autoFocusTrap) {
            el.removeEventListener('keydown', el._autoFocusTrap);
            delete el._autoFocusTrap;
        }

        // Remove escape handler
        if (observed.escHandler) {
            global.document.removeEventListener('keydown', observed.escHandler);
        }

        // Restore focus
        if (observed.prevFocus && typeof observed.prevFocus.focus === 'function') {
            observed.prevFocus.focus();
        }

        // Restore background inert if no Platform.modal modals are open either
        if (_stack.length === 0) {
            _setBackgroundInert(null, false);
        }

        // Announce close
        _announceModal(id, false);

        delete _observedDialogs[id];
        log.debug('auto-released dialog', id);
    }

    /**
     * Start observing dialog elements that become visible via Alpine x-show
     * or any mechanism outside Platform.modal.open(). Uses MutationObserver
     * to detect attribute changes (hidden removal, style.display changes)
     * on role="dialog" and role="alertdialog" elements.
     */
    function _initVisibilityObserver() {
        if (typeof MutationObserver === 'undefined') return;

        let observer = new MutationObserver(function (mutations) {
            for (let i = 0; i < mutations.length; i++) {
                let mutation = mutations[i];
                let target = mutation.target;

                // Only care about dialog/alertdialog elements
                let role = target.getAttribute && target.getAttribute('role');
                if (role !== 'dialog' && role !== 'alertdialog') continue;
                if (!target.id) continue;

                // Check if element is now visible
                let isHidden = target.hasAttribute('hidden') ||
                               target.classList.contains('hidden') ||
                               (target.style && target.style.display === 'none');

                if (!isHidden) {
                    _autoTrapDialog(target);
                } else {
                    _autoReleaseDialog(target);
                }
            }
        });

        // Observe the entire document for attribute changes on dialog elements.
        // Use subtree: true so we catch dialogs anywhere in the DOM.
        observer.observe(global.document.documentElement, {
            attributes: true,
            attributeFilter: ['hidden', 'class', 'style'],
            subtree: true
        });

        log.debug('visibility observer started');
    }

    // Start the observer once DOM is ready (after DOMContentLoaded)
    global.document.addEventListener('DOMContentLoaded', function () {
        // Delay slightly to let Platform.modal register its own modals first
        setTimeout(_initVisibilityObserver, 100);
    });

    // ── Public API ───────────────────────────────────────────────────────────
    function confirmSubmit(event, message, options) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        var t = event && event.target;
        var form = t && t.closest ? t.closest('form') : (t && t.tagName === 'FORM' ? t : null);
        confirmDialog(message, options).then(function (ok) {
            if (ok && form && typeof form.submit === 'function') form.submit();
        });
        return false;
    }

    const modal = {
        register:    register,
        open:        open,
        close:       close,
        resolve:     resolve,
        prompt:      prompt,
        closeAll:    closeAll,
        on:          on,
        off:         off,
        create:      create,
        destroy:     destroy,
        openDrawer:  openDrawer,
        closeDrawer: closeDrawer,
        confirm:  confirmDialog,
        confirmSubmit: confirmSubmit,
        isOpen: function (id) {
            return _registry[id] ? _registry[id].isOpen : false;
        },
        stack: function () { return _stack.slice(); },
        // GLB-028: Expose focus utilities for direct use by Alpine or custom code
        trapFocus:   _trapFocus,
        releaseFocus: _releaseFocus,
        focusableIn: _focusableIn
    };

    // ── Legacy shims ─────────────────────────────────────────────────────────
    // These allow existing templates/JS to keep working without modification.
    if (typeof global.openModal   === 'undefined') global.openModal   = open;
    if (typeof global.closeModal  === 'undefined') global.closeModal  = close;
    if (typeof global.createModal === 'undefined') global.createModal = create;
    if (typeof global.openDrawer  === 'undefined') global.openDrawer  = openDrawer;
    if (typeof global.closeDrawer === 'undefined') global.closeDrawer = closeDrawer;

    // Named convenience shims (modal_manager.js compat)
    global.openAddApplicationsModal  = function () { open('add-applications-modal'); };
    global.closeAddApplicationsModal = function () { close('add-applications-modal'); };
    global.openEditEntryModal        = function (id) { open('edit-entry', { entryId: id }); };
    global.closeEditEntryModal       = function () { close('edit-entry'); };
    global.openDeleteConfirmModal    = function (itemId, itemType) { open('delete-confirm-modal', { itemId: itemId, itemType: itemType }); };
    global.closeDeleteConfirmModal   = function () { close('delete-confirm-modal'); };
    global.openRoadmapConfigModal    = function () { open('roadmap-config'); };
    global.closeRoadmapConfigModal   = function () { close('roadmap-config'); };
    global.openUnifiedMappingModal   = function (ctx) { open('unified-mapping-modal', ctx); };
    global.closeUnifiedMappingModal  = function () { close('unified-mapping-modal'); };
    global.openUnifiedMappingModalDiscovery = function (opts) {
        opts = opts || {};
        if (typeof global.initUnifiedMappingModal === 'function') {
            global.initUnifiedMappingModal(opts);
        }
        open('unified-mapping-modal', opts);
    };

    // CustomEvent bridge (modal.html inline script compat)
    global.window.addEventListener('open-modal', function (e) {
        if (e.detail && e.detail.id) open(e.detail.id, e.detail.payload);
    });
    global.window.addEventListener('close-modal', function (e) {
        if (e.detail && e.detail.id) close(e.detail.id, e.detail.result);
    });

    // Auto-register modals already in DOM on DOMContentLoaded
    global.document.addEventListener('DOMContentLoaded', function () {
        global.document.querySelectorAll('[data-modal-id]').forEach(function (el) {
            register(el.getAttribute('data-modal-id'));
        });
        // Also register modals identified by role="dialog"
        global.document.querySelectorAll('[role="dialog"][id]').forEach(function (el) {
            register(el.id);
        });
    });

    global.Platform.register('modal', modal);

}(window));
