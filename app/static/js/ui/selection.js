/**
 * ui/selection.js — Unified row/item selection module
 *
 * Requires: core/00-namespace.js through core/05-error.js
 *
 * Replaces:
 *   - attachCheckboxListeners() / updateSelectAllState() / updateBulkActionsVisibility()
 *     in shared/data-table.js
 *   - Inline checkbox logic in capability_map/index.js
 *   - Inline selection in consolidation_list/dashboard.js
 *   - Inline selection in vendors/list.js
 *   - Scattered selectedIds Sets across feature modules
 *
 * Design:
 *   - Platform.selection.create(options) — attach selection to a table/list
 *   - Declarative HTML:
 *       data-select-all="instanceId"    — the "select all" checkbox
 *       data-select-row="instanceId"    — individual row checkboxes (value = item id)
 *       data-bulk-actions="instanceId"  — container shown when items selected
 *       data-selected-count="instanceId" — element showing count text
 *   - onChange callback receives the Set of selected IDs
 *   - Supports: select-all, indeterminate state, cross-page selection tracking
 *   - IDs are stored as strings (works for both numeric and UUID keys)
 *
 * Usage:
 *   const sel = Platform.selection.create({
 *       id:       'applications',
 *       onChange: (selectedIds) => updateBulkActions(selectedIds)
 *   });
 *
 *   // After table re-renders, re-wire checkboxes:
 *   sel.refresh();
 *
 *   // Programmatic control:
 *   sel.select('42');
 *   sel.deselect('42');
 *   sel.selectAll();
 *   sel.clear();
 *   const ids = sel.getSelected();   // string[]
 *   const count = sel.count();
 *
 *   // HTML:
 *   <input type="checkbox" data-select-all="applications">
 *   <input type="checkbox" data-select-row="applications" value="42">
 *   <div data-bulk-actions="applications" class="hidden">
 *     <span data-selected-count="applications"></span>
 *     <button>Delete selected</button>
 *   </div>
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before ui/selection.js');
    }

    let log = global.Platform.log
        ? global.Platform.log.child('selection')
        : { debug: function(){}, warn: function(){} };

    // ── Registry ──────────────────────────────────────────────────────────────
    let _instances = Object.create(null);

    // ── Instance factory ──────────────────────────────────────────────────────
    function _createInstance(options) {
        options = options || {};
        let id       = options.id || ('selection-' + Date.now());
        let onChange = options.onChange || null;

        // Selected IDs stored as a Set of strings
        let _selected = new Set();

        // ── DOM helpers ───────────────────────────────────────────────────────
        function _selectAllEl() {
            return global.document.querySelector('[data-select-all="' + id + '"]');
        }
        function _rowCheckboxes() {
            return Array.prototype.slice.call(
                global.document.querySelectorAll('[data-select-row="' + id + '"]')
            );
        }
        function _bulkActionsEl() {
            return global.document.querySelector('[data-bulk-actions="' + id + '"]');
        }
        function _countEl() {
            return global.document.querySelector('[data-selected-count="' + id + '"]');
        }

        // ── Sync UI to state ──────────────────────────────────────────────────
        function _syncUi() {
            let rows     = _rowCheckboxes();
            let allCheck = _selectAllEl();
            let bulk     = _bulkActionsEl();
            let countEl  = _countEl();

            // Sync row checkboxes
            rows.forEach(function (cb) {
                let rowId = String(cb.value || cb.getAttribute('data-id') || '');
                cb.checked = _selected.has(rowId);
            });

            // Sync select-all checkbox
            if (allCheck) {
                let visibleIds = rows.map(function (cb) {
                    return String(cb.value || cb.getAttribute('data-id') || '');
                }).filter(Boolean);

                let allChecked  = visibleIds.length > 0 && visibleIds.every(function (rid) { return _selected.has(rid); });
                let someChecked = visibleIds.some(function (rid) { return _selected.has(rid); });

                allCheck.checked       = allChecked;
                allCheck.indeterminate = someChecked && !allChecked;
            }

            // Sync bulk actions visibility
            if (bulk) {
                if (_selected.size > 0) {
                    bulk.classList.remove('hidden');
                } else {
                    bulk.classList.add('hidden');
                }
            }

            // Sync count text
            if (countEl) {
                countEl.textContent = _selected.size + ' selected';
            }

            log.debug(id, 'selected count:', _selected.size);
        }

        // ── Notify ────────────────────────────────────────────────────────────
        function _notify() {
            _syncUi();
            global.Platform.emit('selection:change', { id: id, selected: Array.from(_selected) });
            if (onChange) onChange(_selected);
        }

        // ── Event handlers ────────────────────────────────────────────────────
        function _onSelectAllChange(e) {
            let el = e.target.closest('[data-select-all="' + id + '"]');
            if (!el) return;
            let rows = _rowCheckboxes();
            if (el.checked) {
                rows.forEach(function (cb) {
                    let rowId = String(cb.value || cb.getAttribute('data-id') || '');
                    if (rowId) _selected.add(rowId);
                });
            } else {
                rows.forEach(function (cb) {
                    let rowId = String(cb.value || cb.getAttribute('data-id') || '');
                    if (rowId) _selected.delete(rowId);
                });
            }
            _notify();
        }

        function _onRowChange(e) {
            let el = e.target.closest('[data-select-row="' + id + '"]');
            if (!el) return;
            let rowId = String(el.value || el.getAttribute('data-id') || '');
            if (!rowId) return;
            if (el.checked) {
                _selected.add(rowId);
            } else {
                _selected.delete(rowId);
            }
            _notify();
        }

        // Attach via event delegation on document
        global.document.addEventListener('change', _onSelectAllChange);
        global.document.addEventListener('change', _onRowChange);

        // ── Public instance API ───────────────────────────────────────────────
        let instance = {
            id: id,

            select: function (itemId) {
                _selected.add(String(itemId));
                _notify();
                return instance;
            },

            deselect: function (itemId) {
                _selected.delete(String(itemId));
                _notify();
                return instance;
            },

            toggle: function (itemId) {
                let sid = String(itemId);
                if (_selected.has(sid)) { _selected.delete(sid); } else { _selected.add(sid); }
                _notify();
                return instance;
            },

            selectAll: function () {
                _rowCheckboxes().forEach(function (cb) {
                    let rowId = String(cb.value || cb.getAttribute('data-id') || '');
                    if (rowId) _selected.add(rowId);
                });
                _notify();
                return instance;
            },

            clear: function () {
                _selected.clear();
                _notify();
                return instance;
            },

            /**
             * Re-sync UI after a table re-render (new checkboxes in DOM).
             * Call this after every data load.
             */
            refresh: function () {
                _syncUi();
                return instance;
            },

            isSelected: function (itemId) {
                return _selected.has(String(itemId));
            },

            getSelected: function () {
                return Array.from(_selected);
            },

            count: function () {
                return _selected.size;
            },

            destroy: function () {
                global.document.removeEventListener('change', _onSelectAllChange);
                global.document.removeEventListener('change', _onRowChange);
                _selected.clear();
                delete _instances[id];
                log.debug('destroyed', id);
            }
        };

        _instances[id] = instance;
        log.debug('created', id);
        return instance;
    }

    // ── Public API ────────────────────────────────────────────────────────────
    let selection = {
        /**
         * Create a selection controller.
         * @param {object} options
         * @param {string}   [options.id]       - Unique instance ID
         * @param {Function} [options.onChange] - Called with Set<string> on change
         * @returns {object} Selection instance
         */
        create: _createInstance,

        get: function (id) { return _instances[id] || null; },

        destroyAll: function () {
            Object.keys(_instances).forEach(function (id) {
                _instances[id].destroy();
            });
        }
    };

    global.Platform.register('selection', selection);

}(window));
